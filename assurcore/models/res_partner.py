# -*- coding: utf-8 -*-
# ==============================================================================
#  res.partner — Surcharge : Structure Famille / Payeur (AssurCore)
#  Maquette de référence : deck2.pdf page 04 « Fiche Client Famille/Payeur »
#
#  Concept clé du marché tunisien :
#    Un PAYEUR (chef de famille) peut régler d'un seul chèque les quittances
#    de tous les membres de sa famille (conjoint + enfants), chacun ayant
#    ses propres polices chez des compagnies différentes.
#
#  Architecture :
#    payer_partner_id  → Many2one  vers le chef de famille (self-référence)
#    family_member_ids → One2many  des membres rattachés à ce payeur
#    solde_caisse_consolide → somme des impayés de tous les membres
#
#  Cycle de vie client :  Prospect → Actif → Fidèle 5+ → VIP → Résilié
#  Ex-table Oracle : PR_CLIENT (NUM_CLIENT, TYPE_CLIENT, ATTRIBUT_CLIENT…)
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Sélections
# ─────────────────────────────────────────────────────────────────────────────

CLIENT_STATE = [
    ('prospect', 'Prospect'),
    ('actif',    'Actif'),
    ('fidele',   'Fidèle 5+'),
    ('vip',      'VIP'),
    ('resilie',  'Résilié'),
]

CATEGORIE_CLIENT = [
    ('CC', 'Compte Clé'),
    ('GE', 'Grande Entreprise'),
    ('PM', 'PME'),
    ('PA', 'Particulier Standard'),
    ('PF', 'Particulier Fidèle'),
]


