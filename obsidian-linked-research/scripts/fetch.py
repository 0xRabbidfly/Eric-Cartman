"""Fetch URL content for obsidian-linked-research skill.

Two paths:
  - Tweet/X URLs → xAI Responses API with x_search tool (rich engagement data)
  - Everything else → stdlib urllib fetch + HTML strip (plain text)

Output: JSON to stdout.

Usage:
  python fetch.py <url>

Requires XAI_API_KEY in environment or .env for tweet URLs.
Web URLs work without any API key.

Zero pip dependencies — stdlib only.
"""

import html as html_mod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

XAI_RESPONSES_URL = "https://api.x.ai/v1/responses"
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-1-fast")
DEBUG = os.environ.get("LINKED_RESEARCH_DEBUG", "").lower() in ("1", "true", "yes")

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _log(msg: str):
    if DEBUG:
        sys.stderr.write(f"[fetch] {msg}\n")
        sys.stderr.flush()


def _log_error(msg: str):
    sys.stderr.write(f"[fetch ERROR] {msg}\n")
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# .env loader (same cascade as last30days)
# ---------------------------------------------------------------------------


def _load_env_file(path: Path) -> Dict[str, str]:
    """Load key=value pairs from a dotenv file."""
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key and value:
                    env[key] = value
    return env


def _get_xai_key() -> Optional[str]:
    """Resolve XAI_API_KEY from env → repo .env → ~/.config/last30days/.env."""
    key = os.environ.get("XAI_API_KEY")
    if key:
        return key

    # Repo-root .env (walk up from this script)
    script_dir = Path(__file__).resolve().parent
    for parent in [script_dir] + list(script_dir.parents):
        env_path = parent / ".env"
        if env_path.exists():
            env = _load_env_file(env_path)
            if env.get("XAI_API_KEY"):
                return env["XAI_API_KEY"]

    # Shared config
    config_env = Path.home() / ".config" / "last30days" / ".env"
    env = _load_env_file(config_env)
    return env.get("XAI_API_KEY")


# ---------------------------------------------------------------------------
# HTTP helper (stdlib only, modeled on last30days/lib/http.py)
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_DELAY = 1.0


