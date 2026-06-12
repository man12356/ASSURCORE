# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO02 — Tests unitaires (critères d'acceptation spec §6)
#  Lancement : odoo-bin -d <db> -u assurcore --test-tags /assurcore:TestEvo02
# ==============================================================================

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install', 'evo02')
class TestEvo02(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Client Test EVO02'})
        cls.payer = cls.env['res.partner'].create({'name': 'Payeur Tiers EVO02'})
        cls.company_ins = cls.env['insurance.company'].create(
            {'name': 'COMPAGNIE TEST'})
        cls.policy = cls.env['insurance.policy'].create({
            'partner_id': cls.partner.id,
            'company_ins_id': cls.company_ins.id,
            'num_police': 'POL-TEST-001',
            'branche': 'AUTO',
            'date_effect': '2026-01-01',
            'date_echeance': '2026-12-31',
        })

    def _make_operation(self, prime=1000.0, quittance='Q-12345'):
        op = self.env['insurance.operation'].create({
            'policy_id': self.policy.id,
            'partner_id': self.partner.id,
            'company_ins_id': self.company_ins.id,
            'code_operation': 'EMI',
            'num_police': 'POL-TEST-001',
            'num_quittance': quittance,
            'montant_prime': prime,
            'date_validite_du': '2026-01-01',
            'date_validite_au': '2026-12-31',
            'state': 'confirmed',
        })
        op.action_generate_receipt()
        return op

    def _make_settlement(self, amount, partner=None):
        return self.env['insurance.settlement'].create({
            'partner_id': (partner or self.partner).id,
            'montant_reg': amount,
            'type_reg': 'C',
            'state': 'regle',
        })

    def _impute(self, settlement, receipt, amount, **vals):
        vals.update({
            'settlement_id': settlement.id,
            'receipt_id': receipt.id,
            'montant_impute': amount,
        })
        return self.env['insurance.settlement.imputation'].create(vals)

    # ── Lot 1 : contraintes ────────────────────────────────────────────────────

    def test_01_internal_ref_and_ident_mode(self):
        """Critère 8 : référence interne unique + ident_mode tracé."""
        op = self._make_operation(quittance='Q-77777')
        self.assertTrue(op.internal_ref and op.internal_ref.startswith('OP-'))
        self.assertEqual(op.ident_mode, 'quittance')
        op_nf = self._make_operation(quittance='NF')
        self.assertEqual(op_nf.ident_mode, 'cle_metier')
        op_police = self._make_operation(quittance='POL-TEST-001')
        self.assertEqual(op_police.ident_mode, 'cle_metier',
                         'N° de police recopié = identifiant non exploitable')

    def test_02_c2_overpayment_refused(self):
        """Critère 1 / C2 : sur-règlement d'une quittance refusé."""
        op = self._make_operation(prime=100.0)
        # amount_total inclut le timbre fiscal : le règlement doit le couvrir
        s1 = self._make_settlement(op.receipt_id.amount_total)
        self._impute(s1, op.receipt_id, op.receipt_id.amount_total)
        s2 = self._make_settlement(100.0)
        with self.assertRaises(ValidationError):
            self._impute(s2, op.receipt_id, 50.0)

    def test_03_c2_skipped_for_reconstructed(self):
        """L'historique migré (is_reconstructed) n'est pas bloqué."""
        op = self._make_operation(prime=100.0)
        s1 = self._make_settlement(500.0)
        total = op.receipt_id.amount_total
        self._impute(s1, op.receipt_id, total, is_reconstructed=True)
        line = self._impute(s1, op.receipt_id, total, is_reconstructed=True)
        self.assertTrue(line.exists(), 'Sur-règlement migré accepté avec flag')

    def test_04_c3_canceled_operation_refused(self):
        """C3 : pas d'imputation si l'opération est annulée."""
        op = self._make_operation(prime=100.0)
        op.write({'state': 'canceled'})
        s = self._make_settlement(50.0)
        with self.assertRaises(ValidationError):
            self._impute(s, op.receipt_id, 10.0)

    def test_05_duplicate_line_refused(self):
        op = self._make_operation(prime=200.0)
        s = self._make_settlement(300.0)
        self._impute(s, op.receipt_id, 50.0)
        with self.assertRaises(ValidationError):
            self._impute(s, op.receipt_id, 30.0)

    def test_06_third_party_flag_and_wizard(self):
        """Critère 2 : paiement pour tiers détecté + confirmation requise."""
        op = self._make_operation(prime=100.0)
        s = self._make_settlement(100.0, partner=self.payer)
        line = self._impute(s, op.receipt_id, 50.0)
        self.assertTrue(line.is_third_party)
        wiz = self.env['insurance.imputation.wizard'].with_context(
            active_id=op.receipt_id.id).create({
                'receipt_id': op.receipt_id.id,
                'settlement_id': s.id,
                'montant_a_imputer': 10.0,
            })
        self.assertTrue(wiz.is_third_party)
        with self.assertRaises(UserError):
            wiz.action_confirmer_imputation()
        wiz.confirm_third_party = True
        wiz.action_confirmer_imputation()  # ne doit plus lever

    def test_07_settlement_state_lifecycle(self):
        """§2.4 : non_facturee → non_reglee → partielle → soldee."""
        op = self.env['insurance.operation'].create({
            'policy_id': self.policy.id,
            'partner_id': self.partner.id,
            'company_ins_id': self.company_ins.id,
            'code_operation': 'EMI',
            'num_quittance': 'Q-CYCLE',
            'montant_prime': 100.0,
            'date_validite_du': '2026-01-01',
            'date_validite_au': '2026-12-31',
            'state': 'confirmed',
        })
        self.assertEqual(op.settlement_state, 'non_facturee')
        op.action_generate_receipt()
        op.invalidate_recordset()
        self.assertEqual(op.settlement_state, 'non_reglee')
        s = self._make_settlement(1000.0)
        self._impute(s, op.receipt_id, op.receipt_id.amount_total / 2)
        op.invalidate_recordset()
        self.assertEqual(op.settlement_state, 'partielle')
        self._impute(
            self._make_settlement(1000.0), op.receipt_id,
            op.receipt_id.amount_residual)
        op.invalidate_recordset()
        self.assertEqual(op.settlement_state, 'soldee')

    # ── Lot 5 : santé ─────────────────────────────────────────────────────────

    def test_08_health_lifecycle(self):
        """Critère 7 : anomalie → état rouge ; justification → motif requis."""
        op = self._make_operation()
        self.assertEqual(op.health_state, 'ok')
        anomaly = op.add_anomaly(
            'SUR_REGLEMENT', detail='Test : lettré 200 pour un dû de 100',
            origin='migration', oracle_ref='REG-7966')
        self.assertEqual(op.health_state, 'anomalie')
        self.assertIn('SUR_REGLEMENT', op.anomaly_note)
        with self.assertRaises(UserError):
            anomaly.action_justify()  # motif obligatoire
        anomaly.resolution_note = 'Validé en comité du 11/06/2026'
        anomaly.action_justify()
        self.assertEqual(op.health_state, 'ok')

    # ── Lot 6 : matcher ───────────────────────────────────────────────────────

    def test_09_matcher_cascade(self):
        """Critères 8-9 : identifiant exploitable → direct ; générique → clé métier."""
        matcher = self.env['insurance.receipt.matcher']
        op = self._make_operation(prime=333.333, quittance='Q-MATCH-1')

        r = matcher.match(
            company_ins_id=self.company_ins.id,
            identifiers={'num_quittance': 'Q-MATCH-1'})
        self.assertEqual(r['score'], 'exact')
        self.assertEqual(r['operation'], op)
        self.assertEqual(r['mode'], 'quittance')

        op_nf = self._make_operation(prime=555.555, quittance='NF')
        r2 = matcher.match(
            company_ins_id=self.company_ins.id,
            identifiers={'num_quittance': 'NF'},
            business_key={'num_police': 'POL-TEST-001',
                          'montant_prime': 555.555,
                          'date_validite_du': str(op_nf.date_validite_du or ''),
                          })
        self.assertEqual(r2['mode'], 'cle_metier')
        self.assertIn(op_nf, r2['candidates'])

        r3 = matcher.match(identifiers={'num_quittance': 'NF'})
        self.assertEqual(r3['score'], 'aucun')

    def test_10_matcher_same_result_manual_vs_ocr_path(self):
        """Critère 9 : même service ⇒ même candidat quel que soit le canal."""
        matcher = self.env['insurance.receipt.matcher']
        op = self._make_operation(prime=777.0, quittance='INST')
        key = {'num_police': 'POL-TEST-001', 'montant_prime': 777.0}
        r_manual = matcher.match(company_ins_id=self.company_ins.id,
                                 identifiers={}, business_key=key)
        r_ocr = matcher.match(company_ins_id=self.company_ins.id,
                              identifiers={'num_quittance': 'INST'},
                              business_key=key)
        self.assertEqual(r_manual['candidates'], r_ocr['candidates'])
        self.assertIn(op, r_ocr['candidates'])
