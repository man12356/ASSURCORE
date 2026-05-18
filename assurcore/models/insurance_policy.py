# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.policy — Police d'Assurance
#  Migré depuis Oracle PR_POLICE (ASSKAREKAMOUN)
#
#  Cycle de vie : Brouillon → Active → Résiliée / Expirée / Impayée
#  Clé métier   : num_police (ex-NUM_POLICE1 VARCHAR2(30))
#  Multi-branches : Auto, Santé, MRH, Transport, Incendie, Vie, RC Pro...
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Constantes métier
# ─────────────────────────────────────────────────────────────────────────────

TYPE_CLIENT = [
    ('E', 'Entreprise'),
    ('P', 'Particulier'),
]

BRANCHE_LIST = [
    ('AUTO',      'Automobile'),
    ('SANTE',     'Santé / Maladie'),
    ('MRH',       'Multirisque Habitation'),
    ('TRANSPORT', 'Transport de Marchandises'),
    ('INCENDIE',  'Incendie & Risques Divers'),
    ('VIE',       'Assurance Vie'),
    ('RC',        'Responsabilité Civile'),
    ('MARITIME',  'Maritime / Corps'),
    ('AUTRE',     'Autre'),
]

STATE_POLICE = [
    ('draft',    'Brouillon'),
    ('active',   'Active'),
    ('unpaid',   'Impayée'),
    ('expired',  'Expirée'),
    ('canceled', 'Résiliée'),
]


# ─────────────────────────────────────────────────────────────────────────────
#  Modèle principal : insurance.policy
# ─────────────────────────────────────────────────────────────────────────────

