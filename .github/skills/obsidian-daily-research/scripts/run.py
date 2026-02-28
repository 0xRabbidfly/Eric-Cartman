#!/usr/bin/env python3
"""
obsidian-daily-research — Lightweight daily research pipeline.

Scans 5 topic tracks (agents, skills, models, MCP, RAG) using the
last30days lib in 'scan' mode, deduplicates against your Obsidian vault,
and writes a structured daily note.

Usage:
    python run.py                      # Full daily pipeline
    python run.py --topic agents       # Single topic only
    python run.py --dry-run            # Fetch + score, print to stdout
    python run.py --promote-only       # Just run #keep → Library pass
    python run.py --show-dedup         # Dump seen URLs from vault
    python run.py --costs              # Show token cost estimate after run

Scheduled via Windows Task Scheduler (see schedule.ps1).
"""

import argparse
import io
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Resolve paths
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent
CONFIG_FILE = SCRIPT_DIR / "config.json"

# Add last30days scripts dir to path FIRST so its 'lib' package is primary
LAST30DAYS_SCRIPTS = (SKILL_DIR.parent / "last30days" / "scripts").resolve()
sys.path.insert(0, str(LAST30DAYS_SCRIPTS))

# Import our own modules via direct file import (avoids 'lib' name clash)
import importlib.util

