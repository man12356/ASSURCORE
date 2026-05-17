# Nettoyer les vues orphelines contenant 'team_id' (qui provient du module sales_team)
views = env['ir.ui.view'].search([
    ('arch_db', 'ilike', 'team_id'),
    ('model', 'in', ['account.move', 'res.partner'])
])

if views:
    print(f"Orphan views found with team_id: {views.mapped('name')}")
    views.unlink()
    env.cr.commit()
    print("Orphan views deleted.")
else:
    print("No orphan views found with team_id.")
