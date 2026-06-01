import xmlrpc.client
import socket

db = 'assurcore_db'
username = 'admin'
password = 'admin'

for port in [8070, 8071]:
    url = f'http://localhost:{port}'
    print(f"Testing port {port}...")
    
    # Try raw TCP connect first
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect(('127.0.0.1', port))
        print(f"  TCP Port {port} is OPEN!")
        s.close()
    except Exception as e:
        print(f"  TCP Port {port} is CLOSED or unreachable: {e}")
        continue
        
    # Try XML-RPC connect
    try:
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})
        print(f"  Odoo XML-RPC is RESPONDING! UID: {uid}")
        
        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        cnt = models.execute_kw(db, uid, password, 'res.partner', 'search_count', [[]])
        print(f"  ResPartner count: {cnt}")
    except Exception as e:
        print(f"  Odoo XML-RPC error: {e}")