def _load_local_module(name: str, filepath: Path):
    """Load a module from the obsidian-daily-research scripts/lib/ directory."""
    spec = importlib.util.spec_from_file_location(name, str(filepath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_local_lib = SCRIPT_DIR / "lib"
topics_mod = _load_local_module("dr_topics", _local_lib / "topics.py")
vault = _load_local_module("dr_vault", _local_lib / "vault_v2.py")
promote = _load_local_module("dr_promote", _local_lib / "promote_v2.py")

# Feedback file path (relative to vault)
FEEDBACK_FILE = SCRIPT_DIR / "feedback.json"


def load_config() -> dict:
    """Load pipeline config from config.json."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback defaults
    return {
        "vault_path": str(Path.home() / "Documents" / "Obsidian Vault"),
        "dailies_folder": "Research/Dailies",
        "library_folder": "Research/Library",
        "keep_tag": "#keep",
        "kept_tag": "#kept",
        "items_per_topic": 8,
        "reading_list_max": 15,
        "depth": "scan",
    }


# ---------------------------------------------------------------------------
# Quality filters — engagement floor, long-form bias, priority accounts
# ---------------------------------------------------------------------------

def _is_spam(item, config: dict, source: str = "x") -> bool:
    """Detect spam/misleading content using config-driven patterns.

    Catches:
    - Claim/link mismatch (e.g., "official Anthropic guide" linking to random GitHub)
    - Low-effort engagement bait ("follow me for more", "like and retweet")
    """
    spam_cfg = config.get("quality_filters", {}).get("spam_detection", {})
    if not spam_cfg.get("enabled", False):
        return False

    text = (item.text if source == "x" else item.title).lower()
    url = item.url.lower()

    # --- Claim/link mismatch ---
    for pattern in spam_cfg.get("claim_link_mismatch_patterns", []):
        claim_re = pattern.get("claim_regex", "")
        link_must = [d.lower() for d in pattern.get("link_must_contain", [])]
        if claim_re and re.search(claim_re, text, re.IGNORECASE):
            # The text makes a claim — does the link back it up?
            if link_must and not any(domain in url for domain in link_must):
                return True  # Claim made but link is to a random domain

    # --- Low-effort engagement bait ---
    for bait in spam_cfg.get("low_effort_patterns", []):
        if re.search(bait, text, re.IGNORECASE):
            return True

    return False


def _classify_content(item, config: dict, source: str = "x") -> str:
    """Classify an item as 'deep-dive', 'lab-pulse', or 'general'.

    deep-dive:  Long-form threads (≥400 chars) or article links
    lab-pulse:  Posts from model providers / their lead devs
    general:    Everything else
    """
    qf = config.get("quality_filters", {})
    lab_accounts = qf.get("lab_accounts", {})
    long_form_min = qf.get("long_form_min_chars", 400)
    article_domains = [d.lower() for d in qf.get("article_domains", [])]

    # Build flat set of all lab handles
    lab_handles = set()
    for handles in lab_accounts.values():
        lab_handles.update(h.lower() for h in handles)

    # Lab pulse check
    if source == "x" and item.author_handle.lower() in lab_handles:
        return "lab-pulse"

    # Deep dive check
    if source == "x" and len(item.text) >= long_form_min:
        return "deep-dive"
    if source == "reddit":
        url_lower = item.url.lower()
        if any(domain in url_lower for domain in article_domains):
            return "deep-dive"
        if len(item.title) > 100:
            return "deep-dive"

    return "general"


def apply_quality_filters(result: dict, config: dict) -> dict:
    """Apply post-scoring quality filters to a topic scan result.

    Five passes, all config-driven via config.json → quality_filters:
      0. Spam detection  — drop misleading/bait content
      1. Engagement floor — drop low-engagement noise
      2. Long-form bonus  — boost articles / long threads
      3. Priority accounts — boost followed accounts & frontier labs
      4. Content classify  — tag each item as deep-dive/lab-pulse/general

    Modifies items in-place and removes filtered items from the result.
    """
    qf = config.get("quality_filters", {})
    if not qf:
        return result

    # --- 0. Spam detection (remove misleading content) ---
    result["x_items"] = [
        item for item in result["x_items"]
        if not _is_spam(item, config, "x")
    ]
    result["reddit_items"] = [
        item for item in result["reddit_items"]
        if not _is_spam(item, config, "reddit")
    ]

    min_eng = qf.get("min_engagement", {})
    reddit_floor = min_eng.get("reddit_score", 0)
    x_likes_floor = min_eng.get("x_likes", 0)

    long_form_bonus = qf.get("long_form_bonus", 0)
    long_form_min_chars = qf.get("long_form_min_chars", 400)
    article_domains = [d.lower() for d in qf.get("article_domains", [])]

    priority = qf.get("priority_accounts", {})
    priority_x = {h.lower() for h in priority.get("x", [])}
    priority_subs = {s.lower() for s in priority.get("reddit_subreddits", [])}
    priority_bonus = qf.get("priority_account_bonus", 0)

    # --- 1. Engagement floor (drop low-engagement items) ---
    # Exception: priority/lab accounts bypass engagement floor
    lab_handles = set()
    for handles in qf.get("lab_accounts", {}).values():
        lab_handles.update(h.lower() for h in handles)

    if reddit_floor > 0:
        result["reddit_items"] = [
            item for item in result["reddit_items"]
            if item.engagement is None  # keep items with unknown engagement
            or item.engagement.score is None
            or item.engagement.score >= reddit_floor
        ]
    if x_likes_floor > 0:
        result["x_items"] = [
            item for item in result["x_items"]
            if item.author_handle.lower() in lab_handles  # lab accounts bypass floor
            or item.author_handle.lower() in priority_x   # priority accounts bypass floor
            or item.engagement is None
            or item.engagement.likes is None
            or item.engagement.likes >= x_likes_floor
        ]

    # --- 2. Long-form content bonus ---
    if long_form_bonus > 0:
        # X: boost items with long text (threads, article links)
        for item in result["x_items"]:
            if len(item.text) >= long_form_min_chars:
                item.score = min(100, item.score + long_form_bonus)

        # Reddit: boost items linking to article domains or with long titles
        for item in result["reddit_items"]:
            url_lower = item.url.lower()
            is_article = any(domain in url_lower for domain in article_domains)
            is_long_title = len(item.title) > 100
            if is_article or is_long_title:
                item.score = min(100, item.score + long_form_bonus)

    # --- 3. Priority account boost ---
    if priority_bonus > 0:
        for item in result["x_items"]:
            if item.author_handle.lower() in priority_x:
                item.score = min(100, item.score + priority_bonus)

        for item in result["reddit_items"]:
            if item.subreddit.lower() in priority_subs:
                item.score = min(100, item.score + priority_bonus)

    # --- 4. Classify content (attach category metadata) ---
    for item in result["x_items"]:
        item._category = _classify_content(item, config, "x")
    for item in result["reddit_items"]:
        item._category = _classify_content(item, config, "reddit")

    return result


def run_topic_scan(
    topic: topics_mod.Topic,
    config: dict,
    l30_config: dict,
    selected_models: dict,
    from_date: str,
    to_date: str,
    seen_urls: set,
    seen_titles: set,
) -> dict:
    """Run a single topic scan. Returns a result dict.

    Uses last30days lib modules directly in scan mode.
    """
    from lib import (
        openai_reddit,
        xai_x,
        normalize,
        score,
        dedupe,
        schema,
    )

    result = {
        "topic": topic,
        "reddit_items": [],
        "x_items": [],
        "errors": [],
    }

    combined_query = topic.display_name

    # --- Reddit scan ---
    if l30_config.get("OPENAI_API_KEY"):
        try:
            # web_search tool requires a model that supports it (gpt-4o or higher)
            # gpt-4o-mini doesn't support web_search in Responses API
            model = selected_models.get("openai", "gpt-4o")
            raw = openai_reddit.search_reddit(
                l30_config["OPENAI_API_KEY"],
                model,
                combined_query,
                from_date,
                to_date,
                depth="scan",
            )
            items = openai_reddit.parse_reddit_response(raw)
            # Normalize
            normalized = normalize.normalize_reddit_items(items, from_date, to_date)
            filtered = normalize.filter_by_date_range(normalized, from_date, to_date)
            # Score
            scored = score.score_reddit_items(filtered)
            sorted_items = score.sort_items(scored)
            # Dedupe internally
            deduped = dedupe.dedupe_reddit(sorted_items)
            result["reddit_items"] = deduped
        except Exception as e:
            result["errors"].append(f"Reddit/{topic.slug}: {e}")

    # --- X scan ---
    if l30_config.get("XAI_API_KEY"):
        try:
            model = l30_config.get("xai_model", "grok-4-1-fast")
            raw = xai_x.search_x(
                l30_config["XAI_API_KEY"],
                model,
                combined_query,
                from_date,
                to_date,
                depth="scan",
            )
            items = xai_x.parse_x_response(raw)
            normalized = normalize.normalize_x_items(items, from_date, to_date)
            filtered = normalize.filter_by_date_range(normalized, from_date, to_date)
            scored = score.score_x_items(filtered)
            sorted_items = score.sort_items(scored)
            deduped = dedupe.dedupe_x(sorted_items)
            result["x_items"] = deduped
        except Exception as e:
            result["errors"].append(f"X/{topic.slug}: {e}")

    # --- Quality filters: engagement floor, long-form bias, priority accounts ---
    result = apply_quality_filters(result, config)

    # --- Vault dedup: remove items already seen ---
    result["reddit_items"] = [
        item for item in result["reddit_items"]
        if item.url not in seen_urls
        and not vault.title_is_seen(item.title, seen_titles)
    ]
    result["x_items"] = [
        item for item in result["x_items"]
        if item.url not in seen_urls
    ]

    return result


def synthesize_all(
    api_key: str,
    topic_results: list,
    from_date: str,
    to_date: str,
) -> dict:
    """Single batched synthesis call across all topics.

    Sends one gpt-5.2 call with combined data instead of 5 separate calls.
    """
    from lib import http

    # Build per-topic summaries
    sections = []
    for tr in topic_results:
        topic = tr["topic"]
        reddit_lines = []
        for item in tr["reddit_items"][:5]:
            eng = ""
            if item.engagement:
                parts = []
                if item.engagement.score is not None:
                    parts.append(f"{item.engagement.score}pts")
                if item.engagement.num_comments is not None:
                    parts.append(f"{item.engagement.num_comments}cmt")
                eng = f" [{', '.join(parts)}]" if parts else ""
            reddit_lines.append(f"  - r/{item.subreddit}: \"{item.title}\"{eng}")

        x_lines = []
        for item in tr["x_items"][:5]:
            eng = ""
            if item.engagement:
                parts = []
                if item.engagement.likes is not None:
                    parts.append(f"{item.engagement.likes}likes")
                eng = f" [{', '.join(parts)}]" if parts else ""
            text = item.text[:120] + "..." if len(item.text) > 120 else item.text
            x_lines.append(f"  - @{item.author_handle}{eng}: \"{text}\"")

        section = f"### {topic.display_name}\n"
        if reddit_lines:
            section += "Reddit:\n" + "\n".join(reddit_lines) + "\n"
        if x_lines:
            section += "X:\n" + "\n".join(x_lines) + "\n"
        if not reddit_lines and not x_lines:
            section += "(No new results)\n"
        sections.append(section)

    prompt = f"""You are a research analyst writing a DAILY morning briefing for an AI practitioner.
This is NOT a weekly summary. This covers what happened TODAY ({to_date}).

DATE: {to_date}
SCAN WINDOW: {from_date} to {to_date}

## SOURCE DATA
{chr(10).join(sections)}

## YOUR TASK
Produce a JSON daily briefing:

{{
  "briefing": "4-6 sentence summary of the biggest AI happenings TODAY. Lead with the single most impactful story. Be vivid and specific — name the companies, people, models, numbers. Write like a sharp morning newsletter opener, not a boring corporate recap. End with one forward-looking thought.",
  "lab_pulse_summary": "2-3 sentences summarizing what the major model providers (Anthropic, OpenAI, Google, Meta, Mistral) and their lead devs said or shipped today. If nothing notable, say so.",
  "topics": [
    {{
      "slug": "topic-slug",
      "headline": "One bold sentence summarizing this topic's news",
      "key_points": ["point1", "point2"]
    }}
  ]
}}

RULES:
- This is a DAILY briefing, not weekly. Use "today" language.
- briefing: lead with the POW moment — the one thing that matters most
- lab_pulse_summary: focus on the 3 big labs (Anthropic, OpenAI, Google) + any notable from Meta/Mistral
- Each topic: 1-3 key_points (short, specific, actionable)
- If a topic had no results, say "Quiet day for this topic"
- Output ONLY valid JSON"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-5.2",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
    }

    try:
        resp = http.post(
            "https://api.openai.com/v1/chat/completions",
            payload,
            headers=headers,
            timeout=60,
        )
        if "choices" in resp and resp["choices"]:
            content = resp["choices"][0].get("message", {}).get("content", "{}")
            return json.loads(content)
    except Exception as e:
        return {"briefing": f"Synthesis failed: {e}", "topics": [], "error": str(e)}

    return {"briefing": "", "topics": []}


# ---------------------------------------------------------------------------
# Must-Follow Account Scanning
# ---------------------------------------------------------------------------

def run_must_follow_scan(
    config: dict,
    l30_config: dict,
    from_date: str,
    to_date: str,
) -> list:
    """Scan must-follow accounts on X. No filters — every tweet is captured.

    Returns a list of dicts: {handle, label, group, items: [x_item, ...]}
    """
    from lib import xai_x, normalize

    must_follow = config.get("must_follow", {})
    accounts = must_follow.get("accounts", [])
    if not accounts or not l30_config.get("XAI_API_KEY"):
        return []

    model = l30_config.get("xai_model", "grok-4-1-fast")
    results = []

    for acct in accounts:
        handle = acct["handle"]
        label = acct.get("label", handle)
        group = acct.get("group", "Other")

        # Search specifically for this person's tweets
        query = f"from:@{handle}"
        try:
            raw = xai_x.search_x(
                l30_config["XAI_API_KEY"],
                model,
                query,
                from_date,
                to_date,
                depth="scan",
            )
            items = xai_x.parse_x_response(raw)
            normalized = normalize.normalize_x_items(items, from_date, to_date)
            # Keep ALL items — no scoring, no engagement filter, no dedup
            results.append({
                "handle": handle,
                "label": label,
                "group": group,
                "items": normalized,
            })
        except Exception as e:
            print(f"  [must-follow] @{handle}: error — {e}")
            results.append({
                "handle": handle,
                "label": label,
                "group": group,
                "items": [],
                "error": str(e),
            })

    return results


# ---------------------------------------------------------------------------
# Feedback Processing (#good / #bad tags)
# ---------------------------------------------------------------------------

def load_feedback(config: dict) -> dict:
    """Load accumulated feedback from feedback.json."""
    if FEEDBACK_FILE.exists():
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"good": [], "bad": [], "stats": {"total_good": 0, "total_bad": 0}}