class InsurancePolicy(models.Model):
    """
    Représente une police d'assurance (contrat).
    Équivalent Odoo de la table Oracle PR_POLICE.

    Relations clés :
      - partner_id        → res.partner  (assuré / client)
      - payer_id          → res.partner  (payeur, peut différer de l'assuré)
      - company_ins_id    → insurance.company (ex-PR_COMPAGNIE)
      - commercial_id     → res.users    (producteur / commercial)
      - operation_ids     → insurance.operation (avenants, renouvellements)
      - receipt_ids       → insurance.receipt   (quittances, hérite account.move)
      - claim_ids         → insurance.claim     (sinistres, ex-PR_SINISTRE)
    """

    _name = 'insurance.policy'
    _description = 'Police d\'Assurance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_effect desc, num_police desc'
    _rec_name = 'num_police'

    # ── 1. Identification ────────────────────────────────────────────────────────
    
    num_police = fields.Char(
        string='N° Police',
        size=30,
        required=True,
        copy=False,
        tracking=True,
        index=True,
        help='Numéro de police tel qu\'il figure sur le document de la compagnie. '
             'Ex-champ Oracle : NUM_POLICE1',
    )

    ref_interne = fields.Char(
        string='Réf. interne',
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('insurance.policy') or '/',
        help='Référence séquentielle interne AssurCore.',
    )

    state = fields.Selection(
        selection=STATE_POLICE,
        string='État',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
        help='Cycle de vie de la police.',
    )

    branch_id = fields.Many2one(
        comodel_name='insurance.branch',
        string='Branche (Paramétrable)',
        tracking=True,
        help='Branche paramétrable.',
    )

    branche = fields.Selection(
        selection=BRANCHE_LIST,
        string='Ancienne Branche',
        tracking=True,
        help='Ancien champ de sélection (conservé pour migration).',
    )

    # ── Client & Payeur (Gestion Famille) ─────────────────────────────────────

    type_client = fields.Selection(
        selection=TYPE_CLIENT,
        string='Type client',
        default='P',
        required=True,
        tracking=True,
        help='Particulier (P) ou Entreprise (E). Ex-champ Oracle : TYPE_CLIENT.',
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Assuré / Client',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        domain="[('active', '=', True)]",
        help='Le titulaire du contrat. '
             'Mappé depuis Oracle NUM_CLIENT + TYPE_CLIENT + ATTRIBUT_CLIENT.',
    )

    payer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Payeur (chef de famille)',
        ondelete='restrict',
        tracking=True,
        help='Quand le payeur est différent de l\'assuré (ex: père qui règle '
             'les polices de toute sa famille). Permet le lettrage multi-quittances '
             'en un seul chèque.',
    )

    is_family_policy = fields.Boolean(
        string='Police famille',
        compute='_compute_is_family_policy',
        store=True,
        help='Vrai si le payeur est différent de l\'assuré (cas famille).',
    )

    raison_sociale = fields.Char(
        string='Raison sociale / Nom affiché',
        size=50,
        tracking=True,
        help='Nom affiché sur les documents. Pré-rempli depuis le partenaire. '
             'Ex-champ Oracle : RAISON_SOCIALE.',
    )

    # ── Compagnie & Branche ───────────────────────────────────────────────────

    company_ins_id = fields.Many2one(
        comodel_name='insurance.company',
        string='Compagnie d\'assurance',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Compagnie gestionnaire du risque (STAR, GAT, LLOYD, COMAR, ASTRÉE…). '
             'Ex-champ Oracle : COMPAGNIE (VARCHAR2).',
    )

    branche = fields.Selection(
        selection=BRANCHE_LIST,
        string='Branche',
        required=True,
        tracking=True,
        help='Branche d\'assurance. Ex-champ Oracle : BRANCHE.',
    )

    risque = fields.Char(
        string='Risque assuré',
        size=100,
        help='Désignation précise du risque (ex: Peugeot 208, Appartement Lac 2…).',
    )

    # ── Véhicule (Branche AUTO — lien fleet.vehicle) ──────────────────────────

    vehicle_id = fields.Many2one(
        comodel_name='fleet.vehicle',
        string='Véhicule',
        ondelete='set null',
        domain="[('driver_id', '=', partner_id)]",
        help='Lien vers le module Flotte d\'Odoo. '
             'Ex-champ Oracle : VEHICULE dans PR_OPERATION.',
    )

    matricule = fields.Char(
        string='Matricule tunisien',
        size=20,
        help='Numéro d\'immatriculation tunisien (ex: 183 TU 4521). '
             'Stocké ici quand le véhicule n\'est pas encore dans le module Flotte.',
    )

    # ── Dates de validité ─────────────────────────────────────────────────────

    date_effect = fields.Date(
        string='Date d\'effet',
        required=True,
        tracking=True,
        help='Date de début de couverture (DATE_VALIDITE_DU dans PR_OPERATION).',
    )

    date_echeance = fields.Date(
        string='Date d\'échéance',
        required=True,
        tracking=True,
        help='Date de fin de couverture (DATE_VALIDITE_AU dans PR_OPERATION).',
    )

    date_prochain_renouvellement = fields.Date(
        string='Prochain renouvellement',
        compute='_compute_prochain_renouvellement',
        store=True,
        help='Calculé automatiquement = date_echeance + 1 jour.',
    )

    jours_avant_echeance = fields.Integer(
        string='Jours avant échéance',
        compute='_compute_jours_avant_echeance',
        help='Nombre de jours restants avant l\'échéance (négatif si expirée).',
    )

    # ── Financier ─────────────────────────────────────────────────────────────

    prime_nette = fields.Monetary(
        string='Prime nette TND',
        currency_field='currency_id',
        tracking=True,
        help='Montant de la prime sans frais ni taxes.',
    )

    commission = fields.Monetary(
        string='Commission TND',
        currency_field='currency_id',
        tracking=True,
        help='Commission perçue par le courtier sur cette police.',
    )

    # Lien vers la règle de commission qui a calculé ce taux
    # (anciennement dans InsurancePolicyCommission — fusionné ici
    #  pour éviter _inherit = 'insurance.policy' dans un autre fichier)
    commission_rule_id = fields.Many2one(
        comodel_name='insurance.commission.rule',
        string='Règle de commission appliquée',
        readonly=True,
        help='Règle de la grille qui a déterminé le taux de commission. '
             'Renseigné automatiquement lors du choix de la compagnie/branche.',
    )

    taux_commission = fields.Float(
        string='Taux commission %',
        digits=(5, 2),
        compute='_compute_taux_commission',
        store=True,
        help='Taux calculé automatiquement = commission / prime_nette × 100.',
    )

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Devise',
        default=lambda self: self.env.ref('base.TND', raise_if_not_found=False)
                             or self.env.company.currency_id,
        readonly=True,
    )

    # ── Trésorerie — Soldes calculés depuis les quittances ────────────────────

    total_quittances = fields.Monetary(
        string='Total quittances TTC',
        currency_field='currency_id',
        compute='_compute_financials',
        store=True,
        help='Somme de toutes les quittances émises (TTC) liées à cette police.',
    )

    total_encaisse = fields.Monetary(
        string='Total encaissé TND',
        currency_field='currency_id',
        compute='_compute_financials',
        store=True,
        help='Somme des montants effectivement encaissés (quittances Encaissée).',
    )

    total_impaye = fields.Monetary(
        string='Total impayé TND',
        currency_field='currency_id',
        compute='_compute_financials',
        store=True,
        help='Montant restant dû = total_quittances − total_encaisse.',
    )

    # ── Relations ─────────────────────────────────────────────────────────────

    operation_ids = fields.One2many(
        comodel_name='insurance.operation',
        inverse_name='policy_id',
        string='Opérations / Avenants',
        help='Tous les avenants, renouvellements, modifications liés à cette police. '
             'Équivalent table Oracle PR_OPERATION.',
    )

    receipt_ids = fields.One2many(
        comodel_name='insurance.receipt',
        inverse_name='policy_id',
        string='Quittances',
        help='Toutes les quittances (échéances) de la police. '
             'Équivalent table Oracle PR_OPERATION (les lignes facturées).',
    )

    claim_ids = fields.One2many(
        comodel_name='insurance.claim',
        inverse_name='policy_id',
        string='Sinistres',
        help='Tous les sinistres déclarés sur cette police. '
             'Équivalent table Oracle PR_SINISTRE.',
    )

    # ── Compteurs pour Smart Buttons ──────────────────────────────────────────

    receipt_count = fields.Integer(
        string='Quittances',
        compute='_compute_counts',
    )

    impaye_count = fields.Integer(
        string='Impayées',
        compute='_compute_counts',
    )

    claim_count = fields.Integer(
        string='Sinistres',
        compute='_compute_counts',
    )

    operation_count = fields.Integer(
        string='Opérations',
        compute='_compute_counts',
    )

    # ── Commercial ────────────────────────────────────────────────────────────

    commercial_id = fields.Many2one(
        comodel_name='res.users',
        string='Commercial / Producteur',
        tracking=True,
        help='Utilisateur AssurCore responsable de la production. '
             'Correspond au NUM_COMMERCIAL dans Oracle PR_CLIENT.',
    )

    agence_courtier = fields.Char(
        string='Agence',
        size=50,
        default=lambda self: self.env.company.name,
        tracking=True,
        help='Agence ou bureau de rattachement (ex: Tunis, Sfax). '
             'Ex-champ Oracle : AGENCE_COURTIER.',
    )

    # ── Métadonnées & Audit ───────────────────────────────────────────────────

    notes = fields.Text(
        string='Notes',
        help='Remarques libres sur la police. Ex-champ Oracle : NOTES.',
    )

    supp_log = fields.Boolean(
        string='Suppression logique',
        default=False,
        help='Marqueur de suppression logique (non suppression physique). '
             'Ex-champ Oracle : SUPP_LOG CHAR(1) DEFAULT \'N\'.',
    )

    active = fields.Boolean(
        string='Actif',
        default=True,
        help='Désactivé = archivé (correspond à SUPP_LOG = \'O\' dans Oracle).',
    )

    date_dernier_maj = fields.Datetime(
        string='Dernière mise à jour',
        readonly=True,
        help='Ex-champ Oracle : DATE_DERNIER_MAJ.',
    )

    user_dernier_maj = fields.Char(
        string='Modifié par',
        size=20,
        readonly=True,
        help='Ex-champ Oracle : UTILISATEUR.',
    )

    # ─────────────────────────────────────────────────────────────────────────
    #  Méthodes calculées (compute)
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('payer_id', 'partner_id')
    def _compute_is_family_policy(self):
        """Une police est 'famille' quand le payeur ≠ l'assuré."""
        for rec in self:
            rec.is_family_policy = bool(
                rec.payer_id and rec.payer_id != rec.partner_id
            )

    @api.depends('date_echeance')
    def _compute_prochain_renouvellement(self):
        for rec in self:
            if rec.date_echeance:
                rec.date_prochain_renouvellement = (
                    rec.date_echeance + relativedelta(days=1)
                )
            else:
                rec.date_prochain_renouvellement = False

    @api.depends('date_echeance')
    def _compute_jours_avant_echeance(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_echeance:
                delta = rec.date_echeance - today
                rec.jours_avant_echeance = delta.days
            else:
                rec.jours_avant_echeance = 0

    @api.depends('prime_nette', 'commission')
    def _compute_taux_commission(self):
        for rec in self:
            if rec.prime_nette:
                rec.taux_commission = (rec.commission / rec.prime_nette) * 100
            else:
                rec.taux_commission = 0.0

    @api.depends('receipt_ids', 'receipt_ids.state', 'receipt_ids.amount_total',
                 'receipt_ids.amount_residual')
    def _compute_financials(self):
        """
        Calcule les agrégats financiers depuis les quittances liées.
        Reproduit la logique de SOLDE_C (Oracle) via les écritures Odoo.
        """
        for rec in self:
            receipts = rec.receipt_ids
            rec.total_quittances = sum(receipts.mapped('amount_total'))
            encaisse = receipts.filtered(
                lambda r: r.state in ('encaissee', 'reversee')
            )
            rec.total_encaisse = sum(encaisse.mapped('amount_total'))
            rec.total_impaye = rec.total_quittances - rec.total_encaisse

    @api.depends('receipt_ids', 'claim_ids', 'operation_ids')
    def _compute_counts(self):
        for rec in self:
            rec.receipt_count = len(rec.receipt_ids)
            rec.impaye_count = len(
                rec.receipt_ids.filtered(lambda r: r.state in ('impayee', 'contentieux'))
            )
            rec.claim_count = len(rec.claim_ids)
            rec.operation_count = len(rec.operation_ids)

    # ─────────────────────────────────────────────────────────────────────────
    #  Onchange
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Pré-remplit la raison sociale depuis le partenaire."""
        if self.partner_id:
            self.raison_sociale = self.partner_id.name
            # Si le partenaire est de type 'company', force le type_client E
            if self.partner_id.is_company:
                self.type_client = 'E'
            else:
                self.type_client = 'P'
            # Par défaut le payeur = le payeur de la famille ou l'assuré lui-même
            if not self.payer_id:
                self.payer_id = self.partner_id.payer_partner_id or self.partner_id

    @api.onchange('branche')
    def _onchange_branche(self):
        """Remet à zéro le véhicule si la branche n'est pas AUTO."""
        if self.branche != 'AUTO':
            self.vehicle_id = False
            self.matricule = False

    @api.onchange('company_ins_id', 'branche', 'prime_nette', 'date_effect')
    def _onchange_compute_commission(self):
        """
        Calcule automatiquement la commission depuis la grille
        insurance.commission.rule dès que la compagnie ou la branche change.
        Remplace le taux statique codé en dur de l'ancienne application Oracle.
        """
        if not (self.company_ins_id and self.branche):
            return
        result = self.env['insurance.commission.rule'].get_commission_rate(
            company_ins_id=self.company_ins_id.id,
            branche=self.branche,
            date=self.date_effect or fields.Date.today(),
        )
        if result['taux_commission'] and self.prime_nette:
            self.commission = self.prime_nette * (result['taux_commission'] / 100.0)
        if result['rule_id']:
            self.commission_rule_id = result['rule_id']
        elif not result['rule_id']:
            return {
                'warning': {
                    'title': _('Aucune règle de commission'),
                    'message': _(
                        'Aucune règle trouvée pour %(compagnie)s / %(branche)s.\n'
                        'Commission mise à 0. Configurez la grille dans '
                        'AssurCore → Paramétrage → Commissions.',
                        compagnie=self.company_ins_id.name,
                        branche=dict(self._fields['branche'].selection).get(
                            self.branche, self.branche),
                    ),
                }
            }

    # ─────────────────────────────────────────────────────────────────────────
    #  Contraintes
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('date_effect', 'date_echeance')
    def _check_dates(self):
        for rec in self:
            if rec.date_effect and rec.date_echeance:
                if rec.date_echeance <= rec.date_effect:
                    raise ValidationError(_(
                        'La date d\'échéance doit être postérieure à la date d\'effet '
                        'sur la police %(police)s.',
                        police=rec.num_police,
                    ))

    _sql_constraints = [
        (
            'num_police_company_uniq',
            'UNIQUE(num_police, company_ins_id)',
            'Le numéro de police doit être unique par compagnie d\'assurance.',
        ),
    ]

    # ─────────────────────────────────────────────────────────────────────────
    #  Transitions d'état (workflow)
    # ─────────────────────────────────────────────────────────────────────────

    def action_activate(self):
        """Brouillon → Active."""
        for rec in self:
            if not rec.date_effect or not rec.date_echeance:
                raise UserError(_(
                    'Veuillez renseigner les dates d\'effet et d\'échéance '
                    'avant d\'activer la police.'
                ))
            rec.write({'state': 'active'})
            rec._update_audit_fields()

    def action_cancel(self):
        """Active → Résiliée."""
        for rec in self:
            if rec.claim_ids.filtered(lambda c: c.state not in ('clos', 'regle')):
                raise UserError(_(
                    'Cette police possède des sinistres ouverts. '
                    'Clôturez-les avant de résilier la police.'
                ))
            rec.write({'state': 'canceled'})
            rec._update_audit_fields()

    def action_reopen(self):
        """Résiliée / Expirée → Active (réouverture)."""
        self.write({'state': 'active'})
        self._update_audit_fields()

    def action_set_unpaid(self):
        """Active → Impayée (appelé par le scheduler)."""
        self.write({'state': 'unpaid'})

    # ─────────────────────────────────────────────────────────────────────────
    #  Actions Smart Buttons
    # ─────────────────────────────────────────────────────────────────────────

    def action_view_receipts(self):
        """Smart Button → liste des quittances de la police."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quittances — %s') % self.num_police,
            'res_model': 'insurance.receipt',
            'view_mode': 'tree,form',
            'domain': [('policy_id', '=', self.id)],
            'context': {'default_policy_id': self.id},
        }

    def action_view_claims(self):
        """Smart Button → liste des sinistres de la police."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sinistres — %s') % self.num_police,
            'res_model': 'insurance.claim',
            'view_mode': 'tree,form',
            'domain': [('policy_id', '=', self.id)],
            'context': {'default_policy_id': self.id},
        }

    def action_view_operations(self):
        """Smart Button → liste des opérations / avenants."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Opérations / Avenants — %s') % self.num_police,
            'res_model': 'insurance.operation',
            'view_mode': 'tree,form',
            'domain': [('policy_id', '=', self.id)],
            'context': {'default_policy_id': self.id},
        }

    # ─────────────────────────────────────────────────────────────────────────
    #  Scheduler automatique (Cron)
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_check_policy_states(self):
        """
        Tâche planifiée quotidienne :
        1. Marque les polices expirées (date_echeance < aujourd'hui)
        2. Marque les polices impayées (impayé > 0 et active)

        NOTE : Les relances e-mail J-30 sont gérées par _cron_send_renewal_emails().
        """
        today = fields.Date.today()

        # 1. Expirations
        expired = self.search([
            ('state', '=', 'active'),
            ('date_echeance', '<', today),
        ])
        if expired:
            expired.write({'state': 'expired'})
            _logger.info('AssurCore: %d polices marquées Expirées.', len(expired))

        # 2. Impayées (total_impaye > 0 et active)
        unpaid = self.search([
            ('state', '=', 'active'),
            ('total_impaye', '>', 0),
        ])
        if unpaid:
            unpaid.write({'state': 'unpaid'})
            _logger.info('AssurCore: %d polices marquées Impayées.', len(unpaid))

    @api.model
    def _cron_send_renewal_emails(self):
        """
        Cron dédié — Envoi des e-mails de relance renouvellement (J-30 et J-7).

        Fenêtre : polices dont l'échéance est entre aujourd'hui et J+30.
        Pour éviter les doublons, on ne relance que si aucun message AssurCore
        renouvellement n'a déjà été envoyé dans les 7 derniers jours.
        Crée aussi une activité CRM pour le commercial.
        """
        today = fields.Date.today()
        horizon = today + relativedelta(days=30)
        seven_days_ago = fields.Datetime.now() - relativedelta(days=7)

        template = self.env.ref(
            'assurcore.email_template_policy_renewal', raise_if_not_found=False
        )
        if not template:
            _logger.warning('AssurCore: template email_template_policy_renewal introuvable.')
            return

        renewals = self.search([
            ('state', 'in', ('active', 'unpaid')),
            ('date_echeance', '>=', today),
            ('date_echeance', '<=', horizon),
            ('partner_id.email', '!=', False),
        ])

        sent_count = 0
        for policy in renewals:
            # Vérifier si un e-mail de relance a déjà été envoyé récemment
            recent_msg = self.env['mail.message'].search([
                ('res_id', '=', policy.id),
                ('model', '=', 'insurance.policy'),
                ('subtype_id.name', 'ilike', 'Email'),
                ('date', '>=', seven_days_ago),
                ('body', 'ilike', 'renouvellement'),
            ], limit=1)
            if recent_msg:
                continue  # Déjà relancé cette semaine

            try:
                template.send_mail(policy.id, force_send=True, raise_exception=False)
                sent_count += 1

                # Créer aussi une activité CRM pour le commercial
                deadline = policy.date_echeance - relativedelta(days=7)
                if deadline >= today:
                    policy.activity_schedule(
                        'mail.mail_activity_data_call',
                        date_deadline=deadline,
                        summary=_(
                            'Relance renouvellement — %(num)s / %(client)s (échéance %(date)s)',
                            num=policy.num_police,
                            client=policy.partner_id.name,
                            date=str(policy.date_echeance),
                        ),
                        user_id=policy.commercial_id.id or self.env.user.id,
                    )
            except Exception as exc:
                _logger.error(
                    'AssurCore: Erreur envoi e-mail relance police %s : %s',
                    policy.num_police, exc
                )

        _logger.info(
            'AssurCore: %d e-mails de relance renouvellement envoyés (horizon 30j).',
            sent_count
        )

    def action_send_renewal_email(self):
        """Action manuelle : envoyer l'e-mail de relance depuis la fiche police."""
        self.ensure_one()
        template = self.env.ref(
            'assurcore.email_template_policy_renewal', raise_if_not_found=False
        )
        if not template:
            raise UserError(_('Template e-mail de relance introuvable. Vérifiez le module.'))
        if not self.partner_id.email:
            raise UserError(_(
                'L\'assuré %s n\'a pas d\'adresse e-mail renseignée.',
                self.partner_id.name
            ))
        template.send_mail(self.id, force_send=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('E-mail envoyé'),
                'message': _(
                    'E-mail de relance envoyé à %s.', self.partner_id.email
                ),
                'type': 'success',
                'sticky': False,
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    #  Utilitaires internes
    # ─────────────────────────────────────────────────────────────────────────

    def _update_audit_fields(self):
        """Met à jour les champs d'audit date/utilisateur (équiv. trigger Oracle)."""
        self.write({
            'date_dernier_maj': fields.Datetime.now(),
            'user_dernier_maj': self.env.user.login,
        })

    @api.model
    def create(self, vals):
        """
        Génère la référence séquentielle, pré-remplit la raison sociale
        et auto-calcule la commission depuis la grille si non fournie.
        """
        if not vals.get('ref_interne') or vals['ref_interne'] == '/':
            vals['ref_interne'] = (
                self.env['ir.sequence'].next_by_code('insurance.policy') or '/'
            )
        if vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            if not vals.get('raison_sociale'):
                vals['raison_sociale'] = partner.name
            if not vals.get('payer_id'):
                vals['payer_id'] = partner.payer_partner_id.id or partner.id
        rec = super().create(vals)
        # Auto-calcul commission depuis la grille
        if rec.company_ins_id and rec.branche and not rec.commission:
            result = self.env['insurance.commission.rule'].get_commission_rate(
                company_ins_id=rec.company_ins_id.id,
                branche=rec.branche,
                date=rec.date_effect or fields.Date.today(),
            )
            if result['taux_commission'] and rec.prime_nette:
                rec.commission = rec.prime_nette * (result['taux_commission'] / 100.0)
            if result['rule_id']:
                rec.commission_rule_id = result['rule_id']
        return rec

    def write(self, vals):
        """Trace automatiquement la date de dernière modification."""
        if any(k not in ('date_dernier_maj', 'user_dernier_maj') for k in vals):
            vals.setdefault('date_dernier_maj', fields.Datetime.now())
            vals.setdefault('user_dernier_maj', self.env.user.login)
        return super().write(vals)

    def name_get(self):
        """Affichage : 'N° Police — Client (Compagnie)'"""
        result = []
        for rec in self:
            name = rec.num_police or '/'
            if rec.partner_id:
                name += ' — ' + rec.partner_id.name
            if rec.company_ins_id:
                name += ' (%s)' % rec.company_ins_id.name
            result.append((rec.id, name))
        return result
