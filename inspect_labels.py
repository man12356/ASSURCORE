import os
import re

models_dir = r"d:\Robot\ASSURPROD\addons\assurcore\models"
for filename in os.listdir(models_dir):
    if not filename.endswith('.py'):
        continue
    filepath = os.path.join(models_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    matches = re.findall(r"string\s*=\s*(['\"])(.*?)\1", content)
    for m in matches:
        label = m[2-1]
        print(f"{filename}: {label}")
