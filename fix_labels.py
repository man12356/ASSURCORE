import re
import glob

def repl(m):
    return f'<span class="o_form_label">{m.group(1)}</span>'

for fpath in glob.glob(r'd:\Robot\ASSURPROD\assurcore\views\*.xml'):
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = re.sub(r'<label\s+string="([^"]+)"\s*/>', repl, content)
    if new_content != content:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed labels in {fpath}")
