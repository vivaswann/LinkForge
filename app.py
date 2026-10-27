from __future__ import annotations

import os
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import analytics
import qr
from database import (
    database,
    get_link_analytics,
    get_link_by_code,
    get_summary_stats,
    init_db,
    is_expired,
    link_row_to_dict,
    list_links_query,
    parse_utc_iso,
    record_click_event,
    utc_now,
)
from status_pages import render_status_page

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
SLUG_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
RESERVED_SLUGS = {
    "health",
    "api",
    "static",
    "docs",
    "redoc",
    "openapi.json",
    "favicon.ico",
    "status",
    "analytics",
    "auth",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="LinkForge",
    version="2.0.0",
    description="A modern, full-featured link management and analytics platform.",
    lifespan=lifespan,
)


@app.middleware("http")
async def vercel_path_rewrite_middleware(request: Request, call_next):
    """Normalize Vercel serverless request path if routed through api/index.py."""
    path = request.scope.get("path", "")
    if path in {"/api/index.py", "/api/index", "/api/index/"}:
        forwarded = (
            request.headers.get("x-forwarded-uri")
            or request.headers.get("x-matched-path")
            or request.headers.get("x-real-path")
        )
        if forwarded:
            clean_path = urlsplit(forwarded).path
            if clean_path and clean_path not in {"/api/index.py", "/api/index", "/api/index/"}:
                request.scope["path"] = clean_path
        else:
            request.scope["path"] = "/"

    return await call_next(request)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Pydantic Request Models ---

class CreateLinkRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    custom_alias: str | None = Field(default=None, max_length=32)
    title: str | None = Field(default=None, max_length=128)
    campaign: str | None = Field(default=None, max_length=64)
    expires_at: str | None = Field(default=None, max_length=64)


class UpdateLinkRequest(BaseModel):
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=128)
    campaign: str | None = Field(default=None, max_length=64)
    expires_at: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class VerifyAuthRequest(BaseModel):
    key: str


# --- Helper Utilities ---

def validate_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise HTTPException(
            status_code=422,
            detail="Enter a complete URL beginning with http:// or https://.",
        )
    if any(character.isspace() for character in cleaned):
        raise HTTPException(status_code=422, detail="The URL cannot contain spaces.")
    return cleaned


def make_code() -> str:
    return "".join(secrets.choice(SLUG_ALPHABET) for _ in range(6))


def public_base_url(request: Request) -> str:
    """Return the configured public origin, falling back to the current request origin."""
    configured = os.getenv("LINKFORGE_BASE_URL", "").strip().rstrip("/")
    if configured:
        parsed = urlsplit(configured)
        if parsed.scheme in {"http", "https"} and parsed.netloc and parsed.hostname:
            return configured
    return str(request.base_url).rstrip("/")


def get_client_ip(request: Request) -> str:
    """Extract client public IP address, handling proxy headers (Vercel, Render, Cloudflare)."""
    # 1. Cloudflare
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()

    # 2. Vercel, Render, Nginx
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()

    # 3. Standard reverse proxy list
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and forwarded.strip():
        client_ip = forwarded.split(",")[0].strip()
        if client_ip:
            return client_ip

    # 4. Direct client connection host
    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


def link_to_dict(row: sqlite3.Row, request: Request) -> dict:
    return link_row_to_dict(row, public_base_url(request))


def get_admin_key_env() -> str | None:
    raw = os.getenv("LINKFORGE_ADMIN_KEY", "").strip()
    return raw if raw else None


def check_admin_auth(request: Request) -> bool:
    """Check if admin key authentication is satisfied.
    
    If LINKFORGE_ADMIN_KEY is not configured in the environment, authentication is
    disabled to facilitate open local development and testing.
    """
    configured_key = get_admin_key_env()
    if not configured_key:
        return True

    # 1. Header X-Admin-Key
    header_key = request.headers.get("X-Admin-Key", "").strip()
    if header_key and secrets.compare_digest(header_key, configured_key):
        return True

    # 2. Cookie linkforge_admin_key
    cookie_key = request.cookies.get("linkforge_admin_key", "").strip()
    if cookie_key and secrets.compare_digest(cookie_key, configured_key):
        return True

    # 3. Query parameter admin_key
    query_key = request.query_params.get("admin_key", "").strip()
    if query_key and secrets.compare_digest(query_key, configured_key):
        return True

    return False


def require_admin(request: Request) -> None:
    if not check_admin_auth(request):
        raise HTTPException(
            status_code=401,
            detail="Admin authentication required. Provide a valid X-Admin-Key header or cookie.",
        )


# --- Core UI Routes ---

