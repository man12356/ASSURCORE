# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError
from odoo import fields
from datetime import date, timedelta

class TestOcrFlow(TransactionCase):

    def setUp(self):
        super(TestOcrFlow, self).setUp()
        self.Partner = self.env['res.partner']
        self.Company = self.env['insurance.company']
        self.Policy = self.env['insurance.policy']
        self.Parser = self.env['insurance.document.parser']
        self.Wizard = self.env['insurance.ocr.wizard']
        
        self.insurance_company = self.Company.search([('name', '=', 'STAR')], limit=1)
        if not self.insurance_company:
            self.insurance_company = self.Company.create({
                'name': 'STAR',
                'code': 'STAR',
            })

    def test_01_ocr_extraction_simulation(self):
        """Test de la simulation OCR sur la police."""
        # Crée une police en brouillon
        policy = self.Policy.create({
            'num_police': 'POL-OCR-TEST-001',
            'partner_id': self.Partner.create({'name': 'Dummy Client'}).id,
            'company_ins_id': self.insurance_company.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
        })
        
        # Lance la simulation OCR sur la police
        action = policy.action_test_ocr()
        self.assertEqual(action.get('type'), 'ir.actions.client')
        
        # Après simulation, l'OCR mock a créé/mis à jour une police avec le même numéro
        # et compagnie, mais comme le client 'Foulen Ben Foulen' n'existe pas,
        # la police doit être passée à l'état 'draft_ocr' avec les champs OCR bruts renseignés.
        updated_policy = self.Policy.search([
            ('num_police', '=', 'POL-OCR-TEST-001'),
            ('company_ins_id', '=', self.insurance_company.id)
        ])
        self.assertTrue(updated_policy)
        self.assertEqual(updated_policy.state, 'draft_ocr')
        self.assertEqual(updated_policy.ocr_raw_partner_name, 'Foulen Ben Foulen')
        self.assertEqual(updated_policy.ocr_raw_cin, '01234567')
        self.assertEqual(updated_policy.ocr_raw_company_type, 'person')

    def test_02_wizard_b2c_existing_partner(self):
        """Test du wizard pour un client B2C existant."""
        policy = self.Policy.create({
            'num_police': 'POL-OCR-TEST-002',
            'partner_id': self.Partner.create({'name': 'Dummy Client'}).id,
            'company_ins_id': self.insurance_company.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
        })
        policy.action_test_ocr()
        
        # Crée le vrai partenaire existant
        real_partner = self.Partner.create({
            'name': 'Foulen Ben Foulen',
            'cin': '01234567',
        })
        
        # Ouvre le wizard
        action = policy.action_open_ocr_wizard()
        wizard = self.Wizard.with_context(action['context']).create({
            'policy_id': policy.id,
            'partner_id': real_partner.id,
        })
        
        # Confirme
        wizard.action_confirm()
        
        self.assertEqual(policy.state, 'draft')
        self.assertEqual(policy.partner_id.id, real_partner.id)
        self.assertFalse(policy.ocr_raw_partner_name)

    def test_03_wizard_b2c_new_partner(self):
        """Test du wizard pour un nouveau client B2C (création)."""
        policy = self.Policy.create({
            'num_police': 'POL-OCR-TEST-003',
            'partner_id': self.Partner.create({'name': 'Dummy Client'}).id,
            'company_ins_id': self.insurance_company.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
        })
        policy.action_test_ocr()
        
        # Ouvre le wizard et demande la création d'un nouveau partenaire
        action = policy.action_open_ocr_wizard()
        wizard = self.Wizard.with_context(action['context']).create({
            'policy_id': policy.id,
            'create_new_partner': True,
            'partner_id': False,
            'new_partner_name': 'Foulen Ben Foulen',
            'new_partner_cin': '01234567',
        })
        
        wizard.action_confirm()
        
        self.assertEqual(policy.state, 'draft')
        self.assertEqual(policy.partner_id.name, 'Foulen Ben Foulen')
        self.assertEqual(policy.partner_id.cin, '01234567')
        self.assertFalse(policy.partner_id.is_company)

    def test_04_wizard_b2b_new_company(self):
        """Test du wizard pour une nouvelle entreprise B2B (création)."""
        policy = self.Policy.create({
            'num_police': 'POL-OCR-TEST-004',
            'partner_id': self.Partner.create({'name': 'Dummy Client'}).id,
            'company_ins_id': self.insurance_company.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
            'state': 'draft_ocr',
            'ocr_raw_partner_name': 'Ste Import Export',
            'ocr_raw_company_type': 'company',
            'ocr_raw_matricule_fiscal': '1234567MAM000',
        })
        
        # Ouvre le wizard et demande la création d'une entreprise
        action = policy.action_open_ocr_wizard()
        wizard = self.Wizard.with_context(action['context']).create({
            'policy_id': policy.id,
            'create_new_partner': True,
            'partner_id': False,
            'new_partner_name': 'Ste Import Export',
            'new_partner_matricule_fiscal': '1234567MAM000',
        })
        
        # Le trigger _onchange_create_new_partner remplit les types
        wizard._onchange_create_new_partner()
        wizard.action_confirm()
        
        self.assertEqual(policy.state, 'draft')
        self.assertEqual(policy.partner_id.name, 'Ste Import Export')
        self.assertEqual(policy.partner_id.matricule_fiscal, '1234567MAM000')
        self.assertTrue(policy.partner_id.is_company)
