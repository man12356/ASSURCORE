# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.claim — Sinistre d'Assurance
#  insurance.claim.event — Événement / Timeline du Sinistre
#
#  Maquette de référence : deck2.pdf page 05
#  Cycle de vie : Déclaré → Transmis → Expertise → Indemnisation → Réglé → Clos
#
#  Ex-tables Oracle :
#    PR_SINISTRE      → insurance.claim
#    PR_SUIVI_SINISTRE → insurance.claim.event (observations chronologiques)
#    PR_TEXTE_SINISTRE → notes textuelles sur le sinistre
#    PR_PAYEMENT_IND_SINISTRE → paiements indemnité
#
#  Architecture :
#    insurance.claim       → fiche principale du sinistre
#    insurance.claim.event → journal des événements (timeline page 05)
#                            chaque étape (déclaration, expertise, accord) est
#                            un enregistrement daté avec pièces jointes
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

CLAIM_STATE = [
    ('declare',       'Déclaré'),
    ('transmis',      'Transmis'),
    ('expertise',     'En expertise'),
    ('indemnisation', 'Indemnisation'),
    ('regle',         'Réglé'),
    ('clos',          'Clos'),
]

EVENT_TYPE = [
    ('declaration',    'Déclaration reçue'),
    ('transmission',   'Transmis à la compagnie'),
    ('expertise',      'Expertise sur place'),
    ('rapport',        'Rapport d\'expertise'),
    ('proposition',    'Indemnisation proposée'),
    ('accord',         'Accord client'),
    ('paiement',       'Paiement indemnité'),
    ('recours',        'Recours / Contestation'),
    ('cloture',        'Clôture du dossier'),
    ('note',           'Note interne'),
]


# ─────────────────────────────────────────────────────────────────────────────
#  insurance.claim — Sinistre
# ─────────────────────────────────────────────────────────────────────────────

