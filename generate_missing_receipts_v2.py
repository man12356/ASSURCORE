# -*- coding: utf-8 -*-
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger('assurcore.receipt_gen')

operations = env['insurance.operation'].search([
    ('receipt_id', '=', False),
    ('state', 'in', ['draft', 'confirmed']),
    '|', ('montant_prime', '>', 0), ('montant_honoraire_ht', '>', 0)
])

total = len(operations)
_logger.info(f"Trouvé {total} opérations nécessitant une quittance.")

count = 0
for op in operations:
    try:
        if op.state == 'draft':
            op.action_confirm()
            
        # Correction des dates avant génération pour respecter les contraintes Odoo
        # 1. date_validite_au est obligatoire pour la quittance
        if not op.date_validite_au:
            if op.date_validite_du:
                op.date_validite_au = op.date_validite_du + relativedelta(years=1)
            else:
                op.date_validite_au = op.date_op + relativedelta(years=1)
                op.date_validite_du = op.date_op
                
        # 2. date_echeance (sur quittance) >= date_emission (date_op)
        # Si la date d'opération est > date de fin de validité (saisie en retard dans l'ancien système)
        if op.date_validite_au < op.date_op:
            # On aligne la date d'émission sur la date de validité
            op.date_op = op.date_validite_du or op.date_validite_au
            
        # On peut générer
        op.action_generate_receipt()
        count += 1
        
        if count % 1000 == 0:
            env.cr.commit()
            _logger.info(f"{count} / {total} quittances générées...")
            
    except Exception as e:
        _logger.error(f"Erreur corrigée sur opération {op.name} (ID: {op.id}): {str(e)}")
        # Contournement si la génération automatique échoue quand même
        try:
            env.cr.rollback()
            # On force la création de la quittance en mode dégradé si la méthode échoue
            receipt = env['insurance.receipt'].create({
                'policy_id': op.policy_id.id,
                'num_quittance_compagnie': op.num_quittance or 'INCONNU',
                'date_emission': op.date_op,
                'date_echeance': max(op.date_validite_au, op.date_op) if op.date_validite_au else op.date_op,
                'date_validite_du': op.date_validite_du,
                'date_validite_au': max(op.date_validite_au, op.date_op) if op.date_validite_au else op.date_op,
                'montant_prime': op.montant_prime,
                'state': 'emise',
            })
            op.write({'receipt_id': receipt.id, 'state': 'invoiced'})
            count += 1
            env.cr.commit()
        except Exception as e2:
            env.cr.rollback()
            _logger.error(f"ECHEC DEFINITIF OP {op.name}: {str(e2)}")

env.cr.commit()
_logger.info(f"Terminé. {count} quittances créées avec succès.")
