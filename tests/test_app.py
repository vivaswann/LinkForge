"""Comprehensive automated tests for LinkForge URL shortener, link management, and analytics."""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi.testclient import TestClient

import app as app_module
from database import DB_PATH, init_db


def setup_function():
    # Use a fresh database for each test.
    import gc
    gc.collect()
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except PermissionError:
            pass
    init_db()
    with app_module.database() as conn:
        conn.execute("DELETE FROM clicks")
        conn.execute("DELETE FROM links")


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

        # Reserved aliases should be rejected
        reserved = client.post(
            "/api/links", json={"url": "https://example.com", "custom_alias": "health"}
        )
        assert reserved.status_code == 422


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
        # Missing scheme
        assert client.post("/api/links", json={"url": "example.com/no-scheme"}).status_code == 422
        # Disallowed scheme
        assert client.post("/api/links", json={"url": "ftp://example.com/files"}).status_code == 422
        # JavaScript scheme
        assert client.post("/api/links", json={"url": "javascript:alert(1)"}).status_code == 422
        # Spaces in URL
        assert client.post("/api/links", json={"url": "https://example.com/has space"}).status_code == 422


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
        created = client.post(
            "/api/links", json={"url": "https://example.com", "custom_alias": "verysafelink"}
        )
        assert created.status_code == 201
        assert created.json()["link"]["short_url"] == "https://links.example.com/verysafelink"
        assert client.get("/api/config").json()["base_url"] == "https://links.example.com"


def test_create_with_optional_fields_and_edit():
    future_time = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(timespec="seconds")
    with TestClient(app_module.app) as client:
        created = client.post(
            "/api/links",
            json={
                "url": "https://example.com/launch",
                "custom_alias": "launch2026",
                "title": "Launch Landing Page",
                "campaign": "q4-promo",
                "expires_at": future_time,
            },
        )
        assert created.status_code == 201
        link = created.json()["link"]
        assert link["title"] == "Launch Landing Page"
        assert link["campaign"] == "q4-promo"
        assert link["expires_at"] is not None
        assert link["status"] == "active"
        assert link["is_expired"] is False

        # Edit link
        updated = client.patch(
            "/api/links/launch2026",
            json={
                "title": "Updated Launch Title",
                "campaign": "holiday-promo",
                "url": "https://example.com/new-dest",
            },
        )
        assert updated.status_code == 200
        up_link = updated.json()["link"]
        assert up_link["title"] == "Updated Launch Title"
        assert up_link["campaign"] == "holiday-promo"
        assert up_link["url"] == "https://example.com/new-dest"


def test_link_expiration_handling():
    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    with TestClient(app_module.app) as client:
        created = client.post(
            "/api/links",
            json={
                "url": "https://example.com/expired-target",
                "custom_alias": "expired-link",
                "expires_at": past_time,
            },
        )
        assert created.status_code == 201
        link = created.json()["link"]
        assert link["status"] == "expired"
        assert link["is_expired"] is True

        # Expired link MUST NOT redirect; it should return 410 Gone with clean expired page
        resp = client.get("/expired-link", follow_redirects=False)
        assert resp.status_code == 410
        assert "This link has expired" in resp.text

        # Click count should remain 0
        get_res = client.get("/api/links/expired-link").json()["link"]
        assert get_res["clicks"] == 0


def test_disabled_links_handling():
    with TestClient(app_module.app) as client:
        created = client.post(
            "/api/links",
            json={"url": "https://example.com/target", "custom_alias": "toggle-me"},
        )
        assert created.status_code == 201

        # Disable link via toggle endpoint
        toggled = client.post("/api/links/toggle-me/toggle")
        assert toggled.status_code == 200
        assert toggled.json()["link"]["is_active"] is False
        assert toggled.json()["link"]["status"] == "disabled"

        # Disabled link returns 403 Forbidden with clean disabled page
        resp = client.get("/toggle-me", follow_redirects=False)
        assert resp.status_code == 403
        assert "This link is temporarily paused" in resp.text

        # Re-activate link
        reactivated = client.post("/api/links/toggle-me/toggle")
        assert reactivated.status_code == 200
        assert reactivated.json()["link"]["is_active"] is True

        # Should redirect now
        redirected = client.get("/toggle-me", follow_redirects=False)
        assert redirected.status_code == 302
        assert redirected.headers["location"] == "https://example.com/target"


def test_click_analytics_and_privacy():
    with TestClient(app_module.app) as client:
        created = client.post(
            "/api/links",
            json={"url": "https://example.com/product", "custom_alias": "metrics-link"},
        )
        assert created.status_code == 201

        # Simulate mobile click with Hacker News referrer
        client.get(
            "/metrics-link",
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                "Referer": "https://news.ycombinator.com/item?id=9999",
            },
            follow_redirects=False,
        )

        # Simulate desktop click with Google referrer
        client.get(
            "/metrics-link",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.google.com/search?q=example",
            },
            follow_redirects=False,
        )

        analytics = client.get("/api/links/metrics-link/analytics").json()
        assert analytics["total_clicks"] == 2
        assert len(analytics["clicks_by_date"]) == 1
        assert analytics["clicks_by_date"][0]["count"] == 2

        # Check devices detection
        device_names = {d["device"] for d in analytics["devices"]}
        assert "Mobile" in device_names
        assert "Desktop" in device_names

        # Check referrers detection
        referrer_names = {r["referrer"] for r in analytics["referrers"]}
        assert "Hacker News" in referrer_names
        assert "Google" in referrer_names

        # Check recent clicks log
        assert len(analytics["recent_clicks"]) == 2

        # Privacy check: Verify no raw IP address is stored in the clicks table
        with app_module.database() as conn:
            cursor = conn.execute("PRAGMA table_info(clicks)")
            columns = [row["name"] for row in cursor.fetchall()]
            assert "ip" not in columns
            assert "ip_address" not in columns


