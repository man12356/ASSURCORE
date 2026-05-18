import xmlrpc.client

for port in [8070, 8071]:
    url = f"http://localhost:{port}"
    print(f"\n--- Probing {url} ---")
    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        uid = common.authenticate("assurcore_db", "admin", "admin", {})
        if not uid:
            print("  Authentication failed (check DB name, username, or password).")
            continue
        print(f"  Authenticated successfully! UID: {uid}")
        
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        langs = models.execute_kw(
            "assurcore_db", uid, "admin",
            "res.lang", "search_read",
            [[("active", "=", True)]],
            {"fields": ["code", "name"]}
        )
        print(f"  Active languages in DB: {langs}")
        
        admin_info = models.execute_kw(
            "assurcore_db", uid, "admin",
            "res.users", "search_read",
            [[("id", "=", uid)]],
            {"fields": ["lang"]}
        )
        print(f"  Admin User Language: {admin_info[0]['lang']}")
    except Exception as e:
        print(f"  Connection/RPC error on port {port}: {e}")
