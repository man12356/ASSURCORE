import os

for root, dirs, files in os.walk("d:\\Robot\\ASSURPROD"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, 1):
                        if "type_client_assur" in line:
                            print(f"{path}:{line_no}: {line.strip()}")
            except Exception as e:
                pass
