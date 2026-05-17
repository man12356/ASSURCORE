# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.commission.rule — Grille de Commissions par Compagnie × Branche
#  res.company — Extension : champs fiscaux tunisiens (Timbre + TVA)
#
#  Principe : Ne jamais coder en dur un taux ou un montant fiscal.
#
#  La matrice de commissions permet au manager de paramétrer :
#    STAR  + AUTO  → 10.0 %
#    STAR  + VIE   → 15.0 %
#    GAT   + AUTO  → 12.0 %
#    (toutes compagnies) + MRH → 8.0 %   (règle générique)
#
#  Logique de résolution (du plus spécifique au plus générique) :
#    1. Compagnie + Branche (exact)
#    2. Compagnie seule (toutes branches)
#    3. Branche seule (toutes compagnies)
#    4. Règle globale (compagnie=False, branche=False)
#    5. 0.0% si aucune règle trouvée
#
#  Modification de insurance.policy :
#    Ajout de _onchange_commission_rule qui remplit automatiquement
#    commission = prime_nette × taux de la grille.
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Extension res.company — Champs fiscaux tunisiens
#  Ces champs pointent vers les taxes account.tax créées dans insurance_data.xml
#  et constituent la SEULE source de vérité pour les montants fiscaux.
# ─────────────────────────────────────────────────────────────────────────────

class ResCompanyAssurcore(models.Model):
    """
    Extension de res.company pour les paramètres fiscaux tunisiens d'AssurCore.
    Les montants sont portés par les taxes account.tax — jamais codés en dur.
    """

    _inherit = 'res.company'

    # ── Taxes fiscales tunisiennes ────────────────────────────────────────────

    timbre_fiscal_tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Taxe — Timbre Fiscal (TND)',
        domain=[('amount_type', '=', 'fixed'), ('type_tax_use', '=', 'sale')],
        help='Taxe de type "Montant fixe" représentant le timbre fiscal tunisien. '
             'Montant actuel légal : 1.000 TND. '
             'MODIFIER LE MONTANT DE LA TAXE (pas le code Python) '
             'si la Loi de Finances change ce montant.',
    )

    tva_courtage_tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='TVA sur Honoraires de Courtage',
        domain=[('amount_type', '=', 'percent'), ('type_tax_use', '=', 'sale')],
        help='Taxe TVA applicable sur les honoraires de courtage. '
             'Standard tunisien : 7%. '
             'Peut varier selon le type de prestation (13%, 19%).',
    )

    # ── Paramètres trésorerie ─────────────────────────────────────────────────

    seuil_contentieux_jours = fields.Integer(
        string='Seuil Contentieux (jours)',
        default=90,
        help='Nombre de jours de retard après lequel une quittance est '
             'automatiquement basculée en Contentieux par le cron.',
    )

    seuil_relance_jours = fields.Integer(
        string='Seuil Relance Automatique (jours)',
        default=30,
        help='Horizon en jours pour les relances de renouvellement CRM.',
    )

    # ── Journal comptable assurance ───────────────────────────────────────────

    journal_assurance_id = fields.Many2one(
        comodel_name='account.journal',
        string='Journal Quittances Assurance',
        domain=[('type', '=', 'sale')],
        help='Journal Odoo utilisé pour générer les écritures comptables '
             'des quittances d\'assurance encaissées.',
    )


# ─────────────────────────────────────────────────────────────────────────────
#  insurance.commission.rule — Matrice de Commissions
# ─────────────────────────────────────────────────────────────────────────────

