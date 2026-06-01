import os
import glob

test_dir = 'd:/Robot/ASSURPROD/DATA_TEST'
reel_dir = 'd:/Robot/ASSURPROD/DATA_REEL_22-05-2026/DATA_REEL'

test_files = glob.glob(os.path.join(test_dir, '*.tsv'))
reel_files = glob.glob(os.path.join(reel_dir, '*.tsv'))

test_basenames = {os.path.basename(f) for f in test_files}
reel_basenames = {os.path.basename(f) for f in reel_files}

print("=== FILE COMPARISON ===")
only_in_test = test_basenames - reel_basenames
only_in_reel = reel_basenames - test_basenames
common_files = test_basenames & reel_basenames

print(f"Total TSV in DATA_TEST: {len(test_files)}")
print(f"Total TSV in DATA_REEL: {len(reel_files)}")
if only_in_test:
    print(f"Files only in DATA_TEST ({len(only_in_test)}): {sorted(only_in_test)}")
if only_in_reel:
    print(f"Files only in DATA_REEL ({len(only_in_reel)}): {sorted(only_in_reel)}")

print("\n=== COLUMN SCHEMA COMPARISON ===")
for fname in sorted(common_files):
    test_path = os.path.join(test_dir, fname)
    reel_path = os.path.join(reel_dir, fname)
    
    with open(test_path, encoding='utf-8', errors='replace') as f:
        l = f.readline()
        test_headers = [h.strip().strip('"') for h in l.split('\t')] if l else []
        
    with open(reel_path, encoding='utf-8', errors='replace') as f:
        l = f.readline()
        reel_headers = [h.strip().strip('"') for h in l.split('\t')] if l else []
        
    if test_headers != reel_headers:
        test_set = set(test_headers)
        reel_set = set(reel_headers)
        added = reel_set - test_set
        removed = test_set - reel_set
        
        print(f"\nDifferences in {fname}:")
        if added:
            print(f"  Added columns: {added}")
        if removed:
            print(f"  Removed columns: {removed}")
        if not added and not removed:
            print(f"  Same columns but different order:")
            print(f"    DATA_TEST: {test_headers}")
            print(f"    DATA_REEL: {reel_headers}")
            
print("\n=== ROW COUNTS COMPARISON FOR COMMON FILES ===")
for fname in sorted(common_files):
    test_path = os.path.join(test_dir, fname)
    reel_path = os.path.join(reel_dir, fname)
    
    with open(test_path, encoding='utf-8', errors='replace') as f:
        test_rows = sum(1 for _ in f) - 1
    with open(reel_path, encoding='utf-8', errors='replace') as f:
        reel_rows = sum(1 for _ in f) - 1
        
    if test_rows != reel_rows:
        print(f"  {fname:<40} | DATA_TEST: {test_rows:<6} | DATA_REEL: {reel_rows:<6} | Diff: {reel_rows - test_rows}")
