# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase
from datetime import date, timedelta

class TestInsuranceSettlement(TransactionCase):

    def setUp(self):
        super(TestInsuranceSettlement, self).setUp()
        self.Partner = self.env['res.partner']
        self.Company = self.env['insurance.company']
        self.Policy = self.env['insurance.policy']
        self.Receipt = self.env['insurance.receipt']
        self.Settlement = self.env['insurance.settlement']
        
        self.father = self.Partner.create({'name': 'Father Payer', 'is_payer': True})
        self.son = self.Partner.create({'name': 'Son Member', 'payer_partner_id': self.father.id})
        
        self.comp = self.Company.search([('name', '=', 'STAR')], limit=1)
        if not self.comp:
            self.comp = self.Company.create({'name': 'STAR', 'code': 'STAR'})
            
        # Policy for father
        self.pol_father = self.Policy.create({
            'num_police': 'POL-F-' + str(fields.Datetime.now()),
            'partner_id': self.father.id,
            'company_ins_id': self.comp.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
            'prime_nette': 1000.0,
        })
        
        # Policy for son
        self.pol_son = self.Policy.create({
            'num_police': 'POL-S-' + str(fields.Datetime.now()),
            'partner_id': self.son.id,
            'company_ins_id': self.comp.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
            'prime_nette': 500.0,
        })
        
        # Create receipts
        self.rec_father = self.Receipt.create({
            'policy_id': self.pol_father.id,
            'date_emission': date.today(),
            'date_echeance': date.today() + timedelta(days=30),
            'montant_prime': 1000.0,
        })
        self.rec_son = self.Receipt.create({
            'policy_id': self.pol_son.id,
            'date_emission': date.today(),
            'date_echeance': date.today() + timedelta(days=30),
            'montant_prime': 500.0,
        })

    def test_01_simple_settlement(self):
        """Règlement simple d'une quittance."""
        settlement = self.Settlement.create({
            'receipt_id': self.rec_father.id,
            'partner_id': self.father.id,
            'montant_reg': 1107.60, # TTC calculé
            'type_reg': 'C',
            'num_cheque': '123456',
        })
        
        self.assertEqual(settlement.state, 'brouillon')
        self.assertEqual(self.rec_father.amount_paid, 0.0)
        
        settlement.action_confirmer()
        self.assertEqual(settlement.state, 'regle')
        self.rec_father.action_encaisser()
        self.assertAlmostEqual(self.rec_father.amount_paid, 1107.60, places=2)
        self.assertEqual(self.rec_father.state, 'encaissee')

    def test_02_cheque_rejection(self):
        """Test du rejet de chèque."""
        settlement = self.Settlement.create({
            'receipt_id': self.rec_father.id,
            'partner_id': self.father.id,
            'montant_reg': 1107.60,
            'state': 'regle',
        })
        self.rec_father._compute_amounts()
        self.assertAlmostEqual(self.rec_father.amount_paid, 1107.60, places=2)
        
        # Rejet
        settlement.action_rejeter()
        self.assertEqual(settlement.state, 'impaye')
        self.rec_father._compute_amounts()
        self.assertEqual(self.rec_father.amount_paid, 0.0)
        self.assertEqual(self.rec_father.state, 'emise')

    def test_03_multi_receipt_family(self):
        """Cas famille : Un chèque règle deux quittances (père + fils)."""
        # Dans ce modèle, un settlement est lié à UN receipt_id.
        # Pour simuler le cas famille d'un seul chèque, on peut imaginer :
        # 1. Soit deux lignes de settlement avec même num_cheque (vendu comme ventilation).
        # 2. Soit une quittance consolidée (non implémenté ici).
        # Ici on va créer deux settlements du même payeur (père).
        
        sett_father = self.Settlement.create({
            'receipt_id': self.rec_father.id,
            'partner_id': self.father.id,
            'montant_reg': self.rec_father.amount_total,
            'num_cheque': 'CHQ-FAM-001',
        })
        sett_son = self.Settlement.create({
            'receipt_id': self.rec_son.id,
            'partner_id': self.father.id, # C'est le père qui paye pour le fils
            'montant_reg': self.rec_son.amount_total,
            'num_cheque': 'CHQ-FAM-001',
        })
        
        sett_father.action_confirmer()
        sett_son.action_confirmer()
        
        self.rec_father.action_encaisser()
        self.rec_son.action_encaisser()
        
        self.assertEqual(self.rec_father.state, 'encaissee')
        self.assertEqual(self.rec_son.state, 'encaissee')
        self.assertEqual(self.rec_son.payer_id, self.father)
