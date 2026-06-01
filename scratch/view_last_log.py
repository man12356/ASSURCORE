with open("d:\\Robot\\ASSURPROD\\import_assurcore_v2.log", "r", encoding="utf-8") as f:
    lines = f.readlines()
for line in lines[-50:]:
    print(line, end="")
