# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO02 — Lot 6 : Identification des quittances — règle générale + OCR
#  Réf. : SPEC_Imputation_Operation_Graphe_Navigation.md (§2.6)
#
#  Cascade RG-QUIT (unique pour tout le système — toutes compagnies) :
#    1. Identifiant compagnie exploitable (n° quittance / contrat + ID,
#       non vide, non générique) → identification directe.
#    2. Sinon, clé métier : compagnie + n° police + dates d'effet + nature
#       + montant prime → rapprochement à score.
#    3. Dans tous les cas : référence interne unique (insurance.operation.ref).
#
#  Le service insurance.receipt.matcher est LE point d'entrée commun :
#  saisie manuelle, import bordereaux, pipeline OCR (document parser).
# ==============================================================================

from odoo import api, fields, models, _

GENERIC_PARAM = 'assurcore.generic_quittance_values'
GENERIC_DEFAULT = 'NF,INST,DIVERS,N/F,NEANT,RAS'


class InsuranceOperationIdent(models.Model):
    _inherit = 'insurance.operation'

    internal_ref = fields.Char(
        string='Référence interne',
        readonly=True, copy=False, index=True,
        help='Identifiant technique unique AssurCore (OP-AAAA-NNNNNN). '
             'Sert aux liens techniques ; le n° de quittance compagnie '
             'n\'est jamais une clé.',
    )

    ident_mode = fields.Selection(
        [('quittance', 'Identifiant compagnie'),
         ('cle_metier', 'Clé métier')],
        string='Mode d\'identification',
        compute='_compute_ident_mode', store=True, index=True,
        help='Trace si l\'opération est identifiable par son n° de quittance '
             'compagnie ou seulement par ses données métier (police, dates, '
             'nature, montant).',
    )

    _sql_constraints = [
        ('internal_ref_uniq', 'unique(internal_ref)',
         'La référence interne d\'opération doit être unique.'),
    ]

    @api.depends('num_quittance', 'num_police')
    def _compute_ident_mode(self):
        matcher = self.env['insurance.receipt.matcher']
        for rec in self:
            rec.ident_mode = (
                'quittance'
                if matcher.is_identifier_usable(rec.num_quittance, rec.num_police)
                else 'cle_metier'
            )

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        if not rec.internal_ref:
            rec.internal_ref = (
                self.env['ir.sequence'].next_by_code('insurance.operation.ref')
            )
        return rec


class InsuranceReceiptMatcher(models.AbstractModel):
    """Service de rapprochement unique (RG-QUIT).

    Usage :
        result = env['insurance.receipt.matcher'].match(
            company_ins_id=…,                # ID insurance.company
            identifiers={'num_quittance': …, 'num_police': …},
            business_key={'num_police': …, 'date_validite_du': …,
                          'date_validite_au': …, 'nature': …,
                          'montant_prime': …},
        )
        → {'score': 'exact'|'approchant'|'aucun',
           'operation': recordset (1 si exact),
           'candidates': recordset (si approchant),
           'mode': 'quittance'|'cle_metier'}
    """

    _name = 'insurance.receipt.matcher'
    _description = 'Service de rapprochement quittance/opération (RG-QUIT)'

    AMOUNT_TOLERANCE = 0.005  # TND

    # ── Étape 0 : identifiant exploitable ? ────────────────────────────────────

    @api.model
    def _generic_values(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            GENERIC_PARAM, GENERIC_DEFAULT)
        return {v.strip().upper() for v in raw.split(',') if v.strip()}

    @api.model
    def is_identifier_usable(self, num_quittance, num_police=None):
        """Vrai si le n° de quittance compagnie est exploitable comme clé :
        non vide, non générique, différent du n° de police recopié."""
        val = (num_quittance or '').strip().upper()
        if not val or val in ('0', '00'):
            return False
        if val in self._generic_values():
            return False
        if num_police and val == (num_police or '').strip().upper():
            return False  # n° de police recopié en guise de quittance
        return True

    # ── Cascade de rapprochement ───────────────────────────────────────────────

    @api.model
    def match(self, company_ins_id=False, identifiers=None, business_key=None):
        identifiers = identifiers or {}
        business_key = business_key or {}
        Operation = self.env['insurance.operation']

        num_q = identifiers.get('num_quittance')
        num_p = identifiers.get('num_police') or business_key.get('num_police')

        # 1) Identifiant compagnie exploitable → recherche directe
        if self.is_identifier_usable(num_q, num_p):
            domain = [('num_quittance', '=', num_q.strip())]
            if company_ins_id:
                domain.append(('company_ins_id', '=', company_ins_id))
            found = Operation.search(domain)
            if len(found) == 1:
                return {'score': 'exact', 'operation': found,
                        'candidates': found, 'mode': 'quittance'}
            if len(found) > 1 and num_p:
                refined = found.filtered(
                    lambda o: (o.num_police or '').strip() == num_p.strip())
                if len(refined) == 1:
                    return {'score': 'exact', 'operation': refined,
                            'candidates': refined, 'mode': 'quittance'}
                if refined:
                    return {'score': 'approchant', 'operation': Operation,
                            'candidates': refined, 'mode': 'quittance'}
            if found:
                return {'score': 'approchant', 'operation': Operation,
                        'candidates': found, 'mode': 'quittance'}
            # identifiant exploitable mais introuvable → on tente la clé métier

        # 2) Clé métier : police obligatoire, puis resserrage progressif
        if not num_p:
            return {'score': 'aucun', 'operation': Operation,
                    'candidates': Operation, 'mode': 'cle_metier'}

        domain = [('num_police', '=', num_p.strip())]
        if company_ins_id:
            domain.append(('company_ins_id', '=', company_ins_id))
        base = Operation.search(domain)
        if not base:
            return {'score': 'aucun', 'operation': Operation,
                    'candidates': Operation, 'mode': 'cle_metier'}

        candidates = base

        d_du = business_key.get('date_validite_du')
        d_au = business_key.get('date_validite_au')
        if d_du:
            exact_dates = candidates.filtered(
                lambda o: o.date_validite_du
                and fields.Date.to_date(d_du) == o.date_validite_du)
            if exact_dates:
                candidates = exact_dates
        if d_au:
            exact_fin = candidates.filtered(
                lambda o: o.date_validite_au
                and fields.Date.to_date(d_au) == o.date_validite_au)
            if exact_fin:
                candidates = exact_fin

        nature = business_key.get('nature')
        if nature:
            same_nature = candidates.filtered(lambda o: o.nature == nature)
            if same_nature:
                candidates = same_nature

        montant = business_key.get('montant_prime')
        montant_filter_applied = False
        if montant:
            same_amount = candidates.filtered(
                lambda o: abs((o.montant_prime or 0.0) - float(montant))
                <= self.AMOUNT_TOLERANCE)
            if same_amount:
                candidates = same_amount
                montant_filter_applied = True

        # Score : exact si candidat unique avec dates + montant confirmés
        if (len(candidates) == 1 and montant_filter_applied
                and (d_du or d_au)):
            return {'score': 'exact', 'operation': candidates,
                    'candidates': candidates, 'mode': 'cle_metier'}
        if candidates:
            return {'score': 'approchant', 'operation': Operation,
                    'candidates': candidates[:10], 'mode': 'cle_metier'}
        return {'score': 'aucun', 'operation': Operation,
                'candidates': Operation, 'mode': 'cle_metier'}


