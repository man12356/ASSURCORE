import xmlrpc.client

url = 'http://localhost:8071'
db = 'assurcore_db'
username = 'admin'
password = 'admin'

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    print("Authentication failed.")
    exit(1)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

print("=== INCOMING MAIL SERVERS ===")
try:
    servers = models.execute_kw(
        db, uid, password,
        'fetchmail.server', 'search_read',
        [[]],
        {'fields': ['name', 'server', 'port', 'user', 'state']}
    )
    for s in servers:
        print(f"Name: {s.get('name')}")
        print(f"  Server: {s.get('server')}:{s.get('port')}")
        print(f"  User: {s.get('user')}")
        print(f"  State: {s.get('state')}")
        print("-" * 30)
except Exception as e:
    print("Error fetching fetchmail.server:", e)

print("\n=== MAIL ALIASES ===")
try:
    aliases = models.execute_kw(
        db, uid, password,
        'mail.alias', 'search_read',
        [[]],
        {'fields': ['alias_name', 'alias_model_id']}
    )
    for a in aliases:
        model_id = a.get('alias_model_id')
        model_name = model_id[1] if model_id else "None"
        if 'document' in model_name or 'ocr' in model_name or 'parser' in model_name or 'policy' in model_name:
            print(f"Alias: {a.get('alias_name')}")
            print(f"  Target Model: {model_name}")
            print("-" * 30)
except Exception as e:
    print("Error fetching mail.alias:", e)
