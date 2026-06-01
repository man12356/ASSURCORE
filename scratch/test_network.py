import socket

target_ip = '8.8.8.8'
target_port = 53

print(f"Testing raw socket connection to {target_ip}:{target_port}...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect((target_ip, target_port))
    print("SUCCESS! Outbound IP connections are allowed.")
    s.close()
except Exception as e:
    print(f"FAILED: {e}")
