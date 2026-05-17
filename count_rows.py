import os
import glob

files = glob.glob('d:/Robot/ASSURPROD/DATA_TEST/*.tsv')
for f in files:
    try:
        with open(f, encoding='utf-8', errors='replace') as fp:
            count = sum(1 for line in fp) - 1
        basename = os.path.basename(f)
        if count > 0:
            print(f"{basename:40} : {count:6} rows")
    except Exception as e:
        print(f"Error reading {f}: {e}")
