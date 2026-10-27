"""Privacy-friendly device category and referrer detection."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

BOT_PATTERNS = re.compile(
    r"(bot|crawl|spider|slurp|headless|curl|wget|python-requests|httpx|postman|ahrefs|semrush|bytespider|facebookexternalhit|whatsapp|slackbot|discordbot|googlebot)",
    re.IGNORECASE,
)
TABLET_PATTERNS = re.compile(r"(ipad|tablet|playbook|silk|kindle)", re.IGNORECASE)
MOBILE_PATTERNS = re.compile(
    r"(mobile|iphone|ipod|android|blackberry|webos|windows phone|iemobile|opera mini)",
    re.IGNORECASE,
)


def detect_device(user_agent: str | None) -> str:
    """Classify the user agent into a coarse device category.
    
    Returns one of: 'Desktop', 'Mobile', 'Tablet', 'Bot / Crawler', or 'Unknown'.
    Does not fingerprint visitors or track identity.
    """
    if not user_agent or not user_agent.strip():
        return "Unknown"

    ua = user_agent.strip()

    if BOT_PATTERNS.search(ua):
        return "Bot / Crawler"

    # Some Android tablets don't include 'Mobile' in the UA
    if TABLET_PATTERNS.search(ua) or ("android" in ua.lower() and "mobile" not in ua.lower()):
        return "Tablet"

    if MOBILE_PATTERNS.search(ua):
        return "Mobile"

    return "Desktop"


def clean_referrer(referrer: str | None) -> str:
    """Extract a clean, privacy-conscious referrer domain from the HTTP Referer header.
    
    Returns the cleaned hostname or 'Direct / None'. Query strings and path details are discarded.
    """
    if not referrer or not referrer.strip():
        return "Direct / None"

    cleaned = referrer.strip()
    try:
        parsed = urlsplit(cleaned)
        domain = parsed.hostname or parsed.netloc
        if not domain:
            return "Direct / None"

        domain = domain.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        # Friendly mapping for common referrers
        if "google." in domain:
            return "Google"
        if domain in {"t.co", "twitter.com", "x.com"}:
            return "X (Twitter)"
        if "linkedin." in domain:
            return "LinkedIn"
        if "facebook." in domain or domain in {"fb.com", "m.facebook.com"}:
            return "Facebook"
        if "instagram." in domain:
            return "Instagram"
        if "youtube." in domain or domain == "youtu.be":
            return "YouTube"
        if "reddit." in domain:
            return "Reddit"
        if "github." in domain:
            return "GitHub"
        if "news.ycombinator.com" in domain:
            return "Hacker News"

        return domain
    except Exception:
        return "Direct / None"
