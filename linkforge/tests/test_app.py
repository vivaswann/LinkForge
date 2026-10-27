"""Small API tests. Install pytest and httpx to run them."""
from fastapi.testclient import TestClient

import app as app_module


def setup_function():
    # Use a fresh database file for each test.
    if app_module.DB_PATH.exists():
        app_module.DB_PATH.unlink()
    app_module.init_db()


def test_create_and_redirect_increments_click_count():
    with TestClient(app_module.app) as client:
        created = client.post("/api/links", json={"url": "https://example.com/hello"})
        assert created.status_code == 201
        link = created.json()["link"]
        assert link["code"]
        assert link["clicks"] == 0

        redirected = client.get(f"/{link['code']}", follow_redirects=False)
        assert redirected.status_code == 302
        assert redirected.headers["location"] == "https://example.com/hello"

        listing = client.get("/api/links").json()
        assert listing["total_clicks"] == 1
        assert listing["links"][0]["clicks"] == 1


def test_custom_alias_and_duplicate_alias():
    with TestClient(app_module.app) as client:
        first = client.post(
            "/api/links", json={"url": "https://example.com", "custom_alias": "my-demo"}
        )
        assert first.status_code == 201
        assert first.json()["link"]["code"] == "my-demo"

        duplicate = client.post(
            "/api/links", json={"url": "https://another.example", "custom_alias": "my-demo"}
        )
        assert duplicate.status_code == 409


def test_dashboard_and_static_assets_load():
    with TestClient(app_module.app) as client:
        page = client.get("/")
        css = client.get("/static/styles.css")
        script = client.get("/static/app.js")
        assert page.status_code == 200
        assert "LinkForge" in page.text
        assert css.status_code == 200
        assert script.status_code == 200


def test_rejects_incomplete_url():
    with TestClient(app_module.app) as client:
        response = client.post("/api/links", json={"url": "example.com/no-scheme"})
        assert response.status_code == 422


def test_delete_link():
    with TestClient(app_module.app) as client:
        created = client.post("/api/links", json={"url": "https://example.com"})
        code = created.json()["link"]["code"]
        deleted = client.delete(f"/api/links/{code}")
        assert deleted.status_code == 204
        assert client.get(f"/api/links/{code}").status_code == 404


def test_configured_public_base_url(monkeypatch):
    monkeypatch.setenv("LINKFORGE_BASE_URL", "https://links.example.com/")
    with TestClient(app_module.app) as client:
        created = client.post("/api/links", json={"url": "https://example.com", "custom_alias": "verysafelink"})
        assert created.status_code == 201
        assert created.json()["link"]["short_url"] == "https://links.example.com/verysafelink"
        assert client.get("/api/config").json()["base_url"] == "https://links.example.com"
