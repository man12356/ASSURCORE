import xmlrpc.client

url = 'https://assurcore.metadidomi.com'
db = 'assurcore_db'
username = 'admin'
password = 'admin'

print(f"Connecting to remote VPS XML-RPC at {url}...")
try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    print("SUCCESS! Authenticated successfully, UID:", uid)
    
    # Check if type_sinistre exists in insurance.claim fields
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    fields = models.execute_kw(db, uid, password, 'insurance.claim', 'fields_get', [], {'attributes': ['type']})
    if 'type_sinistre' in fields:
        print("✓ Field 'type_sinistre' exists in remote Odoo database!")
    else:
        print("✗ Field 'type_sinistre' does NOT exist in remote Odoo database!")
except Exception as e:
    print(f"Connection failed: {e}")
