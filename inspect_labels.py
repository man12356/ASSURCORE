import os
import re

models_dir = r"d:\Robot\ASSURPROD\assurcore\models"
output_file = r"d:\Robot\ASSURPROD\labels_report.txt"

with open(output_file, 'w', encoding='utf-8') as out:
    for filename in os.listdir(models_dir):
        if not filename.endswith('.py'):
            continue
        filepath = os.path.join(models_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        matches = re.findall(r"(\w+)\s*=\s*fields\.\w+\([\s\S]*?string\s*=\s*(['\"])(.*?)\2", content)
        out.write(f"\n================ {filename} ================\n")
        for m in matches:
            field_name = m[0]
            label = m[2]
            out.write(f"  {field_name}: {label}\n")

print("Labels report written successfully!")
