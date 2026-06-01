with open("d:\\Robot\\ASSURPROD\\import_assurcore_v2.log", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "type_client_assur" in line:
        # print some context
        start = max(0, i - 2)
        end = min(len(lines), i + 3)
        print(f"--- Match at line {i} ---")
        for j in range(start, end):
            print(f"{j}: {lines[j]}", end="")
