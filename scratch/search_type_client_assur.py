with open("d:\\Robot\\ASSURPROD\\import_assurcore_v2.log", "r", encoding="utf-8") as f:
    for line in f:
        if "type_client_assur" in line:
            print(line.strip())
