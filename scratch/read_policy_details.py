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

print("=== POLICY DETAILS ON PRODUCTION ===")
try:
    policy = models.execute_kw(
        db, uid, password,
        'insurance.policy', 'read',
        [[7436]],
        {'fields': ['num_police', 'state', 'partner_id', 'matricule', 'prime_nette', 'ocr_raw_partner_name']}
    )
    if policy:
        p = policy[0]
        print(f"Policy: {p.get('num_police')}")
        print(f"  State: {p.get('state')}")
        print(f"  Partner: {p.get('partner_id')}")
        print(f"  Plate (Matricule): {p.get('matricule')}")
        print(f"  Prime Nette: {p.get('prime_nette')}")
        print(f"  Raw Partner (OCR): {p.get('ocr_raw_partner_name')}")
        print("-" * 40)
        
        # Check attachments linked to this policy
        attachments = models.execute_kw(
            db, uid, password,
            'ir.attachment', 'search_read',
            [[('res_model', '=', 'insurance.policy'), ('res_id', '=', 7436)]],
            {'fields': ['name', 'create_date']}
        )
        print("Linked Attachments:")
        for att in attachments:
            print(f"  - {att.get('name')} (Created: {att.get('create_date')})")
    else:
        print("Policy 7436 not found.")
except Exception as e:
    print("Error:", e)
