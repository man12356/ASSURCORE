import os

tsv_path = 'd:/Robot/ASSURPROD/DATA_REEL_22-05-2026/DATA_REEL/PR_SINISTRE_DATA_TABLE.tsv'
with open(tsv_path, encoding='utf-8', errors='replace') as f:
    headers = [h.strip().strip('"') for h in f.readline().split('\t')]
    
    col_indices = {
        'TYPE_SINISTRE': headers.index('TYPE_SINISTRE'),
        'BRIS_DE_GLACES': headers.index('BRIS_DE_GLACES'),
        'VOL_INCENDIE': headers.index('VOL_INCENDIE'),
        'NUM_SINISTRE': headers.index('NUM_SINISTRE')
    }
    
    data = []
    for line in f:
        parts = [p.strip().strip('"') for p in line.split('\t')]
        if len(parts) > max(col_indices.values()):
            row_dict = {k: parts[idx] for k, idx in col_indices.items()}
            data.append(row_dict)

print(f"Total lines read: {len(data)}")
for col in ['TYPE_SINISTRE', 'BRIS_DE_GLACES', 'VOL_INCENDIE']:
    unique_vals = set(r[col] for r in data)
    print(f"Unique values for {col}: {unique_vals}")
    
print("\nFirst 10 rows:")
for r in data[:10]:
    print(r)
