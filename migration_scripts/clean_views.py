import subprocess

script = """
views = env['ir.ui.view'].search([('model', '=', 'res.partner'), ('arch_db', 'ilike', 'sale_order_count')])
print('Found sale_order_count res.partner views:', len(views))
views.unlink()
env.cr.commit()

views_team = env['ir.ui.view'].search([('arch_db', 'ilike', 'team_id'), ('model', 'in', ['account.move', 'res.partner'])])
print('Found team_id views:', len(views_team))
views_team.unlink()
env.cr.commit()
"""

print("Cleaning up Odoo views inside assurcore_web container...")
res = subprocess.run(
    ["docker", "exec", "-i", "assurcore_web", "odoo", "shell", "-d", "assurcore_db", "--no-http"],
    input=script,
    capture_output=True,
    text=True
)

print("STDOUT:")
print(res.stdout)
print("STDERR:")
print(res.stderr)
print("Exit Code:", res.returncode)
