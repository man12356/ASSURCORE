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

print("=== CHECKING POLICIES STATE ===")
try:
    policies = models.execute_kw(
        db, uid, password,
        'insurance.policy', 'search_read',
        [[('num_police', 'in', ['POL-LLOYD-7788', 'J54554', 'POL-CARTE-5544', 'POL-STAR-B2B-100'])]],
        {'fields': ['num_police', 'state', 'partner_id', 'ocr_raw_partner_name']}
    )
    for p in policies:
        print(f"Policy: {p.get('num_police')}")
        print(f"  State: {p.get('state')}")
        print(f"  Partner: {p.get('partner_id')}")
        print(f"  Raw Partner: {p.get('ocr_raw_partner_name')}")
        print("-" * 30)
except Exception as e:
    print("Error:", e)
