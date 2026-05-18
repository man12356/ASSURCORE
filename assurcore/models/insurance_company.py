# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.company — Référentiel des Compagnies d'Assurance
#  Ex-table Oracle : PR_COMPAGNIE
#  Compagnies connues : STAR, GAT, LLOYD, COMAR, ASTRÉE, AMI, MAE…
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class InsuranceCompany(models.Model):
    """
    Table de référence des compagnies d'assurance avec lesquelles
    le courtier a des conventions. Correspond à PR_COMPAGNIE dans Oracle.
    """

    _name        = 'insurance.company'
    _description = 'Compagnie d\'Assurance'
    _order       = 'priorite_envoi asc, name asc'
    _rec_name    = 'name'

    # ── Identification ─────────────────────────────────────────────────────────

    name = fields.Char(
        string='Nom compagnie',
        required=True,
        size=30,
        tracking=True,
        help='Nom court de la compagnie (ex: STAR, GAT, LLOYD). '
             'Ex-champ Oracle : COMPAGNIE VARCHAR2(30) dans PR_COMPAGNIE.',
    )

    raison_sociale = fields.Char(
        string='Raison sociale complète',
        size=100,
        help='Raison sociale officielle pour les documents légaux.',
    )

    code = fields.Char(
        string='Code',
        size=10,
        index=True,
        help='Code court utilisé dans les références (ex: STAR, GAT).',
    )

    # ── Contact ────────────────────────────────────────────────────────────────

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Fiche partenaire Odoo',
        ondelete='set null',
        help='Lien vers le partenaire Odoo de la compagnie '
             '(adresse, contacts, facturation).',
    )

    email = fields.Char(string='Email', size=100)
    phone = fields.Char(string='Téléphone', size=30)
    website = fields.Char(string='Site web', size=100)

    # ── Gestion trésorerie ─────────────────────────────────────────────────────

    priorite_envoi = fields.Integer(
        string='Priorité d\'envoi des bordereaux',
        default=10,
        help='Ordre de traitement lors de l\'envoi des bordereaux de reversement. '
             'Ex-champ Oracle : PRIORITE_ENVOI_COMPAGNIE NUMBER(7,0) dans PR_COMPAGNIE.',
    )

    delai_reversement = fields.Integer(
        string='Délai de reversement (jours)',
        default=30,
        help='Délai contractuel maximum pour reverser les primes encaissées.',
    )

    taux_commission_defaut = fields.Float(
        string='Taux commission par défaut (%)',
        digits=(5, 2),
        default=0.0,
        help='Taux de commission général si aucune règle spécifique n\'existe '
             'dans la grille insurance.commission.rule.',
    )

    # ── Métadonnées ────────────────────────────────────────────────────────────

    agence_courtier = fields.Char(
        string='Agence de rattachement',
        size=50,
        default=lambda self: self.env.company.name,
        help='Ex-champ Oracle : AGENCE_COURTIER VARCHAR2(50) dans PR_COMPAGNIE.',
    )

    notes = fields.Text(
        string='Notes / Conditions conventionnelles',
        help='Ex-champ Oracle : NOTES VARCHAR2(250) dans PR_COMPAGNIE.',
    )

    active = fields.Boolean(
        string='Actif',
        default=True,
        help='Désactiver pour archiver une compagnie sans perdre l\'historique.',
    )

    # ── Compteurs calculés ─────────────────────────────────────────────────────

    policy_count = fields.Integer(
        string='Polices',
        compute='_compute_counts',
    )

    receipt_count = fields.Integer(
        string='Quittances',
        compute='_compute_counts',
    )

    @api.depends('name')
    def _compute_counts(self):
        for rec in self:
            rec.policy_count = self.env['insurance.policy'].search_count(
                [('company_ins_id', '=', rec.id)]
            )
            rec.receipt_count = self.env['insurance.receipt'].search_count(
                [('company_ins_id', '=', rec.id)]
            )

    # ── Contraintes ────────────────────────────────────────────────────────────

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)',
         'Ce nom de compagnie existe déjà.'),
        ('code_uniq', 'UNIQUE(code)',
         'Ce code compagnie existe déjà.'),
    ]

    @api.constrains('taux_commission_defaut')
    def _check_taux(self):
        for rec in self:
            if not 0 <= rec.taux_commission_defaut <= 100:
                raise ValidationError(_(
                    'Le taux de commission doit être entre 0 et 100%.'
                ))

    def action_view_policies(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Polices — %s') % self.name,
            'res_model': 'insurance.policy',
            'view_mode': 'tree,form',
            'domain': [('company_ins_id', '=', self.id)],
        }
