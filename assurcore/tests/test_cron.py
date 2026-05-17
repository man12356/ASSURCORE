# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase
from datetime import date, timedelta

class TestAssurCoreCron(TransactionCase):

    def setUp(self):
        super(TestAssurCoreCron, self).setUp()
        self.Partner = self.env['res.partner']
        self.Policy = self.env['insurance.policy']
        self.Receipt = self.env['insurance.receipt']
        self.Company = self.env['insurance.company']
        
        self.comp = self.Company.search([('name', '=', 'STAR')], limit=1)
        if not self.comp:
            self.comp = self.Company.create({'name': 'STAR', 'code': 'STAR'})
        self.partner = self.Partner.create({'name': 'Cron Test Partner'})

    def test_01_policy_cron(self):
        """Test du cron de mise à jour des polices (expiration et relance)."""
        today = fields.Date.today()
        
        # 1. Police expirée
        p_expired = self.Policy.create({
            'num_police': 'POL-EXP-' + str(fields.Datetime.now()),
            'partner_id': self.partner.id,
            'company_ins_id': self.comp.id,
            'branche': 'AUTO',
            'date_effect': today - timedelta(days=400),
            'date_echeance': today - timedelta(days=1),
            'state': 'active',
        })
        
        # 2. Police proche échéance (Relance J-30)
        p_renew = self.Policy.create({
            'num_police': 'POL-REN-' + str(fields.Datetime.now()),
            'partner_id': self.partner.id,
            'company_ins_id': self.comp.id,
            'branche': 'AUTO',
            'date_effect': today - timedelta(days=335),
            'date_echeance': today + timedelta(days=15),
            'state': 'active',
        })
        
        self.env.flush_all()
        self.env.invalidate_all()
        self.Policy._cron_check_policy_states()
        
        self.assertEqual(p_expired.state, 'expired')
        
        # Vérifier création activité sur p_renew
        activities = self.env['mail.activity'].search([
            ('res_id', '=', p_renew.id),
            ('res_model', '=', 'insurance.policy')
        ])
        self.assertTrue(activities)
        self.assertIn('Relance renouvellement', activities[0].summary)

    def test_02_receipt_overdue_cron(self):
        """Test du cron de passage en contentieux automatique."""
        # Seuil par défaut = 90 jours (configuré sur res.company)
        self.env.company.seuil_contentieux_jours = 90
        
        policy = self.Policy.create({
            'num_police': 'POL-REC-' + str(fields.Datetime.now()),
            'partner_id': self.partner.id,
            'company_ins_id': self.comp.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
        })
        
        # Quittance en retard de 100 jours
        receipt = self.Receipt.create({
            'policy_id': policy.id,
            'date_emission': date.today() - timedelta(days=150),
            'date_echeance': date.today() - timedelta(days=100),
            'state': 'emise',
            'montant_prime': 100.0,
        })
        
        self.Receipt._cron_update_overdue_receipts()
        
        self.assertEqual(receipt.state, 'contentieux')
