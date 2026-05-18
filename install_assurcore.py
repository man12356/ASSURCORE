import xmlrpc.client

url = 'http://localhost:8071'
db = 'assurcore_db'
username = 'admin'
password = 'admin'

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
print("Authenticated successfully, UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# 1. Update module list
print("Updating module list...")
models.execute_kw(db, uid, password, 'ir.module.module', 'update_list', [])

# 2. Find assurcore module
print("Searching for 'assurcore' module...")
module_ids = models.execute_kw(
    db, uid, password,
    'ir.module.module', 'search',
    [[('name', '=', 'assurcore')]]
)

if not module_ids:
    print("Error: assurcore module not found in database!")
else:
    module_id = module_ids[0]
    print(f"Found assurcore module, ID: {module_id}")
    
    # 3. Install the module
    print("Installing 'assurcore' module...")
    models.execute_kw(
        db, uid, password,
        'ir.module.module', 'button_immediate_install',
        [[module_id]]
    )
    print("Installation request completed successfully!")
