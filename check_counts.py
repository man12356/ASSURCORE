# Check counts
settlements = env['insurance.settlement'].search_count([])
invoices = env['account.move'].search_count([('move_type', '=', 'out_invoice')])
print(f'Settlements count: {settlements}')
print(f'Invoices count: {invoices}')
