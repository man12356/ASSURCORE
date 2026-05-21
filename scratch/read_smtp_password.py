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

print("=== READING SMTP PASSWORD ===")
try:
    servers = models.execute_kw(
        db, uid, password,
        'ir.mail_server', 'search_read',
        [[('smtp_user', '=', 'contact@exregister.io')]],
        {'fields': ['name', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass']}
    )
    for s in servers:
        print(f"Name: {s.get('name')}")
        print(f"  User: {s.get('smtp_user')}")
        print(f"  Password (length): {len(s.get('smtp_pass')) if s.get('smtp_pass') else 0}")
        print(f"  Password value: {s.get('smtp_pass')}")
except Exception as e:
    print("Error:", e)
