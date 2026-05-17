# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase
from datetime import date, timedelta

class TestReceiptLogic(TransactionCase):

    def setUp(self):
        super(TestReceiptLogic, self).setUp()
        self.Partner = self.env['res.partner']
        self.Company = self.env['insurance.company']
        self.Policy = self.env['insurance.policy']
        self.Receipt = self.env['insurance.receipt']
        
        self.partner = self.Partner.create({'name': 'Test Client Receipt ' + str(fields.Datetime.now())})
        self.company = self.Company.search([('name', '=', 'STAR')], limit=1)
        if not self.company:
            self.company = self.Company.create({'name': 'STAR', 'code': 'STAR'})
        self.policy = self.Policy.create({
            'num_police': 'POL-TEST-001-R-' + str(fields.Datetime.now()),
            'partner_id': self.partner.id,
            'company_ins_id': self.company.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
        })

    def test_01_receipt_calculation(self):
        """Vérification de la formule de calcul TTC tunisienne."""
        # Prime: 1000, Honoraire: 100, TVA: 7%, Timbre: 0.600
        receipt = self.Receipt.create({
            'policy_id': self.policy.id,
            'date_emission': date.today(),
            'date_echeance': date.today() + timedelta(days=30),
            'montant_prime': 1000.0,
            'montant_honoraire_ht': 100.0,
            'taux_tva': 7.0,
            'timbre_fiscal': 0.600,
        })
        
        # Attendu: 1000 + 100 + (100 * 0.07) + 0.600 = 1107.600
        self.assertAlmostEqual(receipt.montant_tva, 7.0, places=3)
        self.assertAlmostEqual(receipt.amount_total, 1107.600, places=3)
        self.assertAlmostEqual(receipt.amount_residual, 1107.600, places=3)

    def test_02_overdue_severity(self):
        """Test du calcul automatique du retard et de la sévérité."""
        # Création d'une quittance échue il y a 45 jours
        receipt = self.Receipt.create({
            'policy_id': self.policy.id,
            'date_emission': date.today() - timedelta(days=100),
            'date_echeance': date.today() - timedelta(days=45),
            'montant_prime': 500.0,
            'state': 'emise',
        })
        
        # Selon les constantes (généralement 30 et 60)
        self.assertTrue(receipt.is_overdue)
        self.assertEqual(receipt.jours_retard, 45)
        # 45 > 30 (Moderate) mais < 60 (Severe)
        self.assertEqual(receipt.overdue_severity, 'moderate')
        
        # Passage à 65 jours
        receipt.date_echeance = date.today() - timedelta(days=65)
        self.assertEqual(receipt.overdue_severity, 'severe')