class HTTPError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _http_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    """Make an HTTP request and return parsed JSON."""
    headers = headers or {}
    headers.setdefault("User-Agent", "obsidian-linked-research/1.0")

    data = None
    if json_data is not None:
        data = json.dumps(json_data).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    _log(f"{method} {url}")

    last_error: Optional[HTTPError] = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                _log(f"Response: {resp.status} ({len(body)} bytes)")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            err_body = None
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            _log(f"HTTP {e.code}: {e.reason}")
            last_error = HTTPError(f"HTTP {e.code}: {e.reason}", e.code, err_body)
            if 400 <= e.code < 500 and e.code != 429:
                raise last_error
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except urllib.error.URLError as e:
            _log(f"URL Error: {e.reason}")
            last_error = HTTPError(f"URL Error: {e.reason}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except json.JSONDecodeError as e:
            raise HTTPError(f"Invalid JSON response: {e}")
        except (OSError, TimeoutError, ConnectionResetError) as e:
            _log(f"Connection error: {type(e).__name__}: {e}")
            last_error = HTTPError(f"Connection error: {type(e).__name__}: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

    if last_error:
        raise last_error
    raise HTTPError("Request failed with no error details")


# ---------------------------------------------------------------------------
# URL classification
# ---------------------------------------------------------------------------

_X_RE = re.compile(r"https?://(?:www\.)?(x\.com|twitter\.com)/", re.IGNORECASE)


def _normalize_url(url: str) -> str:
    """Strip tracking query params (s=, t=, etc.) from URLs.

    Share links append junk like ?s=20 (web) or ?s=46&t=... (iOS).
    Returns the canonical URL without those params.
    """
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    parsed = urlparse(url)
    if not parsed.query:
        return url
    # Keep only params that aren't share-tracking noise
    _STRIP_PARAMS = {"s", "t", "ref_src", "ref_url", "src"}
    kept = {k: v for k, v in parse_qs(parsed.query).items() if k not in _STRIP_PARAMS}
    clean_query = urlencode(kept, doseq=True) if kept else ""
    return urlunparse(parsed._replace(query=clean_query))


def is_tweet_url(url: str) -> bool:
    """Return True if URL points to an X/Twitter post."""
    return bool(_X_RE.match(url))


def _resolve_redirect(url: str, timeout: int = 10) -> Optional[str]:
    """Follow HTTP redirects (e.g. t.co shortlinks) and return the final URL.

    Returns the resolved URL or None on failure.
    Does a HEAD request to avoid downloading the full page.
    """
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": CHROME_UA})
        # Build an opener that doesn't auto-follow redirects so we can read Location
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None  # stop following
        opener = urllib.request.build_opener(NoRedirect)
        try:
            opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location", "")
                if location:
                    _log(f"Redirect {e.code}: {url} → {location}")
                    return location
        # If no redirect, try following normally
        req2 = urllib.request.Request(url, method="HEAD", headers={"User-Agent": CHROME_UA})
        with urllib.request.urlopen(req2, timeout=timeout) as resp:
            return resp.url
    except Exception as e:
        _log(f"Redirect resolution failed for {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Tweet fetching via xAI Responses API with x_search
# ---------------------------------------------------------------------------

TWEET_FETCH_PROMPT = """You have access to real-time X (Twitter) data. I need the FULL content of this specific post/thread:

URL: {url}

Return ONLY valid JSON in this exact format, no other text:
{{
  "text": "The complete post text (include full thread if it's a thread)",
  "author_handle": "username (without @)",
  "author_name": "Display Name",
  "date": "YYYY-MM-DD",
  "engagement": {{
    "likes": 100,
    "reposts": 25,
    "replies": 15,
    "quotes": 5
  }},
  "thread_context": "If this is part of a thread, include the preceding context here. Otherwise empty string.",
  "is_thread": false,
  "media_descriptions": ["Description of any images/videos if present"],
  "image_urls": ["https://pbs.twimg.com/media/... direct image URLs"],
  "url": "{url}"
}}

Rules:
- Get the EXACT post content, don't paraphrase
- If it's a thread, concatenate all posts in order in the 'text' field
- date must be YYYY-MM-DD format or null if unknown
- engagement values can be null if unknown
- media_descriptions: describe any images/videos attached to the post
- image_urls: include ALL direct image/media URLs (pbs.twimg.com links). Return empty array if none.
- Output ONLY valid JSON, no markdown fences
"""


# Regex to find URLs embedded in tweet text
_URL_IN_TEXT_RE = re.compile(r'https?://\S+')
_X_ARTICLE_RE = re.compile(r'https?://(?:www\.)?x\.com/i/article/\d+', re.IGNORECASE)


X_ARTICLE_FETCH_PROMPT = """You have access to real-time X (Twitter) data. I need the FULL content of this X Article:

URL: {url}

This is a long-form X Article (not a regular tweet). Please retrieve and return the COMPLETE article text.

Return ONLY valid JSON in this exact format, no other text:
{{
  "article_title": "The title of the article",
  "article_text": "The complete article text, preserving paragraphs with newlines",
  "author_handle": "username (without @)",
  "author_name": "Display Name",
  "image_urls": ["https://pbs.twimg.com/media/... direct image URLs from the article"]
}}

Rules:
- Get the COMPLETE article text — do not truncate or summarize
- Preserve paragraph breaks as newlines
- image_urls: include ALL direct image/media URLs embedded in the article (pbs.twimg.com links). Return empty array if none.
- Output ONLY valid JSON, no markdown fences
"""


def fetch_tweet(url: str, api_key: str) -> Dict[str, Any]:
    """Fetch tweet content via xAI Responses API with x_search tool.

    If the tweet contains an embedded X Article or external URL,
    does a follow-up fetch to get the full article content.

    Returns parsed tweet data dict with optional 'article_content' field.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": XAI_MODEL,
        "tools": [{"type": "x_search"}],
        "input": [
            {
                "role": "user",
                "content": TWEET_FETCH_PROMPT.format(url=url),
            }
        ],
    }

    raw = _http_request("POST", XAI_RESPONSES_URL, headers=headers, json_data=payload, timeout=120)
    data = _parse_xai_response(raw)

    if "error" in data:
        return data

    # --- Follow-up: detect embedded URLs and fetch full content ---
    text = data.get("text", "")
    embedded_urls = _URL_IN_TEXT_RE.findall(text)

    # Resolve t.co shortlinks to their real destinations
    resolved_urls = []
    for u in embedded_urls:
        u = u.rstrip(".,;:!?)")
        if "t.co/" in u:
            real = _resolve_redirect(u)
            if real:
                _log(f"Resolved t.co → {real}")
                u = real
        resolved_urls.append(_normalize_url(u))

    for embedded_url in resolved_urls:
        # X Article → xAI can't read these (JS-rendered), signal agent to use browser
        if _X_ARTICLE_RE.match(embedded_url):
            _log(f"X Article detected in tweet → requires browser fetch: {embedded_url}")
            # Try xAI first — it may get title/author even if not full text
            article = _fetch_x_article(embedded_url, api_key)
            article_text = (article.get("article_text", "") or "") if article else ""
            # Detect xAI stub responses (various phrasings for "I couldn't get it")
            _STUB_PHRASES = [
                "could not be retrieved", "not available", "tools available do not allow",
                "failed to fetch", "unable to retrieve", "could not retrieve",
                "could not access", "cannot access", "not accessible",
            ]
            is_stub = len(article_text) < 300 or any(p in article_text.lower() for p in _STUB_PHRASES)
            if article and not article.get("error"):
                data["article_title"] = article.get("article_title", "")
                if not data.get("author_name") and article.get("author_name"):
                    data["author_name"] = article["author_name"]
                # Merge article image_urls into main result
                article_imgs = article.get("image_urls", [])
                if article_imgs:
                    existing = data.get("image_urls", [])
                    data["image_urls"] = existing + [u for u in article_imgs if u not in existing]
                if not is_stub:
                    data["article_content"] = article_text
                else:
                    data["article_content"] = ""
                    data["article_url"] = embedded_url
                    data["needs_browser"] = True
            else:
                data["article_url"] = embedded_url
                data["needs_browser"] = True
            break  # only fetch the first article

        # External URL (not x.com) → web fetch
        elif not _X_RE.match(embedded_url):
            _log(f"External URL detected in tweet → web fetch: {embedded_url}")
            web = fetch_web(embedded_url)
            if not web.get("error"):
                data["article_content"] = web.get("content", "")
                data["article_title"] = web.get("title", "")
            break  # only fetch the first external link

    return data


def _fetch_x_article(url: str, api_key: str) -> Dict[str, Any]:
    """Fetch full X Article content via xAI."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": XAI_MODEL,
        "tools": [{"type": "x_search"}],
        "input": [
            {
                "role": "user",
                "content": X_ARTICLE_FETCH_PROMPT.format(url=url),
            }
        ],
    }

    try:
        raw = _http_request("POST", XAI_RESPONSES_URL, headers=headers, json_data=payload, timeout=60)
    except HTTPError as e:
        _log_error(f"X Article fetch failed: {e}")
        return {"error": str(e)}
    except (KeyboardInterrupt, TimeoutError) as e:
        _log_error(f"X Article fetch timed out or interrupted: {e}")
        return {"error": f"X Article fetch timed out: {e}"}

    return _parse_x_article_response(raw)


def _parse_x_article_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract article content from xAI response."""
    if "error" in response and response["error"]:
        return {"error": str(response["error"])}

    output_text = _extract_output_text(response)
    if not output_text:
        return {"error": "No output text in xAI response"}

    # Try parsing the whole output as JSON first
    try:
        data = json.loads(output_text)
        if isinstance(data, dict) and ("article_text" in data or "article_title" in data):
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting JSON block from surrounding text
    # Use a non-greedy match to avoid grabbing too much
    for pattern in [
        r'\{[^{}]*"article_text"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # shallow nesting
        r'\{[\s\S]*?"article_text"[\s\S]*?\}\s*$',  # from article_text to end
    ]:
        json_match = re.search(pattern, output_text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                continue

    # Last resort: try to find any JSON object
    for json_match in re.finditer(r'\{[^{}]+\}', output_text):
        try:
            data = json.loads(json_match.group())
            if isinstance(data, dict) and ("article_text" in data or "article_title" in data):
                return data
        except json.JSONDecodeError:
            continue

    # Fallback: return the raw text as article content
    _log("Could not parse X Article JSON — returning raw text")
    return {"article_text": output_text[:12000], "article_title": "", "author_handle": "", "author_name": ""}


def _extract_output_text(response: Dict[str, Any]) -> str:
    """Extract the output text string from an xAI Responses API response.

    Handles both the new output[] format and older choices[] format.
    """
    output_text = ""
    if "output" in response:
        output = response["output"]
        if isinstance(output, str):
            output_text = output
        elif isinstance(output, list):
            for item in output:
                if isinstance(item, dict):
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "output_text":
                                output_text = c.get("text", "")
                                break
                    elif "text" in item:
                        output_text = item["text"]
                elif isinstance(item, str):
                    output_text = item
                if output_text:
                    break

    # Fallback: older choices format
    if not output_text and "choices" in response:
        for choice in response["choices"]:
            if "message" in choice:
                output_text = choice["message"].get("content", "")
                break

    return output_text


def _parse_xai_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured tweet data from xAI Responses API output."""

    # Check for API errors
    if "error" in response and response["error"]:
        error = response["error"]
        err_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        _log_error(f"xAI API error: {err_msg}")
        return {"error": err_msg}

    output_text = _extract_output_text(response)
    if not output_text:
        _log_error("No output text in xAI response")
        return {"error": "No output text in xAI response"}

    # Extract JSON from response
    json_match = re.search(r'\{[\s\S]*"text"[\s\S]*\}', output_text)
    if not json_match:
        _log_error("No JSON found in xAI response")
        _log(f"Raw output: {output_text[:500]}")
        return {"error": "No JSON in response", "raw_text": output_text[:2000]}

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        _log_error("Invalid JSON in xAI response")
        return {"error": "Invalid JSON in response", "raw_text": output_text[:2000]}

    # Validate and clean
    if data.get("date"):
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(data["date"])):
            data["date"] = None

    engagement = data.get("engagement")
    if isinstance(engagement, dict):
        for key in ("likes", "reposts", "replies", "quotes"):
            val = engagement.get(key)
            if val is not None:
                try:
                    engagement[key] = int(val)
                except (ValueError, TypeError):
                    engagement[key] = None

    return data


# ---------------------------------------------------------------------------
# Web page fetching via urllib (plain text extraction)
# ---------------------------------------------------------------------------


def _extract_images(html: str, base_url: str) -> List[str]:
    """Extract meaningful image URLs from HTML.

    Finds <img> src attributes and <meta property="og:image"> content.
    Filters out tracking pixels, tiny icons, and data URIs.
    Resolves relative URLs against base_url.
    """
    from urllib.parse import urljoin, urlparse

    images: List[str] = []
    seen: set = set()

    def _add(src: str):
        if not src or src in seen:
            return
        # Skip data URIs, SVG inline, tracking pixels, tiny icons
        if src.startswith("data:"):
            return
        # Resolve relative URLs
        if not src.startswith("http"):
            src = urljoin(base_url, src)
        # Skip common non-content images
        _SKIP_PATTERNS = [
            r'favicon', r'logo[\-_.]', r'icon[\-_.]', r'sprite',
            r'tracking', r'pixel', r'1x1', r'badge', r'button',
            r'avatar[\-_.]', r'emoji', r'\.svg$',
        ]
        src_lower = src.lower()
        for pat in _SKIP_PATTERNS:
            if re.search(pat, src_lower):
                return
        seen.add(src)
        images.append(src)

    # OG image (highest priority — usually the hero/share image)
    og_match = re.search(
        r'<meta\s+(?:[^>]*?)property=["\']og:image["\']\s+content=["\'](.*?)["\']',
        html, re.IGNORECASE
    )
    if not og_match:
        # Try reversed attribute order: content before property
        og_match = re.search(
            r'<meta\s+(?:[^>]*?)content=["\'](.*?)["\']\s+(?:[^>]*?)property=["\']og:image["\']',
            html, re.IGNORECASE
        )
    if og_match:
        _add(og_match.group(1).strip())

    # <img> tags — extract src attributes
    for img_match in re.finditer(r'<img\s[^>]*?src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        _add(img_match.group(1).strip())

    _log(f"Extracted {len(images)} image(s) from HTML")
    return images


def fetch_web(url: str, timeout: int = 15) -> Dict[str, Any]:
    """Fetch a web page and extract plain text content + image URLs.

    Returns dict with url, title (from <title>), content (plain text, max 8000 chars),
    and image_urls (list of meaningful image URLs found in the page).
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": CHROME_UA,
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        _log_error(f"Failed to fetch {url}: {e}")
        return {"type": "web", "url": url, "title": "", "content": "", "image_urls": [], "error": str(e)}

    # Extract <title>
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    title = html_mod.unescape(title_match.group(1).strip()) if title_match else ""

    # Extract images BEFORE stripping HTML
    image_urls = _extract_images(raw, url)

    # Strip scripts, styles, then all HTML tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) < 100:
        _log_error(f"Extracted text too short ({len(text)} chars) for {url}")
        return {"type": "web", "url": url, "title": title, "content": text, "image_urls": image_urls, "error": "Content too short — may require JavaScript rendering"}

    return {
        "type": "web",
        "url": url,
        "title": title,
        "content": text[:8000],
        "image_urls": image_urls,
    }


# ---------------------------------------------------------------------------
# Image downloading
# ---------------------------------------------------------------------------


def download_images(image_urls: List[str], output_dir: str, slug: str = "img") -> List[Dict[str, str]]:
    """Download images to output_dir and return list of {url, filename, path}.

    Filenames are: {slug}-1.{ext}, {slug}-2.{ext}, etc.
    Handles pbs.twimg.com format= URLs and standard image extensions.
    """
    from pathlib import Path as P

    out = P(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results = []
    for i, url in enumerate(image_urls, 1):
        if not url or not url.startswith("http"):
            continue

        # Determine extension from URL
        ext = "jpg"  # default
        # pbs.twimg.com uses ?format=png&name=large
        fmt_match = re.search(r'[?&]format=(\w+)', url)
        if fmt_match:
            ext = fmt_match.group(1).lower()
        else:
            # Try extension from path
            path_ext = re.search(r'\.(jpe?g|png|gif|webp|svg)', url, re.IGNORECASE)
            if path_ext:
                ext = path_ext.group(1).lower()
                if ext == "jpeg":
                    ext = "jpg"

        filename = f"{slug}-{i}.{ext}"
        filepath = out / filename

        try:
            req = urllib.request.Request(url, headers={"User-Agent": CHROME_UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            with open(filepath, "wb") as f:
                f.write(data)
            _log(f"Downloaded image: {filename} ({len(data)} bytes)")
            results.append({"url": url, "filename": filename, "path": str(filepath)})
        except Exception as e:
            _log_error(f"Failed to download {url}: {e}")
            results.append({"url": url, "filename": filename, "error": str(e)})

    return results


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch URL content for obsidian-linked-research")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--download-images", metavar="DIR",
                        help="Download images to DIR and include local paths in output")
    parser.add_argument("--slug", default="img",
                        help="Filename prefix for downloaded images (default: img)")
    args = parser.parse_args()

    url = args.url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    url = _normalize_url(url)

    # Ensure UTF-8 stdout on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if is_tweet_url(url):
        api_key = _get_xai_key()
        if not api_key:
            result = {
                "type": "tweet",
                "url": url,
                "error": "XAI_API_KEY not found. Set it in .env, environment, or ~/.config/last30days/.env",
            }
        else:
            _log(f"Tweet URL detected → xAI x_search ({XAI_MODEL})")
            tweet_data = fetch_tweet(url, api_key)
            result = {"type": "tweet", "url": url, **tweet_data}
    else:
        _log(f"Web URL detected → HTTP fetch")
        result = fetch_web(url)

    # Download images if requested
    if args.download_images:
        all_image_urls = result.get("image_urls", [])
        if not all_image_urls:
            _log("No image URLs found in result")
        else:
            downloaded = download_images(all_image_urls, args.download_images, args.slug)
            result["downloaded_images"] = downloaded

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
