import xmlrpc.client

url = 'https://assurcore.metadidomi.com'
db = 'assurcore_db'

passwords_to_try = ['admin', 'AssurProdSecret2026!']
uid = None
password = None

for pwd in passwords_to_try:
    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        res = common.authenticate(db, 'admin', pwd, {})
        if res:
            uid = res
            password = pwd
            print(f"Authenticated on production with password: {pwd}")
            break
    except Exception as e:
        print(f"Failed auth for {pwd}: {e}")

if not uid:
    print("Authentication failed on production.")
    exit(1)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

print("\n=== PROD INCOMING MAIL SERVERS (fetchmail.server) ===")
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

print("\n=== PROD OUTGOING MAIL SERVERS (ir.mail_server) ===")
try:
    servers = models.execute_kw(
        db, uid, password,
        'ir.mail_server', 'search_read',
        [[]],
        {'fields': ['name', 'smtp_host', 'smtp_port', 'smtp_user', 'active']}
    )
    for s in servers:
        print(f"Name: {s.get('name')}")
        print(f"  SMTP Host: {s.get('smtp_host')}:{s.get('smtp_port')}")
        print(f"  User: {s.get('smtp_user')}")
        print(f"  Active: {s.get('active')}")
        print("-" * 30)
except Exception as e:
    print("Error fetching ir.mail_server:", e)

print("\n=== PROD MAIL ALIASES (mail.alias) ===")
try:
    aliases = models.execute_kw(
        db, uid, password,
        'mail.alias', 'search_read',
        [[]],
        {'fields': ['alias_name', 'alias_model_id', 'alias_domain_id']}
    )
    for a in aliases:
        model_id = a.get('alias_model_id')
        model_name = model_id[1] if model_id else "None"
        domain_id = a.get('alias_domain_id')
        domain_name = domain_id[1] if domain_id else "None"
        print(f"Alias: {a.get('alias_name')} (Domain: {domain_name})")
        print(f"  Target Model: {model_name}")
        print("-" * 30)
except Exception as e:
    print("Error fetching mail.alias:", e)
