# -*- coding: utf-8 -*-
# ==============================================================================
#  fleet.vehicle — Extension pour l'Assurance Tunisienne
# ==============================================================================

from odoo import fields, models

class FleetVehicle(models.Model):
    """
    Surcharge du modèle fleet.vehicle d'Odoo pour intégrer les caractéristiques
    propres au calcul et à la gestion du risque automobile en Tunisie.
    """
    _inherit = 'fleet.vehicle'

    puissance_fiscale = fields.Integer(
        string='Puissance Fiscale (CV)',
        help='Puissance fiscale du véhicule en chevaux fiscaux (CV).'
    )

    valeur_venale = fields.Monetary(
        string='Valeur Vénale (TND)',
        currency_field='currency_id',
        help='Valeur marchande actuelle du véhicule en Dinars Tunisiens.'
    )

    valeur_a_neuf = fields.Monetary(
        string='Valeur à Neuf (TND)',
        currency_field='currency_id',
        help='Valeur à neuf d\'achat du véhicule en Dinars Tunisiens.'
    )

    usage_vehicule = fields.Selection(
        selection=[
            ('prive', 'Privé / Personnel'),
            ('professionnel', 'Professionnel / Utilitaire'),
            ('transport_marchandises', 'Transport de marchandises'),
            ('transport_personnes', 'Transport de personnes (Taxi/Louage)'),
            ('autre', 'Autre'),
        ],
        string='Usage du véhicule',
        help='Usage principal déclaré pour le contrat d\'assurance.'
    )

    # Réutilisation ou définition de la devise par défaut si non disponible
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Devise par défaut',
        default=lambda self: self.env.ref('base.TND', raise_if_not_found=False)
                             or self.env.company.currency_id,
    )
