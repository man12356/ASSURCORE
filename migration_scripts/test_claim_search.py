import xmlrpc.client
url = 'http://localhost:8071'
db = 'assurcore_db'
user = 'admin'
pwd = 'admin'

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, user, pwd, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
try:
    res = models.execute_kw(db, uid, pwd, 'insurance.claim', 'search', [[('name', '=', 'ORA-SIN-2015-0')]], {'limit': 1})
    print("SUCCESS SEARCH:", res)
except Exception as e:
    print("ERROR SEARCH:", e)
