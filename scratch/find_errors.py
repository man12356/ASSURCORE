with open("d:\\Robot\ASSURPROD\\import_assurcore_v2.log", "r", encoding="utf-8") as f:
    for line in f:
        if "ERROR" in line or "Erreur" in line or "Exception" in line or "ValueError" in line:
            print(line.strip())
