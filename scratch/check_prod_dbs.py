import xmlrpc.client

url = 'https://assurcore.metadidomi.com'
db = 'assurcore_db'

try:
    db_service = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/db")
    db_list = db_service.list()
    print("Databases on prod VPS:", db_list)
except Exception as e:
    print("Error listing databases:", e)
