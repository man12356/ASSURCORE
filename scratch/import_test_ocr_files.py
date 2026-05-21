import os
import base64
import xmlrpc.client

url = 'http://localhost:8071'
db = 'assurcore_db'
username = 'admin'
passwords = ['admin', 'AssurProdSecret2026!']

# 1. Authenticate
uid = None
password = None
for pwd in passwords:
    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        uid = common.authenticate(db, username, pwd, {})
        if uid:
            password = pwd
            print(f"Successfully authenticated with password: {pwd}")
            break
    except Exception as e:
        print(f"Failed authentication with password {pwd}: {e}")

if not uid:
    print("Error: Could not authenticate with any of the passwords.")
    exit(1)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# 2. Path to TEST DOC OCR directory
test_dir = r"d:\Robot\ASSURPROD\TEST DOC OCR"
if not os.path.exists(test_dir):
    print(f"Error: Directory not found at {test_dir}")
    exit(1)

files = [f for f in os.listdir(test_dir) if f.lower().endswith('.pdf')]
print(f"Found PDF files to import: {files}")

for filename in files:
    filepath = os.path.join(test_dir, filename)
    print(f"\nProcessing {filename}...")
    
    # Read and encode PDF data
    try:
        with open(filepath, 'rb') as f:
            pdf_data = f.read()
        encoded_data = base64.b64encode(pdf_data).decode('utf-8')
    except Exception as e:
        print(f"Error reading file {filename}: {e}")
        continue
        
    try:
        # Create attachment first
        attachment_id = models.execute_kw(
            db, uid, password,
            'ir.attachment', 'create',
            [{
                'name': filename,
                'type': 'binary',
                'datas': encoded_data,
                'res_model': 'insurance.document.parser',
            }]
        )
        print(f"  Created ir.attachment ID: {attachment_id}")
        
        # Create document parser record
        parser_id = models.execute_kw(
            db, uid, password,
            'insurance.document.parser', 'create',
            [{
                'name': f"Test OCR — {filename}",
                'state': 'pending',
                'attachment_id': attachment_id,
            }]
        )
        print(f"  Created insurance.document.parser ID: {parser_id}")
        
        # Link attachment to parser record
        models.execute_kw(
            db, uid, password,
            'ir.attachment', 'write',
            [[attachment_id], {'res_id': parser_id}]
        )
        
        # Trigger simulated OCR extraction
        print("  Running simulated OCR extraction...")
        action_result = models.execute_kw(
            db, uid, password,
            'insurance.document.parser', 'action_test_ocr',
            [[parser_id]]
        )
        
        # Fetch the created policy ID
        parser_data = models.execute_kw(
            db, uid, password,
            'insurance.document.parser', 'read',
            [[parser_id]],
            {'fields': ['policy_id']}
        )
        policy_id = parser_data[0]['policy_id']
        print(f"  OCR Finished. Created Policy ID: {policy_id}")
        
    except Exception as e:
        print(f"  Error importing/parsing {filename}: {e}")

print("\nImport and OCR simulation run finished successfully!")
