import xmlrpc.client

url = 'http://localhost:8071'
db = 'assurcore_db'
username = 'admin'
password = 'admin'

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

try:
    print("Testing search_read with list of lists:")
    res = models.execute_kw(
        db, uid, password,
        'res.partner', 'search_read',
        [[['ref', 'like', 'ORA-']]],
        {'fields': ['id', 'ref']}
    )
    print("Result size:", len(res))
    if res:
        print("First record:", res[0])
except Exception as e:
    print("Error with list of lists:", e)

try:
    print("Testing search_read with list of tuples:")
    res2 = models.execute_kw(
        db, uid, password,
        'res.partner', 'search_read',
        [[('ref', 'like', 'ORA-')]],
        {'fields': ['id', 'ref']}
    )
    print("Result 2 size:", len(res2))
except Exception as e:
    print("Error with list of tuples:", e)
