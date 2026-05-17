# -*- coding: utf-8 -*-
# Génération en masse des quittances depuis les opérations confirmées
import logging

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
            
        # Appel de la méthode de génération standard
        op.action_generate_receipt()
        count += 1
        
        # Commit par lots de 1000 pour éviter les locks de DB et la surcharge mémoire
        if count % 1000 == 0:
            env.cr.commit()
            _logger.info(f"{count} / {total} quittances générées...")
            
    except Exception as e:
        _logger.error(f"Erreur sur opération {op.name} (ID: {op.id}): {str(e)}")
        env.cr.rollback()

env.cr.commit()
_logger.info(f"Terminé. {count} quittances créées avec succès.")
