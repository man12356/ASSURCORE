# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger('assurcore.configure_accounting')

company = self.env.company
print(f"Configuring accounting for company: {company.name} (ID: {company.id})")

# 1. Create Tunisian specific accounts if they don't exist
accounts_data = [
    {
        'code': '706000',
        'name': 'Produits assurance (primes nettes)',
        'account_type': 'income',
    },
    {
        'code': '706100',
        'name': 'Honoraires de courtage d\'assurance',
        'account_type': 'income',
    },
    {
        'code': '445710',
        'name': 'Etat - TVA collectée 7%',
        'account_type': 'liability_current',
    },
    {
        'code': '447100',
        'name': 'Etat - Timbre fiscal d\'assurance',
        'account_type': 'liability_current',
    }
]

created_accounts = {}
for acc_info in accounts_data:
    code = acc_info['code']
    existing = self.env['account.account'].search([
        ('code', '=', code),
        ('company_id', '=', company.id)
    ], limit=1)
    
    if existing:
        print(f"Account {code} ({existing.name}) already exists.")
        created_accounts[code] = existing
    else:
        new_acc = self.env['account.account'].create({
            'code': code,
            'name': acc_info['name'],
            'account_type': acc_info['account_type'],
            'company_id': company.id,
        })
        print(f"Created account {code}: {new_acc.name}")
        created_accounts[code] = new_acc

# 2. Configure Taxes repartition lines to post to these accounts
tva_tax = self.env['account.tax'].search([
    ('name', 'like', 'TVA Courtage Assurance 7% TN'),
    ('company_id', '=', company.id)
], limit=1)

tf_tax = self.env['account.tax'].search([
    ('name', 'like', 'Timbre Fiscal TN — Assurance'),
    ('company_id', '=', company.id)
], limit=1)

if tva_tax:
    print(f"Found TVA tax: {tva_tax.name}")
    rep_lines = tva_tax.invoice_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax')
    if rep_lines and created_accounts.get('445710'):
        rep_lines.write({'account_id': created_accounts['445710'].id})
        print("Linked TVA tax to account 445710.")
        
if tf_tax:
    print(f"Found Timbre Fiscal tax: {tf_tax.name}")
    rep_lines = tf_tax.invoice_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax')
    if rep_lines and created_accounts.get('447100'):
        rep_lines.write({'account_id': created_accounts['447100'].id})
        print("Linked Timbre Fiscal tax to account 447100.")

# 3. Create or configure Treasury Journals (Caisse Espèces, Banque BIAT, etc.)
journals_data = [
    {
        'name': 'Caisse AssurCore',
        'code': 'CAASS',
        'type': 'cash',
    },
    {
        'name': 'Banque BIAT AssurCore',
        'code': 'BIATA',
        'type': 'bank',
    }
]

for jr_info in journals_data:
    existing = self.env['account.journal'].search([
        ('code', '=', jr_info['code']),
        ('company_id', '=', company.id)
    ], limit=1)
    
    if existing:
        print(f"Journal {jr_info['code']} ({existing.name}) already exists.")
    else:
        new_jr = self.env['account.journal'].create({
            'name': jr_info['name'],
            'code': jr_info['code'],
            'type': jr_info['type'],
            'company_id': company.id,
            'currency_id': self.env.ref('base.TND').id,
        })
        print(f"Created journal {jr_info['code']}: {new_jr.name}")

# Commit the transaction
self.env.cr.commit()
print("Accounting configuration completed successfully!")