class InsuranceClaim(models.Model):
    """
    Sinistre d'assurance déclaré par un client et géré par le courtier
    en interface avec la compagnie.

    Chaque étape est tracée dans insurance.claim.event (timeline).
    Les montants évoluent : réclamé → expertise → indemnité finale (- franchise).

    Équivalent Oracle : PR_SINISTRE + PR_SUIVI_SINISTRE.
    """

    _name = 'insurance.claim'
    _description = 'Sinistre d\'Assurance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_sinistre desc, name desc'
    _rec_name = 'name'

    # ── Identification ─────────────────────────────────────────────────────────

    name = fields.Char(
        string='Réf. Sinistre',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'insurance.claim'
        ) or '/',
        tracking=True,
        help='Référence séquentielle AssurCore. Ex : SIN/2026/0421. '
             'Ex-champ Oracle : REF_SINISTRE dans PR_SINISTRE.',
    )

    ref_compagnie = fields.Char(
        string='Réf. Sinistre compagnie',
        size=20,
        tracking=True,
        help='Numéro de dossier attribué par la compagnie d\'assurance. '
             'Ex-champ Oracle : REF_SINISTRE VARCHAR2(20) dans PR_SINISTRE.',
    )

    state = fields.Selection(
        selection=CLAIM_STATE,
        string='État',
        default='declare',
        required=True,
        tracking=True,
        copy=False,
        help='Pipeline de traitement du sinistre (maquette deck page 05).',
    )

    # ── Police & Assuré ────────────────────────────────────────────────────────

    policy_id = fields.Many2one(
        comodel_name='insurance.policy',
        string='Police',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Police concernée par ce sinistre.',
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Assuré',
        related='policy_id.partner_id',
        store=True,
        index=True,
    )

    company_ins_id = fields.Many2one(
        comodel_name='insurance.company',
        string='Compagnie',
        related='policy_id.company_ins_id',
        store=True,
    )

    branche = fields.Selection(
        related='policy_id.branche',
        store=True,
        string='Branche',
    )

    commercial_id = fields.Many2one(
        comodel_name='res.users',
        string='Commercial',
        related='policy_id.commercial_id',
        store=True,
    )

    agence_courtier = fields.Char(
        related='policy_id.agence_courtier',
        store=True,
        string='Agence',
    )

    # ── Identification du sinistre ─────────────────────────────────────────────

    date_sinistre = fields.Datetime(
        string='Date & heure du sinistre',
        required=True,
        tracking=True,
        help='Date et heure exactes de l\'événement assuré. '
             'Ex-champ Oracle : DATE_SINISTRE DATE dans PR_SINISTRE.',
    )

    date_declaration = fields.Date(
        string='Date de déclaration',
        default=fields.Date.today,
        tracking=True,
        help='Date à laquelle le courtier a reçu la déclaration.',
    )

    lieu_sinistre = fields.Char(
        string='Lieu du sinistre',
        size=150,
        help='Adresse ou description du lieu (ex: Av. Habib Bourguiba, Tunis).',
    )

    lib_sinistre = fields.Text(
        string='Description du sinistre',
        help='Narration détaillée des faits. '
             'Ex-champ Oracle : LIB_SINISTRE VARCHAR2(250) dans PR_SINISTRE.',
    )

    categorie_indemnisation = fields.Char(
        string='Catégorie d\'indemnisation',
        size=50,
        help='Classification (ex: Collision, Incendie, Vol, Dommages corporels). '
             'Ex-champ Oracle : CATEGORIE_INDEMNISATION dans PR_SINISTRE.',
    )

    tiers = fields.Char(
        string='Tiers impliqués',
        size=50,
        help='Identité des tiers (adversaires, témoins). '
             'Ex-champ Oracle : TIERS VARCHAR2(50) dans PR_SINISTRE.',
    )

    vehicule = fields.Char(
        string='Véhicule / Bien sinistré',
        size=30,
        help='Matricule ou désignation du bien sinistré.',
    )

    # ── Montants (3 cartes financières — maquette page 05) ────────────────────
    # Progression : Réclamé → Expertise → Indemnité finale (- franchise)

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        default=lambda self: self.env.ref('base.TND', raise_if_not_found=False)
                             or self.env.company.currency_id,
        readonly=True,
    )

    montant_reclame = fields.Monetary(
        string='Montant réclamé (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Montant déclaré par le client lors de la déclaration. '
             'Carte 1 de la maquette page 05.',
    )

    montant_expertise = fields.Monetary(
        string='Montant expertise (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Estimation de l\'expert mandaté par la compagnie. '
             'Carte 2 de la maquette page 05.',
    )

    franchise = fields.Monetary(
        string='Franchise (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Montant restant à la charge de l\'assuré (franchise contractuelle).',
    )

    montant_indemnite = fields.Monetary(
        string='Indemnité finale (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Montant d\'indemnisation définitif validé par la compagnie. '
             'Carte 3 de la maquette page 05. '
             'Ex-champ Oracle : MONTANT_INDEMNITE NUMBER(11,3) dans PR_SINISTRE.',
    )

    montant_indemnite_net = fields.Monetary(
        string='Indemnité nette franchise (TND)',
        currency_field='currency_id',
        compute='_compute_indemnite_net',
        store=True,
        help='Indemnité finale − Franchise = montant effectivement versé à l\'assuré.',
    )

    montant_honoraire_sin_ht = fields.Monetary(
        string='Honoraires sinistre HT (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Honoraires du courtier pour la gestion du sinistre. '
             'Ex-champ Oracle : MONTANT_HON_SIN_HT NUMBER(11,3) dans PR_SINISTRE.',
    )

    # ── Expert ────────────────────────────────────────────────────────────────

    expert_id = fields.Many2one(
        comodel_name='res.partner',
        string='Expert mandaté',
        domain=[('is_company', '=', False)],
        help='Expert désigné par la compagnie pour évaluer le sinistre.',
    )

    date_expertise = fields.Date(
        string='Date d\'expertise',
        tracking=True,
    )

    # ── Facturation sinistre ──────────────────────────────────────────────────

    hon_sin_facture = fields.Boolean(
        string='Honoraires facturés',
        default=False,
        help='Indique si les honoraires de gestion du sinistre ont été facturés. '
             'Ex-champ Oracle : HON_SIN_FACTURE CHAR(1) DEFAULT \'N\'.',
    )

    facture_indemnite_id = fields.Many2one(
        comodel_name='account.move',
        string='Facture indemnité',
        readonly=True,
        copy=False,
        help='Facture Odoo émise pour le remboursement de l\'indemnité.',
    )

    # ── Chronologie — Timeline des événements ─────────────────────────────────

    event_ids = fields.One2many(
        comodel_name='insurance.claim.event',
        inverse_name='claim_id',
        string='Chronologie',
        help='Journal horodaté des étapes du traitement du sinistre. '
             'Équivalent Oracle : PR_SUIVI_SINISTRE (DATE_OBSERVATION, OBSERVATION).',
    )

    event_count = fields.Integer(
        string='Événements',
        compute='_compute_event_count',
    )

    # ── Smart Buttons ─────────────────────────────────────────────────────────

    @api.depends('event_ids')
    def _compute_event_count(self):
        for rec in self:
            rec.event_count = len(rec.event_ids)

    @api.depends('montant_indemnite', 'franchise')
    def _compute_indemnite_net(self):
        for rec in self:
            rec.montant_indemnite_net = max(
                0.0, rec.montant_indemnite - rec.franchise
            )

    # ── Tags libres ───────────────────────────────────────────────────────────

    tag_ids = fields.Many2many(
        comodel_name='insurance.claim.tag',
        string='Tags',
        help='Tags structurés pour filtrer le portefeuille de sinistres '
             '(ex: #collision-arriere, #constat-conteste).',
    )

    # ── Métadonnées ───────────────────────────────────────────────────────────

    notes = fields.Text(string='Notes internes')
    supp_log = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    annee_sinistre = fields.Integer(
        string='Année sinistre',
        compute='_compute_annee',
        store=True,
        help='Ex-champ Oracle : ANNEE_SIN NUMBER(4,0) dans PR_SINISTRE.',
    )

    @api.depends('date_sinistre')
    def _compute_annee(self):
        for rec in self:
            rec.annee_sinistre = rec.date_sinistre.year if rec.date_sinistre else 0

    # ─────────────────────────────────────────────────────────────────────────
    #  Transitions d'état (pipeline)
    # ─────────────────────────────────────────────────────────────────────────

    def action_transmettre(self):
        """Déclaré → Transmis à la compagnie."""
        for rec in self:
            if rec.state != 'declare':
                raise UserError(_('Le sinistre doit être en état Déclaré.'))
            rec.write({'state': 'transmis'})
            rec._log_event('transmission',
                           _('Dossier transmis à %s.') % rec.company_ins_id.name)

    def action_expertise(self):
        """Transmis → En expertise."""
        for rec in self:
            if rec.state != 'transmis':
                raise UserError(_('Le sinistre doit être Transmis.'))
            rec.write({'state': 'expertise'})
            rec._log_event('expertise',
                           _('Expertise déclenchée.'))

    def action_indemnisation(self):
        """En expertise → Indemnisation."""
        for rec in self:
            if rec.state != 'expertise':
                raise UserError(_('Le sinistre doit être En expertise.'))
            if not rec.montant_indemnite:
                raise UserError(_(
                    'Renseignez le montant d\'indemnité proposé avant de passer '
                    'en phase d\'Indemnisation.'
                ))
            rec.write({'state': 'indemnisation'})
            rec._log_event(
                'proposition',
                _('Indemnisation proposée : %(montant).3f TND '
                  '(franchise : %(franchise).3f TND).',
                  montant=rec.montant_indemnite,
                  franchise=rec.franchise),
            )

    def action_regler(self):
        """Indemnisation → Réglé (accord client + paiement)."""
        for rec in self:
            if rec.state != 'indemnisation':
                raise UserError(_('Le sinistre doit être en phase d\'Indemnisation.'))
            rec.write({'state': 'regle'})
            rec._log_event(
                'paiement',
                _('Accord client obtenu. Indemnité nette versée : %(net).3f TND.',
                  net=rec.montant_indemnite_net),
            )

    def action_clore(self):
        """Réglé → Clos."""
        for rec in self:
            if rec.state != 'regle':
                raise UserError(_(
                    'Le sinistre doit être Réglé avant d\'être clôturé.'
                ))
            rec.write({'state': 'clos'})
            rec._log_event('cloture', _('Dossier sinistre clôturé.'))

    def action_reopen(self):
        """Réouverture (recours ou litige)."""
        for rec in self:
            if rec.state not in ('clos', 'regle'):
                raise UserError(_('Seuls les sinistres Réglés ou Clos peuvent être réouverts.'))
            rec.write({'state': 'indemnisation'})
            rec._log_event('recours', _('Dossier réouvert — recours ou contestation.'))

    # ─────────────────────────────────────────────────────────────────────────
    #  Utilitaires
    # ─────────────────────────────────────────────────────────────────────────

    def _log_event(self, event_type, description):
        """Crée un événement chronologique et poste un message dans le chatter."""
        self.ensure_one()
        self.env['insurance.claim.event'].create({
            'claim_id': self.id,
            'event_type': event_type,
            'date_event': fields.Datetime.now(),
            'description': description,
            'user_id': self.env.user.id,
        })
        self.message_post(body=description)

    def action_view_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chronologie — %s') % self.name,
            'res_model': 'insurance.claim.event',
            'view_mode': 'tree,form',
            'domain': [('claim_id', '=', self.id)],
            'context': {'default_claim_id': self.id},
        }

    # ─────────────────────────────────────────────────────────────────────────
    #  Contraintes
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('montant_reclame', 'montant_expertise', 'montant_indemnite', 'franchise')
    def _check_montants(self):
        for rec in self:
            for fname, label in [
                ('montant_reclame', 'Montant réclamé'),
                ('montant_expertise', 'Montant expertise'),
                ('montant_indemnite', 'Indemnité finale'),
                ('franchise', 'Franchise'),
            ]:
                if getattr(rec, fname) < 0:
                    raise ValidationError(_(
                        '%(label)s ne peut pas être négatif.', label=label
                    ))

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == '/':
            vals['name'] = (
                self.env['ir.sequence'].next_by_code('insurance.claim') or '/'
            )
        rec = super().create(vals)
        # Événement automatique de déclaration
        rec._log_event('declaration', _('Déclaration de sinistre enregistrée.'))
        return rec

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name
            if rec.partner_id:
                name += ' — ' + rec.partner_id.name
            if rec.lib_sinistre:
                name += ' (%s)' % rec.lib_sinistre[:40]
            result.append((rec.id, name))
        return result


