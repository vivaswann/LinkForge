"""Database connection, migration, and query management for LinkForge."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def get_db_path() -> Path:
    """Resolve database file path, supporting custom overrides or Vercel serverless /tmp."""
    env_path = os.getenv("LINKFORGE_DB_PATH", "").strip()
    if env_path:
        return Path(env_path)
    if os.getenv("VERCEL"):
        # Vercel serverless functions have a read-only filesystem except for /tmp
        return Path("/tmp/linkforge.db")
    return BASE_DIR / "linkforge.db"


DB_PATH = get_db_path()


def utc_now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_utc_iso(date_str: str | None) -> datetime | None:
    """Safely parse an ISO date string into a UTC datetime object."""
    if not date_str:
        return None
    try:
        # Handle trailing Z or timezone offsets
        clean_str = date_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def is_expired(expires_at: str | None) -> bool:
    """Check if the provided expiration timestamp has passed."""
    dt = parse_utc_iso(expires_at)
    if dt is None:
        return False
    return datetime.now(timezone.utc) >= dt


@contextmanager
def database(db_path: Path | None = None):
    """Context manager for SQLite connections with foreign keys enabled."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(db_path: Path | None = None) -> None:
    """Initialize or migrate the SQLite database safely without data loss."""
    with database(db_path) as connection:
        # 1. Create original table if not existing
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

        # 2. Check existing columns in 'links' and apply backward-compatible migrations
        columns_info = connection.execute("PRAGMA table_info(links)").fetchall()
        existing_columns = {col["name"] for col in columns_info}

        if "title" not in existing_columns:
            connection.execute("ALTER TABLE links ADD COLUMN title TEXT")
        if "campaign" not in existing_columns:
            connection.execute("ALTER TABLE links ADD COLUMN campaign TEXT")
        if "is_active" not in existing_columns:
            connection.execute("ALTER TABLE links ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        if "expires_at" not in existing_columns:
            connection.execute("ALTER TABLE links ADD COLUMN expires_at TEXT")
        if "updated_at" not in existing_columns:
            connection.execute("ALTER TABLE links ADD COLUMN updated_at TEXT")

        # 3. Create click events analytics table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id INTEGER NOT NULL,
                clicked_at TEXT NOT NULL,
                referrer TEXT NOT NULL DEFAULT 'Direct / None',
                device_category TEXT NOT NULL DEFAULT 'Desktop',
                device_name TEXT NOT NULL DEFAULT 'Unknown Device',
                ip_address TEXT NOT NULL DEFAULT '127.0.0.1',
                FOREIGN KEY (link_id) REFERENCES links(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_clicks_link_id ON clicks(link_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_clicks_clicked_at ON clicks(clicked_at)")

        # Migration: ensure ip_address and device_name exist on clicks table
        clicks_columns_info = connection.execute("PRAGMA table_info(clicks)").fetchall()
        existing_clicks_columns = {col["name"] for col in clicks_columns_info}
        if "ip_address" not in existing_clicks_columns:
            connection.execute("ALTER TABLE clicks ADD COLUMN ip_address TEXT NOT NULL DEFAULT '127.0.0.1'")
        if "device_name" not in existing_clicks_columns:
            connection.execute("ALTER TABLE clicks ADD COLUMN device_name TEXT NOT NULL DEFAULT 'Unknown Device'")


def link_row_to_dict(row: sqlite3.Row, base_url: str) -> dict:
    """Format a SQLite row into a clean link dictionary with status."""
    keys = row.keys()
    expires_at = row["expires_at"] if "expires_at" in keys else None
    is_active = bool(row["is_active"]) if "is_active" in keys else True
    expired = is_expired(expires_at)

    if not is_active:
        status = "disabled"
    elif expired:
        status = "expired"
    else:
        status = "active"

    return {
        "id": row["id"],
        "code": row["code"],
        "url": row["original_url"],
        "short_url": f"{base_url}/{row['code']}",
        "clicks": row["clicks"],
        "created_at": row["created_at"],
        "title": row["title"] if "title" in keys and row["title"] else None,
        "campaign": row["campaign"] if "campaign" in keys and row["campaign"] else None,
        "is_active": is_active,
        "expires_at": expires_at,
        "updated_at": row["updated_at"] if "updated_at" in keys and row["updated_at"] else None,
        "status": status,
        "is_expired": expired,
    }


def get_link_by_code(code: str, db_path: Path | None = None) -> sqlite3.Row | None:
    """Fetch a single link row by its short code (case-insensitive)."""
    with database(db_path) as conn:
        return conn.execute("SELECT * FROM links WHERE code = ?", (code.lower(),)).fetchone()


def get_link_by_id(link_id: int, db_path: Path | None = None) -> sqlite3.Row | None:
    """Fetch a single link row by its ID."""
    with database(db_path) as conn:
        return conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()


def list_links_query(
    search: str | None = None,
    status_filter: str | None = None,
    campaign_filter: str | None = None,
    sort_by: str = "newest",
    db_path: Path | None = None,
) -> list[sqlite3.Row]:
    """Query links with search, filtering, and sorting."""
    with database(db_path) as conn:
        query = "SELECT * FROM links WHERE 1=1"
        params: list[object] = []

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            query += " AND (LOWER(code) LIKE ? OR LOWER(original_url) LIKE ? OR LOWER(COALESCE(title, '')) LIKE ? OR LOWER(COALESCE(campaign, '')) LIKE ?)"
            params.extend([term, term, term, term])

        if campaign_filter and campaign_filter.strip() and campaign_filter != "all":
            query += " AND LOWER(COALESCE(campaign, '')) = ?"
            params.append(campaign_filter.strip().lower())

        if status_filter == "disabled":
            query += " AND is_active = 0"
        elif status_filter == "active":
            query += " AND is_active = 1 AND (expires_at IS NULL OR expires_at > ?)"
            params.append(utc_now())
        elif status_filter == "expired":
            query += " AND is_active = 1 AND expires_at IS NOT NULL AND expires_at <= ?"
            params.append(utc_now())

        if sort_by == "oldest":
            query += " ORDER BY id ASC"
        elif sort_by == "clicks_desc":
            query += " ORDER BY clicks DESC, id DESC"
        elif sort_by == "clicks_asc":
            query += " ORDER BY clicks ASC, id DESC"
        elif sort_by == "title":
            query += " ORDER BY COALESCE(title, code) COLLATE NOCASE ASC"
        else:  # default "newest"
            query += " ORDER BY id DESC"

        return conn.execute(query, params).fetchall()


def get_summary_stats(db_path: Path | None = None) -> dict:
    """Compute aggregate statistics across the links collection."""
    now = utc_now()
    with database(db_path) as conn:
        total_links = conn.execute("SELECT COUNT(*) AS c FROM links").fetchone()["c"]
        total_clicks = conn.execute("SELECT COALESCE(SUM(clicks), 0) AS c FROM links").fetchone()["c"]
        active_links = conn.execute(
            "SELECT COUNT(*) AS c FROM links WHERE is_active = 1 AND (expires_at IS NULL OR expires_at > ?)",
            (now,),
        ).fetchone()["c"]
        expired_links = conn.execute(
            "SELECT COUNT(*) AS c FROM links WHERE is_active = 1 AND expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        ).fetchone()["c"]
        disabled_links = conn.execute("SELECT COUNT(*) AS c FROM links WHERE is_active = 0").fetchone()["c"]

        campaign_rows = conn.execute(
            "SELECT DISTINCT campaign FROM links WHERE campaign IS NOT NULL AND campaign != '' ORDER BY campaign ASC"
        ).fetchall()
        campaigns = [row["campaign"] for row in campaign_rows]

    return {
        "total_links": total_links,
        "total_clicks": total_clicks,
        "active_links": active_links,
        "expired_links": expired_links,
        "disabled_links": disabled_links,
        "campaigns": campaigns,
    }


def record_click_event(
    link_id: int,
    referrer: str,
    device_category: str,
    device_name: str = "Unknown Device",
    ip_address: str = "127.0.0.1",
    db_path: Path | None = None,
) -> None:
    """Record a click event in the clicks table and increment the link clicks count."""
    now = utc_now()
    with database(db_path) as conn:
        conn.execute(
            """
            INSERT INTO clicks (link_id, clicked_at, referrer, device_category, device_name, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (link_id, now, referrer, device_category, device_name, ip_address),
        )
        conn.execute("UPDATE links SET clicks = clicks + 1 WHERE id = ?", (link_id,))


def get_link_analytics(link_id: int, db_path: Path | None = None) -> dict:
    """Retrieve real analytics metrics for a specific link."""
    with database(db_path) as conn:
        total_clicks_row = conn.execute(
            "SELECT COUNT(*) AS c FROM clicks WHERE link_id = ?", (link_id,)
        ).fetchone()
        total_clicks = total_clicks_row["c"] if total_clicks_row else 0

        # Clicks grouped by date (YYYY-MM-DD)
        date_rows = conn.execute(
            """
            SELECT substr(clicked_at, 1, 10) AS date_str, COUNT(*) AS count
            FROM clicks
            WHERE link_id = ?
            GROUP BY date_str
            ORDER BY date_str ASC
            """,
            (link_id,),
        ).fetchall()
        clicks_by_date = [{"date": row["date_str"], "count": row["count"]} for row in date_rows]

        # Referrers breakdown
        referrer_rows = conn.execute(
            """
            SELECT referrer, COUNT(*) AS count
            FROM clicks
            WHERE link_id = ?
            GROUP BY referrer
            ORDER BY count DESC
            LIMIT 10
            """,
            (link_id,),
        ).fetchall()
        referrers = []
        for row in referrer_rows:
            pct = round((row["count"] / total_clicks * 100), 1) if total_clicks > 0 else 0.0
            referrers.append({"referrer": row["referrer"], "count": row["count"], "percentage": pct})

        # Device breakdown (grouped by detailed device name)
        device_rows = conn.execute(
            """
            SELECT COALESCE(device_name, device_category) AS dev_label, COUNT(*) AS count
            FROM clicks
            WHERE link_id = ?
            GROUP BY dev_label
            ORDER BY count DESC
            """,
            (link_id,),
        ).fetchall()
        devices = []
        for row in device_rows:
            pct = round((row["count"] / total_clicks * 100), 1) if total_clicks > 0 else 0.0
            devices.append({"device": row["dev_label"], "count": row["count"], "percentage": pct})

        # Recent 25 click events with IP and device name
        recent_rows = conn.execute(
            """
            SELECT clicked_at, referrer, device_category,
                   COALESCE(device_name, device_category) AS device_name,
                   COALESCE(ip_address, '127.0.0.1') AS ip_address
            FROM clicks
            WHERE link_id = ?
            ORDER BY id DESC
            LIMIT 25
            """,
            (link_id,),
        ).fetchall()
        recent_clicks = [
            {
                "clicked_at": row["clicked_at"],
                "referrer": row["referrer"],
                "device": row["device_category"],
                "device_name": row["device_name"],
                "ip_address": row["ip_address"],
            }
            for row in recent_rows
        ]

    return {
        "total_clicks": total_clicks,
        "clicks_by_date": clicks_by_date,
        "referrers": referrers,
        "devices": devices,
        "recent_clicks": recent_clicks,
    }
