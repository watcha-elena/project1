def test_admin_module_imports():
    from admin import AdminClient, ADMIN_LOGIN_URL, ADMIN_MOVIES_URL
    client = AdminClient()
    assert not client.logged_in
    assert ADMIN_LOGIN_URL == "https://admin.kubecha.com/brew/session/new"
    assert ADMIN_MOVIES_URL == "https://admin.kubecha.com/brew/galaxy/movies"
