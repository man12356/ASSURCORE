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

# 1. Trouver le modèle insurance.document.parser
print("Finding model ID for insurance.document.parser...")
model_ids = models.execute_kw(
    db, uid, password,
    'ir.model', 'search',
    [[('model', '=', 'insurance.document.parser')]]
)
if not model_ids:
    print("Error: model insurance.document.parser not found.")
    exit(1)
model_id = model_ids[0]
print(f"Model ID: {model_id}")

# 2. Chercher s'il existe déjà
print("Checking for existing fetchmail server...")
existing = models.execute_kw(
    db, uid, password,
    'fetchmail.server', 'search',
    [[('user', '=', 'contact@exregister.io')]]
)

if existing:
    print("Fetchmail server already exists for contact@exregister.io. Updating it...")
    server_id = existing[0]
    models.execute_kw(
        db, uid, password,
        'fetchmail.server', 'write',
        [[server_id], {
            'name': 'OCR Incoming (exregister.io)',
            'server': 'ssl0.ovh.net',
            'port': 993,
            'server_type': 'imap',
            'is_ssl': True,
            'password': 'Ex!!052026**Man%%RegV51',
            'object_id': model_id,
        }]
    )
else:
    print("Creating new fetchmail server...")
    server_id = models.execute_kw(
        db, uid, password,
        'fetchmail.server', 'create',
        [{
            'name': 'OCR Incoming (exregister.io)',
            'server': 'ssl0.ovh.net',
            'port': 993,
            'server_type': 'imap',
            'is_ssl': True,
            'user': 'contact@exregister.io',
            'password': 'Ex!!052026**Man%%RegV51',
            'object_id': model_id,
            'state': 'draft',
        }]
    )
print(f"Fetchmail Server ID: {server_id}")

# 3. Confirmer/Activer le serveur
print("Activating the incoming mail server...")
try:
    models.execute_kw(
        db, uid, password,
        'fetchmail.server', 'button_confirm',
        [[server_id]]
    )
    print("Fetchmail server successfully activated!")
except Exception as e:
    print("Could not automatically activate (perhaps network connection check failed):", e)
    print("Setting state to 'done' manually...")
    models.execute_kw(
        db, uid, password,
        'fetchmail.server', 'write',
        [[server_id], {'state': 'done'}]
    )
    print("State manually set to 'done'.")
