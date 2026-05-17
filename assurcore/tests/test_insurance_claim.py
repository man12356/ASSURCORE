# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta

class TestInsuranceClaim(TransactionCase):

    def setUp(self):
        super(TestInsuranceClaim, self).setUp()
        self.Partner = self.env['res.partner']
        self.Company = self.env['insurance.company']
        self.Policy = self.env['insurance.policy']
        self.Claim = self.env['insurance.claim']
        
        self.partner = self.Partner.create({'name': 'Claimant Partner'})
        self.comp = self.Company.search([('name', '=', 'STAR')], limit=1)
        if not self.comp:
            self.comp = self.Company.create({'name': 'STAR', 'code': 'STAR'})
            
        self.policy = self.Policy.create({
            'num_police': 'POL-CLAIM-' + str(fields.Datetime.now()),
            'partner_id': self.partner.id,
            'company_ins_id': self.comp.id,
            'branche': 'AUTO',
            'date_effect': date.today() - timedelta(days=365),
            'date_echeance': date.today() + timedelta(days=30),
            'state': 'active',
        })

    def test_01_claim_lifecycle(self):
        """Test complet du workflow d'un sinistre."""
        claim = self.Claim.create({
            'policy_id': self.policy.id,
            'date_sinistre': datetime.now(),
            'lib_sinistre': 'Accident parking',
            'montant_reclame': 2000.0,
        })
        
        self.assertEqual(claim.state, 'declare')
        self.assertEqual(claim.event_count, 1) # Déclaration auto
        
        # 1. Transmission
        claim.action_transmettre()
        self.assertEqual(claim.state, 'transmis')
        
        # 2. Expertise
        claim.action_expertise()
        self.assertEqual(claim.state, 'expertise')
        
        # 3. Indemnisation
        with self.assertRaises(UserError): # Pas de montant
            claim.action_indemnisation()
            
        claim.montant_indemnite = 1500.0
        claim.franchise = 200.0
        claim.action_indemnisation()
        self.assertEqual(claim.state, 'indemnisation')
        self.assertEqual(claim.montant_indemnite_net, 1300.0)
        
        # 4. Règlement
        claim.action_regler()
        self.assertEqual(claim.state, 'regle')
        
        # 5. Clôture
        claim.action_clore()
        self.assertEqual(claim.state, 'clos')

    def test_02_indemnite_net_calc(self):
        """Vérifie le calcul de l'indemnité nette avec franchise."""
        claim = self.Claim.create({
            'policy_id': self.policy.id,
            'date_sinistre': datetime.now(),
            'montant_indemnite': 1000.0,
            'franchise': 300.0,
        })
        self.assertEqual(claim.montant_indemnite_net, 700.0)
        
        # Franchise > Indemnité
        claim.franchise = 1200.0
        self.assertEqual(claim.montant_indemnite_net, 0.0)

    def test_03_claim_annee(self):
        """Vérifie le calcul de l'année du sinistre."""
        dt = datetime(2023, 5, 15, 10, 0, 0)
        claim = self.Claim.create({
            'policy_id': self.policy.id,
            'date_sinistre': dt,
        })
        self.assertEqual(claim.annee_sinistre, 2023)
