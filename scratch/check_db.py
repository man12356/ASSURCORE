import xmlrpc.client

url = 'http://localhost:8071'
db = 'assurcore_db'
username = 'admin'
password = 'admin'

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

print(f"UID: {uid}")
for model in ['res.partner', 'insurance.company', 'insurance.policy', 'insurance.risk', 'insurance.receipt', 'insurance.settlement']:
    try:
        cnt = models.execute_kw(db, uid, password, model, 'search_count', [[]])
        print(f"{model}: {cnt} records")
    except Exception as e:
        print(f"Error on {model}: {e}")
