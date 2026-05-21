import xmlrpc.client
import time

url = 'https://assurcore.metadidomi.com'
db = 'assurcore_db'
password = 'admin'

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, 'admin', password, {})

if not uid:
    print("Authentication failed.")
    exit(1)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# 1. Trouver le serveur de messagerie entrant
print("Finding incoming mail server for contact@exregister.io...")
server_ids = models.execute_kw(
    db, uid, password,
    'fetchmail.server', 'search',
    [[('user', '=', 'contact@exregister.io')]]
)

if not server_ids:
    print("Error: incoming mail server not found.")
    exit(1)

server_id = server_ids[0]
print(f"Incoming Server ID: {server_id}")

# 2. Déclencher le fetch des e-mails
print("Triggering email fetch (fetch_mail) on production...")
try:
    models.execute_kw(
        db, uid, password,
        'fetchmail.server', 'fetch_mail',
        [[server_id]]
    )
    print("Fetch mail execution completed successfully!")
except Exception as e:
    print("Error during fetch_mail execution:", e)

# 3. Attendre 3 secondes et lister les documents reçus par l'OCR
print("Waiting 3 seconds...")
time.sleep(3)

print("\n=== LIST OF RECENT OCR DOCUMENTS IN PRODUCTION ===")
try:
    parsers = models.execute_kw(
        db, uid, password,
        'insurance.document.parser', 'search_read',
        [[]],
        {'fields': ['name', 'create_date', 'state', 'policy_id'], 'limit': 5, 'order': 'id desc'}
    )
    for p in parsers:
        print(f"Parser Name: {p.get('name')}")
        print(f"  Created: {p.get('create_date')}")
        print(f"  State: {p.get('state')}")
        print(f"  Policy: {p.get('policy_id')}")
        print("-" * 40)
except Exception as e:
    print("Error fetching documents:", e)
