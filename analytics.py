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


def detect_device_name(user_agent: str | None) -> str:
    """Extract a human-friendly device, OS, and browser name from the User-Agent header.
    
    Examples:
    - 'iPhone (Safari)'
    - 'Windows 10/11 (Chrome)'
    - 'Mac (Safari)'
    - 'Android Phone (Chrome)'
    - 'Linux (Firefox)'
    - 'iPad (Safari)'
    - 'Googlebot'
    """
    if not user_agent or not user_agent.strip():
        return "Unknown Device"

    ua = user_agent.strip()
    ua_lower = ua.lower()

    # Detect bots
    if BOT_PATTERNS.search(ua):
        if "googlebot" in ua_lower:
            return "Googlebot"
        if "discordbot" in ua_lower:
            return "Discordbot"
        if "twitterbot" in ua_lower or "x.com" in ua_lower:
            return "Twitterbot"
        if "slackbot" in ua_lower:
            return "Slackbot"
        if "curl" in ua_lower:
            return "cURL Client"
        if "python" in ua_lower or "httpx" in ua_lower:
            return "Python HTTP Client"
        return "Bot / Crawler"

    # Detect Platform / Operating System
    platform = "Desktop"
    if "iphone" in ua_lower:
        platform = "iPhone"
    elif "ipad" in ua_lower:
        platform = "iPad"
    elif "android" in ua_lower:
        platform = "Android Tablet" if "tablet" in ua_lower or "mobile" not in ua_lower else "Android Phone"
    elif "windows" in ua_lower:
        if "windows nt 10.0" in ua_lower:
            platform = "Windows 10/11"
        else:
            platform = "Windows"
    elif "macintosh" in ua_lower or "mac os" in ua_lower:
        platform = "Mac"
    elif "linux" in ua_lower:
        platform = "Linux"
    elif "cros" in ua_lower:
        platform = "ChromeOS"

    # Detect Browser
    browser = ""
    if "edg/" in ua_lower or "edge/" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "samsungbrowser" in ua_lower:
        browser = "Samsung Internet"
    elif "chrome/" in ua_lower:
        browser = "Chrome"
    elif "firefox/" in ua_lower:
        browser = "Firefox"
    elif "safari/" in ua_lower:
        browser = "Safari"

    if platform and browser:
        return f"{platform} ({browser})"
    return platform or browser or "Unknown Device"


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
