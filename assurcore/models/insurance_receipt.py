# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.receipt — Quittance d'Assurance
#  Maquette de référence : deck2.pdf pages 02, 03 (Pipeline + Tree Dense)
#
#  Cycle de vie (pipeline) :
#    Émise → Notifiée → Partielle → Encaissée → Reversée → Contentieux
#
#  Spécificité tunisienne :
#    TIMBRE FISCAL : montant fixe légal porté par la taxe account.tax
#    configurée dans res.company.timbre_fiscal_tax_id (insurance_data.xml).
#    NE JAMAIS CODER EN DUR. Pour changer le montant (Loi de Finances),
#    modifier uniquement la taxe dans Odoo → Comptabilité → Taxes.
#    TVA assurance : taux porté par res.company.tva_courtage_tax_id.
#
#  Architecture :
#    - insurance.receipt est un modèle AUTONOME (pas d'héritage account.move)
#    - move_id FK vers account.move est créé lors du passage en Encaissée
#    - Le lettrage multi-quittances (famille) est géré via insurance.settlement
#      → account.payment dans Odoo
#
#  Ex-tables Oracle : PR_OPERATION (quittances émises), PR_JOUR_ENC (journée
#  d'encaissement), PR_PAYEMENT_JOUR_ENC (paiements), PR_REGELEMENT (règlements)
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Constantes techniques (jamais fiscales)
# ─────────────────────────────────────────────────────────────────────────────
# !! AUCUN montant fiscal n'est codé en dur ici !!
# Les montants sont portés par account.tax via res.company :
#   → timbre_fiscal  : self.env.company.timbre_fiscal_tax_id.amount
#   → taux_tva       : self.env.company.tva_courtage_tax_id.amount
# Référence : insurance_data.xml + models/insurance_commission_rule.py

# Seuils d'alerte retard (jours) — cohérents avec les design tokens SCSS
OVERDUE_MODERATE = 30   # $ac-overdue-moderate
OVERDUE_SEVERE   = 60   # $ac-overdue-severe

RECEIPT_STATE = [
    ('emise',      'Émise'),
    ('notifiee',   'Notifiée'),
    ('partielle',  'Partielle'),
    ('encaissee',  'Encaissée'),
    ('reversee',   'Reversée'),
    ('contentieux','Contentieux'),
]

TYPE_REG = [
    ('C', 'Chèque'),
    ('E', 'Espèces'),
    ('V', 'Virement bancaire'),
    ('P', 'Prélèvement'),
    ('A', 'Avoir compensé'),
]


# ─────────────────────────────────────────────────────────────────────────────
#  insurance.receipt — Quittance d'Assurance
# ─────────────────────────────────────────────────────────────────────────────

