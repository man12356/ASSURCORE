import os

views_dir = "d:\\Robot\\ASSURPROD\\addons\\assurcore\\views"
for file in os.listdir(views_dir):
    if file.endswith(".xml"):
        path = os.path.join(views_dir, file)
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if "<menuitem" in line:
                    print(f"{file}:{line_no}: {line.strip()}")
