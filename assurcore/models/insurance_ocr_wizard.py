# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO01 — Étape 2 : Wizard de Validation OCR
#  insurance.ocr.wizard (TransientModel)
#
#  Rôle : Interface humaine pour valider les brouillons OCR dont le client
#         n'a pas pu être identifié automatiquement par _create_policy_from_ocr.
#
#  Flux :
#    Police en state='draft_ocr' + partner_id vide + ocr_raw_partner_name rempli
#      → Bouton "Valider brouillon OCR" → Wizard s'ouvre
#        → Opérateur choisit partner_id existant  OU coche create_new_partner
#          → action_confirm() → police liée au bon client → state='draft'
#
#  Règle métier fondamentale (JAMAIS violée) :
#    La création de res.partner est TOUJOURS une décision humaine,
#    validée explicitement via ce wizard. Le backend OCR ne crée
#    jamais de partenaire de son propre chef.
# ==============================================================================

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class InsuranceOcrWizard(models.TransientModel):
    """
    Wizard de validation manuelle des brouillons OCR sans client identifié.

    Ouverture :
      Depuis la fiche d'une insurance.policy en état 'draft_ocr'
      via le bouton action_open_ocr_wizard() (défini sur InsurancePolicyOCRState).

    Logique UI :
      1. Le wizard pré-charge les données brutes OCR (nom, CIN) en lecture seule.
      2. Si un partner_id a déjà été trouvé par le backend, il est affiché.
      3. Sinon, l'opérateur peut :
           a) Rechercher manuellement un partenaire existant dans partner_id
           b) Cocher create_new_partner pour créer un nouveau partenaire
              avec les données OCR (nom + CIN)
      4. En cliquant "Confirmer" (action_confirm) :
           - Le partner_id est lié à la police
           - Les champs ocr_raw_* sont effacés
           - La police passe à l'état 'draft' (prête pour activation manuelle)
    """

    _name        = 'insurance.ocr.wizard'
    _description = 'Wizard — Validation Brouillon OCR'

    # ── Police source ─────────────────────────────────────────────────────────

    policy_id = fields.Many2one(
        comodel_name='insurance.policy',
        string='Police à valider',
        required=True,
        readonly=True,
        ondelete='cascade',
        help='Police en brouillon OCR pour laquelle ce wizard est ouvert.',
    )

    # ── Données OCR brutes (lecture seule — pour guider l'opérateur) ─────────

    ocr_raw_partner_name = fields.Char(
        string='Nom client lu par OCR',
        readonly=True,
        help='Valeur brute retournée par le moteur OCR. '
             'Utilisez-la pour rechercher le bon partenaire ci-dessous.',
    )

    ocr_raw_cin = fields.Char(
        string='CIN lu par OCR',
        readonly=True,
        help='CIN brut retourné par l\'OCR. '
             'Peut être utilisé pour identifier le client dans Odoo.',
    )

    # ── Champs B2B (EVO01 Étape 2.5) — Entreprises ────────────────────────────

    ocr_raw_company_type = fields.Selection(
        selection=[('person', 'Personne physique'), ('company', 'Entreprise')],
        string='Type assuré (OCR)',
        readonly=True,
        help='Type d\'entité détecté par l\'OCR. '
             'Détermine si la création utilisera le CIN ou le Matricule Fiscal.',
    )

    ocr_raw_matricule_fiscal = fields.Char(
        string='Matricule Fiscal lu par OCR',
        readonly=True,
        help='Matricule Fiscal tunisien retourné par l\'OCR. '
             'Utilisé pour identifier une entreprise assurée.',
    )

    # ── Sélection du partenaire ────────────────────────────────────────────────

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client assuré',
        domain="[('customer_rank', '>', 0)]",
        help='Recherchez et sélectionnez le client correspondant. '
             'Si aucun résultat, cochez "Créer un nouveau client" ci-dessous.',
    )

    create_new_partner = fields.Boolean(
        string='Créer un nouveau client',
        default=False,
        help='Cochez cette case si aucun client existant ne correspond '
             'aux données OCR. Un nouveau res.partner sera créé avec '
             'le nom et le CIN lus par l\'OCR lors de la confirmation.',
    )

    # ── Informations complémentaires pour la création ─────────────────────────
    # Pré-remplies depuis l'OCR, modifiables par l'opérateur avant création

    new_partner_name = fields.Char(
        string='Nom du nouveau client',
        help='Pré-rempli depuis le nom lu par l\'OCR. Modifiable si nécessaire.',
    )

    new_partner_cin = fields.Char(
        string='CIN du nouveau client',
        size=8,
        help='Pré-rempli depuis le CIN lu par l\'OCR. '
             'Obligatoire si type = Personne physique.',
    )

    new_partner_matricule_fiscal = fields.Char(
        string='Matricule Fiscal du nouveau client',
        size=20,
        help='Pré-rempli depuis le Matricule Fiscal lu par l\'OCR. '
             'Obligatoire si type = Entreprise.',
    )

    new_partner_type = fields.Selection(
        selection=[('E', 'Entreprise'), ('P', 'Particulier')],
        string='Type',
        default='P',
        help='Type de client à créer. '
             'Pré-rempli selon le type détecté par l\'OCR.',
    )

    # ── Résumé de la police (readonly — pour contexte) ────────────────────────

    policy_num_police    = fields.Char(related='policy_id.num_police',    string='N° Police',    readonly=True)
    policy_company       = fields.Many2one(related='policy_id.company_ins_id', string='Compagnie', readonly=True)
    policy_prime         = fields.Monetary(related='policy_id.prime_nette', currency_field='currency_id', string='Prime TND', readonly=True)
    policy_date_effect   = fields.Date(related='policy_id.date_effect',   string='Effet',         readonly=True)
    policy_date_echeance = fields.Date(related='policy_id.date_echeance', string='Échéance',      readonly=True)
    currency_id          = fields.Many2one(related='policy_id.currency_id', string='Devise', readonly=True)

    # ─────────────────────────────────────────────────────────────────────────
    #  Chargement automatique depuis la police (default_get)
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        """
        Pré-charge les données de la police et les valeurs OCR brutes
        depuis le contexte {'default_policy_id': policy.id}.
        """
        defaults = super().default_get(fields_list)

        policy_id = defaults.get('policy_id') or self.env.context.get('default_policy_id')
        if policy_id:
            policy = self.env['insurance.policy'].browse(policy_id)
            if policy.exists():
                company_type = policy.ocr_raw_company_type or 'person'
                defaults.update({
                    'policy_id':                   policy.id,
                    'ocr_raw_partner_name':         policy.ocr_raw_partner_name      or '',
                    'ocr_raw_cin':                  policy.ocr_raw_cin               or '',
                    # Nouveaux champs B2B (EVO01 Étape 2.5)
                    'ocr_raw_company_type':         company_type,
                    'ocr_raw_matricule_fiscal':     policy.ocr_raw_matricule_fiscal  or '',
                    # Pré-remplir les champs de création avec les données OCR
                    'new_partner_name':             policy.ocr_raw_partner_name      or '',
                    'new_partner_cin':              policy.ocr_raw_cin               or '',
                    'new_partner_matricule_fiscal': policy.ocr_raw_matricule_fiscal  or '',
                    # Pré-sélectionner le type selon l'OCR
                    'new_partner_type': 'E' if company_type == 'company' else 'P',
                    # Si un partner_id est déjà lié, le montrer
                    'partner_id': policy.partner_id.id if policy.partner_id else False,
                })

        return defaults

    # ─────────────────────────────────────────────────────────────────────────
    #  Onchange
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('create_new_partner')
    def _onchange_create_new_partner(self):
        """
        Quand l'opérateur coche "Créer un nouveau client" :
          - Vide le champ partner_id (les deux sont mutuellement exclusifs)
          - Pré-remplit les champs de création depuis les données OCR
        """
        if self.create_new_partner:
            self.partner_id = False
            # Pré-remplir depuis les données brutes OCR si les champs sont vides
            if not self.new_partner_name:
                self.new_partner_name = self.ocr_raw_partner_name
            # Pré-remplir CIN (B2C) ou Matricule Fiscal (B2B) selon le type
            company_type = self.ocr_raw_company_type or 'person'
            if company_type == 'company':
                if not self.new_partner_matricule_fiscal:
                    self.new_partner_matricule_fiscal = self.ocr_raw_matricule_fiscal
                self.new_partner_type = 'E'
            else:
                if not self.new_partner_cin:
                    self.new_partner_cin = self.ocr_raw_cin
                self.new_partner_type = 'P'

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """
        Quand l'opérateur sélectionne un partenaire existant :
          - Décoche automatiquement create_new_partner (exclusivité mutuelle)
        """
        if self.partner_id:
            self.create_new_partner = False

    # ─────────────────────────────────────────────────────────────────────────
    #  Contraintes
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('partner_id', 'create_new_partner', 'new_partner_name')
    def _check_partner_choice(self):
        """Valide que l'opérateur a fait UN choix cohérent."""
        for rec in self:
            if not rec.partner_id and not rec.create_new_partner:
                raise ValidationError(_(
                    'Vous devez soit :\n'
                    '  • Sélectionner un client existant dans le champ "Client assuré"\n'
                    '  • Cocher "Créer un nouveau client"\n\n'
                    'Données OCR : %(name)s / CIN %(cin)s',
                    name=rec.ocr_raw_partner_name or '?',
                    cin=rec.ocr_raw_cin or '?',
                ))
            if rec.create_new_partner and not rec.new_partner_name:
                raise ValidationError(_(
                    'Le nom du nouveau client est obligatoire pour la création.'
                ))
            if rec.partner_id and rec.create_new_partner:
                raise ValidationError(_(
                    'Impossible de sélectionner un client existant ET '
                    'de cocher "Créer un nouveau client" simultanément.'
                ))

    # ─────────────────────────────────────────────────────────────────────────
    #  action_confirm — Validation finale
    # ─────────────────────────────────────────────────────────────────────────

    def action_confirm(self):
        """
        Valide le brouillon OCR et passe la police à l'état 'draft'.

        Séquence :
          1. Si create_new_partner → créer res.partner avec new_partner_name + new_partner_cin
          2. Lier partner_id à la police (partner_id + payer_id)
          3. Effacer les champs temporaires ocr_raw_partner_name / ocr_raw_cin
          4. Passer la police à l'état 'draft' (prête pour activation humaine)
          5. Poster un message dans le chatter de la police

        Returns:
            dict : Action de fermeture du wizard
        """
        self.ensure_one()

        policy = self.policy_id
        if not policy.exists():
            raise UserError(_('La police associée à ce wizard n\'existe plus.'))

        if policy.state != 'draft_ocr':
            raise UserError(_(
                'La police %(num)s n\'est plus en état "Brouillon OCR" '
                '(état actuel : %(state)s). '
                'Le wizard ne peut plus être appliqué.',
                num=policy.num_police,
                state=dict(policy._fields['state'].selection).get(policy.state, policy.state),
            ))

        # ── Étape 1 : Résoudre le partenaire ─────────────────────────────────
        partner = self.partner_id

        if self.create_new_partner:
            # ── Création humaine et volontaire — JAMAIS automatique ───────────
            # Logique B2B/B2C (EVO01 Étape 2.5) :
            #   company_type='company' → is_company=True + matricule_fiscal
            #   company_type='person'  → is_company=False + cin
            company_type = self.ocr_raw_company_type or 'person'
            is_company   = (company_type == 'company')

            create_vals = {
                'name':             self.new_partner_name.strip(),
                'is_company':       is_company,
                'customer_rank':    1,
                'comment': (
                    f'Créé manuellement via Wizard OCR — '
                    f'Police {policy.num_police or "?"} | '
                    f'Opérateur : {self.env.user.name}'
                ),
            }

            if is_company:
                # Entreprise : injecter le Matricule Fiscal
                mf = (self.new_partner_matricule_fiscal or '').strip()
                if mf:
                    create_vals['matricule_fiscal'] = mf
                create_vals['assujetti_tva'] = True
            else:
                # Personne physique : injecter le CIN
                cin = (self.new_partner_cin or '').strip()
                if cin:
                    create_vals['cin'] = cin
            partner = self.env['res.partner'].create(create_vals)

            _logger.info(
                'AssurCore OCR Wizard: %s créé manuellement — '
                '"%s" (%s: %s) par %s',
                'Entreprise' if is_company else 'Client',
                partner.name,
                'MF' if is_company else 'CIN',
                self.new_partner_matricule_fiscal or self.new_partner_cin or 'N/A',
                self.env.user.name,
            )

        if not partner:
            raise UserError(_(
                "Aucun client n'a été sélectionné ou créé. "
                "Veuillez choisir un client avant de confirmer."
            ))

        # ── Étape 2 : Lier le partenaire à la police ─────────────────────────
        # ── Étape 3 : Effacer les champs temporaires OCR ─────────────────────
        # ── Étape 4 : Passer à l'état 'draft' ────────────────────────────────
        policy.write({
            'partner_id':                   partner.id,
            'payer_id':                     partner.id,
            'raison_sociale':               partner.name,
            # Effacement des 4 champs temporaires OCR (nettoyage)
            'ocr_raw_partner_name':         False,
            'ocr_raw_cin':                  False,
            'ocr_raw_company_type':         False,
            'ocr_raw_matricule_fiscal':     False,
            # Transition vers 'draft' : l'opérateur peut maintenant activer
            'state':                        'draft',
        })

        # ── Étape 5 : Message dans le Chatter de la police ───────────────────
        is_company_final = partner.is_company
        action_label = (
            _('Nouveau %(type)s créé : <b>%(name)s</b>',
              type='Entreprise' if is_company_final else 'Client',
              name=partner.name)
            if self.create_new_partner
            else _('%(type)s identifié : <b>%(name)s</b>',
                   type='Entreprise' if is_company_final else 'Client',
                   name=partner.name)
        )
        policy.message_post(
            body=_(
                'Brouillon OCR validé par <b>%(user)s</b>.<br/>'
                '%(action)s<br/>'
                'Identifiant : %(id_label)s <b>%(id_value)s</b><br/>'
                'Police prête pour activation.',
                user=self.env.user.name,
                action=action_label,
                id_label='MF :' if is_company_final else 'CIN :',
                id_value=(partner.matricule_fiscal or partner.cin or 'N/A'),
            ),
            subtype_id=self.env.ref('mail.mt_note').id,
        )

        _logger.info(
            'AssurCore OCR Wizard: police %s validée — '
            '%s "%s" lié — état → draft',
            policy.num_police,
            'Entreprise' if is_company_final else 'Client',
            partner.name,
        )

        # ── Fermer le wizard et rouvrir la police validée ─────────────────────
        return {
            'type':      'ir.actions.act_window',
            'name':      _('Police validée'),
            'res_model': 'insurance.policy',
            'res_id':    policy.id,
            'view_mode': 'form',
            'target':    'current',
        }

    def action_cancel(self):
        """Ferme le wizard sans modifier la police."""
        return {'type': 'ir.actions.act_window_close'}
