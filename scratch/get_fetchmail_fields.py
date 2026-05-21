import xmlrpc.client

url = 'http://localhost:8071'
db = 'assurcore_db'
password = 'admin'

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, 'admin', password, {})

if not uid:
    print("Authentication failed.")
    exit(1)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

try:
    fields = models.execute_kw(
        db, uid, password,
        'fetchmail.server', 'fields_get',
        [],
        {'attributes': ['type', 'required']}
    )
    for field_name in sorted(fields.keys()):
        print(f"{field_name}: {fields[field_name].get('type')} (required: {fields[field_name].get('required')})")
except Exception as e:
    print("Error:", e)