class ResPartner(models.Model):
    """
    Extension du partenaire Odoo standard pour le métier assurance tunisien.
    Ajoute : la structure Famille/Payeur, le cycle de vie client,
    les champs d'identité tunisiens (CIN, MF), et les agrégats financiers
    qui alimentent le Dashboard Trésorerie (solde_caisse_consolide).
    """

    _inherit = 'res.partner'

    # ── 1. Cycle de vie client (Statusbar — maquette page 04) ─────────────────

    client_state = fields.Selection(
        selection=CLIENT_STATE,
        string='Statut client',
        default='prospect',
        tracking=True,
        help='Pipeline de maturité du client. '
             'Alimente la statusbar Odoo dans la vue Form.',
    )

    date_premiere_police = fields.Date(
        string='Première police',
        compute='_compute_anciennete',
        store=False,
        help='Date de la police la plus ancienne. '
             'Permet de déclencher automatiquement le passage en Fidèle 5+.',
    )

    anciennete_annees = fields.Integer(
        string='Ancienneté (ans)',
        compute='_compute_anciennete',
        store=False,
    )

    # ── 2. Structure Famille / Payeur ─────────────────────────────────────────

    is_payer = fields.Boolean(
        string='Payeur principal (chef de famille)',
        default=False,
        tracking=True,
        help='Cochez si ce partenaire est le payeur centralisé pour plusieurs '
             'assurés de sa famille. Il recevra un seul relevé consolidé.',
    )

    payer_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Payeur / Chef de famille',
        domain="[('is_payer', '=', True), ('id', '!=', id)]",
        ondelete='set null',
        index=True,
        tracking=True,
        help='Rattache ce membre à un payeur principal. '
             'Le lettrage des chèques sera effectué sur le payeur. '
             'Concept clé pour le cas tunisien : un père paye un seul chèque '
             'pour les polices de toute sa famille.',
    )

    family_member_ids = fields.One2many(
        comodel_name='res.partner',
        inverse_name='payer_partner_id',
        string='Membres de la famille',
        help='Liste de tous les assurés dont ce partenaire est le payeur.',
    )

    family_member_count = fields.Integer(
        string='Membres',
        compute='_compute_family_counts',
        help='Nombre de membres rattachés à ce payeur (hors lui-même).',
    )

    policy_ids = fields.One2many(
        comodel_name='insurance.policy',
        inverse_name='partner_id',
        string='Polices d\'assurance',
    )

    receipt_ids = fields.One2many(
        comodel_name='insurance.receipt',
        inverse_name='partner_id',
        string='Quittances',
    )

    claim_ids = fields.One2many(
        comodel_name='insurance.claim',
        inverse_name='partner_id',
        string='Sinistres',
    )

    # ── 3. Identité tunisienne ─────────────────────────────────────────────────

    cin = fields.Char(
        string='N° CIN',
        size=8,
        index=True,
        help='Carte d\'Identité Nationale tunisienne (8 chiffres). '
             'Ex-champ Oracle : CIN NUMBER(8,0) dans PR_CLIENT.',
    )

    matricule_fiscal = fields.Char(
        string='Matricule Fiscal',
        size=20,
        index=True,
        help='Identifiant fiscal tunisien (ex: 1234567/A/M/000). '
             'Ex-champ Oracle : MF VARCHAR2(20) dans PR_CLIENT.',
    )

    registre_commerce = fields.Char(
        string='N° RC',
        size=20,
        help='Registre de Commerce pour les entreprises. '
             'Ex-champ Oracle : RC VARCHAR2(20) dans PR_CLIENT.',
    )

    assujetti_tva = fields.Boolean(
        string='Assujetti TVA',
        default=True,
        help='Détermine si la TVA est applicable sur les honoraires. '
             'Ex-champ Oracle : ASSUJETTI CHAR(1) DEFAULT \'O\' dans PR_CLIENT.',
    )

    categorie_client = fields.Selection(
        selection=CATEGORIE_CLIENT,
        string='Catégorie client',
        help='Segment commercial. Ex-champ Oracle : CATEGORIE_CLIENT CHAR(2) dans PR_CLIENT.',
    )

    taux_remise = fields.Float(
        string='Taux de remise %',
        digits=(5, 2),
        default=0.0,
        help='Remise commerciale accordée à ce client sur les honoraires. '
             'Ex-champ Oracle : TAUX_REMISE NUMBER(5,2) dans PR_CLIENT.',
    )

    # ── 4. Agrégats financiers — Famille consolidée ────────────────────────────
    #       Alimentent le Dashboard Trésorerie et la Fiche Client

    solde_caisse_consolide = fields.Monetary(
        string='Solde global famille (TND)',
        currency_field='currency_id',
        compute='_compute_solde_consolide',
        store=False,
        help='Somme des impayés de ce client ET de tous les membres de sa famille. '
             'Valeur négative = dette envers le cabinet (rouge sur la fiche). '
             'Valeur nulle/positive = à jour (bleu sur la fiche). '
             'Reproduit la logique Oracle SOLDE_C dans PR_COMPTE_CLIENT.',
    )

    total_encaisse_ytd = fields.Monetary(
        string='Encaissé YTD (TND)',
        currency_field='currency_id',
        compute='_compute_financial_totals',
        store=False,
        help='Total encaissé sur l\'année civile en cours (Année To Date). '
             'Correspond au Smart Button "Encaissé YTD" de la maquette.',
    )

    total_prime_portefeuille = fields.Monetary(
        string='Total primes portefeuille (TND)',
        currency_field='currency_id',
        compute='_compute_financial_totals',
        store=False,
        help='Somme de toutes les primes émises (polices actives).',
    )

    # ── 5. Compteurs pour Smart Buttons (maquette page 04) ────────────────────

    policy_count = fields.Integer(
        string='Polices actives',
        compute='_compute_assurance_counts',
    )

    receipt_count = fields.Integer(
        string='Quittances',
        compute='_compute_assurance_counts',
    )

    impaye_count = fields.Integer(
        string='Quittances impayées',
        compute='_compute_assurance_counts',
    )

    claim_count = fields.Integer(
        string='Sinistres',
        compute='_compute_assurance_counts',
    )

    # ── 6. Champs calculés ────────────────────────────────────────────────────

    @api.depends()  # store=False : recalcul a la demande, pas besoin de trigger
    def _compute_anciennete(self):
        today = fields.Date.today()
        for partner in self:
            policies = partner.policy_ids.filtered(lambda p: p.date_effect)
            if policies:
                first_date = min(policies.mapped('date_effect'))
                partner.date_premiere_police = first_date
                delta = relativedelta(today, first_date)
                partner.anciennete_annees = delta.years
            else:
                partner.date_premiere_police = False
                partner.anciennete_annees = 0

    @api.depends('family_member_ids')
    def _compute_family_counts(self):
        for partner in self:
            partner.family_member_count = len(partner.family_member_ids)

    @api.depends('is_payer')  # store=False : policy_ids non disponible au chargement
    def _compute_solde_consolide(self):
        """
        Calcule le solde consolidé de la famille :
        - Pour un PAYEUR : impayés propres + impayés de tous les membres
        - Pour un membre ordinaire : uniquement ses propres impayés

        La valeur est NÉGATIVE si le client doit de l'argent (dette),
        ce qui permet un affichage rouge sur la fiche (maquette page 04).
        """
        for partner in self:
            # Impayés directs (polices dont ce partenaire est l'assuré)
            own_impaye = sum(partner.policy_ids.mapped('total_impaye'))

            # Impayés des membres de la famille (si payeur principal)
            family_impaye = 0.0
            if partner.is_payer and partner.family_member_ids:
                for member in partner.family_member_ids:
                    family_impaye += sum(member.policy_ids.mapped('total_impaye'))

            total_impaye = own_impaye + family_impaye
            # Négatif = dette client → affichage rouge sur fiche
            partner.solde_caisse_consolide = -total_impaye if total_impaye else 0.0

    @api.depends()  # store=False : recalcul a la demande
    def _compute_financial_totals(self):
        today = fields.Date.today()
        year_start = today.replace(month=1, day=1)

        for partner in self:
            # Total encaissé YTD (sur les polices de ce client)
            receipts_ytd = self.env['insurance.receipt'].search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ('encaissee', 'reversee')),
                ('date_emission', '>=', year_start),
            ])
            partner.total_encaisse_ytd = sum(receipts_ytd.mapped('amount_total'))

            # Total primes portefeuille (toutes polices actives)
            active_policies = partner.policy_ids.filtered(
                lambda p: p.state == 'active'
            )
            partner.total_prime_portefeuille = sum(
                active_policies.mapped('prime_nette')
            )

    @api.depends()  # store=False : recalcul a la demande
    def _compute_assurance_counts(self):
        """Compteurs pour les Smart Buttons de la fiche client."""
        for partner in self:
            policies = partner.policy_ids
            partner.policy_count = len(
                policies.filtered(lambda p: p.state == 'active')
            )

            all_receipts = policies.mapped('receipt_ids')
            partner.receipt_count = len(all_receipts)
            partner.impaye_count = len(
                all_receipts.filtered(
                    lambda r: r.state in ('emise', 'notifiee', 'contentieux')
                )
            )
            partner.claim_count = len(policies.mapped('claim_ids'))

    # ── 7. Actions Smart Buttons ──────────────────────────────────────────────

    def action_view_policies(self):
        """Smart Button → liste des polices du client."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Polices — %s') % self.name,
            'res_model': 'insurance.policy',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_receipts(self):
        """Smart Button → quittances du client (toutes compagnies)."""
        self.ensure_one()
        # Inclure les quittances en tant que payeur (famille)
        domain = [
            '|',
            ('partner_id', '=', self.id),
            ('payer_id', '=', self.id),
        ]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quittances — %s') % self.name,
            'res_model': 'insurance.receipt',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'default_partner_id': self.id,
                'default_payer_id': self.id if self.is_payer else False,
            },
        }

    def action_view_impayes(self):
        """Smart Button → quittances impayées (badge rouge maquette)."""
        self.ensure_one()
        domain = [
            '|',
            ('partner_id', '=', self.id),
            ('payer_id', '=', self.id),
            ('state', 'in', ('emise', 'notifiee', 'contentieux')),
        ]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Impayés — %s') % self.name,
            'res_model': 'insurance.receipt',
            'view_mode': 'tree,form',
            'domain': domain,
        }

    def action_view_claims(self):
        """Smart Button → sinistres du client."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sinistres — %s') % self.name,
            'res_model': 'insurance.claim',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    # ── 8. Transitions d'état (workflow client) ───────────────────────────────

    def action_set_actif(self):
        """Prospect → Actif (dès la première police émise)."""
        self.write({'client_state': 'actif'})

    def action_set_fidele(self):
        """Actif → Fidèle 5+ (déclenché par le cron d'ancienneté)."""
        self.write({'client_state': 'fidele'})

    def action_set_vip(self):
        """Fidèle → VIP (décision commerciale manuelle)."""
        self.write({'client_state': 'vip'})

    def action_set_resilie(self):
        """→ Résilié (toutes polices résiliées)."""
        for partner in self:
            active_policies = partner.policy_ids.filtered(
                lambda p: p.state not in ('canceled', 'expired')
            )
            if active_policies:
                raise ValidationError(_(
                    'Ce client possède encore %d police(s) active(s). '
                    'Résiliez-les avant de clore le dossier client.',
                    len(active_policies),
                ))
        self.write({'client_state': 'resilie'})

    # ── 9. Cron : mise à jour automatique du statut client ────────────────────

    @api.model
    def _cron_update_client_states(self):
        """
        Tâche planifiée quotidienne :
        1. Passe en 'Fidèle 5+' les clients actifs depuis ≥ 5 ans
        2. Met à jour is_payer automatiquement si un membre a été rattaché
        """
        # Fidélisation automatique à 5 ans
        actifs = self.search([
            ('client_state', '=', 'actif'),
            ('anciennete_annees', '>=', 5),
        ])
        if actifs:
            actifs.write({'client_state': 'fidele'})
            _logger.info(
                'AssurCore: %d clients promus Fidèle 5+.', len(actifs)
            )

        # Activation automatique (prospect avec une police active)
        prospects_avec_police = self.search([
            ('client_state', '=', 'prospect'),
            ('policy_ids.state', '=', 'active'),
        ])
        if prospects_avec_police:
            prospects_avec_police.write({'client_state': 'actif'})
            _logger.info(
                'AssurCore: %d prospects activés (police active détectée).',
                len(prospects_avec_police),
            )

    # ── 10. Contraintes ────────────────────────────────────────────────────────

    @api.constrains('payer_partner_id', 'is_payer')
    def _check_payer_consistency(self):
        for partner in self:
            # Un payeur principal ne peut pas être lui-même un membre d'un autre payeur
            if partner.is_payer and partner.payer_partner_id:
                raise ValidationError(_(
                    '%(name)s est défini comme payeur principal. '
                    'Il ne peut pas simultanément être rattaché à un autre payeur.',
                    name=partner.name,
                ))
            # Éviter la self-référence
            if partner.payer_partner_id == partner:
                raise ValidationError(_(
                    'Un partenaire ne peut pas être son propre payeur.'
                ))

    _sql_constraints = [
        # (
        #     'cin_uniq',
        #     'UNIQUE(cin)',
        #     'Ce numéro de CIN est déjà enregistré pour un autre client.',
        # ),
        # (
        #     'matricule_fiscal_uniq',
        #     'UNIQUE(matricule_fiscal)',
        #     'Ce matricule fiscal est déjà enregistré pour un autre client.',
        # ),
    ]

    # ── 11. Onchange ───────────────────────────────────────────────────────────

    @api.onchange('family_member_ids')
    def _onchange_family_members(self):
        """Active automatiquement is_payer si des membres sont ajoutés."""
        if self.family_member_ids:
            self.is_payer = True

    @api.onchange('is_company')
    def _onchange_is_company_assur(self):
        """Force la catégorie entreprise si is_company."""
        if self.is_company:
            self.assujetti_tva = True
