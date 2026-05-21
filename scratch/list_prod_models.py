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

print("=== LISTING MODELS CONTAINING 'insurance' OR 'parser' ===")
try:
    res = models.execute_kw(
        db, uid, password,
        'ir.model', 'search_read',
        [[('model', 'like', 'insurance')]],
        {'fields': ['model', 'name']}
    )
    for r in res:
        print(f"{r.get('model')}: {r.get('name')}")
except Exception as e:
    print("Error:", e)