class InsuranceCommissionRule(models.Model):
    """
    Grille de paramétrage des taux de commission par Compagnie × Branche.

    Exemple de configuration :
      ┌────────────┬────────────┬──────────────┬──────────────┐
      │ Compagnie  │  Branche   │ Taux Comm. % │ Taux Hon. %  │
      ├────────────┼────────────┼──────────────┼──────────────┤
      │ STAR       │ AUTO       │   10.00      │    5.00      │
      │ STAR       │ VIE        │   15.00      │    8.00      │
      │ GAT        │ AUTO       │   12.00      │    5.00      │
      │ COMAR      │ SANTE      │    9.00      │    6.00      │
      │ (toutes)   │ MRH        │    8.00      │    4.00      │
      │ (toutes)   │ (toutes)   │    7.00      │    3.00      │  ← défaut global
      └────────────┴────────────┴──────────────┴──────────────┘

    Accès : Menu AssurCore → Paramétrage → Grille de Commissions
    Droits : group_assurcore_manager uniquement (lecture seule pour agent)
    """

    _name = 'insurance.commission.rule'
    _description = 'Règle de Commission Assurance'
    _order = 'priorite desc, company_ins_id, branche'
    _rec_name = 'display_name'

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

    # ── Clé de la règle (Compagnie × Branche) ─────────────────────────────────

    company_ins_id = fields.Many2one(
        comodel_name='insurance.company',
        string='Compagnie',
        ondelete='cascade',
        index=True,
        help='Laisser vide pour une règle applicable à TOUTES les compagnies.',
    )

    branche = fields.Selection(
        selection=BRANCHE_LIST,
        string='Branche',
        index=True,
        help='Laisser vide pour une règle applicable à TOUTES les branches.',
    )

    # ── Taux ──────────────────────────────────────────────────────────────────

    taux_commission = fields.Float(
        string='Taux Commission %',
        digits=(5, 2),
        required=True,
        help='Pourcentage de commission perçu sur la prime nette. '
             'Exemple : 10.00 pour 10%.',
    )

    taux_honoraire = fields.Float(
        string='Taux Honoraires %',
        digits=(5, 2),
        default=0.0,
        help='Pourcentage d\'honoraires de courtage calculé sur la prime nette. '
             'Différent de la commission : les honoraires sont facturés TTC au client.',
    )

    # ── Validité temporelle ───────────────────────────────────────────────────

    date_debut = fields.Date(
        string='Valable à partir du',
        help='Date de début de validité de cette règle. '
             'Vide = applicable depuis toujours.',
    )

    date_fin = fields.Date(
        string='Valable jusqu\'au',
        help='Date de fin de validité. '
             'Vide = pas de date d\'expiration.',
    )

    # ── Priorité de résolution ────────────────────────────────────────────────

    priorite = fields.Integer(
        string='Priorité',
        default=10,
        help='Plus la valeur est élevée, plus la règle est prioritaire. '
             'Utilisé pour départager deux règles applicables au même cas. '
             'Règle spécifique (Compagnie + Branche) : 100. '
             'Règle générique (toutes compagnies) : 10.',
    )

    # ── Métadonnées ───────────────────────────────────────────────────────────

    active = fields.Boolean(default=True)

    notes = fields.Text(
        string='Notes',
        help='Convention signée, date de négociation, conditions particulières…',
    )

    display_name = fields.Char(
        string='Règle',
        compute='_compute_display_name',
        store=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    #  Calculs
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('company_ins_id', 'branche', 'taux_commission')
    def _compute_display_name(self):
        for rule in self:
            parts = []
            parts.append(rule.company_ins_id.name if rule.company_ins_id else '(Toutes compagnies)')
            parts.append(dict(self.BRANCHE_LIST).get(rule.branche, '(Toutes branches)'))
            parts.append('→ %.2f%%' % rule.taux_commission)
            rule.display_name = ' / '.join(parts)

    # ─────────────────────────────────────────────────────────────────────────
    #  API publique : résolution du taux applicable
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def get_commission_rate(self, company_ins_id, branche, date=None):
        """
        Retourne le taux de commission applicable (float %) pour une
        combinaison Compagnie × Branche à une date donnée.

        Algorithme de résolution (du plus spécifique au plus générique) :
          1. Compagnie + Branche exact        → plus prioritaire
          2. Compagnie + (toutes branches)
          3. (toutes compagnies) + Branche
          4. Règle globale (défaut)           → moins prioritaire
          5. 0.0% si aucune règle             → log d'alerte

        Args:
            company_ins_id (int): ID de l'insurance.company
            branche (str): code de la branche ('AUTO', 'SANTE', etc.)
            date (date|None): date de référence (défaut = aujourd'hui)

        Returns:
            dict: {'taux_commission': float, 'taux_honoraire': float, 'rule_id': int|None}
        """
        if date is None:
            date = fields.Date.today()

        date_domain = [
            '|', ('date_debut', '=', False), ('date_debut', '<=', date),
            '|', ('date_fin', '=', False),   ('date_fin',   '>=', date),
        ]

        # Ordre de priorité : règles les plus spécifiques en premier
        candidates = []

        # 1. Exact match (Compagnie + Branche)
        if company_ins_id and branche:
            candidates.append([
                ('company_ins_id', '=', company_ins_id),
                ('branche', '=', branche),
            ] + date_domain)

        # 2. Compagnie seule
        if company_ins_id:
            candidates.append([
                ('company_ins_id', '=', company_ins_id),
                ('branche', '=', False),
            ] + date_domain)

        # 3. Branche seule (toutes compagnies)
        if branche:
            candidates.append([
                ('company_ins_id', '=', False),
                ('branche', '=', branche),
            ] + date_domain)

        # 4. Règle globale
        candidates.append([
            ('company_ins_id', '=', False),
            ('branche', '=', False),
        ] + date_domain)

        for domain in candidates:
            rule = self.search(domain + [('active', '=', True)],
                               order='priorite desc', limit=1)
            if rule:
                return {
                    'taux_commission': rule.taux_commission,
                    'taux_honoraire': rule.taux_honoraire,
                    'rule_id': rule.id,
                }

        # Aucune règle — log d'alerte pour le manager
        _logger.warning(
            'AssurCore — Aucune règle de commission pour '
            'company_ins_id=%s, branche=%s. Taux = 0%%.',
            company_ins_id, branche,
        )
        return {'taux_commission': 0.0, 'taux_honoraire': 0.0, 'rule_id': None}

    @api.model
    def get_honoraire_rate(self, company_ins_id, branche, date=None):
        """Raccourci : retourne uniquement le taux d'honoraires."""
        result = self.get_commission_rate(company_ins_id, branche, date)
        return result['taux_honoraire']

    # ─────────────────────────────────────────────────────────────────────────
    #  Contraintes
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('taux_commission', 'taux_honoraire')
    def _check_taux(self):
        for rule in self:
            if rule.taux_commission < 0 or rule.taux_commission > 100:
                raise ValidationError(_(
                    'Le taux de commission doit être compris entre 0 et 100%.'
                ))
            if rule.taux_honoraire < 0 or rule.taux_honoraire > 100:
                raise ValidationError(_(
                    'Le taux d\'honoraires doit être compris entre 0 et 100%.'
                ))

    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rule in self:
            if rule.date_debut and rule.date_fin:
                if rule.date_fin < rule.date_debut:
                    raise ValidationError(_(
                        'La date de fin doit être postérieure à la date de début.'
                    ))

    _sql_constraints = [
        (
            'rule_unique',
            'UNIQUE(company_ins_id, branche, date_debut)',
            'Une règle de commission existe déjà pour cette combinaison '
            'Compagnie / Branche / Date de début.',
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  Extension insurance.policy — Onchange commission automatique
#  Injecté ici (pas dans insurance_policy.py) pour éviter les imports circulaires
