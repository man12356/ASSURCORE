# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta

class TestResPartnerAssurCore(TransactionCase):

    def setUp(self):
        super(TestResPartnerAssurCore, self).setUp()
        self.Partner = self.env['res.partner']
        self.Policy = self.env['insurance.policy']
        self.Company = self.env['insurance.company']
        
        self.comp = self.Company.search([('name', '=', 'STAR')], limit=1)
        if not self.comp:
            self.comp = self.Company.create({'name': 'STAR', 'code': 'STAR'})

    def test_01_family_structure(self):
        """Test de la hiérarchie familiale et des contraintes de payeur."""
        # Création du chef de famille
        father = self.Partner.create({
            'name': 'Father Payer',
            'is_payer': True,
        })
        
        # Création d'un membre
        son = self.Partner.create({
            'name': 'Son Member',
            'payer_partner_id': father.id,
        })
        
        self.assertEqual(son.payer_partner_id, father)
        self.assertIn(son, father.family_member_ids)
        self.assertEqual(father.family_member_count, 1)

        # Contrainte : Payeur ne peut pas avoir lui-même un payeur
        with self.assertRaises(ValidationError):
            mother = self.Partner.create({
                'name': 'Mother Payer',
                'is_payer': True,
                'payer_partner_id': father.id,
            })

    def test_02_solde_consolide(self):
        """Vérifie le calcul du solde consolidé (dette rouge)."""
        father = self.Partner.create({'name': 'Father', 'is_payer': True})
        son = self.Partner.create({'name': 'Son', 'payer_partner_id': father.id})
        
        # Police du père (impayé 100)
        p1 = self.Policy.create({
            'num_police': 'POL-FATHER-' + str(fields.Datetime.now()),
            'partner_id': father.id,
            'company_ins_id': self.comp.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
            'prime_nette': 1000.0,
        })
        # Mocking impayé (car calculé depuis les quittances normalement)
        # Mais dans le modèle, total_impaye est calculé.
        # Pour le test, on va créer une quittance impayée.
        self.env['insurance.receipt'].create({
            'policy_id': p1.id,
            'partner_id': father.id,
            'date_emission': date.today(),
            'date_echeance': date.today() + timedelta(days=30),
            'montant_prime': 100.0,
            'state': 'emise',
        })
        
        # Police du fils (impayé 50)
        p2 = self.Policy.create({
            'num_police': 'POL-SON-' + str(fields.Datetime.now()),
            'partner_id': son.id,
            'company_ins_id': self.comp.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
            'prime_nette': 500.0,
        })
        self.env['insurance.receipt'].create({
            'policy_id': p2.id,
            'partner_id': son.id,
            'date_emission': date.today(),
            'date_echeance': date.today() + timedelta(days=30),
            'montant_prime': 50.0,
            'state': 'emise',
        })

        # Re-calcul des financials de la police (qui trigger le solde partner)
        p1._compute_financials()
        p2._compute_financials()
        
        # Solde consolidé du père doit être -(100 + 50) = -150
        # Note: Dans le code, solde_caisse_consolide est compute et non store.
        self.assertEqual(father.solde_caisse_consolide, -(p1.total_impaye + p2.total_impaye))

    def test_03_client_lifecycle(self):
        """Test du pipeline Prospect -> Actif -> Fidèle."""
        partner = self.Partner.create({'name': 'New Prospect'})
        self.assertEqual(partner.client_state, 'prospect')
        
        # Création d'une police active -> passage en Actif
        policy = self.Policy.create({
            'num_police': 'POL-ACTIF-' + str(fields.Datetime.now()),
            'partner_id': partner.id,
            'company_ins_id': self.comp.id,
            'branche': 'AUTO',
            'date_effect': date.today(),
            'date_echeance': date.today() + timedelta(days=365),
            'state': 'active',
        })
        
        # Déclenchement du cron de mise à jour des états
        self.Partner._cron_update_client_states()
        self.assertEqual(partner.client_state, 'actif')
        
        # Vieillissement artificiel pour test Fidèle (simulé via compute)
        # On ne peut pas modifier date_premiere_police car c'est un compute.
        # On va mocker la date d'effet de la police.
        policy.date_effect = date.today() - timedelta(days=365*6)
        
        # Re-exécution du cron
        self.Partner._cron_update_client_states()
        self.assertEqual(partner.client_state, 'fidele')