def render_index_html() -> Response:
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return FileResponse(index_path)


@app.get("/", include_in_schema=False)
@app.get("/api/index.py", include_in_schema=False)
@app.get("/api/index", include_in_schema=False)
def home() -> Response:
    return render_index_html()


@app.get("/analytics/{code}", include_in_schema=False)
def analytics_page(code: str) -> Response:
    return render_index_html()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --- Auth Routes ---

@app.get("/api/auth/status")
def auth_status(request: Request) -> dict:
    configured = bool(get_admin_key_env())
    authenticated = check_admin_auth(request) if configured else True
    return {
        "auth_required": configured,
        "authenticated": authenticated,
    }


@app.post("/api/auth/verify")
def auth_verify(payload: VerifyAuthRequest, response: Response) -> dict:
    configured_key = get_admin_key_env()
    if not configured_key:
        return {"success": True, "message": "Authentication not configured."}

    if secrets.compare_digest(payload.key.strip(), configured_key):
        response.set_cookie(
            key="linkforge_admin_key",
            value=payload.key.strip(),
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days
        )
        return {"success": True}
    raise HTTPException(status_code=401, detail="Invalid admin key.")


@app.post("/api/auth/logout")
def auth_logout(response: Response) -> dict:
    response.delete_cookie("linkforge_admin_key")
    return {"success": True}


# --- API Routes ---

@app.get("/api/config")
def get_config(request: Request) -> dict:
    return {"base_url": public_base_url(request)}


@app.get("/api/links")
def list_links(
    request: Request,
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    campaign: str | None = Query(default=None),
    sort: str = Query(default="newest"),
) -> dict:
    rows = list_links_query(
        search=search,
        status_filter=status,
        campaign_filter=campaign,
        sort_by=sort,
    )
    links = [link_to_dict(row, request) for row in rows]
    summary = get_summary_stats()
    return {
        "links": links,
        "total_links": summary["total_links"],
        "total_clicks": summary["total_clicks"],
        "summary": summary,
    }


@app.post("/api/links", status_code=201)
def create_link(
    payload: CreateLinkRequest,
    request: Request,
    _: None = Depends(require_admin),
) -> dict:
    original_url = validate_url(payload.url)

    if payload.custom_alias:
        code = payload.custom_alias.strip()
        if not ALIAS_PATTERN.fullmatch(code):
            raise HTTPException(
                status_code=422,
                detail="Custom aliases must be 3–32 characters and contain only letters, numbers, hyphens, or underscores.",
            )
        code = code.lower()
        if code in RESERVED_SLUGS:
            raise HTTPException(
                status_code=422,
                detail=f"The alias '{code}' is reserved by the system. Please pick another.",
            )
    else:
        code = make_code()

    # Validate expires_at if provided
    formatted_expires = None
    if payload.expires_at and payload.expires_at.strip():
        parsed_dt = parse_utc_iso(payload.expires_at)
        if parsed_dt is None:
            raise HTTPException(
                status_code=422,
                detail="Invalid expiration date format. Use ISO format (YYYY-MM-DDTHH:MM).",
            )
        formatted_expires = parsed_dt.isoformat(timespec="seconds")

    title = payload.title.strip() if payload.title and payload.title.strip() else None
    campaign = payload.campaign.strip() if payload.campaign and payload.campaign.strip() else None

    with database() as connection:
        if payload.custom_alias:
            existing = connection.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="That alias is already in use. Try another one.")
        else:
            for _ in range(5):
                existing = connection.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone()
                if not existing:
                    break
                code = make_code()
            else:
                raise HTTPException(status_code=500, detail="Could not generate a unique short code. Please retry.")

        now = utc_now()
        cursor = connection.execute(
            """
            INSERT INTO links (code, original_url, title, campaign, clicks, is_active, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0, 1, ?, ?, ?)
            """,
            (code, original_url, title, campaign, formatted_expires, now, now),
        )
        row = connection.execute("SELECT * FROM links WHERE id = ?", (cursor.lastrowid,)).fetchone()

    return {"link": link_to_dict(row, request)}


