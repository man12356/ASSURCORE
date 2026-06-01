with open("d:\\Robot\\ASSURPROD\\import_assurcore_v2.log", "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if "v2" in line or "Phase 2" in line or "AssurCore ETL" in line or "BILAN FINAL" in line:
            print(f"Line {i}: {line.strip()}")
