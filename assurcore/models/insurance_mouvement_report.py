# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.mouvement.report — Vue SQL consultative pour le rapport
#  "Etat Mouvement Clients primes"
# ==============================================================================

from odoo import fields, models, tools

class InsuranceMouvementReport(models.Model):
    """
    Modèle Odoo consultatif basé sur une Vue SQL Postgres.
    Exécute la requête de filtrage et de regroupement en temps réel sur les
    données des tables existantes (insurance.operation, insurance.policy,
    res.partner, insurance.company).
    """
    _name = 'insurance.mouvement.report'
    _description = 'Rapport Consultatif Mouvement Clients Primes'
    _auto = False
    _order = 'date_op desc, num_operation desc'

    # ── Champs de la Vue SQL ──
    num_police = fields.Char(string='N° Police', readonly=True)
    num_operation = fields.Char(string='N° Opération', readonly=True)
    date_op = fields.Date(string="Date d'opération", readonly=True)
    designation = fields.Char(string='Désignation', readonly=True)
    num_quittance = fields.Char(string='N° Quittance', readonly=True)
    num_attestation = fields.Char(string='N° Attestation', readonly=True)
    vehicule = fields.Char(string='Véhicule', readonly=True)
    compagnie = fields.Char(string='Compagnie', readonly=True)
    date_validite_du = fields.Date(string='Couverture du', readonly=True)
    date_validite_au = fields.Date(string='Couverture au', readonly=True)
    montant_prime = fields.Float(string='Montant Prime', readonly=True)
    montant_honoraire_ht = fields.Float(string='Honoraires HT', readonly=True)
    annee_fact_prime = fields.Integer(string='Année Fact. Prime', readonly=True)
    num_edit_facture_prime = fields.Char(string='Réf Facture Prime', readonly=True)
    annee_fact_hon = fields.Integer(string='Année Fact. Hon.', readonly=True)
    num_edit_facture_hon = fields.Char(string='Réf Facture Hon.', readonly=True)
    num_client = fields.Char(string='Code Client', readonly=True)
    categorie_facture_prime = fields.Char(string='Cat. Facture Prime', readonly=True)
    categorie_facture_hon = fields.Char(string='Cat. Facture Hon.', readonly=True)
    attribut_client = fields.Char(string='Attribut Client', readonly=True)
    type_client = fields.Selection(
        selection=[('E', 'Entreprise'), ('P', 'Particulier')],
        string='Type Client',
        readonly=True
    )
    raison_sociale = fields.Char(string='Raison Sociale', readonly=True)
    t_c = fields.Selection(
        selection=[('T', 'Tiers'), ('P', 'Propre')],
        string='Type Contrat (T_C)',
        readonly=True
    )

    def init(self):
        """Crée ou met à jour la Vue SQL Postgres."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    op.id AS id,
                    pol.num_police AS num_police,
                    op.name AS num_operation,
                    op.date_op AS date_op,
                    op.designation AS designation,
                    op.num_quittance AS num_quittance,
                    op.num_attestation AS num_attestation,
                    op.vehicule AS vehicule,
                    comp.name AS compagnie,
                    op.date_validite_du AS date_validite_du,
                    op.date_validite_au AS date_validite_au,
                    op.montant_prime AS montant_prime,
                    op.montant_honoraire_ht AS montant_honoraire_ht,
                    op.annee_fact_prime AS annee_fact_prime,
                    op.num_edit_facture_prime AS num_edit_facture_prime,
                    op.annee_fact_hon AS annee_fact_hon,
                    op.num_edit_facture_hon AS num_edit_facture_hon,
                    part.ref AS num_client,
                    op.categorie_facture_prime AS categorie_facture_prime,
                    op.categorie_facture_hon AS categorie_facture_hon,
                    op.attribut_client AS attribut_client,
                    pol.type_client AS type_client,
                    part.name AS raison_sociale,
                    op.type_contrat AS t_c
                FROM insurance_operation op
                LEFT JOIN insurance_policy pol ON op.policy_id = pol.id
                LEFT JOIN res_partner part ON pol.partner_id = part.id
                LEFT JOIN insurance_company comp ON pol.company_ins_id = comp.id
                ORDER BY op.date_op ASC, op.name ASC
            )
        """ % self._table)
