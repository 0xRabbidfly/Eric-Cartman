"""RSS feed parser — fetch and parse podcast RSS feeds.

Extracts episode metadata and audio enclosure URLs from RSS/Atom feeds.
Uses feedparser if available, falls back to stdlib xml.etree for zero-dep mode.
"""

import hashlib
import re
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# Try feedparser first, fall back to stdlib XML
# ---------------------------------------------------------------------------

_HAS_FEEDPARSER = False
try:
    import feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class Episode:
    """Parsed podcast episode from RSS."""

    def __init__(
        self,
        id: str,
        title: str,
        published: str,
        audio_url: str,
        duration: str = "",
        description: str = "",
        link: str = "",
        show_name: str = "",
    ):
        self.id = id
        self.title = title
        self.published = published  # YYYY-MM-DD
        self.audio_url = audio_url
        self.duration = duration
        self.description = description
        self.link = link
        self.show_name = show_name

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "title": self.title,
            "published": self.published,
            "audio_url": self.audio_url,
            "duration": self.duration,
            "description": self.description,
            "link": self.link,
            "show_name": self.show_name,
        }

    def safe_filename(self) -> str:
        """Generate a filesystem-safe filename from episode metadata."""
        # Strip dangerous characters
        safe_title = re.sub(r'[<>:"/\\|?*]', '', self.title)
        safe_title = safe_title.strip('. ')
        # Truncate to reasonable length
        if len(safe_title) > 120:
            safe_title = safe_title[:120].rsplit(' ', 1)[0]
        return f"{self.published} - {safe_title}"


# ---------------------------------------------------------------------------
# Feed parsing
# ---------------------------------------------------------------------------

def fetch_feed(rss_url: str, timeout: int = 30) -> str:
    """Fetch raw RSS XML from URL."""
    req = urllib.request.Request(
        rss_url,
        headers={
            "User-Agent": "podcast-to-obsidian/1.0 (https://github.com/eric-cartman)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_feed(rss_url: str, max_episodes: int = 50) -> List[Episode]:
    """Parse RSS feed and return list of Episode objects.

    Uses feedparser if available, otherwise falls back to stdlib XML parsing.
    """
    if _HAS_FEEDPARSER:
        return _parse_with_feedparser(rss_url, max_episodes)
    return _parse_with_stdlib(rss_url, max_episodes)


def _parse_with_feedparser(rss_url: str, max_episodes: int) -> List[Episode]:
    """Parse using feedparser library."""
    feed = feedparser.parse(rss_url)
    show_name = feed.feed.get("title", "Unknown Show")
    episodes = []

    for entry in feed.entries[:max_episodes]:
        # Find audio enclosure
        audio_url = ""
        for link in entry.get("links", []):
            if link.get("type", "").startswith("audio/") or link.get("rel") == "enclosure":
                audio_url = link.get("href", "")
                break
        for enc in entry.get("enclosures", []):
            if enc.get("type", "").startswith("audio/"):
                audio_url = enc.get("href", audio_url or "")
                break

        if not audio_url:
            continue  # Skip entries without audio

        # Parse date
        published = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                pass
        if not published and hasattr(entry, "published"):
            published = _parse_date_string(entry.published)

        # Episode ID — prefer guid, fall back to hash of audio URL
        ep_id = entry.get("id", "") or entry.get("guid", "")
        if not ep_id:
            ep_id = hashlib.sha256(audio_url.encode()).hexdigest()[:16]

        # Duration
        duration = ""
        itunes_duration = entry.get("itunes_duration", "")
        if itunes_duration:
            duration = _normalize_duration(str(itunes_duration))

        episodes.append(Episode(
            id=ep_id,
            title=entry.get("title", "Untitled"),
            published=published,
            audio_url=audio_url,
            duration=duration,
            description=_clean_html(entry.get("summary", "")),
            link=entry.get("link", ""),
            show_name=show_name,
        ))

    return episodes


def _parse_with_stdlib(rss_url: str, max_episodes: int) -> List[Episode]:
    """Fallback parser using stdlib xml.etree.ElementTree."""
    xml_text = fetch_feed(rss_url)
    root = ET.fromstring(xml_text)

    # Namespace handling
    ns = {
        "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "atom": "http://www.w3.org/2005/Atom",
    }

    channel = root.find("channel")
    if channel is None:
        return []

    show_name_el = channel.find("title")
    show_name = show_name_el.text if show_name_el is not None and show_name_el.text else "Unknown Show"

    episodes = []
    items = channel.findall("item")[:max_episodes]

    for item in items:
        # Audio enclosure
        enclosure = item.find("enclosure")
        audio_url = ""
        if enclosure is not None:
            audio_url = enclosure.get("url", "")
            enc_type = enclosure.get("type", "")
            if enc_type and not enc_type.startswith("audio/"):
                audio_url = ""  # Not audio

        if not audio_url:
            continue

        # Title
        title_el = item.find("title")
        title = title_el.text if title_el is not None and title_el.text else "Untitled"

        # Date
        pub_el = item.find("pubDate")
        published = ""
        if pub_el is not None and pub_el.text:
            published = _parse_date_string(pub_el.text)

        # Episode ID
        guid_el = item.find("guid")
        ep_id = guid_el.text if guid_el is not None and guid_el.text else ""
        if not ep_id:
            ep_id = hashlib.sha256(audio_url.encode()).hexdigest()[:16]

        # Duration
        duration_el = item.find("itunes:duration", ns)
        duration = ""
        if duration_el is not None and duration_el.text:
            duration = _normalize_duration(duration_el.text)

        # Description
        desc_el = item.find("description")
        description = ""
        if desc_el is not None and desc_el.text:
            description = _clean_html(desc_el.text)

        # Link
        link_el = item.find("link")
        link = link_el.text if link_el is not None and link_el.text else ""

        episodes.append(Episode(
            id=ep_id,
            title=title,
            published=published,
            audio_url=audio_url,
            duration=duration,
            description=description,
            link=link,
            show_name=show_name,
        ))

    return episodes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date_string(date_str: str) -> str:
    """Best-effort parse of RSS date string to YYYY-MM-DD."""
    # Common RSS date formats
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Last resort — extract YYYY-MM-DD pattern
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if match:
        return match.group(0)
    return ""


def _normalize_duration(raw: str) -> str:
    """Normalize itunes:duration to HH:MM:SS format."""
    raw = raw.strip()
    # Already HH:MM:SS or MM:SS
    if ":" in raw:
        parts = raw.split(":")
        if len(parts) == 2:
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        if len(parts) == 3:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return raw
    # Seconds only
    try:
        total = int(raw)
        h, remainder = divmod(total, 3600)
        m, s = divmod(remainder, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except ValueError:
        return raw


def _clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    # Truncate very long descriptions
    if len(clean) > 1000:
        clean = clean[:1000].rsplit(" ", 1)[0] + "..."
    return clean
