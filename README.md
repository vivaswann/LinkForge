# LinkForge

A beginner-friendly URL shortener built with FastAPI, SQLite, and plain HTML/CSS/JavaScript. Create short links, choose custom aliases, count clicks, copy links, and delete links from a dashboard.

## Features

- Short codes generated with Python's `secrets` module
- Optional custom aliases (3–32 letters, numbers, hyphens, or underscores)
- SQLite persistence, so links remain after a server restart
- HTTP redirects and click counts
- Dashboard with total links, total clicks, creation dates, and link management
- URL and alias validation
- Local-first setup; no external database account required

## Requirements

- Python 3.10 or newer
- Internet connection only if you want the optional Google Fonts used in the UI; the application itself runs locally

## Run locally

### Windows PowerShell

```powershell
cd linkforge
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

If PowerShell blocks activation, use Command Prompt instead:

```bat
.venv\Scripts\activate.bat
```

Then open <http://127.0.0.1:8000> in your browser.

### macOS / Linux

```bash
cd linkforge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

## Use a clean public domain after deployment

When you run LinkForge on your own laptop, the address includes the local host and port (for example, `127.0.0.1:8000`). That is only the local development address. To have a shareable URL without that IP and port, deploy LinkForge so it has a public domain, such as `https://your-app.onrender.com`.

### Deploy to Render

1. Push the contents of this folder to a GitHub repository.
2. In Render, choose **New → Blueprint** and connect that repository. Render will read the included `render.yaml` and create a web service.
3. Once deployment finishes, open the public `onrender.com` URL. Short links will use that public host instead of `127.0.0.1:8000`.
4. If the generated links show the wrong scheme or host, add `LINKFORGE_BASE_URL` in the service's environment variables, set to the exact public origin with no trailing slash. For example: `https://your-app.onrender.com`.

For local testing, leave `LINKFORGE_BASE_URL` unset.

**Storage note:** Render's default filesystem is ephemeral, and this app stores links in SQLite. On a free Render service, saved links can disappear when the service restarts or spins down. See Render's [persistent disk documentation](https://render.com/docs/disks) before using this as a durable public service; a managed database is the better long-term improvement.

## Try it

1. Paste a complete URL such as `https://example.com`.
2. Optionally enter a custom alias such as `example-home`.
3. Select **Forge link**.
4. Open the generated short URL in a new tab. The destination should open and the click count should increase after refreshing the dashboard.
5. Copy or delete a link from the table.

## Run tests

Install development dependencies and run the automated API tests:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## API routes

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/config` | Return the configured public base URL |
| `GET` | `/api/links` | List links and summary stats |
| `POST` | `/api/links` | Create a short link |
| `GET` | `/api/links/{code}` | Get one link |
| `DELETE` | `/api/links/{code}` | Delete a link |
| `GET` | `/{code}` | Redirect to the destination and count the click |
| `GET` | `/docs` | Interactive API documentation |

Example create request:

```json
{
  "url": "https://example.com/some/long/path",
  "custom_alias": "example-path"
}
```

`custom_alias` can be omitted to generate a random code.

## Notes and next steps

This is a learning project, not a production URL-shortening service. Before public deployment, add rate limiting, abuse/spam controls, safer handling of external destinations, automated tests, and appropriate logging. This version records total clicks only; it does not store visitor IP addresses or fingerprint visitors.

Possible extensions: click history by day, QR-code generation, expiration dates, link search, password-protected destinations, and automated tests.
