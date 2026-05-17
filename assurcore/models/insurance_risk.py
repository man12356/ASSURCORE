# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.risk   — Référentiel des Risques Assurables par Branche
#  insurance.operation.code — Codes d'Opérations paramétrables
#
#  Ex-tables Oracle : PR_RISQUE (37 lignes), PR_CODE_OPERATION (87 lignes)
#
#  Ces tables remplacent les anciens champs Char/Selection pour offrir
#  un paramétrage relationnel complet exigé par le client.
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# ─────────────────────────────────────────────────────────────────────────────
#  insurance.risk — Catégories de risques assurables
#  Ex-table Oracle : PR_RISQUE (colonnes : RISQUE, BRANCHE)
# ─────────────────────────────────────────────────────────────────────────────

class InsuranceRisk(models.Model):
    """
    Référentiel des risques assurables, classés par branche.
    Exemple : RISQUE='Comptant' BRANCHE='AUTO'
              RISQUE='Terme'    BRANCHE='INCENDIE'

    Remplace le champ Char 'risque' sur insurance.policy
    par une relation Many2one vers ce modèle.
    """

    _name        = 'insurance.risk'
    _description = 'Risque Assurable'
    _order       = 'branche asc, name asc'
    _rec_name    = 'display_name'

    BRANCHE_LIST = [
        ('AUTO',       'Automobile'),
        ('SANTE',      'Santé / Maladie'),
        ('MRH',        'Multirisque Habitation'),
        ('TRANSPORT',  'Transport de Marchandises'),
        ('INCENDIE',   'Incendie & Risques Divers'),
        ('VIE',        'Assurance Vie'),
        ('RC',         'Responsabilité Civile'),
        ('MARITIME',   'Maritime / Corps'),
        ('ASSISTANCE', 'Assistance'),
        ('AVIATIONS',  'Aviations'),
        ('AUTRE',      'Autre'),
    ]

    name = fields.Char(
        string='Désignation du risque',
        required=True,
        size=50,
        help='Ex-champ Oracle : RISQUE VARCHAR2(50) dans PR_RISQUE.',
    )

    branche = fields.Selection(
        selection=BRANCHE_LIST,
        string='Branche',
        required=True,
        index=True,
        help='Ex-champ Oracle : BRANCHE VARCHAR2(100) dans PR_RISQUE.',
    )

    branche_oracle = fields.Char(
        string='Branche Oracle (original)',
        size=100,
        help='Valeur originale BRANCHE de PR_RISQUE conservée pour référence historique.',
    )

    active = fields.Boolean(default=True)

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('name', 'branche')
    def _compute_display_name(self):
        branche_map = dict(self.BRANCHE_LIST)
        for rec in self:
            branche_label = branche_map.get(rec.branche, rec.branche or '')
            rec.display_name = f'{branche_label} — {rec.name}' if rec.name else ''

    _sql_constraints = [
        ('name_branche_uniq', 'UNIQUE(name, branche)',
         'Ce risque existe déjà pour cette branche.'),
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  insurance.operation.code — Codes d'Opérations paramétrables
#  Ex-table Oracle : PR_CODE_OPERATION / PR_CODE_SERVICE
#  Remplace le champ Selection 'code_operation' sur insurance.operation
# ─────────────────────────────────────────────────────────────────────────────

class InsuranceOperationCode(models.Model):
    """
    Table de référence des codes d'opération assurance.
    Chaque code correspond à un type d'acte : Émission, Renouvellement,
    Avenant, Annulation, Résiliation…

    Remplace la Sélection statique sur insurance.operation
    par un modèle relationnel paramétrable depuis l'interface.
    """

    _name        = 'insurance.operation.code'
    _description = 'Code d\'Opération Assurance'
    _order       = 'code asc'
    _rec_name    = 'display_name'

    code = fields.Char(
        string='Code (3 chiffres)',
        required=True,
        size=10,
        index=True,
        help='Ex: 001=Émission, 002=Renouvellement, 003=Avenant, 006=Annulation. '
             'Ex-champ Oracle : CODE_OPERATION1 CHAR(3).',
    )

    designation = fields.Char(
        string='Désignation',
        required=True,
        size=250,
        help='Ex-champ Oracle : DESIGNATION VARCHAR2(250) dans PR_CODE_OPERATION.',
    )

    libelle_honoraire = fields.Char(
        string='Libellé honoraires',
        size=500,
        help='Texte par défaut pour les honoraires liés à ce type d\'opération. '
             'Ex-champ Oracle : LIBELLE_HONORAIRE VARCHAR2(500).',
    )

    description = fields.Text(
        string='Description détaillée',
        help='Ex-champ Oracle : DESCRIPTION VARCHAR2(1000).',
    )

    type_operation = fields.Selection(
        selection=[
            ('EMI', 'Émission initiale'),
            ('REN', 'Renouvellement'),
            ('AVN', 'Avenant'),
            ('SUS', 'Suspension'),
            ('ANN', 'Annulation'),
            ('RES', 'Résiliation'),
            ('REM', 'Remise en vigueur'),
            ('CES', 'Cession'),
            ('HON', 'Honoraires seuls'),
            ('AUTRE', 'Autre'),
        ],
        string='Type normalisé Odoo',
        help='Mapping vers la sélection normalisée du module AssurCore. '
             'Permet de continuer à utiliser la logique métier existante.',
    )

    montant_honoraire_defaut = fields.Float(
        string='Honoraires par défaut (TND)',
        digits=(11, 3),
        default=0.0,
        help='Montant d\'honoraires pré-rempli par défaut pour ce type d\'opération.',
    )

    taux_honoraire_defaut = fields.Float(
        string='Taux honoraires par défaut (%)',
        digits=(5, 2),
        default=0.0,
        help='Taux d\'honoraires calculé sur la prime, pré-rempli par défaut.',
    )

    active = fields.Boolean(default=True)

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('code', 'designation')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.code}] {rec.designation}' if rec.code else rec.designation or ''

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)',
         'Ce code d\'opération existe déjà.'),
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  Extension res.partner — Champ is_expert
#  Ajoute un marqueur booléen pour identifier les experts en assurance
#  (correspondait à PR_EXPERT dans l'ancien système)
# ─────────────────────────────────────────────────────────────────────────────

class ResPartnerExpert(models.Model):
    """
    Extension de res.partner pour marquer les experts en assurance.
    Plutôt que de créer un modèle séparé 'insurance.expert', nous réutilisons
    res.partner (même logique que pour les compagnies d'assurance).
    L'expert existant (PR_EXPERT : 1 ligne) sera créé via res.partner
    avec is_expert=True.
    """

    _inherit = 'res.partner'

    is_expert = fields.Boolean(
        string='Expert en assurance',
        default=False,
        index=True,
        help='Cochez pour identifier ce partenaire comme expert mandaté '
             'sur les sinistres. Correspond à PR_EXPERT dans Oracle.',
    )

    specialite_expert = fields.Char(
        string='Spécialité',
        size=100,
        help='Domaine d\'expertise (Auto, Incendie, Maritime…).',
    )
