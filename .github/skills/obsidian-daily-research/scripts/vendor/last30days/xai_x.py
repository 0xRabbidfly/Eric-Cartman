"""xAI API client for X (Twitter) discovery."""

import json
import re
import sys
from typing import Any, Dict, List, Optional

from . import http


def _log(msg: str):
    """Log info to stderr."""
    sys.stderr.write(f"[X] {msg}\n")
    sys.stderr.flush()


def _log_error(msg: str):
    """Log error to stderr."""
    sys.stderr.write(f"[X ERROR] {msg}\n")
    sys.stderr.flush()

# xAI uses responses endpoint with Agent Tools API
XAI_RESPONSES_URL = "https://api.x.ai/v1/responses"

# Depth configurations: (min, max) posts to request
DEPTH_CONFIG = {
    "scan": (5, 8),
    "quick": (8, 12),
    "default": (20, 30),
    "deep": (40, 60),
}

X_SEARCH_PROMPT = """You have access to real-time X (Twitter) data. Search for posts about: {topic}

Focus on posts from {from_date} to {to_date}. Find {min_items}-{max_items} high-quality, relevant posts.

IMPORTANT RULES:
1. For EACH post, include an inline citation link so I can trace the source.
2. Return ONLY valid JSON in the exact format below, no other text.
3. The url for each item MUST be the real X post URL from your search results. Do NOT fabricate or guess status IDs.

{{
  "items": [
    {{
      "text": "Post text content (truncated if long)",
      "url": "https://x.com/user/status/...",
      "author_handle": "username",
      "date": "YYYY-MM-DD or null if unknown",
      "engagement": {{
        "likes": 100,
        "reposts": 25,
        "replies": 15,
        "quotes": 5
      }},
      "why_relevant": "Brief explanation of relevance",
      "relevance": 0.85
    }}
  ]
}}

Rules:
- url MUST be the exact URL from the search results — never invent a status ID
- relevance is 0.0 to 1.0 (1.0 = highly relevant)
- date must be YYYY-MM-DD format or null
- engagement can be null if unknown
- Include diverse voices/accounts if applicable
- Prefer posts with substantive content, not just links"""

# Strict prompt for must-follow account scans.
# Only original posts authored BY the handle — no replies, no @-mentions.
MUST_FOLLOW_PROMPT = """You have access to real-time X (Twitter) data.

Find {min_items}-{max_items} ORIGINAL posts authored by EXACTLY this account: @{handle}
Date range: {from_date} to {to_date}.

CRITICAL RULES — read carefully:
1. ONLY return posts where the AUTHOR is @{handle}. The post must be written/published by @{handle}.
2. Do NOT return posts by other users that merely @-mention or tag @{handle}.
3. Do NOT return replies by @{handle} to other users (no posts starting with "@someone").
4. Do NOT return retweets/reposts — only original content from @{handle}.
5. Every item in your response MUST have author_handle = "{handle}".
6. If @{handle} has fewer than {min_items} original posts in this date range, return whatever exists — do NOT pad with other accounts' posts.
7. The url for each item MUST be the real X post URL from your search results. Do NOT fabricate or guess status IDs.

IMPORTANT: Return ONLY valid JSON in this exact format, no other text:
{{
  "items": [
    {{
      "text": "Post text content (truncated if long)",
      "url": "https://x.com/{handle}/status/...",
      "author_handle": "{handle}",
      "date": "YYYY-MM-DD or null if unknown",
      "is_reply": false,
      "engagement": {{
        "likes": 100,
        "reposts": 25,
        "replies": 15,
        "quotes": 5
      }},
      "why_relevant": "Brief description of what this post is about",
      "relevance": 0.85
    }}
  ]
}}

Remember: author_handle MUST be "{handle}" for every single item. URLs MUST be real — never invent status IDs."""


