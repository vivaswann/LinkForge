from __future__ import annotations

import os
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "linkforge.db"
STATIC_DIR = BASE_DIR / "static"
ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
SLUG_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="LinkForge",
    version="1.0.0",
    description="A small URL shortener with click tracking.",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CreateLinkRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    custom_alias: str | None = Field(default=None, max_length=32)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def database():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                original_url TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )


def validate_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Enter a complete URL beginning with http:// or https://.")
    if any(character.isspace() for character in cleaned):
        raise HTTPException(status_code=422, detail="The URL cannot contain spaces.")
    return cleaned


def make_code() -> str:
    return "".join(secrets.choice(SLUG_ALPHABET) for _ in range(6))


def public_base_url(request: Request) -> str:
    """Return the configured public origin, falling back to the current request origin.

    Set LINKFORGE_BASE_URL after deployment (for example, https://links.example.com).
    Do not set it to a public domain until that domain actually points to this app.
    """
    configured = os.getenv("LINKFORGE_BASE_URL", "").strip().rstrip("/")
    if configured:
        parsed = urlsplit(configured)
        if parsed.scheme in {"http", "https"} and parsed.netloc and parsed.hostname:
            return configured
    return str(request.base_url).rstrip("/")


def link_to_dict(row: sqlite3.Row, request: Request) -> dict:
    return {
        "id": row["id"],
        "code": row["code"],
        "url": row["original_url"],
        "short_url": f"{public_base_url(request)}/{row['code']}",
        "clicks": row["clicks"],
        "created_at": row["created_at"],
    }


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/config")
def get_config(request: Request) -> dict:
    return {"base_url": public_base_url(request)}


@app.get("/api/links")
def list_links(request: Request) -> dict:
    with database() as connection:
        rows = connection.execute("SELECT * FROM links ORDER BY id DESC").fetchall()
    links = [link_to_dict(row, request) for row in rows]
    return {
        "links": links,
        "total_links": len(links),
        "total_clicks": sum(link["clicks"] for link in links),
    }


@app.post("/api/links", status_code=201)
def create_link(payload: CreateLinkRequest, request: Request) -> dict:
    original_url = validate_url(payload.url)

    if payload.custom_alias:
        code = payload.custom_alias.strip()
        if not ALIAS_PATTERN.fullmatch(code):
            raise HTTPException(
                status_code=422,
                detail="Custom aliases must be 3–32 characters and contain only letters, numbers, hyphens, or underscores.",
            )
        code = code.lower()
    else:
        code = make_code()

    with database() as connection:
        if payload.custom_alias:
            existing = connection.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="That alias is already in use. Try another one.")
        else:
            # A collision is very unlikely, but retry rather than failing unexpectedly.
            for _ in range(5):
                existing = connection.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone()
                if not existing:
                    break
                code = make_code()
            else:
                raise HTTPException(status_code=500, detail="Could not generate a unique short code. Please retry.")

        cursor = connection.execute(
            "INSERT INTO links (code, original_url, clicks, created_at) VALUES (?, ?, 0, ?)",
            (code, original_url, utc_now()),
        )
        row = connection.execute("SELECT * FROM links WHERE id = ?", (cursor.lastrowid,)).fetchone()

    return {"link": link_to_dict(row, request)}


@app.get("/api/links/{code}")
def get_link(code: str, request: Request) -> dict:
    with database() as connection:
        row = connection.execute("SELECT * FROM links WHERE code = ?", (code.lower(),)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Short link not found.")
    return {"link": link_to_dict(row, request)}


@app.delete("/api/links/{code}", status_code=204)
def delete_link(code: str) -> Response:
    with database() as connection:
        cursor = connection.execute("DELETE FROM links WHERE code = ?", (code.lower(),))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Short link not found.")
    return Response(status_code=204)


@app.get("/{code}", include_in_schema=False)
def redirect_short_link(code: str) -> RedirectResponse:
    # Keep this route after the API and static routes so it does not shadow them.
    with database() as connection:
        row = connection.execute("SELECT original_url FROM links WHERE code = ?", (code.lower(),)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="That LinkForge link does not exist.")
        connection.execute("UPDATE links SET clicks = clicks + 1 WHERE code = ?", (code.lower(),))
        target_url = row["original_url"]
    return RedirectResponse(url=target_url, status_code=302)
