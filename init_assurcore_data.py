# 1. Initialisation des branches
branches = [
    ('AUTO',      'Automobile'),
    ('SANTE',     'Santé / Maladie'),
    ('MRH',       'Multirisque Habitation'),
    ('TRANSPORT', 'Transport de Marchandises'),
    ('INCENDIE',  'Incendie & Risques Divers'),
    ('VIE',       'Assurance Vie'),
    ('RC',        'Responsabilité Civile'),
    ('MARITIME',  'Maritime / Corps'),
    ('AUTRE',     'Autre'),
]
for code, name in branches:
    if not env['insurance.branch'].search([('code', '=', code)]):
        env['insurance.branch'].create({'code': code, 'name': name})
        print(f"Branch created: {name}")

# 2. Migration des polices existantes vers les nouvelles branches
for policy in env['insurance.policy'].search([('branch_id', '=', False), ('branche', '!=', False)]):
    branch = env['insurance.branch'].search([('code', '=', policy.branche)], limit=1)
    if branch:
        policy.branch_id = branch
        print(f"Policy {policy.num_police} migrated to branch {branch.name}")

# 3. Activation des clients (prospect -> actif)
env['res.partner']._cron_update_client_states()
print("Client states updated.")

# 4. Nettoyage des activités orphelines (SANS BOM)
acts = env['mail.activity'].search([])
orphan = acts.filtered(lambda a: a.res_model not in env)
if orphan:
    print(f"Cleaning up {len(orphan)} orphan activities...")
    orphan.unlink()

env.cr.commit()
print("Commit SUCCESS")
