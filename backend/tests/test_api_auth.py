"""Auth + permissions + org isolation API tests."""
from __future__ import annotations

from tests.conftest import auth_headers


class TestAuth:
    def test_register_and_login(self, client):
        r = client.post("/auth/register", json={
            "email": "new@radartest.fr", "password": "Str0ngPass!", "organization_name": "Nova"})
        assert r.status_code == 201
        assert r.json()["access_token"]

        r = client.post("/auth/login", json={"email": "new@radartest.fr", "password": "Str0ngPass!"})
        assert r.status_code == 200
        assert r.json()["refresh_token"]

    def test_duplicate_email(self, client, demo_user):
        r = client.post("/auth/register", json={"email": demo_user["email"], "password": "Str0ngPass!"})
        assert r.status_code == 400
        assert "existe" in r.json()["detail"]

    def test_wrong_password(self, client, demo_user):
        r = client.post("/auth/login", json={"email": demo_user["email"], "password": "wrong"})
        assert r.status_code == 401

    def test_weak_password(self, client):
        r = client.post("/auth/register", json={"email": "w@radartest.fr", "password": "short"})
        assert r.status_code == 422

    def test_refresh(self, client, demo_user):
        login = client.post("/auth/login", json={"email": demo_user["email"], "password": "Str0ngPassword!"})
        refresh = login.json()["refresh_token"]
        r = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_invalid_token_rejected(self, client):
        r = client.get("/auth/me", headers=auth_headers("garbage.token.value"))
        assert r.status_code == 401

    def test_me_no_auth(self, client):
        assert client.get("/auth/me").status_code == 401

    def test_me_and_org(self, client, demo_user):
        me = client.get("/auth/me", headers=auth_headers(demo_user["token"])).json()
        assert me["email"] == demo_user["email"]
        org = client.get("/auth/me/org", headers=auth_headers(demo_user["token"])).json()
        assert org["name"] == "ACME"

    def test_forgot_password_unknown_email_no_leak(self, client):
        r = client.post("/auth/forgot-password", json={"email": "absent@radartest.fr"})
        assert r.status_code == 200

    def test_reset_password_full_flow(self, client):
        reg = client.post("/auth/register", json={
            "email": "reset@radartest.fr", "password": "OldPassword1!", "organization_name": "R"})
        assert reg.status_code == 201
        from app.core import security
        from app.core.db import SessionLocal
        from app.models import User

        db = SessionLocal()
        user = db.query(User).filter(User.email == "reset@radartest.fr").first()
        token = security.create_password_reset_token(user.id)
        db.close()

        r = client.post("/auth/reset-password", json={"token": token, "new_password": "NewPassword2!"})
        assert r.status_code == 200
        r = client.post("/auth/login", json={"email": "reset@radartest.fr", "password": "NewPassword2!"})
        assert r.status_code == 200

    def test_verify_email(self, client):
        reg = client.post("/auth/register", json={
            "email": "verify@radartest.fr", "password": "Str0ngPass!", "organization_name": "V"})
        assert reg.status_code == 201
        from app.core import security
        from app.core.db import SessionLocal
        from app.models import User

        db = SessionLocal()
        user = db.query(User).filter(User.email == "verify@radartest.fr").first()
        token = security.create_email_token(user.id)
        db.close()
        r = client.post("/auth/verify-email", json={"token": token})
        assert r.status_code == 200
        db = SessionLocal()
        assert db.query(User).filter(User.id == user.id).first().email_verified_at is not None
        db.close()

    def test_password_change(self, client, demo_user):
        r = client.post("/auth/me/password",
                        headers=auth_headers(demo_user["token"]),
                        json={"current_password": "Str0ngPassword!", "new_password": "NewStr0ngPass!"})
        assert r.status_code == 200
        r = client.post("/auth/login", json={"email": demo_user["email"], "password": "NewStr0ngPass!"})
        assert r.status_code == 200

    def test_weak_password_change_rejected(self, client, demo_user):
        r = client.post("/auth/me/password",
                        headers=auth_headers(demo_user["token"]),
                        json={"current_password": "Str0ngPassword!", "new_password": "tiny"})
        assert r.status_code == 422


class TestOrgIsolation:
    def _register(self, client, email):
        r = client.post("/auth/register", json={"email": email, "password": "Str0ngPass!",
                                                "organization_name": f"Org-{email}"})
        assert r.status_code == 201
        return r.json()["access_token"]

    def test_product_ownership(self, client, demo_user):
        token_a = demo_user["token"]
        token_b = self._register(client, "b@radartest.fr")

        r = client.post("/products", headers=auth_headers(token_a),
                        json={"url": "https://a.test/shared", "name": "Produit A", "competitor_name": "C"})
        product_id = r.json()["id"]

        # org B cannot see/read/delete org A's product
        assert client.get("/products", headers=auth_headers(token_b)).json() == []
        assert client.get(f"/products/{product_id}", headers=auth_headers(token_b)).status_code == 404
        assert client.delete(f"/products/{product_id}", headers=auth_headers(token_b)).status_code == 404
        assert client.patch(f"/products/{product_id}", headers=auth_headers(token_b),
                            json={"name": "hijack"}).status_code == 404

    def test_changes_isolation(self, client, demo_user):
        token_b = self._register(client, "c@radartest.fr")
        assert client.get("/changes", headers=auth_headers(token_b)).json() == []

    def test_competitor_isolation(self, client, demo_user):
        token_b = self._register(client, "d@radartest.fr")
        comps = client.get("/competitors", headers=auth_headers(token_b)).json()
        assert comps == []

    def test_add_product_with_other_org_competitor(self, client, demo_user):
        token_b = self._register(client, "e@radartest.fr")
        client.post("/products", headers=auth_headers(demo_user["token"]),
                    json={"url": "https://a.test/shared", "name": "Produit A", "competitor_name": "CA"})
        comp_a = client.get("/competitors", headers=auth_headers(demo_user["token"])).json()[0]
        r = client.post("/products", headers=auth_headers(token_b), json={
            "url": "https://e.test/x", "name": "X", "competitor_id": comp_a["id"]})
        assert r.status_code == 400
        assert "concurrent invalide" in r.json()["detail"]


class TestAdminGuard:
    def test_non_admin_forbidden(self, client, demo_user):
        assert client.get("/admin/stats", headers=auth_headers(demo_user["token"])).status_code == 403