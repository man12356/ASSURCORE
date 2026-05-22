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

print("=== VERIFYING MENUS ON PRODUCTION ===")
menus_to_check = [
    'assurcore.menu_assurcore_policies',
    'assurcore.menu_assurcore_operations',
    'assurcore.menu_assurcore_fleet_vehicle',
    'assurcore.menu_insurance_branch',
    'assurcore.menu_insurance_mouvement_report_wizard',
    'assurcore.menu_insurance_journal_enc'
]

for m in menus_to_check:
    try:
        # Resolve xml_id to database ID
        data = models.execute_kw(
            db, uid, password,
            'ir.model.data', 'search_read',
            [[('module', '=', m.split('.')[0]), ('name', '=', m.split('.')[1])]],
            {'fields': ['res_id']}
        )
        if data:
            menu_id = data[0]['res_id']
            # Read menu info
            menu = models.execute_kw(
                db, uid, password,
                'ir.ui.menu', 'read',
                [[menu_id]],
                {'fields': ['name', 'complete_name', 'action']}
            )
            if menu:
                print(f"✅ Menu {m}: '{menu[0].get('complete_name')}' is Active (Action: {menu[0].get('action')})")
            else:
                print(f"❌ Menu {m}: Resolved to res_id {menu_id} but not found in ir.ui.menu")
        else:
            print(f"❌ Menu {m}: XML ID not found in database!")
    except Exception as e:
        print(f"⚠ Error checking menu {m}: {e}")
