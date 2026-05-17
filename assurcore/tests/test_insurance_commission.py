# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import timedelta

class TestInsuranceCommission(TransactionCase):

    def setUp(self):
        super(TestInsuranceCommission, self).setUp()
        self.CommissionRule = self.env['insurance.commission.rule']
        # Nettoyage des règles existantes pour garantir l'isolation complète des tests
        self.CommissionRule.search([]).unlink()
        self.Company = self.env['insurance.company']
        self.Policy = self.env['insurance.policy']
        self.Partner = self.env['res.partner']
        
        # Setup test data
        self.comp_star = self.Company.search([('name', '=', 'STAR')], limit=1)
        if not self.comp_star:
            self.comp_star = self.Company.create({'name': 'STAR', 'code': 'STAR'})
            
        self.comp_gat = self.Company.search([('name', '=', 'GAT')], limit=1)
        if not self.comp_gat:
            self.comp_gat = self.Company.create({'name': 'GAT', 'code': 'GAT'})
            
        self.partner = self.Partner.create({'name': 'Test Commission Partner'})

    def test_01_resolution_logic(self):
        """Test de la cascade de résolution des commissions."""
        
        # 1. Règle Globale (7%)
        self.CommissionRule.create({
            'taux_commission': 7.0,
            'priorite': 10,
        })
        
        # 2. Règle par Branche (MRH -> 8%)
        self.CommissionRule.create({
            'branche': 'MRH',
            'taux_commission': 8.0,
            'priorite': 20,
        })
        
        # 3. Règle par Compagnie (STAR -> 9%)
        self.CommissionRule.create({
            'company_ins_id': self.comp_star.id,
            'taux_commission': 9.0,
            'priorite': 30,
        })
        
        # 4. Règle Spécifique (STAR + AUTO -> 12%)
        self.CommissionRule.create({
            'company_ins_id': self.comp_star.id,
            'branche': 'AUTO',
            'taux_commission': 12.0,
            'priorite': 100,
        })

        # Vérifications
        # STAR + AUTO -> 12%
        res = self.CommissionRule.get_commission_rate(self.comp_star.id, 'AUTO')
        self.assertEqual(res['taux_commission'], 12.0)
        
        # STAR + SANTE (pas de règle spécifique) -> 9% (Compagnie STAR)
        res = self.CommissionRule.get_commission_rate(self.comp_star.id, 'SANTE')
        self.assertEqual(res['taux_commission'], 9.0)
        
        # GAT + MRH -> 8% (Branche MRH)
        res = self.CommissionRule.get_commission_rate(self.comp_gat.id, 'MRH')
        self.assertEqual(res['taux_commission'], 8.0)
        
        # GAT + SANTE -> 7% (Globale)
        res = self.CommissionRule.get_commission_rate(self.comp_gat.id, 'SANTE')
        self.assertEqual(res['taux_commission'], 7.0)

    def test_02_policy_auto_fill(self):
        """Vérifie que la police se remplit automatiquement lors du onchange."""
        self.CommissionRule.create({
            'company_ins_id': self.comp_star.id,
            'branche': 'AUTO',
            'taux_commission': 10.0,
        })
        
        policy = self.Policy.new({
            'partner_id': self.partner.id,
            'company_ins_id': self.comp_star.id,
            'branche': 'AUTO',
            'prime_nette': 1000.0,
            'date_effect': fields.Date.today(),
            'date_echeance': fields.Date.today(),
        })
        
        # Trigger onchange
        policy._onchange_compute_commission()
        
        self.assertEqual(policy.commission, 100.0)
        self.assertEqual(policy.taux_commission, 10.0)

    def test_03_date_validity(self):
        """Test de la validité temporelle des règles."""
        today = fields.Date.today()
        
        # Règle passée (10%)
        self.CommissionRule.create({
            'company_ins_id': self.comp_star.id,
            'taux_commission': 10.0,
            'date_debut': today - timedelta(days=100),
            'date_fin': today - timedelta(days=1),
        })
        
        # Règle actuelle (15%)
        self.CommissionRule.create({
            'company_ins_id': self.comp_star.id,
            'taux_commission': 15.0,
            'date_debut': today,
        })
        
        res = self.CommissionRule.get_commission_rate(self.comp_star.id, 'AUTO', date=today)
        self.assertEqual(res['taux_commission'], 15.0)
        
        res_past = self.CommissionRule.get_commission_rate(self.comp_star.id, 'AUTO', date=today - timedelta(days=10))
        self.assertEqual(res_past['taux_commission'], 10.0)
