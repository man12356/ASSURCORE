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

print("=== OUTGOING MAIL SERVERS (ir.mail_server) ===")
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

print("\n=== ALL MAIL ALIASES (mail.alias) ===")
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

print("\n=== GENERAL CONFIG SETTINGS (mail_domain / alias_domain) ===")
try:
    # check default alias domain in res.config.settings
    ir_config_parameter = models.execute_kw(
        db, uid, password,
        'ir.config_parameter', 'search_read',
        [[('key', 'ilike', 'mail')]],
        {'fields': ['key', 'value']}
    )
    for param in ir_config_parameter:
        print(f"{param.get('key')}: {param.get('value')}")
except Exception as e:
    print("Error fetching ir.config_parameter:", e)