class InsuranceDocumentParserMatcher(models.Model):
    """Branchement OCR : le parseur de documents appelle le service unique.

    Les gabarits d'extraction par compagnie doivent alimenter au minimum :
    compagnie, n° quittance (si présent), n° police, dates d'effet,
    nature, montant prime — puis appeler action_match_operation().
    """

    _inherit = 'insurance.document.parser'

    matched_operation_id = fields.Many2one(
        comodel_name='insurance.operation',
        string='Opération rapprochée',
        readonly=True, copy=False,
        help='Opération identifiée par le service de rapprochement RG-QUIT.',
    )
    match_score = fields.Selection(
        [('exact', 'Exact'), ('approchant', 'Approchant'), ('aucun', 'Aucun')],
        string='Score de rapprochement', readonly=True, copy=False,
    )
    match_candidate_ids = fields.Many2many(
        comodel_name='insurance.operation',
        relation='evo02_parser_match_candidate_rel',
        string='Candidats au rapprochement', readonly=True, copy=False,
    )

    def action_match_operation(self, identifiers=None, business_key=None):
        """Appelle le matcher avec les données extraites du document.

        Les wizards OCR fournissent identifiers/business_key extraits ;
        à défaut, on tente avec les liens déjà connus du parseur (police).
        """
        self.ensure_one()
        identifiers = identifiers or {}
        business_key = business_key or {}

        if not business_key.get('num_police') and self.policy_id:
            business_key['num_police'] = self.policy_id.num_police
        company_id = (self.company_ins_id.id
                      if getattr(self, 'company_ins_id', False) else False)

        result = self.env['insurance.receipt.matcher'].match(
            company_ins_id=company_id,
            identifiers=identifiers,
            business_key=business_key,
        )
        self.write({
            'matched_operation_id': result['operation'].id or False,
            'match_score': result['score'],
            'match_candidate_ids': [(6, 0, result['candidates'].ids)],
        })

        # Document toujours rattaché : à l'opération si exact,
        # sinon anomalie QUITTANCE_GENERIQUE si aucun candidat.
        if result['score'] == 'exact' and result['operation']:
            self.env['ir.attachment'].search([
                ('res_model', '=', self._name), ('res_id', '=', self.id),
            ]).copy({'res_model': 'insurance.operation',
                     'res_id': result['operation'].id})
        elif result['score'] == 'aucun' and hasattr(self, 'add_anomaly'):
            pass  # le parseur n'a pas le mixin santé ; l'anomalie est portée
                  # par l'opération créée en aval par le wizard OCR.
        return result
