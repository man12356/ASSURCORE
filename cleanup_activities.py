# Nettoyage des activités orphelines (ex: sale.order sans module sale)
activities = env['mail.activity'].search([])
orphan = activities.filtered(lambda a: a.res_model not in env)
if orphan:
    print(f"AssurCore Cleanup: Suppression de {len(orphan)} activités orphelines...")
    orphan.unlink()
    env.cr.commit()
else:
    print("AssurCore Cleanup: Aucune activité orpheline trouvée.")
