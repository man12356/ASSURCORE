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

# 5. Configuration permanente de la société Courtier (ASSURANCES KAMOUN) et de la devise TND
company = env.ref('base.main_company')
tnd = env['res.currency'].search([('name', '=', 'TND')], limit=1)
if tnd:
    tnd.write({'active': True})
    company.write({'currency_id': tnd.id})
    print("TND Currency activated and assigned to the company.")

partner = company.partner_id
tn_country = env.ref('base.tn')

# Recherche ou création de l'État de Tunis pour la Tunisie
state = env['res.country.state'].search([('country_id', '=', tn_country.id), ('name', '=ilike', 'Tunis')], limit=1)
if not state:
    state = env['res.country.state'].create({
        'name': 'Tunis',
        'code': 'TUN',
        'country_id': tn_country.id
    })
    print(f"Created state: {state.name} ({state.code})")

partner.write({
    'name': 'ASSURANCES KAMOUN',
    'street': 'C01 Immeuble Carthage Palace',
    'street2': 'Centre Urbain Nord',
    'city': 'Tunis',
    'state_id': state.id,
    'zip': '1082',
    'phone': '+216 71 822 747',
    'mobile': '+216 58 385 385',
    'email': 'contact@assuranceskamoun.com',
    'website': 'https://assuranceskamoun.com',
    'country_id': tn_country.id,
})
company.write({'name': 'ASSURANCES KAMOUN'})
print("Company properties successfully configured and persisted.")

# 6. Activation de la langue fr_FR et configuration par défaut de tous les utilisateurs en français
print("=== Configuring French Language ===")
env['res.lang']._activate_lang('fr_FR')
env['res.users'].search([]).write({'lang': 'fr_FR'})
env['res.partner'].search([]).write({'lang': 'fr_FR'})
print("All users and partners successfully set to French (fr_FR).")

# 7. Création des utilisateurs importés (Zied est le chef, les autres font la saisie)
users_to_create = [
    {
        'name': 'ZIED KAMOUN',
        'login': 'Karekamoun@gmail.com',
        'password': 'Kar5252455%%Mp!!6325',
        'group': 'assurcore.group_assurcore_manager'
    },
    {
        'name': 'HANEN',
        'login': 'hanen@assuranceskamoun.com',
        'password': 'ZAKARIA',
        'group': 'assurcore.group_assurcore_agent'
    },
    {
        'name': 'LEILA',
        'login': 'leila@assuranceskamoun.com',
        'password': 'YOUNESS',
        'group': 'assurcore.group_assurcore_agent'
    },
    {
        'name': 'RIDHA',
        'login': 'ridha@assuranceskamoun.com',
        'password': 'RIDHA',
        'group': 'assurcore.group_assurcore_agent'
    },
    {
        'name': 'MOHAMEDALI',
        'login': 'mohamedali@assuranceskamoun.com',
        'password': 'dalidali',
        'group': 'assurcore.group_assurcore_agent'
    },
    {
        'name': 'ASMA',
        'login': 'asma@assuranceskamoun.com',
        'password': 'WIEM',
        'group': 'assurcore.group_assurcore_agent'
    }
]

for user_data in users_to_create:
    user = env['res.users'].search([('login', '=', user_data['login'])], limit=1)
    group = env.ref(user_data['group'])
    if not user:
        user = env['res.users'].create({
            'name': user_data['name'],
            'login': user_data['login'],
            'password': user_data['password'],
            'groups_id': [(6, 0, [group.id, env.ref('base.group_user').id])]
        })
        print(f"User created: {user_data['name']} ({user_data['login']})")
    else:
        user.write({
            'name': user_data['name'],
            'password': user_data['password'],
            'groups_id': [(6, 0, [group.id, env.ref('base.group_user').id])]
        })
        print(f"User updated: {user_data['name']} ({user_data['login']})")

env.cr.commit()
print("Commit SUCCESS")
