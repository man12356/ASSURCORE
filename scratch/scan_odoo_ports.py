import socket
import xmlrpc.client

db = 'assurcore_db'
username = 'admin'
password = 'admin'

print("Scanning ports from 8060 to 8090...")
for port in range(8060, 8091):
    # Try raw TCP connect
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.1)
    try:
        s.connect(('127.0.0.1', port))
        print(f"Port {port} is OPEN!")
        s.close()
        
        # Test XML-RPC on this port
        url = f'http://localhost:{port}'
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})
        print(f"  -> SUCCESS! Odoo responding on {url} (UID: {uid})")
    except Exception as e:
        pass
print("Scan complete!")
