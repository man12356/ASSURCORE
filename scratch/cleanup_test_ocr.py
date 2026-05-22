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

# 1. Trouver le partenaire "BEN ALI SLIM"
print("Finding test partner 'BEN ALI SLIM'...")
partner_ids = models.execute_kw(
    db, uid, password,
    'res.partner', 'search',
    [[('name', '=', 'BEN ALI SLIM')]]
)

# 2. Trouver la police "POL-LLOYD-7788"
print("Finding test policy 'POL-LLOYD-7788'...")
policy_ids = models.execute_kw(
    db, uid, password,
    'insurance.policy', 'search',
    [[('num_police', '=', 'POL-LLOYD-7788')]]
)

if policy_ids:
    policy_id = policy_ids[0]
    print(f"Policy ID: {policy_id}")
    # Reset policy to draft_ocr and clear links
    models.execute_kw(
        db, uid, password,
        'insurance.policy', 'write',
        [[policy_id], {
            'state': 'draft_ocr',
            'partner_id': False,
            'payer_id': False,
            'ocr_raw_partner_name': 'BEN ALI SLIM',
            'ocr_raw_cin': '09876543',
            'ocr_raw_company_type': 'person',
            'ocr_raw_matricule_fiscal': False,
        }]
    )
    print("Policy successfully reset to draft_ocr and links cleared.")

if partner_ids:
    print(f"Deleting test partner IDs: {partner_ids}")
    try:
        models.execute_kw(
            db, uid, password,
            'res.partner', 'unlink',
            [partner_ids]
        )
        print("Test partner successfully deleted.")
    except Exception as e:
        print("Could not delete test partner (probably linked, clearing references first):", e)
