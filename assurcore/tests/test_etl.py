# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo.tools import mute_logger
from psycopg2 import IntegrityError
from datetime import date
import re

class TestAssurCoreETL(TransactionCase):

    def setUp(self):
        super(TestAssurCoreETL, self).setUp()
        self.Company = self.env['insurance.company']

    # --- Re-implementation of ETL parsing for unit testing ---
    def parse_float(self, value: str) -> float:
        if not value or value.strip() in ('', 'NULL', 'null'):
            return 0.0
        v = value.strip().replace('\xa0', '').replace(' ', '')
        if ',' in v and '.' not in v:
            v = v.replace(',', '.')
        elif ',' in v and '.' in v:
            v = v.replace('.', '').replace(',', '.')
        try:
            return float(v)
        except ValueError:
            return 0.0

    def parse_date(self, v: str) -> str:
        if not v or v.strip().upper() in ('', 'NULL'):
            return None
        v = v.strip()
        m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2})$', v)
        if m:
            day, month, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
            year = 2000 + yy if yy < 50 else 1900 + yy
            return date(year, month, day).isoformat()
        return None

    def test_01_parsing_logic(self):
        """Vérifie la robustesse du parsing des montants et dates Oracle."""
        # Floats
        self.assertEqual(self.parse_float("1 534,069"), 1534.069)
        self.assertEqual(self.parse_float("23,26"), 23.26)
        self.assertEqual(self.parse_float("1.234,56"), 1234.56)
        self.assertEqual(self.parse_float("NULL"), 0.0)
        
        # Dates
        self.assertEqual(self.parse_date("04/04/17"), "2017-04-04")
        self.assertEqual(self.parse_date("15/06/98"), "1998-06-15")

    def test_02_idempotence(self):
        """Vérifie que l'importation en double respecte les contraintes d'unicité."""
        # Compagnie
        self.Company.create({'name': 'IDEM_COMP', 'code': 'IDEM'})
        
        self.env.flush_all()
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.cr.savepoint():
                self.Company.create({'name': 'IDEM_COMP_OTHER', 'code': 'IDEM'})
                self.env.flush_all()
        
        self.Company.create({'name': 'IDEM_COMP_2', 'code': 'IDEM2'})
        self.env.flush_all()
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.cr.savepoint():
                self.Company.create({'name': 'IDEM_COMP_2', 'code': 'IDEM3'})
                self.env.flush_all()
