# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta

class TestPolicyFlow(TransactionCase):

    def setUp(self):
        super(TestPolicyFlow, self).setUp()
        # Création de données de base pour les tests
        self.Partner = self.env['res.partner']
        self.Company = self.env['insurance.company']
        self.Policy = self.env['insurance.policy']
        
        self.partner = self.Partner.create({
            'name': 'Test Client ' + str(fields.Datetime.now()),
            'customer_rank': 1,
        })
        
        self.insurance_company = self.Company.search([('name', '=', 'STAR')], limit=1)
        if not self.insurance_company:
            self.insurance_company = self.Company.create({
                'name': 'STAR',
                'code': 'STAR',
            })

    def test_01_policy_creation(self):
        """Test de la création simple d'une police et génération de référence."""
        policy = self.Policy.create({
            'num_police': 'POL-TEST-001-' + str(fields.Datetime.now()),
            'partner_id': self.partner.id,
            'company_ins_id': self.insurance_company.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
        })
        self.assertEqual(policy.state, 'draft', "La police doit être en brouillon à la création.")
        self.assertNotEqual(policy.ref_interne, '/', "Une référence interne doit être générée.")

    def test_02_policy_activation(self):
        """Test du passage de brouillon à active."""
        policy = self.Policy.create({
            'num_police': 'POL-TEST-002-' + str(fields.Datetime.now()),
            'partner_id': self.partner.id,
            'company_ins_id': self.insurance_company.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
        })
        policy.action_activate()
        self.assertEqual(policy.state, 'active', "La police devrait être active.")

    def test_03_invalid_dates(self):
        """Test de la contrainte sur les dates (échéance <= effet)."""
        with self.assertRaises(ValidationError):
            self.Policy.create({
                'num_police': 'POL-TEST-003-' + str(fields.Datetime.now()),
                'partner_id': self.partner.id,
                'company_ins_id': self.insurance_company.id,
                'branche': 'AUTO',
                'date_effect': date.today(),
                'date_echeance': date.today() - timedelta(days=1),
            })