def test_qr_code_generation():
    with TestClient(app_module.app) as client:
        created = client.post(
            "/api/links",
            json={"url": "https://example.com/qr-demo", "custom_alias": "qr-code-test"},
        )
        assert created.status_code == 201

        # Fetch QR preview
        resp = client.get("/api/links/qr-code-test/qr")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")

        # Fetch QR download
        dl_resp = client.get("/api/links/qr-code-test/qr?download=true")
        assert dl_resp.status_code == 200
        assert "attachment" in dl_resp.headers["content-disposition"]
        assert "linkforge-qr-code-test-qr.png" in dl_resp.headers["content-disposition"]


def test_backward_compatible_database_migration():
    """Verify that an existing database with the old schema is migrated safely without data loss."""
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DROP TABLE IF EXISTS clicks")
        conn.execute("DROP TABLE IF EXISTS links")
        conn.execute(
            """
            CREATE TABLE links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                original_url TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 42,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO links (code, original_url, clicks, created_at) VALUES (?, ?, ?, ?)",
            ("verysafelink", "https://example.com/safe", 42, "2024-01-01T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    # Run modern app init_db
    app_module.init_db()

    with TestClient(app_module.app) as client:
        # Existing link must still be present and readable
        resp = client.get("/api/links/verysafelink")
        assert resp.status_code == 200
        link = resp.json()["link"]
        assert link["code"] == "verysafelink"
        assert link["url"] == "https://example.com/safe"
        assert link["clicks"] == 42
        assert link["status"] == "active"

        # Redirecting should continue working and increment clicks to 43
        redir = client.get("/verysafelink", follow_redirects=False)
        assert redir.status_code == 302
        assert redir.headers["location"] == "https://example.com/safe"

        # Verify new count
        updated_link = client.get("/api/links/verysafelink").json()["link"]
        assert updated_link["clicks"] == 43


def test_admin_authentication(monkeypatch):
    monkeypatch.setenv("LINKFORGE_ADMIN_KEY", "super-secret-key-123")
    with TestClient(app_module.app) as client:
        # Unauthenticated link creation must fail with 401
        unauthed = client.post("/api/links", json={"url": "https://example.com/protected"})
        assert unauthed.status_code == 401

        # Header authentication must succeed
        authed_header = client.post(
            "/api/links",
            json={"url": "https://example.com/protected", "custom_alias": "secured-slug"},
            headers={"X-Admin-Key": "super-secret-key-123"},
        )
        assert authed_header.status_code == 201

        # Cookie verification flow
        verify = client.post("/api/auth/verify", json={"key": "super-secret-key-123"})
        assert verify.status_code == 200
        assert "linkforge_admin_key" in client.cookies

        # Subsequent delete using cookie authentication succeeds
        deleted = client.delete("/api/links/secured-slug")
        assert deleted.status_code == 204


def test_search_and_filter_links():
    with TestClient(app_module.app) as client:
        client.post(
            "/api/links",
            json={"url": "https://example.com/alpha", "custom_alias": "alpha", "campaign": "growth"},
        )
        client.post(
            "/api/links",
            json={"url": "https://example.com/beta", "custom_alias": "beta", "campaign": "brand"},
        )

        # Search by term
        search_res = client.get("/api/links?search=alpha").json()
        assert search_res["total_links"] == 2  # aggregate total
        assert len(search_res["links"]) == 1
        assert search_res["links"][0]["code"] == "alpha"

        # Filter by campaign
        camp_res = client.get("/api/links?campaign=brand").json()
        assert len(camp_res["links"]) == 1
        assert camp_res["links"][0]["code"] == "beta"


def test_vercel_entrypoint_and_routes():
    """Verify that api/index.py properly exports the FastAPI app and handles routing."""
    from api.index import app as vercel_app

    with TestClient(vercel_app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        created = client.post("/api/links", json={"url": "https://example.com/vercel-test"})
        assert created.status_code == 201
        assert created.json()["link"]["url"] == "https://example.com/vercel-test"


def test_database_path_resolution(monkeypatch, tmp_path):
    """Verify that get_db_path respects LINKFORGE_DB_PATH and VERCEL environment flags."""
    from database import get_db_path

    # Custom LINKFORGE_DB_PATH
    custom_path = str(tmp_path / "custom.db")
    monkeypatch.setenv("LINKFORGE_DB_PATH", custom_path)
    monkeypatch.delenv("VERCEL", raising=False)
    assert str(get_db_path()) == custom_path

    # VERCEL serverless environment flag
    monkeypatch.delenv("LINKFORGE_DB_PATH", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert str(get_db_path()) == str(Path("/tmp/linkforge.db"))