def save_feedback(data: dict):
    """Save feedback data to feedback.json."""
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def process_feedback_tags(config: dict) -> dict:
    """Scan dailies for #good / #bad tags and accumulate feedback.

    Replaces #good → #good-noted, #bad → #bad-noted so items
    aren't reprocessed. Returns summary of what was found.
    """
    fb_config = config.get("feedback_tags", {})
    good_tag = fb_config.get("good_tag", "#good")
    bad_tag = fb_config.get("bad_tag", "#bad")
    suffix = fb_config.get("processed_tag_suffix", "-noted")

    dailies_folder = config.get("dailies_folder", "Research/Dailies")
    feedback_data = load_feedback(config)

    new_good = []
    new_bad = []

    # Scan dailies for feedback tags
    md_files = sorted(vault.list_md_files(dailies_folder))
    for filepath in md_files:
        text = vault.read_file(filepath)
        if not text:
            continue

        has_good = good_tag in text and f"{good_tag}{suffix}" not in text.replace(good_tag + suffix, "")
        has_bad = bad_tag in text and f"{bad_tag}{suffix}" not in text.replace(bad_tag + suffix, "")

        if not has_good and not has_bad:
            continue

        lines = text.splitlines()
        modified = False

        for i, line in enumerate(lines):
            # Skip already-processed lines
            if f"{good_tag}{suffix}" in line or f"{bad_tag}{suffix}" in line:
                continue

            # Extract link info from the line
            link_match = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', line)

            if good_tag in line and f"{good_tag}{suffix}" not in line:
                entry = {
                    "date": _extract_date_from_path(filepath),
                    "title": link_match.group(1) if link_match else line[:80],
                    "url": link_match.group(2) if link_match else "",
                    "source_file": filepath,
                }
                new_good.append(entry)
                lines[i] = line.replace(good_tag, f"{good_tag}{suffix}")
                modified = True

            if bad_tag in line and f"{bad_tag}{suffix}" not in line:
                entry = {
                    "date": _extract_date_from_path(filepath),
                    "title": link_match.group(1) if link_match else line[:80],
                    "url": link_match.group(2) if link_match else "",
                    "source_file": filepath,
                }
                new_bad.append(entry)
                lines[i] = line.replace(bad_tag, f"{bad_tag}{suffix}")
                modified = True

        if modified:
            vault.write_file(filepath, "\n".join(lines))

    # Accumulate
    if new_good or new_bad:
        feedback_data["good"].extend(new_good)
        feedback_data["bad"].extend(new_bad)
        feedback_data["stats"]["total_good"] += len(new_good)
        feedback_data["stats"]["total_bad"] += len(new_bad)
        save_feedback(feedback_data)

    return {"new_good": len(new_good), "new_bad": len(new_bad), "data": feedback_data}