class InsuranceReceipt(models.Model):
    """
    Quittance d'assurance : document émis pour chaque période de couverture
    d'une police. Correspond à une ligne facturable dans l'ancien Oracle
    (PR_OPERATION avec CASE_A_COCHER_PRIME = 'O').

    Relations clés :
      - policy_id       → insurance.policy    (police parente)
      - partner_id      → res.partner         (assuré — déduit de la police)
      - payer_id        → res.partner         (payeur — peut être le chef de famille)
      - company_ins_id  → insurance.company   (compagnie)
      - settlement_ids  → insurance.settlement (règlements / chèques reçus)
      - move_id         → account.move        (écriture comptable générée)
    """

    _name = 'insurance.receipt'
    _description = 'Quittance d\'Assurance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_echeance asc, name asc'
    _rec_name = 'name'

    # ── Identification ─────────────────────────────────────────────────────────

    name = fields.Char(
        string='N° Quittance',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'insurance.receipt'
        ) or '/',
        tracking=True,
        help='Numéro séquentiel AssurCore. '
             'Ex-champ Oracle : NUM_QUITTANCE VARCHAR2(30) dans PR_OPERATION.',
    )

    num_quittance_compagnie = fields.Char(
        string='N° Quittance compagnie',
        size=30,
        tracking=True,
        help='Référence de la quittance telle que fournie par la compagnie. '
             'Ex-champ Oracle : NUM_QUITTANCE dans PR_OPERATION.',
    )

    num_attestation = fields.Char(
        string='N° Attestation',
        size=20,
        help='Numéro d\'attestation d\'assurance. '
             'Ex-champ Oracle : NUM_ATTESTATION dans PR_OPERATION.',
    )

    state = fields.Selection(
        selection=RECEIPT_STATE,
        string='État',
        default='emise',
        required=True,
        tracking=True,
        copy=False,
        help='Pipeline de la quittance (maquette page 02 : '
             'Émise → Notifiée → Partielle → Encaissée → Reversée → Contentieux).',
    )

    # ── Liens vers la Police (champs déduits — store=True pour performances) ──

    policy_id = fields.Many2one(
        comodel_name='insurance.policy',
        string='Police',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Assuré',
        related='policy_id.partner_id',
        store=True,
        index=True,
        help='Déduit automatiquement de la police. '
             'C\'est le titulaire du contrat (pas forcément le payeur).',
    )

    payer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Payeur',
        related='policy_id.payer_id',
        store=True,
        index=True,
        help='Payeur effectif (chef de famille). '
             'Un seul chèque de ce partenaire peut lettrer plusieurs quittances.',
    )

    company_ins_id = fields.Many2one(
        comodel_name='insurance.company',
        string='Compagnie',
        related='policy_id.company_ins_id',
        store=True,
        index=True,
    )

    branche = fields.Selection(
        selection=[
            ('AUTO',      'Automobile'),
            ('SANTE',     'Santé / Maladie'),
            ('MRH',       'Multirisque Habitation'),
            ('TRANSPORT', 'Transport'),
            ('INCENDIE',  'Incendie & Risques Divers'),
            ('VIE',       'Vie'),
            ('RC',        'RC Pro'),
            ('MARITIME',  'Maritime'),
            ('AUTRE',     'Autre'),
        ],
        string='Branche',
        related='policy_id.branche',
        store=True,
    )

    commercial_id = fields.Many2one(
        comodel_name='res.users',
        string='Commercial',
        related='policy_id.commercial_id',
        store=True,
    )

    agence_courtier = fields.Char(
        string='Agence',
        related='policy_id.agence_courtier',
        store=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────

    date_emission = fields.Date(
        string='Date d\'émission',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date à laquelle la quittance a été émise par la compagnie.',
    )

    date_echeance = fields.Date(
        string='Date d\'échéance',
        required=True,
        tracking=True,
        help='Date limite de paiement. Après cette date, la quittance passe '
             'en "Contentieux" si non réglée. '
             'Ex-champ Oracle : DATE_ECHEANCE dans PR_OPERATION.',
    )

    date_validite_du = fields.Date(
        string='Couverture du',
        help='Début de la période de couverture assurée.',
    )

    date_validite_au = fields.Date(
        string='Couverture au',
        help='Fin de la période de couverture assurée.',
    )

    # ── Montants — Spécificités tunisiennes ───────────────────────────────────

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Devise',
        default=lambda self: self.env.ref('base.TND', raise_if_not_found=False)
                             or self.env.company.currency_id,
        readonly=True,
    )

    montant_prime = fields.Monetary(
        string='Prime nette (TND)',
        currency_field='currency_id',
        required=True,
        tracking=True,
        help='Montant brut de la prime, reversé à la compagnie. '
             'Ex-champ Oracle : MONTANT_PRIME NUMBER(11,3) dans PR_OPERATION.',
    )

    commission = fields.Monetary(
        string='Commission courtier (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Part revenant au courtier sur cette quittance. '
             'Ex-champ Oracle : COMMISSION NUMBER(11,3) dans PR_OPERATION.',
    )

    montant_honoraire_ht = fields.Monetary(
        string='Honoraires HT (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Honoraires de courtage hors taxe. '
             'Ex-champ Oracle : MONTANT_HONORAIRE_HT NUMBER(11,3) dans PR_OPERATION.',
    )

    # ── Taxes dynamiques — SEULE source de vérité fiscale ───────────────────
    # Ces champs pointent vers des account.tax configurées dans insurance_data.xml
    # et paramétrables via Odoo → Comptabilité → Taxes (sans toucher au code).

    timbre_fiscal_tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Taxe — Timbre Fiscal',
        domain=[('amount_type', '=', 'fixed'), ('type_tax_use', '=', 'sale')],
        default=lambda self: self.env.company.timbre_fiscal_tax_id,
        ondelete='restrict',
        help='Taxe Odoo de type "Montant fixe" représentant le timbre fiscal '
             'tunisien. Montant lu dynamiquement depuis cette taxe. '
             'Pour changer le montant légal, modifier la taxe — jamais le code.',
    )

    tva_courtage_tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='TVA Courtage',
        domain=[('amount_type', '=', 'percent'), ('type_tax_use', '=', 'sale')],
        default=lambda self: self.env.company.tva_courtage_tax_id,
        ondelete='restrict',
        help='Taxe TVA applicable sur les honoraires de courtage. '
             'Taux lu depuis la taxe (standard 7%). Peut être modifié '
             'par quittance pour les cas exceptionnels (13%, 19%).',
    )

    taux_tva = fields.Float(
        string='Taux TVA %',
        compute='_compute_tax_rates',
        store=True,
        readonly=False,
        digits=(4, 2),
        help='Taux de TVA calculé depuis tva_courtage_tax_id.amount. '
             'Modifiable manuellement pour les cas particuliers. '
             'Ex-champ Oracle : TAUX_TVA NUMBER(4,2) dans PR_FACTURE.',
    )

    timbre_fiscal = fields.Monetary(
        string='Timbre Fiscal (TND)',
        currency_field='currency_id',
        compute='_compute_tax_rates',
        store=True,
        readonly=False,
        tracking=True,
        help='Montant du timbre fiscal lu dynamiquement depuis timbre_fiscal_tax_id.amount. '
             'JAMAIS codé en dur. Modifiable manuellement si dérogation accordée. '
             'Ex-champ Oracle : TIMBRE_FISCAL NUMBER(11,3) dans PR_AVOIR.',
    )

    montant_tva = fields.Monetary(
        string='Montant TVA (TND)',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True,
        help='TVA calculée automatiquement sur les honoraires HT.',
    )

    amount_total = fields.Monetary(
        string='Total TTC (TND)',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True,
        help='Prime nette + Honoraires HT + TVA + Timbre Fiscal.',
    )

    amount_paid = fields.Monetary(
        string='Encaissé (TND)',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True,
        help='Somme des règlements confirmés sur cette quittance.',
    )

    amount_residual = fields.Monetary(
        string='Reste dû (TND)',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True,
        help='Solde restant = Total TTC − Encaissé. '
             'Affiché dans la colonne "Impayé" du dashboard.',
    )

    prime_echeance = fields.Monetary(
        string='Prime à l\'échéance (TND)',
        currency_field='currency_id',
        help='Prime proratisée pour la période d\'échéance. '
             'Ex-champ Oracle : PRIME_ECHEANCE NUMBER(11,3) dans PR_OPERATION.',
    )

    # ── Retard — KPI Dashboard ─────────────────────────────────────────────────

    jours_retard = fields.Integer(
        string='Retard (jours)',
        compute='_compute_retard',
        store=True,
        help='Nombre de jours depuis l\'échéance. '
             'Positif = en retard. Négatif = pas encore échu.',
    )

    is_overdue = fields.Boolean(
        string='En retard',
        compute='_compute_retard',
        store=True,
        help='Vrai si jours_retard > 0 et état non encaissé/reversé.',
    )

    overdue_severity = fields.Selection(
        selection=[
            ('none',     'À jour'),
            ('moderate', '> 30 jours'),
            ('severe',   '> 60 jours'),
        ],
        string='Niveau de retard',
        compute='_compute_retard',
        store=True,
        help='Pilote la couleur du badge dans la vue Tree (maquette page 03).',
    )

    # ── Type d'opération ──────────────────────────────────────────────────────

    nature = fields.Selection(
        selection=[
            ('R', 'Renouvellement'),
            ('N', 'Nouveau contrat'),
            ('A', 'Avenant'),
            ('S', 'Sinistre — honoraires'),
            ('F', 'Frais / Facturation'),
        ],
        string='Nature',
        default='R',
        help='Nature de l\'opération. '
             'Ex-champ Oracle : NATURE CHAR(1) DEFAULT \'R\' dans PR_OPERATION.',
    )

    type_client_op = fields.Selection(
        selection=[('T', 'Tiers'), ('P', 'Portefeuille')],
        string='Type opération',
        default='T',
        help='Ex-champ Oracle : T_C CHAR(1) dans PR_OPERATION.',
    )

    designation = fields.Char(
        string='Désignation',
        size=250,
        help='Libellé de la quittance. '
             'Ex-champ Oracle : DESIGNATION VARCHAR2(250) dans PR_OPERATION.',
    )

    vehicule = fields.Char(
        string='Véhicule / Risque',
        size=30,
        help='Identification du bien assuré (matricule, immeuble…). '
             'Ex-champ Oracle : VEHICULE VARCHAR2(30) dans PR_OPERATION.',
    )

    # ── Règlements ─────────────────────────────────────────────────────────────

    settlement_ids = fields.One2many(
        comodel_name='insurance.settlement',
        inverse_name='receipt_id',
        string='Règlements',
        help='Chèques, espèces ou virements reçus sur cette quittance. '
             'Équivalent Oracle : PR_REGELEMENT.',
    )

    settlement_count = fields.Integer(
        string='Règlements',
        compute='_compute_settlement_count',
    )

    # ── Comptabilité ───────────────────────────────────────────────────────────

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Écriture comptable',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='Écriture comptable générée dans Odoo lors de l\'encaissement. '
             'Permet le lettrage natif Odoo (reconciliation multi-quittances).',
    )

    journal_enc_id = fields.Many2one(
        comodel_name='insurance.journal.enc',
        string='Journée d\'encaissement',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='Journée d\'encaissement de la compagnie. '
             'Équivalent Oracle : NUM_JOUR_ENC dans PR_OPERATION / PR_JOUR_ENC.',
    )

    # ── Métadonnées ────────────────────────────────────────────────────────────

    notes = fields.Text(string='Notes internes')

    supp_log = fields.Boolean(
        string='Suppression logique',
        default=False,
        help='Ex-champ Oracle : SUPP_LOG CHAR(1) DEFAULT \'N\'.',
    )

    active = fields.Boolean(default=True)

    date_dernier_maj = fields.Datetime(
        string='Dernière MAJ',
        readonly=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    #  Calculs (compute)
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('timbre_fiscal_tax_id', 'tva_courtage_tax_id')
    def _compute_tax_rates(self):
        """
        Lit les montants fiscaux DYNAMIQUEMENT depuis les taxes account.tax.
        Aucun montant n'est codé en dur dans cette méthode.
        Modifier la taxe dans Odoo → Comptabilité → Taxes suffit.
        """
        for rec in self:
            # Timbre Fiscal : montant fixe depuis la taxe (ex: 1.000 TND)
            if rec.timbre_fiscal_tax_id:
                rec.timbre_fiscal = rec.timbre_fiscal_tax_id.amount
            else:
                rec.timbre_fiscal = 0.0

            # Taux TVA : pourcentage depuis la taxe (ex: 7.0)
            if rec.tva_courtage_tax_id:
                rec.taux_tva = rec.tva_courtage_tax_id.amount
            else:
                rec.taux_tva = 0.0

    @api.depends(
        'montant_prime', 'commission', 'montant_honoraire_ht',
        'taux_tva', 'timbre_fiscal',
        'settlement_ids', 'settlement_ids.montant_reg',
        'settlement_ids.state',
    )
    def _compute_amounts(self):
        """
        Calcule les montants TTC, encaissé et résiduel.

        Formule TTC tunisienne :
          TTC = Prime nette + Honoraires HT + TVA (% sur honoraires) + Timbre Fiscal
        """
        for rec in self:
            # TVA uniquement sur les honoraires HT (pas sur la prime pure)
            rec.montant_tva = rec.montant_honoraire_ht * (rec.taux_tva / 100.0)

            rec.amount_total = (
                rec.montant_prime
                + rec.montant_honoraire_ht
                + rec.montant_tva
                + rec.timbre_fiscal
            )

            # Encaissé = somme des règlements confirmés (état 'regle' ou 'encaisse')
            confirmed_settlements = rec.settlement_ids.filtered(
                lambda s: s.state in ('regle', 'encaisse')
            )
            rec.amount_paid = sum(confirmed_settlements.mapped('montant_reg'))
            rec.amount_residual = rec.amount_total - rec.amount_paid

    @api.depends('date_echeance', 'state')
    def _compute_retard(self):
        """
        Calcule le retard en jours et le niveau d'alerte.
        Pilote les couleurs du badge dans la vue Tree (maquette page 03).
        """
        today = fields.Date.today()
        for rec in self:
            if rec.date_echeance and rec.state not in ('encaissee', 'reversee'):
                delta = (today - rec.date_echeance).days
                rec.jours_retard = delta
                rec.is_overdue = delta > 0
                if delta > OVERDUE_SEVERE:
                    rec.overdue_severity = 'severe'
                elif delta > OVERDUE_MODERATE:
                    rec.overdue_severity = 'moderate'
                else:
                    rec.overdue_severity = 'none'
            else:
                rec.jours_retard = 0
                rec.is_overdue = False
                rec.overdue_severity = 'none'

    @api.depends('settlement_ids')
    def _compute_settlement_count(self):
        for rec in self:
            rec.settlement_count = len(rec.settlement_ids)

    # ─────────────────────────────────────────────────────────────────────────
    #  Onchange — Timbre Fiscal automatique
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('policy_id')
    def _onchange_policy_id(self):
        """
        Pré-remplit les champs depuis la police parente :
        - dates de validité
        - véhicule/matricule
        - timbre fiscal (toujours 0.600 TND)
        """
        if self.policy_id:
            self.date_validite_du = self.policy_id.date_effect
            self.date_validite_au = self.policy_id.date_echeance
            self.date_echeance = self.policy_id.date_echeance
            self.vehicule = self.policy_id.matricule or self.policy_id.risque.name
            # Taxes fiscales : lues depuis la configuration de la société
            # (jamais codées en dur — décret Loi de Finances)
            company = self.env.company
            if not self.timbre_fiscal_tax_id and company.timbre_fiscal_tax_id:
                self.timbre_fiscal_tax_id = company.timbre_fiscal_tax_id
            if not self.tva_courtage_tax_id and company.tva_courtage_tax_id:
                self.tva_courtage_tax_id = company.tva_courtage_tax_id

    # ─────────────────────────────────────────────────────────────────────────
    #  Transitions d'état (Pipeline quittance — maquette page 02)
    # ─────────────────────────────────────────────────────────────────────────

    def action_notifier(self):
        """Émise → Notifiée (relance envoyée au client)."""
        for rec in self:
            if rec.state != 'emise':
                raise UserError(_('Seules les quittances Émises peuvent être Notifiées.'))
            rec.write({'state': 'notifiee'})
            rec._update_audit()
            # Créer une activité de suivi
            rec.activity_schedule(
                'mail.mail_activity_data_call',
                date_deadline=fields.Date.today() + relativedelta(days=7),
                summary=_('Relancer le client — %s') % rec.partner_id.name,
                user_id=rec.commercial_id.id or self.env.user.id,
            )

    def action_partial_payment(self):
        """Notifiée → Partielle (acompte reçu)."""
        for rec in self:
            if rec.state not in ('emise', 'notifiee'):
                raise UserError(
                    _('La quittance doit être Émise ou Notifiée pour enregistrer un acompte.')
                )
            if rec.amount_paid <= 0:
                raise UserError(
                    _('Enregistrez d\'abord au moins un règlement avant de passer en Partielle.')
                )
            rec.write({'state': 'partielle'})
            rec._update_audit()

    def action_encaisser(self):
        """Partielle / Notifiée → Encaissée (règlement total)."""
        for rec in self:
            if rec.state not in ('emise', 'notifiee', 'partielle'):
                raise UserError(
                    _('La quittance %(name)s ne peut pas être encaissée depuis l\'état %(state)s.',
                      name=rec.name,
                      state=dict(RECEIPT_STATE)[rec.state])
                )
            if rec.amount_residual > 0.001:  # tolérance arrondi 1 millime
                raise UserError(_(
                    'La quittance n\'est pas totalement réglée. '
                    'Reste dû : %(montant).3f TND. '
                    'Ajoutez un règlement complémentaire ou passez d\'abord en Partielle.',
                    montant=rec.amount_residual,
                ))
            rec.write({'state': 'encaissee'})
            rec._update_audit()
            # Génération de l'écriture comptable Odoo
            rec._create_accounting_move()
            # Mise à jour du statut de la police parente
            rec.policy_id._compute_financials()

    def action_reverser(self):
        """Encaissée → Reversée (bordereau compagnie envoyé)."""
        for rec in self:
            if rec.state != 'encaissee':
                raise UserError(_('Seules les quittances Encaissées peuvent être Reversées.'))
            rec.write({'state': 'reversee'})
            rec._update_audit()

    def action_contentieux(self):
        """→ Contentieux (impayé chronique, relance judiciaire)."""
        for rec in self:
            if rec.state in ('encaissee', 'reversee'):
                raise UserError(_('Une quittance Encaissée ou Reversée ne peut être mise en Contentieux.'))
            rec.write({'state': 'contentieux'})
            rec._update_audit()
            rec.activity_schedule(
                'mail.mail_activity_data_warning',
                date_deadline=fields.Date.today(),
                summary=_(
                    'CONTENTIEUX — Quittance %(name)s / %(client)s / %(montant).3f TND',
                    name=rec.name,
                    client=rec.partner_id.name,
                    montant=rec.amount_residual,
                ),
                user_id=self.env.user.id,
            )

    def action_reopen(self):
        """Contentieux → Émise (remise en cycle après accord)."""
        self.write({'state': 'emise'})
        self._update_audit()

    # ─────────────────────────────────────────────────────────────────────────
    #  Intégration comptable Odoo
    # ─────────────────────────────────────────────────────────────────────────

    def _create_accounting_move(self):
        """
        Crée l'écriture comptable Odoo (account.move) lors de l'encaissement.
        Permet le lettrage natif (reconciliation) avec account.payment.

        Structure de l'écriture :
          DÉBIT  : Compte client (400xxx) — montant TTC
          CRÉDIT : Compte de produits assurance (706xxx) — prime nette
          CRÉDIT : Compte TVA collectée (445xxx) — montant TVA
          CRÉDIT : Compte timbre fiscal (4447xx) — 0.600 TND
        """
        self.ensure_one()
        if self.move_id:
            return  # Écriture déjà existante

        company = self.env.company
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', company.id)],
            limit=1,
        )
        if not journal:
            _logger.warning(
                'AssurCore: Aucun journal de vente trouvé. '
                'L\'écriture comptable de %s ne sera pas créée.',
                self.name,
            )
            return

        # Lignes d'écriture
        move_lines = []

        # Ligne débit client
        move_lines.append((0, 0, {
            'name': _('Quittance %(name)s — %(client)s', name=self.name, client=self.partner_id.name),
            'partner_id': self.payer_id.id or self.partner_id.id,
            'debit': self.amount_total,
            'credit': 0.0,
            'account_id': self.partner_id.property_account_receivable_id.id,
        }))

        # Ligne crédit prime nette (reversement compagnie)
        if self.montant_prime:
            move_lines.append((0, 0, {
                'name': _('Prime nette — %s') % (self.company_ins_id.name or ''),
                'debit': 0.0,
                'credit': self.montant_prime,
                'account_id': self._get_account('706000'),  # Produits assurance
            }))

        # Ligne crédit honoraires HT
        if self.montant_honoraire_ht:
            move_lines.append((0, 0, {
                'name': _('Honoraires courtage HT'),
                'debit': 0.0,
                'credit': self.montant_honoraire_ht,
                'account_id': self._get_account('706100'),  # Honoraires courtage
            }))

        # Ligne crédit TVA collectée
        if self.montant_tva:
            move_lines.append((0, 0, {
                'name': _('TVA %s%%') % self.taux_tva,
                'debit': 0.0,
                'credit': self.montant_tva,
                'account_id': self._get_account('445710'),  # TVA collectée
            }))

        # Ligne crédit timbre fiscal (montant lu depuis la taxe, pas codé en dur)
        if self.timbre_fiscal:
            tax_name = (self.timbre_fiscal_tax_id.name
                        if self.timbre_fiscal_tax_id else _('Timbre Fiscal TN'))
            move_lines.append((0, 0, {
                'name': _('%(tax)s — %(amount).3f TND',
                          tax=tax_name, amount=self.timbre_fiscal),
                'debit': 0.0,
                'credit': self.timbre_fiscal,
                'account_id': self._get_account('447100'),  # Timbre fiscal
            }))

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': self.name,
            'narration': _(
                'Quittance %(qtt)s — Police %(police)s — %(client)s',
                qtt=self.name,
                police=self.policy_id.num_police,
                client=self.partner_id.name,
            ),
            'line_ids': move_lines,
        })
        move.action_post()
        self.move_id = move

    def _get_account(self, code):
        """Cherche un compte comptable par son code dans le plan comptable de la société."""
        account = self.env['account.account'].search(
            [
                ('code', 'like', code),
                ('company_id', '=', self.env.company.id),
            ],
            limit=1,
        )
        if not account:
            # Fallback sur le compte de produits par défaut
            account = self.env['account.account'].search(
                [
                    ('account_type', '=', 'income'),
                    ('company_id', '=', self.env.company.id),
                ],
                limit=1,
            )
        return account.id if account else False

    # ─────────────────────────────────────────────────────────────────────────
    #  Actions Smart Buttons
    # ─────────────────────────────────────────────────────────────────────────

    def action_view_settlements(self):
        """Smart Button → liste des règlements (chèques/virements)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Règlements — %s') % self.name,
            'res_model': 'insurance.settlement',
            'view_mode': 'tree,form',
            'domain': [('receipt_id', '=', self.id)],
            'context': {
                'default_receipt_id': self.id,
                'default_partner_id': self.payer_id.id or self.partner_id.id,
            },
        }

    def action_view_accounting_move(self):
        """Smart Button → écriture comptable Odoo."""
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('Aucune écriture comptable n\'est liée à cette quittance.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Écriture comptable'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
        }

    # ─────────────────────────────────────────────────────────────────────────
    #  Contraintes
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('date_emission', 'date_echeance')
    def _check_dates(self):
        for rec in self:
            if rec.date_emission and rec.date_echeance:
                if rec.date_echeance < rec.date_emission:
                    raise ValidationError(_(
                        'La date d\'échéance (%(ech)s) ne peut être antérieure '
                        'à la date d\'émission (%(emi)s) sur la quittance %(name)s.',
                        ech=rec.date_echeance,
                        emi=rec.date_emission,
                        name=rec.name,
                    ))

    @api.constrains('timbre_fiscal')
    def _check_timbre_fiscal(self):
        """Valide que le timbre fiscal n'est pas négatif."""
        for rec in self:
            if rec.timbre_fiscal < 0:
                raise ValidationError(_(
                    'Le timbre fiscal ne peut pas être négatif.'
                ))
            # Avertissement si l'opérateur dépasse le montant configuré dans la taxe
            ref_amount = (rec.timbre_fiscal_tax_id.amount
                          if rec.timbre_fiscal_tax_id else None)
            if ref_amount is not None and rec.timbre_fiscal != ref_amount:
                _logger.warning(
                    'AssurCore: Timbre fiscal de la quittance %s (%.3f TND) '
                    'différent du montant configuré dans la taxe (%.3f TND). '
                    'Modification intentionnelle ?',
                    rec.name, rec.timbre_fiscal, ref_amount,
                )

    _sql_constraints = [
        (
            'name_uniq',
            'UNIQUE(name)',
            'Le numéro de quittance doit être unique.',
        ),
    ]

    # ─────────────────────────────────────────────────────────────────────────
    #  Cron — Passage automatique en Contentieux
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_update_overdue_receipts(self):
        """
        Tâche planifiée quotidienne :
        Passe en 'Contentieux' les quittances dont le retard dépasse 90 jours.
        """
        seuil_contentieux = fields.Date.today() - relativedelta(days=90)
        overdue = self.search([
            ('state', 'in', ('emise', 'notifiee', 'partielle')),
            ('date_echeance', '<=', seuil_contentieux),
            ('amount_residual', '>', 0),
        ])
        if overdue:
            overdue.write({'state': 'contentieux'})
            _logger.info(
                'AssurCore: %d quittances passées en Contentieux (retard > 90j).',
                len(overdue),
            )

    @api.model
    def _cron_send_overdue_emails(self):
        """
        Cron dédié — Envoi des e-mails de relance quittances impayées.

        Seuils de relance :
          - 1ère relance : J+15 après date_echeance (retard modéré)
          - 2ème relance : J+45 après date_echeance (retard sévère)

        Garde-fou anti-doublon : on ne relance pas si un e-mail a déjà
        été envoyé dans les 14 derniers jours pour cette quittance.
        """
        today = fields.Date.today()
        seuil_1 = today - relativedelta(days=15)   # J+15
        seuil_2 = today - relativedelta(days=45)   # J+45
        fourteen_days_ago = fields.Datetime.now() - relativedelta(days=14)

        template = self.env.ref(
            'assurcore.email_template_receipt_overdue', raise_if_not_found=False
        )
        if not template:
            _logger.warning('AssurCore: template email_template_receipt_overdue introuvable.')
            return

        # Quittances à relancer (J+15 OU J+45) avec e-mail disponible
        overdue_receipts = self.search([
            ('state', 'in', ('emise', 'notifiee', 'partielle')),
            ('amount_residual', '>', 0),
            ('date_echeance', '<=', seuil_1),           # Au moins J+15
            ('date_echeance', '>=', today - relativedelta(days=89)),  # Pas encore Contentieux
        ])

        sent_count = 0
        for rec in overdue_receipts:
            email_dest = rec.payer_id.email or rec.partner_id.email
            if not email_dest:
                continue  # Pas d'e-mail disponible

            # Anti-doublon : vérifier le dernier e-mail de relance
            recent_msg = self.env['mail.message'].search([
                ('res_id', '=', rec.id),
                ('model', '=', 'insurance.receipt'),
                ('subtype_id.name', 'ilike', 'Email'),
                ('date', '>=', fourteen_days_ago),
                ('body', 'ilike', 'quittance'),
            ], limit=1)
            if recent_msg:
                continue  # Déjà relancé cette quinzaine

            try:
                template.send_mail(rec.id, force_send=True, raise_exception=False)
                sent_count += 1
                _logger.debug(
                    'AssurCore: relance quittance %s envoyée à %s (retard: %s j)',
                    rec.name, email_dest, (today - rec.date_echeance).days
                )
            except Exception as exc:
                _logger.error(
                    'AssurCore: Erreur relance quittance %s : %s', rec.name, exc
                )

        _logger.info(
            'AssurCore: %d e-mails relance quittances impayées envoyés.', sent_count
        )


    # ─────────────────────────────────────────────────────────────────────────
    #  Utilitaires internes
    # ─────────────────────────────────────────────────────────────────────────

    def _update_audit(self):
        self.write({
            'date_dernier_maj': fields.Datetime.now(),
        })

    @api.model
    def create(self, vals):
        """
        Génère le numéro séquentiel.
        Les taxes (timbre fiscal, TVA) sont injectées via les defaults
        des champs timbre_fiscal_tax_id / tva_courtage_tax_id,
        qui lisent res.company → jamais de valeur en dur ici.
        """
        if not vals.get('name') or vals['name'] == '/':
            vals['name'] = (
                self.env['ir.sequence'].next_by_code('insurance.receipt') or '/'
            )
        return super().create(vals)

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name
            if rec.partner_id:
                name += ' — ' + rec.partner_id.name
            if rec.company_ins_id:
                name += ' (%s)' % rec.company_ins_id.name
            result.append((rec.id, name))
        return result