def _build_x_search_tool(
    from_date: str = "",
    to_date: str = "",
    allowed_handles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build x_search tool definition with API-level parameters.

    Uses xAI Responses API tool parameters for filtering, which is far
    more reliable than prompt-based filtering.

    See: https://docs.x.ai/developers/tools/x-search
    """
    tool: Dict[str, Any] = {"type": "x_search"}
    params: Dict[str, Any] = {}

    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date
    if allowed_handles:
        # API supports max 10 handles
        params["allowed_x_handles"] = allowed_handles[:10]

    if params:
        tool["x_search"] = params

    return tool


def search_x(
    api_key: str,
    model: str,
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    mock_response: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Search X for relevant posts using xAI API with live search.

    Args:
        api_key: xAI API key
        model: Model to use
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        depth: Research depth - "quick", "default", or "deep"
        mock_response: Mock response for testing

    Returns:
        Raw API response
    """
    if mock_response is not None:
        return mock_response

    min_items, max_items = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Adjust timeout based on depth (generous for API response time)
    timeout = 90 if depth == "quick" else 120 if depth == "default" else 180

    # Use Agent Tools API with x_search — pass date range as API params
    payload = {
        "model": model,
        "tools": [
            _build_x_search_tool(from_date=from_date, to_date=to_date)
        ],
        "input": [
            {
                "role": "user",
                "content": X_SEARCH_PROMPT.format(
                    topic=topic,
                    from_date=from_date,
                    to_date=to_date,
                    min_items=min_items,
                    max_items=max_items,
                ),
            }
        ],
    }

    return http.post(XAI_RESPONSES_URL, payload, headers=headers, timeout=timeout)


def search_x_must_follow(
    api_key: str,
    model: str,
    handle: str,
    from_date: str,
    to_date: str,
    depth: str = "scan",
    mock_response: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Search X for original posts by a specific must-follow account.

    Uses the x_search API's allowed_x_handles parameter to filter at
    the API level (not just prompt), plus a strict prompt for additional
    safety.

    Args:
        api_key: xAI API key
        model: Model to use
        handle: X handle to search (without @)
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        depth: Research depth
        mock_response: Mock response for testing

    Returns:
        Raw API response
    """
    if mock_response is not None:
        return mock_response

    min_items, max_items = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    timeout = 90 if depth == "quick" else 120 if depth == "default" else 180

    # Clean handle (remove @ if present)
    clean_handle = handle.lstrip("@")

    # Use allowed_x_handles + from_date/to_date at API level — this is
    # the primary filter. The prompt is belt-and-suspenders.
    payload = {
        "model": model,
        "tools": [
            _build_x_search_tool(
                from_date=from_date,
                to_date=to_date,
                allowed_handles=[clean_handle],
            )
        ],
        "input": [
            {
                "role": "user",
                "content": MUST_FOLLOW_PROMPT.format(
                    handle=clean_handle,
                    from_date=from_date,
                    to_date=to_date,
                    min_items=min_items,
                    max_items=max_items,
                ),
            }
        ],
    }

    return http.post(XAI_RESPONSES_URL, payload, headers=headers, timeout=timeout, retries=1)


# Batched must-follow prompt — searches multiple handles in a single API call.
# Uses the allowed_x_handles API param (max 10) to filter at the API level.
MUST_FOLLOW_BATCH_PROMPT = """You have access to real-time X (Twitter) data.

Find ORIGINAL posts from these accounts: {handles_list}
Date range: {from_date} to {to_date}.
Target: {min_items}-{max_items} posts total across all accounts.

CRITICAL RULES — read carefully:
1. ONLY return posts AUTHORED by the accounts listed above.
2. Do NOT return posts by other users that merely @-mention or tag these accounts.
3. Do NOT return replies to other users (no posts starting with "@someone").
4. Do NOT return retweets/reposts — only original content.
5. Every item MUST have the correct author_handle matching the actual author.
6. If an account has no original posts in this date range, skip it — do NOT pad with other accounts' posts.
7. The url for each item MUST be the real X post URL from your search results. Do NOT fabricate or guess status IDs.

IMPORTANT: Return ONLY valid JSON in this exact format, no other text:
{{
  "items": [
    {{
      "text": "Post text content (truncated if long)",
      "url": "https://x.com/username/status/...",
      "author_handle": "username",
      "date": "YYYY-MM-DD or null if unknown",
      "is_reply": false,
      "engagement": {{
        "likes": 100,
        "reposts": 25,
        "replies": 15,
        "quotes": 5
      }},
      "why_relevant": "Brief description of what this post is about",
      "relevance": 0.85
    }}
  ]
}}

Remember: author_handle MUST match the ACTUAL author for every item. URLs MUST be real — never invent status IDs."""


def search_x_must_follow_batch(
    api_key: str,
    model: str,
    handles: List[str],
    from_date: str,
    to_date: str,
    depth: str = "scan",
    mock_response: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Search X for original posts by multiple must-follow accounts in one call.

    Uses allowed_x_handles (max 10) to batch API-level filtering for an entire
    group of accounts. Dramatically reduces API call count vs per-handle calls.

    Args:
        api_key: xAI API key
        model: Model to use
        handles: List of X handles (without @), max 10
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        depth: Research depth
        mock_response: Mock response for testing

    Returns:
        Raw API response
    """
    if mock_response is not None:
        return mock_response

    min_items, max_items = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    # Scale items target with number of handles
    max_items = min(max_items * len(handles), 60)
    min_items = min(min_items * len(handles), max_items)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    timeout = 180  # batched calls need more time

    # Clean handles
    clean_handles = [h.lstrip("@") for h in handles[:10]]
    handles_list = ", ".join(f"@{h}" for h in clean_handles)

    payload = {
        "model": model,
        "tools": [
            _build_x_search_tool(
                from_date=from_date,
                to_date=to_date,
                allowed_handles=clean_handles,
            )
        ],
        "input": [
            {
                "role": "user",
                "content": MUST_FOLLOW_BATCH_PROMPT.format(
                    handles_list=handles_list,
                    from_date=from_date,
                    to_date=to_date,
                    min_items=min_items,
                    max_items=max_items,
                ),
            }
        ],
    }

    return http.post(XAI_RESPONSES_URL, payload, headers=headers, timeout=timeout, retries=1)


# ---------------------------------------------------------------------------
# Citation / annotation extraction — get REAL URLs from the API response
# ---------------------------------------------------------------------------

_X_STATUS_RE = re.compile(r'https://x\.com/\w+/status/\d+')
_X_STATUS_I_RE = re.compile(r'https://x\.com/i/status/(\d+)')


def _extract_citation_urls(response: Dict[str, Any]) -> List[str]:
    """Extract real x.com status URLs from the xAI response.

    Checks TWO reliable sources (NOT the model's output text, which may
    contain fabricated URLs):
    1. Top-level `citations` list (always returned by the API)
    2. `annotations` on output_text items (url_citation type)

    Returns:
        List of real x.com/*/status/* URLs (deduplicated, order preserved)
    """
    seen = set()
    urls: List[str] = []

    def _add(url: str):
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    # 1. Top-level citations (most reliable — complete list of all sources)
    for cit in response.get("citations", []):
        if isinstance(cit, str) and "/status/" in cit:
            _add(cit)
        elif isinstance(cit, dict):
            u = cit.get("url", "")
            if "/status/" in u:
                _add(u)

    # 2. Annotations on output_text items (url_citation entries from the API)
    output = response.get("output", [])
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            # Check message content annotations
            if item.get("type") == "message":
                for content_item in item.get("content", []):
                    if not isinstance(content_item, dict):
                        continue
                    for ann in content_item.get("annotations", []):
                        if isinstance(ann, dict):
                            u = ann.get("url", "")
                            if "/status/" in u:
                                _add(u)

    # NOTE: We intentionally do NOT scan the model's output text for URLs.
    # The model may fabricate plausible-looking status IDs. Only the API's
    # citations and annotations contain verified real URLs.

    return urls


def _extract_output_text(response: Dict[str, Any]) -> str:
    """Extract the model's output text from the response."""
    output_text = ""
    if "output" in response:
        output = response["output"]
        if isinstance(output, str):
            return output
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

    # Also check for choices (older format)
    if not output_text and "choices" in response:
        for choice in response["choices"]:
            if "message" in choice:
                output_text = choice["message"].get("content", "")
                break

    return output_text


def _fix_urls_from_citations(
    items: List[Dict[str, Any]],
    citation_urls: List[str],
) -> List[Dict[str, Any]]:
    """Cross-reference model-generated URLs with real citation URLs.

    The model sometimes fabricates status IDs but usually gets the author
    handle correct. Strategy:
    1. If model URL is already in the citation set → keep (verified real).
    2. If model URL handle matches author_handle → keep (trust the model's
       status ID; blindly swapping risks assigning the wrong tweet when an
       author has multiple citations).
    3. If handle is wrong/missing → replace with first citation URL for the
       correct author, or fall back to anonymous x.com/i/status/* URLs.

    Args:
        items: Parsed model items (may have fabricated URLs)
        citation_urls: Real URLs extracted from citations/annotations

    Returns:
        Items with URLs fixed where possible
    """
    if not citation_urls:
        return items

    # Build lookup: author_handle -> [real_urls] (citation order preserved)
    author_urls: Dict[str, List[str]] = {}
    for url in citation_urls:
        m = re.match(r'https://x\.com/(\w+)/status/\d+', url)
        if m:
            handle = m.group(1).lower()
            if handle != "i":  # x.com/i/status/* is handle-less
                author_urls.setdefault(handle, []).append(url)

    # Flat set for exact-match validation
    citation_set = set(citation_urls)

    # Pool of handle-less x.com/i/status/* URLs as last resort
    anon_urls = [u for u in citation_urls if "/i/status/" in u]
    anon_idx = 0

    for item in items:
        model_url = item.get("url", "")
        author = item.get("author_handle", "").lower().lstrip("@")

        # Case 1: model URL is a verified citation — keep and remove from pool
        if model_url in citation_set:
            if author and author in author_urls and model_url in author_urls[author]:
                author_urls[author].remove(model_url)
            continue

        # Case 2: model URL already points to the correct author — keep it.
        # Replacing it with a citation URL risks swapping the wrong tweet when
        # an author has multiple posts (the original bug this fixes).
        url_handle_match = re.match(r'https://x\.com/(\w+)/status/\d+', model_url)
        if url_handle_match:
            url_handle = url_handle_match.group(1).lower()
            if url_handle == author and author:
                if http.DEBUG:
                    _log(f"URL kept (handle match): {model_url} (@{author})")
                continue

        # Case 3: handle mismatch or malformed — replace with real citation URL
        if author and author in author_urls and author_urls[author]:
            real_url = author_urls[author].pop(0)
            if http.DEBUG:
                _log(f"URL fix: {model_url} → {real_url} (matched @{author})")
            item["url"] = real_url
        elif anon_urls and anon_idx < len(anon_urls):
            real_url = anon_urls[anon_idx]
            anon_idx += 1
            if http.DEBUG:
                _log(f"URL fix (anon): {model_url} → {real_url}")
            item["url"] = real_url
        else:
            if http.DEBUG:
                _log(f"URL unverified (no citation match): {model_url}")

    return items


def parse_x_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse xAI response to extract X items.

    Extracts items from the model's JSON output, then cross-references
    URLs with real citation URLs from the API response to fix any
    fabricated status IDs.

    Args:
        response: Raw API response

    Returns:
        List of item dicts with real URLs where possible
    """
    items = []

    # Check for API errors first
    if "error" in response and response["error"]:
        error = response["error"]
        err_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        _log_error(f"xAI API error: {err_msg}")
        if http.DEBUG:
            _log_error(f"Full error response: {json.dumps(response, indent=2)[:1000]}")
        return items

    # Debug: dump response structure
    if http.DEBUG:
        _log(f"Response keys: {list(response.keys())}")
        if "citations" in response:
            _log(f"Citations ({len(response['citations'])}): {response['citations'][:5]}")
        if "output" in response and isinstance(response["output"], list):
            types = [item.get("type", "?") if isinstance(item, dict) else type(item).__name__
                     for item in response["output"]]
            _log(f"Output item types: {types}")

    # Extract real URLs from citations/annotations
    citation_urls = _extract_citation_urls(response)
    if http.DEBUG:
        _log(f"Extracted {len(citation_urls)} citation URLs")

    # Extract the model's text output
    output_text = _extract_output_text(response)
    if not output_text:
        # If no model text but we have citation URLs, we can't build items
        # (we need the metadata from the model's JSON)
        return items

    # Extract JSON from the response
    json_match = re.search(r'\{[\s\S]*"items"[\s\S]*\}', output_text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            items = data.get("items", [])
        except json.JSONDecodeError:
            pass

    # Validate and clean items
    clean_items = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        url = item.get("url", "")
        if not url:
            continue

        # Parse engagement
        engagement = None
        eng_raw = item.get("engagement")
        if isinstance(eng_raw, dict):
            engagement = {
                "likes": int(eng_raw.get("likes", 0)) if eng_raw.get("likes") else None,
                "reposts": int(eng_raw.get("reposts", 0)) if eng_raw.get("reposts") else None,
                "replies": int(eng_raw.get("replies", 0)) if eng_raw.get("replies") else None,
                "quotes": int(eng_raw.get("quotes", 0)) if eng_raw.get("quotes") else None,
            }

        clean_item = {
            "id": f"X{i+1}",
            "text": str(item.get("text", "")).strip()[:500],  # Truncate long text
            "url": url,
            "author_handle": str(item.get("author_handle", "")).strip().lstrip("@"),
            "date": item.get("date"),
            "is_reply": bool(item.get("is_reply", False)),
            "engagement": engagement,
            "why_relevant": str(item.get("why_relevant", "")).strip(),
            "relevance": min(1.0, max(0.0, float(item.get("relevance", 0.5)))),
        }

        # Validate date format
        if clean_item["date"]:
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(clean_item["date"])):
                clean_item["date"] = None

        clean_items.append(clean_item)

    # Cross-reference model URLs with real citation URLs
    if citation_urls:
        clean_items = _fix_urls_from_citations(clean_items, citation_urls)

    return clean_items
