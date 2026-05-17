import ast
import re
import glob

def convert_domain_to_expr(domain):
    if isinstance(domain, bool):
        return str(domain)
    exprs = []
    i = 0
    while i < len(domain):
        item = domain[i]
        if item == '|':
            t1 = domain[i+1]
            t2 = domain[i+2]
            def fmt(t):
                f, o, v = t
                if o == '=': o = '=='
                if isinstance(v, str): v = f"'{v}'"
                return f"{f} {o} {v}"
            exprs.append(f"({fmt(t1)} or {fmt(t2)})")
            i += 3
            continue
        
        f, o, v = item
        if o == '=': o = '=='
        if isinstance(v, str): v = f"'{v}'"
        exprs.append(f"{f} {o} {v}")
        i += 1
    return " and ".join(exprs)

for file_path in glob.glob(r'd:\Robot\ASSURPROD\assurcore\views\*.xml'):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    def repl(m):
        attr_dict_str = m.group(1).replace('&lt;', '<').replace('&gt;', '>')
        try:
            attr_dict = ast.literal_eval(attr_dict_str)
            result = []
            if 'invisible' in attr_dict:
                expr = convert_domain_to_expr(attr_dict['invisible'])
                expr = expr.replace('<', '&lt;').replace('>', '&gt;')
                result.append(f'invisible="{expr}"')
            if 'required' in attr_dict:
                val = attr_dict['required']
                if isinstance(val, bool):
                    result.append(f'required="{val}"')
                else:
                    expr = convert_domain_to_expr(val)
                    expr = expr.replace('<', '&lt;').replace('>', '&gt;')
                    result.append(f'required="{expr}"')
            if 'readonly' in attr_dict:
                val = attr_dict['readonly']
                if isinstance(val, bool):
                    result.append(f'readonly="{val}"')
                else:
                    expr = convert_domain_to_expr(val)
                    expr = expr.replace('<', '&lt;').replace('>', '&gt;')
                    result.append(f'readonly="{expr}"')
            return " ".join(result)
        except Exception as e:
            print(f"Error on {attr_dict_str}: {e}")
            return m.group(0)

    new_content = re.sub(r'attrs="([^"]+)"', repl, content)
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Migrated {file_path}")
