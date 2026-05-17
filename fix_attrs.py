import re
import glob

def fix_view_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    def repl(m):
        s = m.group(1).replace(' ', '')
        if "'invisible':[('policy_count','=',0)]" in s: return 'invisible="policy_count == 0"'
        if "'invisible':[('receipt_count','=',0)]" in s: return 'invisible="receipt_count == 0"'
        if "'invisible':[('impaye_count','=',0)]" in s: return 'invisible="impaye_count == 0"'
        if "'invisible':[('claim_count','=',0)]" in s: return 'invisible="claim_count == 0"'
        if "'invisible':[('total_encaisse_ytd','=',0)]" in s: return 'invisible="total_encaisse_ytd == 0"'
        if "'invisible':[('client_state','!=','vip')]" in s: return 'invisible="client_state != \'vip\'"'
        if "'invisible':[('client_state','!=','resilie')]" in s: return 'invisible="client_state != \'resilie\'"'
        if "'invisible':[('solde_caisse_consolide','=',0)]" in s: return 'invisible="solde_caisse_consolide == 0"'
        if "'invisible':[('solde_caisse_consolide','>=',0)]" in s: return 'invisible="solde_caisse_consolide &gt;= 0"'
        if "'invisible':[('solde_caisse_consolide','<',0)]" in s: return 'invisible="solde_caisse_consolide &lt; 0"'
        if "'invisible':[('is_payer','=',False)]" in s: return 'invisible="not is_payer"'
        if "'invisible':[('is_company','=',False)]" in s: return 'invisible="not is_company"'
        if "'invisible':[('is_payer','=',True)],'required':False" in s: return 'invisible="is_payer"'
        return m.group(0)

    new_content = re.sub(r'attrs=\"([^\"]+)\"', repl, content)
    
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {file_path}")

for f in glob.glob(r'd:\Robot\ASSURPROD\assurcore\views\*.xml'):
    fix_view_file(f)

