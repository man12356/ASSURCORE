# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError
from odoo import fields
from datetime import timedelta

class TestAssurCoreSecurity(TransactionCase):

    def setUp(self):
        super(TestAssurCoreSecurity, self).setUp()
        self.Partner = self.env['res.partner']
        self.CommissionRule = self.env['insurance.commission.rule']
        self.Policy = self.env['insurance.policy']
        
        # Create users
        self.group_agent = self.env.ref('assurcore.group_assurcore_agent')
        self.group_manager = self.env.ref('assurcore.group_assurcore_manager')
        
        self.user_agent = self.env['res.users'].create({
            'name': 'Test Agent',
            'login': 'test_agent',
            'email': 'agent@test.com',
            'groups_id': [(4, self.group_agent.id)],
        })
        
        self.user_manager = self.env['res.users'].create({
            'name': 'Test Manager',
            'login': 'test_manager',
            'email': 'manager@test.com',
            'groups_id': [(4, self.group_manager.id)],
        })

    def test_01_commission_rule_access(self):
        """Vérifie que l'agent ne peut pas modifier la grille de commission."""
        rule = self.CommissionRule.create({'taux_commission': 10.0})
        
        # Agent peut lire
        rule.with_user(self.user_agent).read(['taux_commission'])
        
        # Agent ne peut pas créer
        with self.assertRaises(AccessError):
            self.CommissionRule.with_user(self.user_agent).create({'taux_commission': 15.0})
            
        # Agent ne peut pas modifier
        with self.assertRaises(AccessError):
            rule.with_user(self.user_agent).write({'taux_commission': 20.0})
            
        # Manager peut tout faire
        rule_mgr = self.CommissionRule.with_user(self.user_manager).create({'taux_commission': 25.0})
        rule_mgr.write({'taux_commission': 30.0})

    def test_02_policy_deletion_restriction(self):
        """Vérifie que l'agent ne peut pas supprimer une police."""
        partner = self.Partner.create({'name': 'Test Partner'})
        comp = self.env['insurance.company'].create({'name': 'TEST COMP', 'code': 'TC'})
        
        policy = self.Policy.create({
            'num_police': 'POL-SEC-001',
            'partner_id': partner.id,
            'company_ins_id': comp.id,
            'branche': 'AUTO',
            'date_effect': fields.Date.today(),
            'date_echeance': fields.Date.today() + timedelta(days=1),
        })
        
        # Agent peut modifier
        policy.with_user(self.user_agent).write({'risque': 'Peugeot 208'})
        
        # Agent ne peut pas supprimer
        with self.assertRaises(AccessError):
            policy.with_user(self.user_agent).unlink()
            
        # Manager peut supprimer
        policy.with_user(self.user_manager).unlink()
