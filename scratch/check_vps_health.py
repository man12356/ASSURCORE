import urllib.request
import xmlrpc.client

url = 'https://assurcore.metadidomi.com'

try:
    with urllib.request.urlopen(f"{url}/web/health", timeout=5) as response:
        print("Web Health Status Code:", response.getcode())
except Exception as e:
    print("Health check failed:", e)

db = 'assurcore_db'
password = 'admin'
try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, 'admin', password, {})
    if uid:
        print("Successfully authenticated as admin.")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        res = models.execute_kw(
            db, uid, password,
            'ir.model', 'search',
            [[('model', '=', 'insurance.document.parser')]]
        )
        if res:
            print("Model 'insurance.document.parser' exists in remote database!")
        else:
            print("Model 'insurance.document.parser' NOT found yet.")
except Exception as e:
    print("XML-RPC check failed:", e)
