import xmlrpc.client

url = 'http://localhost:8071'
db = 'assurcore_db'
username = 'admin'
password = 'admin'

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

print("Installing French (fr_FR) language...")
try:
    wizard_id = models.execute_kw(
        db, uid, password,
        'base.language.install', 'create',
        [{'lang': 'fr_FR', 'overwrite': True}]
    )
    models.execute_kw(
        db, uid, password,
        'base.language.install', 'lang_install',
        [wizard_id]
    )
    print("French installed successfully!")
except Exception as e:
    print("Error installing French:", e)

try:
    lang_ids = models.execute_kw(
        db, uid, password,
        'res.lang', 'search',
        [[('code', '=', 'fr_FR')]]
    )
    if lang_ids:
        models.execute_kw(
            db, uid, password,
            'res.lang', 'write',
            [lang_ids, {'active': True}]
        )
        print("French language marked as active.")
except Exception as e:
    print("Error activating French:", e)

try:
    user_ids = models.execute_kw(
        db, uid, password,
        'res.users', 'search',
        [[]]
    )
    if user_ids:
        models.execute_kw(
            db, uid, password,
            'res.users', 'write',
            [user_ids, {'lang': 'fr_FR'}]
        )
        print("Updated all users language to French (fr_FR).")
        
    partner_ids = models.execute_kw(
        db, uid, password,
        'res.partner', 'search',
        [[]]
    )
    if partner_ids:
        models.execute_kw(
            db, uid, password,
            'res.partner', 'write',
            [partner_ids, {'lang': 'fr_FR'}]
        )
        print("Updated all partners language to French (fr_FR).")
except Exception as e:
    print("Error setting users/partners language:", e)

