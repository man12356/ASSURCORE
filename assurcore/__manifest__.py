# -*- coding: utf-8 -*-
# AssurCore -- Module de Courtage Assurance (Tunisie) -- IPF / Mansour Borchani

{
    'name': 'AssurCore -- Courtage & Assurance TN',
    'version': '17.0.1.2.0',
    'category': 'Insurance',
    'summary': 'Gestion de courtage assurance pour le marche tunisien.',
    'author': 'IPF',
    'website': 'https://www.facebook.com/perseverance.formation',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'crm',
        'fleet',
        'contacts',
    ],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'data/insurance_data.xml',
        'views/res_partner_views.xml',
        'views/insurance_company_views.xml',
        'views/insurance_commission_rule_views.xml',
        'views/insurance_policy_views.xml',
        'views/dashboard_views.xml',
        'views/insurance_receipt_views.xml',
        'views/insurance_claim_views.xml',
        'views/insurance_risk_views.xml',
        'views/insurance_mouvement_report_wizard_views.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('prepend', 'assurcore/static/src/scss/_variables.scss'),
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
