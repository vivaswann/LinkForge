# LinkForge

A modern, full-featured link management and analytics platform built with FastAPI, SQLite, and vanilla HTML/CSS/JavaScript. Create short links, choose custom aliases, track real-time click analytics with visitor IP addresses and detailed device names, generate branded QR codes, set link expiration, and organize links by campaign from a polished dark-graphite dashboard.

## Features

- **Advanced Link Creation**: Custom slugs, automatic unpredictable slug generation, optional link titles, campaign tags, and scheduled expiration dates.
- **Link Management Dashboard**: Dark graphite design with restrained violet accents. Search by title, slug, or destination, filter by status (active, expired, paused) and campaign, and sort by date or clicks.
- **Real-Time Click Signals & Analytics**: Tracks total clicks, clicks over time (interactive SVG timeline), referrer domain breakdown, visitor IP addresses, and detailed device/OS detection (e.g. iPhone, Windows, Mac, Android).
- **QR Code Generation**: Generate, preview, and download high-resolution PNG QR codes directly encoding the public short URL.
- **Link Expiration & Status Handling**: Server-side expiration checks with clean expired-link and disabled-link status pages. Expired links never redirect.
- **Safe SQLite Persistence & Migration**: Fully backward-compatible schema migrations. Preserves existing link configurations and database history.
- **Security & Authentication**: Parameterized SQL queries, URL normalization, HTML-escaped outputs, and optional administration protection via `LINKFORGE_ADMIN_KEY`.

## Requirements

- Python 3.10 or newer
- SQLite 3

## Run Locally

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

If PowerShell blocks execution, activate in Command Prompt:

```bat
.venv\Scripts\activate.bat
```

Then open <http://127.0.0.1:8000> in your browser.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

## Deployment

### Deploy to Vercel

LinkForge includes native Vercel Serverless Function support via [`vercel.json`](file:///c:/Users/Official/Desktop/LinkForge/vercel.json) and [`api/index.py`](file:///c:/Users/Official/Desktop/LinkForge/api/index.py):

1. Push this repository to your GitHub account.
2. Import the project in the [Vercel Dashboard](https://vercel.com/new).
3. Vercel automatically detects the Python runtime and routes all traffic to the FastAPI application.
4. (Optional) In your Vercel Project Settings &rarr; **Environment Variables**, add:
   - `LINKFORGE_BASE_URL`: Your public domain (e.g. `https://links.yourdomain.com` or `https://linkforge.vercel.app`) without a trailing slash.
   - `LINKFORGE_ADMIN_KEY`: Your secret administration key.

> **Storage Note:** Serverless functions execute in an ephemeral container. On Vercel, the SQLite database is automatically created in `/tmp/linkforge.db`. For persistent long-term storage across serverless cold starts, use a host with persistent disks (such as Render or a VPS) or point `LINKFORGE_DB_PATH` to a mounted network volume.

### Deploy to Render

LinkForge includes a ready-to-use [`render.yaml`](file:///c:/Users/Official/Desktop/LinkForge/render.yaml) blueprint:

1. Push this repository to your GitHub account.
2. In Render, select **New &rarr; Blueprint** and connect your repository.
3. Render will automatically build the service from `requirements.txt` and start the server with Uvicorn.
4. For durable link storage on Render, attach a [Render Persistent Disk](https://render.com/docs/disks).

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `LINKFORGE_BASE_URL` | Public origin domain (e.g. `https://links.example.com`) without a trailing slash. Used for short URLs and QR codes. | Current request origin |
| `LINKFORGE_ADMIN_KEY` | Optional admin key to protect dashboard write operations (`POST`, `PATCH`, `DELETE`). If unset, access is open. | Unset (open access) |
| `LINKFORGE_DB_PATH` | Path to the SQLite database file. Automatically defaults to `/tmp/linkforge.db` on Vercel serverless. | `./linkforge.db` |

## Run Automated Tests

Install development dependencies and run the automated test suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The test suite covers:
- Short link creation with random and custom slugs
- Duplicate alias rejection and reserved slug protection
- Successful 302 redirects and atomic click counter increments
- Editing and updating link metadata (title, URL, campaign, expiration)
- Deleting links and cascading removal of analytics
- Server-side expiration handling (status 410 with expired landing page)
- Disabled link handling (status 403 with paused landing page)
- Click analytics recording with visitor IP address, device name, and referrer domain
- QR code generation and PNG attachment downloads
- Backward-compatible database schema migrations from legacy tables
- Admin authentication enforcement when `LINKFORGE_ADMIN_KEY` is configured
- Search, filter, and sorting queries
- Vercel serverless entrypoint and `/tmp` database path resolution

## API Routes

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Health check endpoint |
| `GET` | `/api/config` | Return configured public base URL |
| `GET` | `/api/auth/status` | Return authentication status |
| `POST` | `/api/auth/verify` | Authenticate admin key and set session cookie |
| `POST` | `/api/auth/logout` | Clear admin session cookie |
| `GET` | `/api/links` | List links with `search`, `status`, `campaign`, and `sort` query params |
| `POST` | `/api/links` | Create a new short link |
| `GET` | `/api/links/{code}` | Get single link details |
| `PATCH` | `/api/links/{code}` | Update link metadata or expiration |
| `POST` | `/api/links/{code}/toggle` | Toggle link active/paused status |
| `DELETE` | `/api/links/{code}` | Delete a link and its analytics |
| `GET` | `/api/links/{code}/qr` | Generate QR code PNG (`?download=true` for attachment) |
| `GET` | `/api/links/{code}/analytics` | Get click analytics (timeline, referrers, devices, recent log) |
| `GET` | `/{code}` | Redirect to destination (302) or render expired/disabled page |
| `GET` | `/docs` | Interactive Swagger API documentation |

## Project Structure

```
LinkForge/
├── api/
│   └── index.py           # Vercel serverless function entrypoint
├── static/
│   ├── index.html         # Modern dashboard, modals, and analytics view
│   ├── styles.css         # Dark graphite design system & responsive layout
│   └── app.js             # Client application logic & dynamic SVG charts
├── tests/
│   └── test_app.py        # Automated test suite (16 test cases)
├── analytics.py           # Privacy-safe device category and referrer detection
├── app.py                 # FastAPI application and route endpoints
├── database.py            # SQLite connection, safe migrations, and queries
├── qr.py                  # QR code PNG generation using qrcode & Pillow
├── status_pages.py        # Styled HTML status pages for expired, disabled, & 404 links
├── render.yaml            # Render deployment blueprint
├── vercel.json            # Vercel deployment configuration
├── requirements.txt       # Production dependencies (fastapi, uvicorn, qrcode[pil])
├── requirements-dev.txt   # Development dependencies (pytest, httpx)
└── README.md              # Project documentation
```
