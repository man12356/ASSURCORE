import psutil

print("=== RUNNING PROCESSES ===")
for proc in psutil.process_iter(['name']):
    name = proc.info['name']
    if name and any(k in name.lower() for k in ['docker', 'wsl', 'odoo', 'postgres', 'python', 'vbox', 'virtualbox']):
        print(f" - {name}")