# ─────────────────────────────────────────────────────────────────────────────
#  insurance.claim.event — Événement chronologique du sinistre (Timeline)
#  Équivalent Oracle : PR_SUIVI_SINISTRE (DATE_OBSERVATION, OBSERVATION)
#  Maquette page 05 : dots colorés done / active / vide, pièces jointes inline
# ─────────────────────────────────────────────────────────────────────────────

class InsuranceClaimEvent(models.Model):
    """
    Un événement horodaté dans la vie du sinistre.
    Chaque transition d'état, chaque échange compagnie/expert,
    chaque document reçu génère un enregistrement ici.
    """

    _name = 'insurance.claim.event'
    _description = 'Événement Chronologique Sinistre'
    _order = 'date_event desc'
    _rec_name = 'display_name'

    claim_id = fields.Many2one(
        comodel_name='insurance.claim',
        string='Sinistre',
        required=True,
        ondelete='cascade',
        index=True,
    )

    date_event = fields.Datetime(
        string='Date & heure',
        required=True,
        default=fields.Datetime.now,
        help='Ex-champ Oracle : DATE_OBSERVATION DATE dans PR_SUIVI_SINISTRE.',
    )

    event_type = fields.Selection(
        selection=EVENT_TYPE,
        string='Type d\'événement',
        required=True,
        default='note',
        help='Catégorie de l\'événement pour filtrage et couleur du dot timeline.',
    )

    description = fields.Text(
        string='Description',
        required=True,
        help='Ex-champ Oracle : OBSERVATION VARCHAR2(1000) dans PR_SUIVI_SINISTRE.',
    )

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Auteur',
        default=lambda self: self.env.user,
        help='Utilisateur qui a enregistré cet événement.',
    )

    montant = fields.Monetary(
        string='Montant concerné (TND)',
        currency_field='currency_id',
        help='Montant financier lié à cet événement (si applicable).',
    )

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        default=lambda self: self.env.ref('base.TND', raise_if_not_found=False)
                             or self.env.company.currency_id,
        readonly=True,
    )

    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='claim_event_attachment_rel',
        column1='event_id',
        column2='attachment_id',
        string='Pièces jointes',
        help='Documents liés à cet événement (rapport expertise, constat, accord signé…). '
             'Pièces jointes inline de la maquette page 05.',
    )

    is_done = fields.Boolean(
        string='Réalisé',
        default=True,
        help='Pilote l\'apparence du dot timeline : plein (réalisé) vs vide (à venir).',
    )

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('date_event', 'event_type', 'description')
    def _compute_display_name(self):
        type_labels = dict(EVENT_TYPE)
        for rec in self:
            date_str = rec.date_event.strftime('%d/%m · %Hh%M') if rec.date_event else ''
            type_label = type_labels.get(rec.event_type, rec.event_type)
            rec.display_name = f'{date_str} — {type_label}'


# ─────────────────────────────────────────────────────────────────────────────
#  insurance.claim.tag — Tags structurés
#  Maquette page 05 : #collision-arriere, #constat-conteste
# ─────────────────────────────────────────────────────────────────────────────

class InsuranceClaimTag(models.Model):
    _name = 'insurance.claim.tag'
    _description = 'Tag Sinistre'

    name = fields.Char(string='Tag', required=True)
    color = fields.Integer(string='Couleur', default=0)

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Ce tag existe déjà.'),
    ]
