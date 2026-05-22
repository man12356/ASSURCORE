import xmlrpc.client

url = 'https://assurcore.metadidomi.com'
db = 'assurcore_db'
password = 'admin'

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, 'admin', password, {})

if not uid:
    print("Authentication failed.")
    exit(1)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

print("=== PROGRAMMATICALLY GRANTING CONTACT CREATION TO ZIED ===")
try:
    # Get group ID for base.group_partner_manager
    group_ids = models.execute_kw(
        db, uid, password,
        'ir.model.data', 'search_read',
        [[('module', '=', 'base'), ('name', '=', 'group_partner_manager')]],
        {'fields': ['res_id']}
    )
    if not group_ids:
        print("Error: base.group_partner_manager not found!")
        exit(1)
    group_id = group_ids[0]['res_id']
    print(f"Group ID: {group_id}")

    # Find user ZIED KAMOUN
    users = models.execute_kw(
        db, uid, password,
        'res.users', 'search',
        [[('login', '=', 'Karekamoun@gmail.com')]]
    )
    if not users:
        print("Error: User Karekamoun@gmail.com not found!")
        exit(1)
    user_id = users[0]
    print(f"User ID: {user_id}")

    # Add user to the group
    models.execute_kw(
        db, uid, password,
        'res.groups', 'write',
        [[group_id], {'users': [(4, user_id)]}]
    )
    print("✅ Successfully added Zied Kamoun to the Contact Creation group!")

except Exception as e:
    print("Error:", e)
