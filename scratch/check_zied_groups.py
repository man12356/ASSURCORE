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

print("=== CHECKING USER 'ZIED KAMOUN' GROUPS ===")
try:
    # Find Zied user record
    users = models.execute_kw(
        db, uid, password,
        'res.users', 'search_read',
        [[('login', '=', 'Karekamoun@gmail.com')]],
        {'fields': ['name', 'groups_id']}
    )
    if users:
        u = users[0]
        print(f"User: {u['name']} (ID: {u['id']})")
        # Read names of all groups he belongs to
        group_ids = u['groups_id']
        groups = models.execute_kw(
            db, uid, password,
            'res.groups', 'read',
            [group_ids],
            {'fields': ['name', 'category_id', 'full_name']}
        )
        print("Groups:")
        for g in sorted(groups, key=lambda x: x.get('full_name') or x.get('name') or ''):
            print(f"  - {g.get('full_name') or g.get('name')} (ID: {g['id']})")
    else:
        print("User Karekamoun@gmail.com not found.")
except Exception as e:
    print("Error:", e)
