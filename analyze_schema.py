import os
import glob
import json

files = glob.glob('d:/Robot/ASSURPROD/DATA_TEST/*.tsv')
analysis = {}

for f in files:
    try:
        with open(f, encoding='utf-8', errors='replace') as fp:
            lines = fp.readlines()
            headers = lines[0].strip().split('\t') if lines else []
            count = max(0, len(lines) - 1)
            
        basename = os.path.basename(f).replace('_DATA_TABLE.tsv', '')
        analysis[basename] = {
            'rows': count,
            'headers': [h.strip('"') for h in headers]
        }
    except Exception as e:
        print(f"Error reading {f}: {e}")

with open('d:/Robot/ASSURPROD/schema_analysis.json', 'w', encoding='utf-8') as out:
    json.dump(analysis, out, indent=2)

print(f"Analysis saved to schema_analysis.json with {len(analysis)} tables.")
