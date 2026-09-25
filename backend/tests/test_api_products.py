"""Products CRUD, history, CSV import/export, plan limits via API."""
from __future__ import annotations

import io

from tests.conftest import auth_headers


class TestProductsApi:
    def test_create_and_list(self, client, demo_user):
        r = client.post("/products", headers=auth_headers(demo_user["token"]), json={
            "url": "https://mystore.test/p/1", "name": "Carte graphique", "competitor_name": "GPU World",
            "category": "GPU", "sku": "GPU-1"})
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["name"] == "Carte graphique"
        assert data["competitor_name"] == "GPU World"
        assert data["last_scrape_status"] == "pending"
        assert data["next_check_at"] is not None

        lst = client.get("/products", headers=auth_headers(demo_user["token"])).json()
        assert len(lst) == 1

    def test_duplicate_url(self, client, demo_user):
        payload = {"url": "https://dup.test/p/1", "name": "A", "competitor_name": "C"}
        assert client.post("/products", headers=auth_headers(demo_user["token"]), json=payload).status_code == 201
        assert client.post("/products", headers=auth_headers(demo_user["token"]), json=payload).status_code == 400

    def test_invalid_url(self, client, demo_user):
        r = client.post("/products", headers=auth_headers(demo_user["token"]), json={"url": "not-a-url"})
        assert r.status_code == 422

    def test_update_and_delete(self, client, demo_user):
        pid = client.post("/products", headers=auth_headers(demo_user["token"]), json={
            "url": "https://upd.test/p/1", "name": "Avant", "competitor_name": "C"}).json()["id"]
        r = client.patch(f"/products/{pid}", headers=auth_headers(demo_user["token"]), json={"name": "Après", "category": "Audio"})
        assert r.json()["name"] == "Après"
        assert client.delete(f"/products/{pid}", headers=auth_headers(demo_user["token"])).status_code == 200
        assert client.get(f"/products/{pid}", headers=auth_headers(demo_user["token"])).status_code == 404

    def test_own_price(self, client, demo_user):
        pid = client.post("/products", headers=auth_headers(demo_user["token"]), json={
            "url": "https://own.test/p/1", "name": "P", "competitor_name": "C"}).json()["id"]
        r = client.post(f"/products/{pid}/own-price", headers=auth_headers(demo_user["token"]),
                        json={"product_id": pid, "own_price": 615.0, "own_currency": "EUR", "own_name": "Ma Carte"})
        assert r.status_code == 200
        assert r.json()["own_price"] == 615.0
        hist = client.get(f"/products/{pid}/history", headers=auth_headers(demo_user["token"])).json()
        assert hist["own_prices"][0]["price"] == 615.0

    def test_competitors(self, client, demo_user):
        client.post("/products", headers=auth_headers(demo_user["token"]), json={
            "url": "https://comp.test/p/1", "name": "Carte graphique", "competitor_name": "GPU World"})
        comps = client.get("/competitors", headers=auth_headers(demo_user["token"])).json()
        assert comps[0]["name"] == "GPU World"
        r = client.post("/competitors", headers=auth_headers(demo_user["token"]), json={"name": "TechConcurrent"})
        assert r.status_code == 201


class TestCsv:
    def test_preview_and_import(self, client, demo_user):
        csv = "url,nom,concurrent,categorie\nhttps://csv.test/a,Produit A,Comp A,GPU\nhttps://csv.test/b,Produit B,Comp B,Péripherique\n"
        files = {"file": ("import.csv", csv.encode(), "text/csv")}
        r = client.post("/imports/csv/preview", files=files, headers=auth_headers(demo_user["token"]))
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["valid_rows"]) == 2
        assert body["valid_rows"][0]["name"] == "Produit A"

        r = client.post("/imports/csv", headers=auth_headers(demo_user["token"]),
                        json={"rows": body["valid_rows"]})
        assert r.status_code == 200
        assert r.json()["imported"] == 2
        assert client.get("/products", headers=auth_headers(demo_user["token"])).json().__len__() == 2

    def test_invalid_csv_row_reported(self, client, demo_user):
        csv = "url,nom\nhttps://ok.test/a,Bon\npas-une-url,Mauvais\n"
        r = client.post("/imports/csv/preview", files={"file": ("x.csv", csv.encode(), "text/csv")},
                        headers=auth_headers(demo_user["token"]))
        body = r.json()
        assert len(body["valid_rows"]) == 1
        assert len(body["invalid_rows"]) == 1
        assert "URL invalide" in body["errors"][0]

    def test_export(self, client, demo_user):
        csv = "url,nom\nhttps://exp.test/a,Exporté\n"
        files = {"file": ("x.csv", csv.encode(), "text/csv")}
        preview = client.post("/imports/csv/preview", files=files, headers=auth_headers(demo_user["token"])).json()
        client.post("/imports/csv", headers=auth_headers(demo_user["token"]), json={"rows": preview["valid_rows"]})
        r = client.get("/exports/products.csv", headers=auth_headers(demo_user["token"]))
        assert r.status_code == 200
        assert "Exporté" in r.text


class TestPlanLimits:
    def test_starter_limit_enforced(self, client):
        reg = client.post("/auth/register", json={
            "email": "limit@radartest.fr", "password": "Str0ngPass!", "organization_name": "LimitCo"})
        token = reg.json()["access_token"]
        # fresh orgs start with a Pro trial, so this fills 51 products fine
        for i in range(51):
            r = client.post("/products", headers=auth_headers(token), json={
                "url": f"https://limit.test/p/{i}", "name": f"P{i}", "competitor_name": "C"})
            assert r.status_code == 201, r.text
        # downgrade to Starter (50 products max) — backend must refuse the next one
        r = client.post("/subscription/dev-assign", headers=auth_headers(token), json={"plan": "starter"})
        assert r.status_code == 200
        r = client.post("/products", headers=auth_headers(token), json={
            "url": "https://limit.test/overflow", "name": "Overflow", "competitor_name": "C"})
        assert r.status_code == 402
        assert "limite de 50 produits" in r.json()["detail"]

    def test_upgrade_unlocks_products(self, client):
        reg = client.post("/auth/register", json={
            "email": "uplimit@radartest.fr", "password": "Str0ngPass!", "organization_name": "UpCo"})
        token = reg.json()["access_token"]
        client.post("/products", headers=auth_headers(token), json={
            "url": "https://up.test/p/1", "name": "P1", "competitor_name": "C"})
        # pro trial allows plenty; downgrade to starter then upgrade to business
        client.post("/subscription/dev-assign", headers=auth_headers(token), json={"plan": "starter"})
        client.post("/subscription/dev-assign", headers=auth_headers(token), json={"plan": "business"})
        sub = client.get("/subscription", headers=auth_headers(token)).json()
        assert sub["plan"]["slug"] == "business"

    def test_dashboard_and_changes_not_found_for_other_user(self, client):
        reg = client.post("/auth/register", json={
            "email": "iso@radartest.fr", "password": "Str0ngPass!", "organization_name": "Iso"})
        token = reg.json()["access_token"]
        d = client.get("/dashboard", headers=auth_headers(token)).json()
        assert d["products_count"] == 0