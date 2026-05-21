# -*- coding: utf-8 -*-
# Ordre strict : _name = 'X' doit etre importe AVANT _inherit = 'X'

from . import insurance_company
from . import insurance_branch
from . import insurance_bank
from . import insurance_journal_enc
from . import insurance_risk
from . import res_partner
from . import insurance_policy
from . import insurance_commission_rule
from . import insurance_operation
from . import insurance_receipt
from . import insurance_claim
from . import insurance_mouvement_report
from . import insurance_mouvement_report_wizard
from . import fleet_vehicle
# EVO01 Etape 1 : Parseur OCR + etat draft_ocr sur insurance.policy
from . import insurance_document_parser
# EVO01 Etape 2 : Wizard de validation manuelle du client
from . import insurance_ocr_wizard
