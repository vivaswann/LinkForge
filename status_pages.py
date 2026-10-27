"""Clean, responsive HTML status pages for expired, disabled, and not-found links."""
from __future__ import annotations

import html


def render_status_page(
    status_type: str,
    code: str,
    title: str | None = None,
    detail: str | None = None,
) -> str:
    """Render a styled dark-graphite status page with restrained violet accents."""
    safe_code = html.escape(code)
    safe_title = html.escape(title) if title else ""

    if status_type == "expired":
        headline = "This link has expired"
        badge = "EXPIRED"
        badge_class = "badge-expired"
        description = (
            f"The short link <code>/{safe_code}</code> was configured with an expiration date that has now passed. "
            "It is no longer redirecting to its destination."
        )
        icon_svg = """<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>"""
    elif status_type == "disabled":
        headline = "This link is temporarily paused"
        badge = "DISABLED"
        badge_class = "badge-disabled"
        description = (
            f"The short link <code>/{safe_code}</code> has been deactivated by its owner. "
            "Traffic to this link is currently paused."
        )
        icon_svg = """<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>"""
    else:  # not found
        headline = "Link not found"
        badge = "404 NOT FOUND"
        badge_class = "badge-notfound"
        description = (
            f"The short link <code>/{safe_code}</code> does not exist on this LinkForge instance. "
            "It may have been deleted or the address might be mistyped."
        )
        icon_svg = """<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>"""

    title_block = (
        f'<div class="link-meta-title"><span class="meta-label">LINK TITLE</span><span class="meta-val">{safe_title}</span></div>'
        if safe_title
        else ""
    )

    detail_block = f'<p class="meta-detail">{html.escape(detail)}</p>' if detail else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{headline} — LinkForge</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0d14;
      --panel: #141724;
      --panel-border: #252b42;
      --text: #eef2fa;
      --muted: #8e95ae;
      --purple: #8b7dff;
      --purple-hover: #a296ff;
      --mono: "DM Mono", monospace;
      --sans: "Manrope", system-ui, sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: radial-gradient(ellipse at 50% -20%, #201d40 0%, transparent 50%), var(--bg);
      color: var(--text);
      font-family: var(--sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .status-card {{
      max-width: 480px;
      width: 100%;
      background: var(--panel);
      border: 1px solid var(--panel-border);
      border-radius: 14px;
      padding: 36px 32px;
      box-shadow: 0 24px 60px rgba(0,0,0,0.45);
      text-align: center;
    }}
    .brand {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--text);
      text-decoration: none;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: -0.4px;
      margin-bottom: 24px;
    }}
    .brand-mark {{
      display: inline-grid;
      place-items: center;
      width: 22px;
      height: 22px;
      border-radius: 6px;
      background: var(--purple);
      color: #0b0d14;
      font-size: 14px;
      font-weight: 800;
    }}
    .brand span span {{ color: var(--purple); }}
    .icon-wrap {{
      display: inline-grid;
      place-items: center;
      width: 60px;
      height: 60px;
      border-radius: 14px;
      margin-bottom: 18px;
      border: 1px solid;
    }}
    .badge-expired {{
      background: rgba(251, 191, 36, 0.12);
      color: #fbbf24;
      border-color: rgba(251, 191, 36, 0.3);
    }}
    .badge-disabled {{
      background: rgba(248, 113, 113, 0.12);
      color: #f87171;
      border-color: rgba(248, 113, 113, 0.3);
    }}
    .badge-notfound {{
      background: rgba(139, 125, 255, 0.12);
      color: var(--purple);
      border-color: rgba(139, 125, 255, 0.3);
    }}
    .status-badge {{
      display: inline-block;
      font: 500 10px var(--mono);
      letter-spacing: 1px;
      padding: 4px 10px;
      border-radius: 20px;
      margin-bottom: 14px;
    }}
    h1 {{
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
      margin-bottom: 12px;
      color: var(--text);
    }}
    .description {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
      margin-bottom: 24px;
    }}
    code {{
      font-family: var(--mono);
      color: var(--purple);
      background: rgba(139, 125, 255, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .link-meta-title {{
      background: #0d0f19;
      border: 1px solid var(--panel-border);
      border-radius: 8px;
      padding: 10px 14px;
      margin-bottom: 20px;
      text-align: left;
    }}
    .meta-label {{
      display: block;
      font: 500 9px var(--mono);
      color: var(--muted);
      letter-spacing: 0.8px;
      margin-bottom: 3px;
    }}
    .meta-val {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      word-break: break-word;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      height: 42px;
      padding: 0 20px;
      border-radius: 8px;
      background: var(--purple);
      color: #0b0d14;
      text-decoration: none;
      font-weight: 700;
      font-size: 13px;
      transition: background 0.15s, transform 0.15s;
    }}
    .btn:hover {{
      background: var(--purple-hover);
      transform: translateY(-1px);
    }}
  </style>
</head>
<body>
  <div class="status-card">
    <a class="brand" href="/" aria-label="LinkForge home">
      <span class="brand-mark" aria-hidden="true">↗</span>
      <span>link<span>forge</span></span>
    </a>
    <div>
      <div class="icon-wrap {badge_class}">{icon_svg}</div>
      <div class="status-badge {badge_class}">{badge}</div>
      <h1>{headline}</h1>
      <p class="description">{description}</p>
      {title_block}
      {detail_block}
      <a class="btn" href="/">Return to Dashboard &rarr;</a>
    </div>
  </div>
</body>
</html>"""
