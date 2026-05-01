"""Логин с .local доменом и патч факультета через API."""

from app.services import users_service


def test_login_koord_local(client):
    """EmailStr раньше ломался на @koord.local."""
    users_service.create_user("u@koord.local", "KoordPw123987", "user")
    r = client.post(
        "/api/auth/login",
        json={"email": "u@koord.local", "password": "KoordPw123987"},
    )
    assert r.status_code == 200, r.text
    assert "access_token" in r.json()


def test_faculty_via_admin_api(client, admin_headers):
    users_service.create_user("coord@test.local", "CoordPw123098", "user")
    patch = client.patch(
        "/api/admin/users/coord@test.local/faculty",
        json={"faculty": "ИТиАБД"},
        headers=admin_headers,
    )
    assert patch.status_code == 200, patch.text
    me = users_service.get_user("coord@test.local")
    assert me is not None
    assert me["faculty"] == "ИТиАБД"

    patch_clear = client.patch(
        "/api/admin/users/coord@test.local/faculty",
        json={"faculty": None},
        headers=admin_headers,
    )
    assert patch_clear.status_code == 200
    assert users_service.get_user("coord@test.local")["faculty"] is None


def test_faculty_unknown_rejected(client, admin_headers):
    users_service.create_user("x@test.local", "XPw098765439", "user")
    r = client.patch(
        "/api/admin/users/x@test.local/faculty",
        json={"faculty": "НЕСУЩЕСТВУЕТ"},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_admin_users_requires_auth(client):
    r = client.get("/api/admin/users")
    assert r.status_code in (401, 403)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
