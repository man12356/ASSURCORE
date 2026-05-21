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

print("=== CLEANING UP TEST OCR RECORDS ===")

# 1. Trouver et supprimer les document parsers de test
parser_ids = models.execute_kw(
    db, uid, password,
    'insurance.document.parser', 'search',
    [[('name', 'like', 'Test OCR —')]]
)
if parser_ids:
    print(f"Deleting {len(parser_ids)} document parser records...")
    models.execute_kw(db, uid, password, 'insurance.document.parser', 'unlink', [parser_ids])

# 2. Trouver et supprimer les polices de test
policy_ids = models.execute_kw(
    db, uid, password,
    'insurance.policy', 'search',
    [[('num_police', 'in', ['POL-LLOYD-7788', 'POL-CARTE-5566', 'POL-STAR-B2B-9900', 'POL-MAGHREBIA-J54554'])]]
)
if policy_ids:
    print(f"Deleting {len(policy_ids)} policy records...")
    models.execute_kw(db, uid, password, 'insurance.policy', 'unlink', [policy_ids])

# 3. Trouver et supprimer les clients de test créés
partner_ids = models.execute_kw(
    db, uid, password,
    'res.partner', 'search',
    [[('cin', 'in', ['09876543', '01234567', '08422621'])]]
)
if partner_ids:
    print(f"Deleting {len(partner_ids)} B2C test partners...")
    try:
        models.execute_kw(db, uid, password, 'res.partner', 'unlink', [partner_ids])
    except Exception as e:
        print("Could not delete partners directly (perhaps linked elsewhere):", e)

partner_b2b_ids = models.execute_kw(
    db, uid, password,
    'res.partner', 'search',
    [[('matricule_fiscal', '=', '1234567/A/B/M/000')]]
)
if partner_b2b_ids:
    print(f"Deleting {len(partner_b2b_ids)} B2B test partners...")
    try:
        models.execute_kw(db, uid, password, 'res.partner', 'unlink', [partner_b2b_ids])
    except Exception as e:
        print("Could not delete partners directly (perhaps linked elsewhere):", e)

print("Cleanup completed successfully!")