def _extract_date_from_path(filepath: str) -> str:
    """Extract YYYY-MM-DD from a daily note path."""
    m = re.search(r'(\d{4}-\d{2}-\d{2})', filepath)
    return m.group(1) if m else ""


def render_daily_note(
    date_str: str,
    topic_results: list,
    synthesis: dict,
    config: dict,
    must_follow_results: list = None,
    feedback_summary: dict = None,
) -> str:
    """Render the full daily note markdown."""
    topic_slugs = [tr["topic"].slug for tr in topic_results]
    total_reddit = sum(len(tr["reddit_items"]) for tr in topic_results)
    total_x = sum(len(tr["x_items"]) for tr in topic_results)

    # Count must-follow tweets
    mf_count = sum(len(r["items"]) for r in (must_follow_results or []))

    # Collect categorized items across all topics
    deep_dives = []
    lab_pulse_items = []
    for tr in topic_results:
        topic = tr["topic"]
        for item in tr["x_items"]:
            cat = getattr(item, '_category', 'general')
            if cat == 'deep-dive':
                deep_dives.append((item, topic, 'x'))
            elif cat == 'lab-pulse':
                lab_pulse_items.append((item, topic, 'x'))
        for item in tr["reddit_items"]:
            cat = getattr(item, '_category', 'general')
            if cat == 'deep-dive':
                deep_dives.append((item, topic, 'reddit'))

    lines = [
        "---",
        f"date: {date_str}",
        "type: daily-research",
        f"topics: [{', '.join(topic_slugs)}]",
        "status: unread",
        f"reddit_items: {total_reddit}",
        f"x_items: {total_x}",
        f"must_follow_tweets: {mf_count}",
        f"deep_dives: {len(deep_dives)}",
        f"lab_pulse: {len(lab_pulse_items)}",
        "---",
        "",
        f"# Daily Research — {_format_date(date_str)}",
        "",
    ]

    # Briefing — the POW moment
    briefing = synthesis.get("briefing", "")
    if briefing:
        lines.extend([
            "## Today's POW",
            "",
            briefing,
            "",
        ])

    # Must Follow — every tweet from tracked accounts, grouped
    if must_follow_results:
        has_tweets = any(r["items"] for r in must_follow_results)
        if has_tweets:
            lines.extend([
                "## Must Follow \U0001f4cc",
                "",
            ])
            # Group by group label
            groups = {}
            for r in must_follow_results:
                if not r["items"]:
                    continue
                grp = r["group"]
                if grp not in groups:
                    groups[grp] = []
                groups[grp].append(r)

            for group_name, accounts in groups.items():
                lines.extend([f"### {group_name}", ""])
                for acct in accounts:
                    for item in acct["items"]:
                        text = item.text if hasattr(item, 'text') else str(item)
                        url = item.url if hasattr(item, 'url') else ""
                        likes = 0
                        if hasattr(item, 'engagement') and item.engagement and hasattr(item.engagement, 'likes'):
                            likes = item.engagement.likes or 0
                        date_str_item = ""
                        if hasattr(item, 'date') and item.date:
                            date_str_item = f" ({item.date})"
                        text_display = text[:200] + "..." if len(text) > 200 else text
                        lines.append(
                            f"- @{acct['handle']}{date_str_item}: {text_display} "
                            f"[{likes}\u2764\ufe0f]({url})"
                        )
                lines.append("")

    # Lab Pulse — what the model providers said/shipped today
    lab_pulse_summary = synthesis.get("lab_pulse_summary", "")
    if lab_pulse_summary or lab_pulse_items:
        lines.extend([
            "## Lab Pulse \U0001f9ea",
            "",
        ])
        if lab_pulse_summary:
            lines.extend([lab_pulse_summary, ""])
        if lab_pulse_items:
            lines.append("| Author | Post | Likes | Link |")
            lines.append("|--------|------|-------|------|")
            for item, topic, source in lab_pulse_items[:10]:
                likes = item.engagement.likes if item.engagement and item.engagement.likes else 0
                text_short = item.text[:80] + "..." if len(item.text) > 80 else item.text
                lines.append(
                    f"| @{item.author_handle} | {text_short} | {likes} | [→]({item.url}) |"
                )
            lines.append("")

    # Deep Dives — long-form threads and articles
    if deep_dives:
        lines.extend([
            "## Deep Dives \U0001f4d6",
            "",
        ])
        for item, topic, source in deep_dives[:8]:
            if source == 'x':
                title = item.text[:100] + "..." if len(item.text) > 100 else item.text
                lines.append(f"- [ ] [{title}]({item.url}) — @{item.author_handle} #{topic.slug}")
            else:
                lines.append(f"- [ ] [{item.title}]({item.url}) — r/{item.subreddit} #{topic.slug}")
        lines.append("")

    # Reading list (top items across all topics, ranked by score)
    reading_list = _build_reading_list(topic_results, config)
    if reading_list:
        lines.extend([
            "## Reading List",
            "",
        ])
        for item in reading_list:
            source_tag = f"#{item['topic_slug']}"
            lines.append(
                f"- [ ] [{item['title']}]({item['url']}) — {item['summary']} {source_tag}"
            )
        lines.append("")

    # Per-topic sections
    topic_synths = {t.get("slug", ""): t for t in synthesis.get("topics", [])}
    for tr in topic_results:
        topic = tr["topic"]
        synth = topic_synths.get(topic.slug, {})

        lines.extend([
            "---",
            "",
            f"## {topic.display_name}",
            "",
        ])

        # Topic headline
        headline = synth.get("headline", "")
        if headline:
            lines.extend([f"**{headline}**", ""])

        # Key points
        key_points = synth.get("key_points", [])
        if key_points:
            for kp in key_points:
                lines.append(f"- {kp}")
            lines.append("")

        # Sources table — Reddit
        if tr["reddit_items"]:
            lines.extend([
                "### Reddit",
                "",
                "| # | Title | Subreddit | Score | Link |",
                "|---|-------|-----------|-------|------|",
            ])
            for i, item in enumerate(tr["reddit_items"][:8], 1):
                score_val = item.score if hasattr(item, "score") else 0
                title_short = item.title[:60] + "..." if len(item.title) > 60 else item.title
                lines.append(
                    f"| {i} | {title_short} | r/{item.subreddit} | {score_val} | [→]({item.url}) |"
                )
            lines.append("")

        # Sources table — X
        if tr["x_items"]:
            lines.extend([
                "### X",
                "",
                "| # | Post | Author | Likes | Link |",
                "|---|------|--------|-------|------|",
            ])
            for i, item in enumerate(tr["x_items"][:8], 1):
                likes = item.engagement.likes if item.engagement and item.engagement.likes else 0
                text_short = item.text[:60] + "..." if len(item.text) > 60 else item.text
                lines.append(
                    f"| {i} | {text_short} | @{item.author_handle} | {likes} | [→]({item.url}) |"
                )
            lines.append("")

        if not tr["reddit_items"] and not tr["x_items"]:
            lines.extend(["*No new results for this topic today.*", ""])

    # Footer
    lines.extend([
        "---",
        "",
        "## Promote to Library",
        "",
        "> Add `#keep` to any reading list item above to promote it to",
        f"> `{config.get('library_folder', 'Research/Library')}/` on the next run.",
        "",
        "## Rate Results",
        "",
        "> Tag any item with `#good` or `#bad` to give feedback.",
        "> Next run picks it up and logs it — helps tune future results.",
        "",
    ])

    # Feedback stats if available
    if feedback_summary and (feedback_summary.get("new_good") or feedback_summary.get("new_bad")):
        stats = feedback_summary.get("data", {}).get("stats", {})
        lines.extend([
            f"> \U0001f4ca Feedback processed this run: "
            f"+{feedback_summary['new_good']} good, -{feedback_summary['new_bad']} bad "
            f"(lifetime: {stats.get('total_good', 0)} good, {stats.get('total_bad', 0)} bad)",
            "",
        ])

    return "\n".join(lines)


