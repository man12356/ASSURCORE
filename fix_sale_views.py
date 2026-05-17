# Nettoyer les vues orphelines de 'sale' sur res.partner
views = env['ir.ui.view'].search([('model', '=', 'res.partner'), ('arch_db', 'ilike', 'sale_order_count')])
if views:
    print(f"Orphan views found: {views.mapped('name')}")
    # On supprime ou on désactive
    views.unlink()
    env.cr.commit()
    print("Orphan views deleted.")
else:
    print("No orphan views found with sale_order_count.")
