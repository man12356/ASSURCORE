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

print("=== LOCAL INCOMING MAIL SERVERS (including inactive) ===")
try:
    servers = models.execute_kw(
        db, uid, password,
        'fetchmail.server', 'search_read',
        [[('active', 'in', [True, False])]],
        {'fields': ['name', 'server', 'port', 'user', 'active', 'state']}
    )
    for s in servers:
        print(f"Name: {s.get('name')}")
        print(f"  Server: {s.get('server')}:{s.get('port')}")
        print(f"  User: {s.get('user')}")
        print(f"  State: {s.get('state')}")
        print(f"  Active: {s.get('active')}")
        print("-" * 30)
except Exception as e:
    print("Error:", e)