def _build_reading_list(topic_results: list, config: dict) -> list:
    """Build a merged, ranked reading list across all topics."""
    max_items = config.get("reading_list_max", 15)
    all_items = []

    for tr in topic_results:
        topic = tr["topic"]
        for item in tr["reddit_items"]:
            all_items.append({
                "title": item.title,
                "url": item.url,
                "summary": item.why_relevant or f"r/{item.subreddit}",
                "topic_slug": topic.slug,
                "score": item.score * topic.weight,
                "source": "reddit",
            })
        for item in tr["x_items"]:
            all_items.append({
                "title": item.text[:80] + "..." if len(item.text) > 80 else item.text,
                "url": item.url,
                "summary": item.why_relevant or f"@{item.author_handle}",
                "topic_slug": topic.slug,
                "score": item.score * topic.weight,
                "source": "x",
            })

    # Sort by weighted score descending
    all_items.sort(key=lambda x: x["score"], reverse=True)
    return all_items[:max_items]


def _format_date(date_str: str) -> str:
    """Format YYYY-MM-DD as 'Feb 23, 2026'."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%b %d, %Y")
    except ValueError:
        return date_str


def main():
    parser = argparse.ArgumentParser(description="Daily research pipeline → Obsidian")
    parser.add_argument("--topic", help="Run only this topic slug (e.g., agents)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + score, print to stdout only")
    parser.add_argument("--promote-only", action="store_true", help="Only run #keep → Library pass")
    parser.add_argument("--show-dedup", action="store_true", help="Show all seen URLs from vault")
    parser.add_argument("--costs", action="store_true", help="Show estimated token costs after run")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    # Load config
    config = load_config()
    today = datetime.now().strftime("%Y-%m-%d")

    # --show-dedup: just dump URLs and exit
    if args.show_dedup:
        seen = vault.load_seen_urls(config)
        print(f"Seen URLs in vault: {len(seen)}")
        for url in sorted(seen):
            print(f"  {url}")
        return

    # --promote-only: just run promotion pass and exit
    if args.promote_only:
        # Load API key for LLM enrichment
        from lib import env as l30_env
        l30_config = l30_env.get_config()
        openai_key = l30_config.get("OPENAI_API_KEY")
        if not openai_key:
            print("[warn] No OPENAI_API_KEY — will create basic notes without summaries")

        promoted = promote.promote_items(
            config, api_key=openai_key, dry_run=args.dry_run,
        )
        if promoted:
            print(f"Promoted {len(promoted)} items to Library:")
            for item in promoted:
                path = item.get('library_path', item['topic_slug'])
                print(f"  [{item['topic_slug']}] {item['title']} → {path}")
        else:
            print("No #keep items found to promote.")
        return

    # Enable debug
    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"

    # Run promote pass first (tag-to-library for previous dailies)
    # Load API key early so promote can do LLM enrichment
    from lib import env as l30_env
    l30_config = l30_env.get_config()
    openai_key = l30_config.get("OPENAI_API_KEY")

    promoted = promote.promote_items(config, api_key=openai_key)
    if promoted:
        print(f"[promote] Enriched & moved {len(promoted)} items to Library")

    # Process feedback tags (#good / #bad) from previous dailies
    print("[feedback] Scanning for #good / #bad tags...")
    feedback_summary = process_feedback_tags(config)
    if feedback_summary["new_good"] or feedback_summary["new_bad"]:
        print(f"[feedback] Logged +{feedback_summary['new_good']} good, -{feedback_summary['new_bad']} bad")
    else:
        print("[feedback] No new feedback tags found")

    if not l30_config.get("OPENAI_API_KEY") and not l30_config.get("XAI_API_KEY"):
        print("Error: No API keys found. Set them in ~/.config/last30days/.env", file=sys.stderr)
        sys.exit(1)

    # Load topics
    all_topics = topics_mod.load_topics(config)
    if args.topic:
        topic = topics_mod.get_topic_by_slug(all_topics, args.topic)
        if not topic:
            print(f"Error: Unknown topic '{args.topic}'. Available: {[t.slug for t in all_topics]}", file=sys.stderr)
            sys.exit(1)
        all_topics = [topic]

    # Load vault dedup set (zero tokens — pure filesystem)
    print(f"[dedup] Scanning vault for seen URLs...")
    seen_urls = vault.load_seen_urls(config)
    seen_titles = vault.load_seen_titles(config)
    print(f"[dedup] Found {len(seen_urls)} seen URLs, {len(seen_titles)} seen titles")

    # Date range: last 7 days for daily scan (not 30)
    from lib import dates
    from_date, _ = dates.get_date_range(7)
    to_date = today

    # Select models (reuse last30days model selection with caching)
    from lib import models as l30_models
    selected_models = l30_models.get_models(l30_config)

    # Run topic scans sequentially (to stay within rate limits)
    print(f"\n[scan] Starting {len(all_topics)} topic scans (scan mode)...")
    topic_results = []
    total_errors = []

    for topic in all_topics:
        print(f"  [{topic.slug}] Scanning...", end=" ", flush=True)
        result = run_topic_scan(
            topic, config, l30_config, selected_models,
            from_date, to_date, seen_urls, seen_titles,
        )
        r_count = len(result["reddit_items"])
        x_count = len(result["x_items"])
        print(f"→ {r_count}R + {x_count}X items (new)")
        topic_results.append(result)
        total_errors.extend(result["errors"])

        # Add found URLs to seen set to dedup across topics
        for item in result["reddit_items"]:
            seen_urls.add(item.url)
        for item in result["x_items"]:
            seen_urls.add(item.url)

    # Show errors if any
    if total_errors:
        print(f"\n[warn] {len(total_errors)} errors during scan:")
        for err in total_errors:
            print(f"  ! {err}")

    # Must-follow account scan (dedicated per-person X search, no filters)
    must_follow_results = []
    mf_accounts = config.get("must_follow", {}).get("accounts", [])
    if mf_accounts and l30_config.get("XAI_API_KEY"):
        print(f"\n[must-follow] Scanning {len(mf_accounts)} accounts...")
        must_follow_results = run_must_follow_scan(
            config, l30_config, from_date, to_date,
        )
        mf_total = sum(len(r["items"]) for r in must_follow_results)
        print(f"[must-follow] Captured {mf_total} tweets from {len(mf_accounts)} accounts")

    # Synthesize (single batched call)
    synthesis = {}
    if l30_config.get("OPENAI_API_KEY"):
        total_items = sum(
            len(tr["reddit_items"]) + len(tr["x_items"])
            for tr in topic_results
        )
        if total_items > 0:
            print(f"\n[synth] Synthesizing {total_items} items across {len(all_topics)} topics...")
            synthesis = synthesize_all(
                l30_config["OPENAI_API_KEY"],
                topic_results,
                from_date,
                to_date,
            )
            if synthesis.get("briefing"):
                print(f"[synth] Briefing: {synthesis['briefing'][:120]}...")
        else:
            print("\n[synth] No new items to synthesize")
            synthesis = {"briefing": "No new research results today.", "topics": []}

    # Render daily note
    note_content = render_daily_note(
        today, topic_results, synthesis, config,
        must_follow_results=must_follow_results,
        feedback_summary=feedback_summary,
    )

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN — would write this to vault:")
        print("=" * 60)
        print(note_content)
        return

    # Write to vault via Obsidian CLI
    filepath = vault.write_daily_note(config, today, note_content)
    print(f"\n[vault] Written → {filepath}")

    # Cost summary
    if args.costs:
        n_topics = len(all_topics)
        n_mf = len(mf_accounts)
        est_cost = n_topics * 0.03 + n_mf * 0.01  # topic scans + must-follow scans
        print(f"\n[costs] Estimated run cost: ~${est_cost:.2f}")
        print(f"  {n_topics} Reddit scans (auto-selected model + web_search)")
        print(f"  {n_topics} X scans (grok-4-1-fast + x_search)")
        print(f"  {n_mf} must-follow X scans (grok-4-1-fast)")
        print(f"  1 synthesis call (gpt-5.2)")

    # Final summary
    total_reddit = sum(len(tr["reddit_items"]) for tr in topic_results)
    total_x = sum(len(tr["x_items"]) for tr in topic_results)
    mf_total = sum(len(r["items"]) for r in must_follow_results)
    print(f"\nDone! {total_reddit}R + {total_x}X + {mf_total}MF items across {len(all_topics)} topics.")


if __name__ == "__main__":
    main()
