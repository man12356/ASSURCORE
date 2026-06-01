import socket
import xmlrpc.client

hosts_to_try = ['host.docker.internal', '172.17.0.1', '172.18.0.1', '192.168.1.1', '10.0.75.1']
db = 'assurcore_db'
username = 'admin'
password = 'admin'

for host in hosts_to_try:
    print(f"Resolving {host}...")
    try:
        ip = socket.gethostbyname(host)
        print(f"Resolved to {ip}. Scanning ports from 8060 to 8090...")
        for port in range(8060, 8091):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            try:
                s.connect((ip, port))
                print(f"  -> Port {port} is OPEN on {host} ({ip})!")
                s.close()
                
                # Test XML-RPC on this port
                url = f'http://{ip}:{port}'
                common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
                uid = common.authenticate(db, username, password, {})
                print(f"    -> SUCCESS! Odoo responding on {url} (UID: {uid})")
            except Exception as e:
                pass
    except Exception as e:
        print(f"Failed to resolve {host}: {e}")

print("Scan complete!")
