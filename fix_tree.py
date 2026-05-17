import glob
import re

for file_path in glob.glob(r'd:\Robot\ASSURPROD\assurcore\views\*.xml') + glob.glob(r'd:\Robot\ASSURPROD\assurcore\models\*.py'):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content
    # For XML <field name="view_mode">list,form</field>
    new_content = re.sub(r'(<field name="view_mode">.*?)list(.*?<\/field>)', r'\1tree\2', new_content)
    # Also handles list in multiple places if any (like list,form,kanban)
    new_content = re.sub(r'(<field name="view_mode">.*?)list(.*?<\/field>)', r'\1tree\2', new_content)

    new_content = new_content.replace("'view_mode': 'list'", "'view_mode': 'tree'")
    new_content = new_content.replace('"view_mode": "list"', '"view_mode": "tree"')
    
    new_content = new_content.replace("'view_mode': 'list,form'", "'view_mode': 'tree,form'")
    new_content = new_content.replace('"view_mode": "list,form"', '"view_mode": "tree,form"')
    
    new_content = new_content.replace("'view_mode': 'list,form,kanban'", "'view_mode': 'tree,form,kanban'")

    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {file_path}")