# ─────────────────────────────────────────────────────────────────────────────
#  insurance.settlement — Règlement (chèque, espèces, virement)
#  Équivalent Oracle : PR_REGELEMENT + PR_PAYEMENT_JOUR_ENC
# ─────────────────────────────────────────────────────────────────────────────

class InsuranceSettlement(models.Model):
    """
    Un règlement (chèque, espèces, virement) reçu en paiement
    d'une ou plusieurs quittances.

    Cas clé du marché tunisien :
      Un père de famille peut apporter UN seul chèque qui règle
      les quittances de sa femme, de ses enfants et les siennes propres.
      → receipt_id peut être répété via des lignes de ventilation,
        ou le chèque est saisi une fois et lettré manuellement.

    Équivalent Oracle : PR_REGELEMENT (NUM_REG_CLT, NUM_CHEQUE, MONTANT_REG…)
    """

    _name = 'insurance.settlement'
    _description = 'Règlement de Quittance d\'Assurance'
    _inherit = ['mail.thread']
    _order = 'date_reg desc'

    SETTLEMENT_STATE = [
        ('brouillon', 'Brouillon'),
        ('remis',     'Remis en banque'),
        ('regle',     'Réglé'),
        ('encaisse',  'Encaissé'),
        ('impaye',    'Impayé (rejeté)'),
        ('remplace',  'Remplacé'),
    ]

    name = fields.Char(
        string='Référence',
        required=True,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'insurance.settlement'
        ) or '/',
        copy=False,
    )

    receipt_id = fields.Many2one(
        comodel_name='insurance.receipt',
        string='Quittance',
        required=False,
        ondelete='cascade',
        index=True,
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Payeur',
        required=True,
        help='Tireur du chèque / débiteur du virement. '
             'Peut être différent de l\'assuré (cas famille). '
             'Ex-champ Oracle : TIREUR VARCHAR2(50) dans PR_REGELEMENT.',
    )

    date_reg = fields.Date(
        string='Date de règlement',
        required=True,
        default=fields.Date.today,
        help='Ex-champ Oracle : DATE_REG dans PR_REGELEMENT.',
    )

    date_echeance_cheque = fields.Date(
        string='Date d\'échéance chèque',
        help='Date à laquelle le chèque doit être encaissé (chèque de garantie). '
             'Ex-champ Oracle : DATE_ECHEANCE dans PR_REGELEMENT.',
    )

    type_reg = fields.Selection(
        selection=TYPE_REG,
        string='Mode de règlement',
        default='C',
        required=True,
        help='Ex-champ Oracle : TYPE_REG CHAR(1) DEFAULT \'C\' dans PR_REGELEMENT.',
    )

    montant_reg = fields.Monetary(
        string='Montant (TND)',
        currency_field='currency_id',
        required=True,
        help='Ex-champ Oracle : MONTANT_REG NUMBER(11,3) dans PR_REGELEMENT.',
    )

    montant_restant = fields.Monetary(
        string='Montant restant non imputé (TND)',
        currency_field='currency_id',
        default=0.0,
        help='Si le chèque dépasse le montant dû, le surplus peut être '
             'reporté sur d\'autres quittances de la même famille. '
             'Ex-champ Oracle : MONTANT_RESTANT NUMBER(11,3) dans PR_REGELEMENT.',
    )

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        default=lambda self: self.env.ref('base.TND', raise_if_not_found=False)
                             or self.env.company.currency_id,
        readonly=True,
    )

    num_cheque = fields.Char(
        string='N° Chèque',
        size=20,
        help='Ex-champ Oracle : NUM_CHEQUE VARCHAR2(20) dans PR_REGELEMENT.',
    )

    banque_tireur = fields.Many2one(
        comodel_name='insurance.bank',
        string='Banque du tireur',
        help='Banque émettrice du chèque. '
             'Ex-champ Oracle : BANQUE_TIREUR VARCHAR2(100) dans PR_REGELEMENT.',
    )

    cin_tireur = fields.Char(
        string='CIN tireur',
        size=8,
        help='Ex-champ Oracle : CIN_TIREUR NUMBER(8,0) dans PR_REGELEMENT.',
    )

    state = fields.Selection(
        selection=SETTLEMENT_STATE,
        string='État',
        default='brouillon',
        tracking=True,
        required=True,
    )

    imputer = fields.Boolean(
        string='Imputé',
        default=False,
        help='Indique si ce règlement a été imputé sur une quittance. '
             'Ex-champ Oracle : IMPUTER CHAR(1) DEFAULT \'N\' dans PR_REGELEMENT.',
    )

    remis_chez = fields.Char(
        string='Remis chez',
        size=100,
        help='Banque où le chèque a été déposé. '
             'Ex-champ Oracle : REMIS_CHEZ VARCHAR2(100) dans PR_REGELEMENT.',
    )

    payment_id = fields.Many2one(
        comodel_name='account.payment',
        string='Paiement Odoo',
        readonly=True,
        copy=False,
        help='Lien vers le paiement Odoo généré lors de la confirmation. '
             'Permet le lettrage automatique (reconciliation) dans la comptabilité.',
    )

    notes = fields.Text(string='Notes')

    def action_remettre_banque(self):
        """Brouillon → Remis en banque."""
        self.write({'state': 'remis'})

    def action_confirmer(self):
        """Remis → Réglé (retour bancaire OK)."""
        for rec in self:
            rec.write({'state': 'regle', 'imputer': True})
            # Recalcul du montant encaissé sur la quittance parente
            rec.receipt_id._compute_amounts()

    def action_encaisser(self):
        """Réglé → Encaissé (banque a crédité le compte)."""
        self.write({'state': 'encaisse'})

    def action_rejeter(self):
        """→ Impayé (chèque sans provision, rejet bancaire)."""
        for rec in self:
            rec.write({'state': 'impaye', 'imputer': False})
            rec.receipt_id._compute_amounts()