@app.get("/api/links/{code}")
def get_link(code: str, request: Request) -> dict:
    row = get_link_by_code(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Short link not found.")
    return {"link": link_to_dict(row, request)}


@app.patch("/api/links/{code}")
def update_link(
    code: str,
    payload: UpdateLinkRequest,
    request: Request,
    _: None = Depends(require_admin),
) -> dict:
    row = get_link_by_code(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Short link not found.")

    updates = []
    params = []

    if payload.url is not None:
        new_url = validate_url(payload.url)
        updates.append("original_url = ?")
        params.append(new_url)

    if payload.title is not None:
        title = payload.title.strip() if payload.title.strip() else None
        updates.append("title = ?")
        params.append(title)

    if payload.campaign is not None:
        campaign = payload.campaign.strip() if payload.campaign.strip() else None
        updates.append("campaign = ?")
        params.append(campaign)

    if payload.expires_at is not None:
        if payload.expires_at.strip() == "":
            updates.append("expires_at = NULL")
        else:
            parsed_dt = parse_utc_iso(payload.expires_at)
            if parsed_dt is None:
                raise HTTPException(
                    status_code=422,
                    detail="Invalid expiration date format. Use ISO format (YYYY-MM-DDTHH:MM).",
                )
            updates.append("expires_at = ?")
            params.append(parsed_dt.isoformat(timespec="seconds"))

    if payload.is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if payload.is_active else 0)

    if updates:
        updates.append("updated_at = ?")
        params.append(utc_now())
        params.append(code.lower())

        with database() as conn:
            conn.execute(f"UPDATE links SET {', '.join(updates)} WHERE code = ?", params)
            updated_row = conn.execute("SELECT * FROM links WHERE code = ?", (code.lower(),)).fetchone()
    else:
        updated_row = row

    return {"link": link_to_dict(updated_row, request)}


@app.post("/api/links/{code}/toggle")
def toggle_link(
    code: str,
    request: Request,
    _: None = Depends(require_admin),
) -> dict:
    row = get_link_by_code(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Short link not found.")

    new_state = 0 if bool(row["is_active"]) else 1
    now = utc_now()
    with database() as conn:
        conn.execute(
            "UPDATE links SET is_active = ?, updated_at = ? WHERE code = ?",
            (new_state, now, code.lower()),
        )
        updated_row = conn.execute("SELECT * FROM links WHERE code = ?", (code.lower(),)).fetchone()

    return {"link": link_to_dict(updated_row, request)}


@app.delete("/api/links/{code}", status_code=204)
def delete_link(
    code: str,
    _: None = Depends(require_admin),
) -> Response:
    with database() as connection:
        cursor = connection.execute("DELETE FROM links WHERE code = ?", (code.lower(),))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Short link not found.")
    return Response(status_code=204)


@app.get("/api/links/{code}/qr")
def get_link_qr(
    code: str,
    request: Request,
    download: bool = Query(default=False),
) -> Response:
    row = get_link_by_code(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Short link not found.")

    # QR code encodes the actual short URL, not the destination URL directly
    short_url = f"{public_base_url(request)}/{row['code']}"
    png_bytes = qr.generate_qr_png(short_url)

    headers = {"Content-Type": "image/png"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="linkforge-{row["code"]}-qr.png"'

    return Response(content=png_bytes, media_type="image/png", headers=headers)


@app.get("/api/links/{code}/analytics")
def link_analytics(code: str, request: Request) -> dict:
    row = get_link_by_code(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Short link not found.")

    link_data = link_to_dict(row, request)
    analytics_data = get_link_analytics(row["id"])

    return {
        "link": link_data,
        **analytics_data,
    }


# --- Redirect Route ---

@app.get("/{code}", include_in_schema=False)
def redirect_short_link(code: str, request: Request) -> Response:
    # Keep this route after API and static routes to avoid shadowing
    code_lower = code.lower()
    row = get_link_by_code(code_lower)

    # 1. Nonexistent link
    if row is None:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return HTMLResponse(
                content=render_status_page("not_found", code=code),
                status_code=404,
            )
        raise HTTPException(status_code=404, detail="That LinkForge link does not exist.")

    # 2. Disabled link
    if not bool(row["is_active"]):
        return HTMLResponse(
            content=render_status_page(
                "disabled",
                code=code,
                title=row["title"] if "title" in row.keys() else None,
            ),
            status_code=403,
        )

    # 3. Expired link
    expires_at = row["expires_at"] if "expires_at" in row.keys() else None
    if is_expired(expires_at):
        return HTMLResponse(
            content=render_status_page(
                "expired",
                code=code,
                title=row["title"] if "title" in row.keys() else None,
            ),
            status_code=410,
        )

    # 4. Valid and active link -> record click event with IP and device name
    ua = request.headers.get("user-agent")
    device_cat = analytics.detect_device(ua)
    device_name = analytics.detect_device_name(ua)
    ref = analytics.clean_referrer(request.headers.get("referer"))
    ip = get_client_ip(request)

    record_click_event(
        row["id"],
        referrer=ref,
        device_category=device_cat,
        device_name=device_name,
        ip_address=ip,
    )
    target_url = row["original_url"]

    return RedirectResponse(url=target_url, status_code=302)
