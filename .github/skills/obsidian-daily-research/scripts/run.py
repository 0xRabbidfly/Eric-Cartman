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
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Resolve paths
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent
PIPELINE_MD = SKILL_DIR / "pipeline.md"

# Vendor dir holds selective copies of last30days + obsidian modules
# (no external skill dependencies at runtime)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

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


# ---------------------------------------------------------------------------
# Token / cost tracking
# ---------------------------------------------------------------------------

# Default cost rates per 1M tokens (USD) — used ONLY as fallback when the API
# does not return an exact cost.  xAI responses include `cost_in_usd_ticks`
# (exact cost), so rates below are irrelevant for Grok models in practice.
# Override via DEFAULT_COST_RATES dict above.
DEFAULT_COST_RATES = {
    # OpenAI Responses API (web_search)
    "gpt-4o":        {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":   {"input": 0.15, "output": 0.60},
    # OpenAI Chat Completions
    "gpt-5.2":       {"input": 2.00, "output": 8.00},
    "gpt-4.1":       {"input": 2.00, "output": 8.00},
    # xAI — fallback only; prefer cost_in_usd_ticks from API response
    "grok-4-1-fast": {"input": 2.00, "output": 8.00},
    "grok-3":        {"input": 3.00, "output": 15.00},
}


class TokenTracker:
    """Accumulates token usage and costs across all API calls.

    Uses exact cost from `cost_in_usd_ticks` when available (xAI),
    otherwise falls back to rate-based estimation (OpenAI).
    """

    def __init__(self, cost_rates: dict | None = None):
        self.calls: list[dict] = []  # individual call records
        self.rates = {**DEFAULT_COST_RATES, **(cost_rates or {})}

    def record(self, label: str, model: str, usage: dict | None):
        """Record a single API call's usage.

        Args:
            label:  Human-readable call label (e.g. 'Reddit/agents')
            model:  Model name used
            usage:  Raw usage dict from API response (or None)
        """
        if not usage:
            self.calls.append({"label": label, "model": model,
                               "input": 0, "output": 0, "total": 0,
                               "exact_cost": None})
            return
        # OpenAI Responses API uses input_tokens/output_tokens
        # OpenAI Chat Completions uses prompt_tokens/completion_tokens
        inp = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        out = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        total = usage.get("total_tokens") or (inp + out)

        # xAI returns exact cost in cost_in_usd_ticks (1 tick = 1e-10 USD)
        exact_cost = None
        ticks = usage.get("cost_in_usd_ticks")
        if ticks is not None:
            exact_cost = ticks / 10_000_000_000

        self.calls.append({"label": label, "model": model,
                           "input": inp, "output": out, "total": total,
                           "exact_cost": exact_cost})

    # --- Aggregations -------------------------------------------------------

    @property
    def total_input(self) -> int:
        return sum(c["input"] for c in self.calls)

    @property
    def total_output(self) -> int:
        return sum(c["output"] for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return sum(c["total"] for c in self.calls)

    @property
    def num_calls(self) -> int:
        return len(self.calls)

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD from per-token rates (fallback when no exact cost)."""
        rate = self.rates.get(model)
        if not rate:
            # Try prefix match (e.g. 'gpt-4o-2024-08-06' → 'gpt-4o')
            for key in self.rates:
                if model.startswith(key):
                    rate = self.rates[key]
                    break
        if not rate:
            return 0.0
        return (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000

    def _call_cost(self, c: dict) -> float:
        """Return cost for a single call: exact if available, otherwise estimated."""
        if c.get("exact_cost") is not None:
            return c["exact_cost"]
        return self._estimate_cost(c["model"], c["input"], c["output"])

    @property
    def total_cost(self) -> float:
        return sum(self._call_cost(c) for c in self.calls)

    @property
    def has_exact_costs(self) -> bool:
        """True if at least one call provided exact cost from the API."""
        return any(c.get("exact_cost") is not None for c in self.calls)

    def by_model(self) -> dict:
        """Aggregate tokens and cost grouped by model."""
        agg: dict[str, dict] = {}
        for c in self.calls:
            m = c["model"]
            if m not in agg:
                agg[m] = {"input": 0, "output": 0, "total": 0, "calls": 0,
                          "cost": 0.0, "has_exact": False}
            agg[m]["input"] += c["input"]
            agg[m]["output"] += c["output"]
            agg[m]["total"] += c["total"]
            agg[m]["calls"] += 1
            agg[m]["cost"] += self._call_cost(c)
            if c.get("exact_cost") is not None:
                agg[m]["has_exact"] = True
        return agg

    def summary_dict(self) -> dict:
        """Return a summary dict for frontmatter / serialization."""
        bm = self.by_model()
        all_exact = all(d["has_exact"] for d in bm.values()) if bm else False
        cost_key = "cost_usd" if all_exact else "estimated_cost_usd"
        return {
            "total_tokens": self.total_tokens,
            "input_tokens": self.total_input,
            "output_tokens": self.total_output,
            "api_calls": self.num_calls,
            cost_key: round(self.total_cost, 4),
            "by_model": {
                m: {"tokens": d["total"], "calls": d["calls"],
                    "cost_usd": round(d["cost"], 4),
                    "exact": d["has_exact"]}
                for m, d in bm.items()
            },
        }


def _extract_usage(response: dict) -> dict | None:
    """Extract usage dict from an API response (OpenAI or xAI)."""
    return response.get("usage") if isinstance(response, dict) else None


# ---------------------------------------------------------------------------
# Pipeline config — parsed from pipeline.md (single source of truth)
# ---------------------------------------------------------------------------

# Hardcoded quality filter defaults (were in config.json, now inlined)
DEFAULT_QUALITY_FILTERS = {
    "min_engagement": {"reddit_score": 50, "x_likes": 100},
    "long_form_bonus": 15,
    "long_form_min_chars": 800,
    "article_domains": [
        "medium.com", "substack.com", "arxiv.org", "github.com",
        "huggingface.co", "openai.com", "anthropic.com", "blog.",
        "notion.site", "dev.to", "towardsdatascience.com",
        "newsletter.", "mirror.xyz", "deepmind.google",
        "latent.space", "mckinsey.com", "cursor.com/blog",
        "manus.im/blog", "cognition.ai", "langchain.com",
        "paddo.dev", "honra.io", "philschmid.de",
    ],
    "priority_accounts": {
        "x": [
            "AnthropicAI", "alexalbert__", "amandaaskell", "bcherny",
            "OpenAI", "sama", "markchen90",
            "GoogleDeepMind", "JeffDean",
            "MetaAI", "ylecun",
            "MistralAI", "arthurmensch",
            "karpathy", "swyx", "hardmaru", "DrJimFan",
            "mntruell", "simonw", "eugeneyan",
        ],
        "reddit_subreddits": [
            "Anthropic", "OpenAI", "LocalLLaMA", "MachineLearning",
        ],
    },
    "priority_account_bonus": 20,
    "spam_detection": {
        "enabled": True,
        "claim_link_mismatch_patterns": [
            {"claim_regex": r"official\s+(anthropic|openai|google|meta)\b",
             "link_must_contain": ["anthropic.com", "openai.com", "google.com",
                                   "deepmind.google", "meta.com",
                                   "github.com/anthropics", "github.com/openai",
                                   "github.com/google"]},
            {"claim_regex": r"official\s+guide|official\s+docs",
             "link_must_contain": [".com/anthropics/", ".com/openai/",
                                   ".com/google/", "docs.anthropic.com",
                                   "platform.openai.com"]},
        ],
        "low_effort_patterns": [
            "follow me for more", "like and retweet",
            "DM me for", "link in bio", r"drop a .* if you",
        ],
    },
    "lab_accounts": {
        "anthropic": ["AnthropicAI", "alexalbert__", "amandaaskell", "bcherny", "jack_clark", "DarioAmodei"],
        "openai": ["OpenAI", "sama", "markchen90"],
        "google": ["GoogleDeepMind", "JeffDean", "googleai"],
        "meta": ["MetaAI", "ylecun"],
        "mistral": ["MistralAI", "arthurmensch"],
    },
}


def _parse_pipeline_md(path: Path) -> dict:
    """Parse pipeline.md into a config dict.

    Extracts three sections:
      # Topics      → config["topics"]  (list of dicts)
      # Must-Follow → config["must_follow_accounts"]  (list of dicts with group)
      # Settings    → merged into config top-level keys

    Lines starting with `>` are comments. Blank lines are ignored.
    """
    config = {
        # Sensible defaults
        "vault_path": str(Path.home() / "Documents" / "Obsidian Vault"),
        "dailies_folder": "Research/Dailies",
        "library_folder": "Research/Library",
        "keep_tag": "#keep",
        "kept_tag": "#kept",
        "items_per_topic": 8,
        "reading_list_max": 15,
        "depth": "scan",
        "quality_filters": DEFAULT_QUALITY_FILTERS,
        "topics": [],
        "must_follow_accounts": [],
        "discovery_accounts": [],
    }

    if not path.exists():
        return config

    section = None  # "topics" | "must-follow" | "settings"
    current_group = "Other"

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()

            # Skip blanks and comments
            if not line or line.startswith(">"):
                continue

            # Top-level section headers (# Topics, # Must-Follow, # Settings)
            if line.startswith("# ") and not line.startswith("## "):
                header = line[2:].strip().lower()
                if "topic" in header:
                    section = "topics"
                elif "must" in header or "follow" in header:
                    section = "must-follow"
                elif "discovery" in header:
                    section = "discovery"
                elif "setting" in header:
                    section = "settings"
                else:
                    section = None
                continue

            # Ignore horizontal rules
            if line.startswith("---"):
                continue

            # Group sub-headers (## Group Name) — only for must-follow
            if line.startswith("## "):
                current_group = line[3:].strip()
                continue

            # Parse items based on current section
            if section == "topics" and line.startswith("- "):
                parts = line[2:].split("|")
                if len(parts) >= 2:
                    slug = parts[0].strip()
                    display = parts[1].strip()
                    weight = float(parts[2].strip()) if len(parts) >= 3 else 1.0
                    config["topics"].append({
                        "slug": slug,
                        "display_name": display,
                        "weight": weight,
                    })

            elif section == "must-follow" and line.startswith("- @"):
                rest = line[3:]  # strip "- @"
                # Detect (solo) tag — gives this account a dedicated API call
                solo = False
                if rest.rstrip().endswith("(solo)"):
                    solo = True
                    rest = rest[:rest.rfind("(solo)")].rstrip()
                for sep in (" — ", " – ", " - "):
                    if sep in rest:
                        handle, label = rest.split(sep, 1)
                        config["must_follow_accounts"].append({
                            "handle": handle.strip(),
                            "label": label.strip(),
                            "group": current_group,
                            "solo": solo,
                        })
                        break
                else:
                    config["must_follow_accounts"].append({
                        "handle": rest.strip(),
                        "label": rest.strip(),
                        "group": current_group,
                        "solo": solo,
                    })

            elif section == "settings" and line.startswith("- "):
                kv = line[2:]
                if ":" in kv:
                    key, val = kv.split(":", 1)
                    key = key.strip()
                    val = val.strip()
                    # Type coercion
                    if val.isdigit():
                        val = int(val)
                    elif val.startswith("~/"):
                        val = str(Path.home() / val[2:])
                    config[key] = val

            elif section == "discovery" and line.startswith("- @"):
                rest = line[3:]  # strip "- @"
                for sep in (" — ", " – ", " - "):
                    if sep in rest:
                        handle, label = rest.split(sep, 1)
                        config["discovery_accounts"].append({
                            "handle": handle.strip(),
                            "label": label.strip(),
                        })
                        break
                else:
                    config["discovery_accounts"].append({
                        "handle": rest.strip(),
                        "label": rest.strip(),
                    })

    return config


def load_config() -> dict:
    """Load pipeline config from pipeline.md."""
    return _parse_pipeline_md(PIPELINE_MD)


# ---------------------------------------------------------------------------
# Text sanitization for markdown output
# ---------------------------------------------------------------------------

def _oneline(text: str, max_len: int = 120) -> str:
    """Collapse text to a single line safe for markdown list items and links.

    Strips newlines, tabs, pipe chars (break tables), and square brackets
    (break markdown links).  Collapses whitespace, then truncates.
    """
    # Replace newlines/tabs with a space
    t = re.sub(r'[\n\r\t]+', ' ', text)
    # Remove characters that break markdown link syntax or tables
    t = t.replace('[', '').replace(']', '').replace('|', '—')
    # Collapse multiple spaces
    t = re.sub(r' {2,}', ' ', t).strip()
    if len(t) > max_len:
        return t[:max_len] + "..."
    return t


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

    Five passes, all driven by DEFAULT_QUALITY_FILTERS:
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

    # --- 0b. Reply filtering (drop replies from topic scans) ---
    # Replies leak through when the API returns them despite prompt instructions.
    # Two checks: is_reply field from API, and text starting with @someone.
    filtered_x = []
    for item in result["x_items"]:
        # Check is_reply flag (carried through from xAI response)
        if getattr(item, 'is_reply', False):
            continue
        # Check text pattern: starts with @someone (but not self-mention)
        text = item.text.strip()
        if text.startswith("@") and not text.lower().startswith(f"@{item.author_handle.lower()}"):
            continue
        filtered_x.append(item)
    result["x_items"] = filtered_x

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
            if (item.engagement is not None
                and item.engagement.score is not None
                and item.engagement.score >= reddit_floor)
        ]
    if x_likes_floor > 0:
        result["x_items"] = [
            item for item in result["x_items"]
            if item.author_handle.lower() in lab_handles  # lab accounts bypass floor
            or item.author_handle.lower() in priority_x   # priority accounts bypass floor
            or (item.engagement is not None
                and item.engagement.likes is not None
                and item.engagement.likes >= x_likes_floor)
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
    tracker: TokenTracker | None = None,
) -> dict:
    """Run a single topic scan. Returns a result dict.

    Uses last30days lib modules directly in scan mode.
    """
    from vendor.last30days import (
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
            if tracker:
                tracker.record(f"Reddit/{topic.slug}", model, _extract_usage(raw))
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
            if tracker:
                tracker.record(f"X/{topic.slug}", model, _extract_usage(raw))
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
    tracker: TokenTracker | None = None,
) -> dict:
    """Single batched synthesis call across all topics.

    Sends one gpt-5.2 call with combined data instead of 5 separate calls.
    """
    from vendor.last30days import http

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
            text = _oneline(item.text, 120)
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
        if tracker:
            tracker.record("Synthesis", "gpt-5.2", _extract_usage(resp))
        if "choices" in resp and resp["choices"]:
            content = resp["choices"][0].get("message", {}).get("content", "{}")
            return json.loads(content)
    except Exception as e:
        return {"briefing": f"Synthesis failed: {e}", "topics": [], "error": str(e)}

    return {"briefing": "", "topics": []}


# ---------------------------------------------------------------------------
# Must-Follow Account Scanning (hybrid batch/solo)
# ---------------------------------------------------------------------------


def run_must_follow_scan(
    config: dict,
    l30_config: dict,
    from_date: str,
    to_date: str,
    tracker: TokenTracker | None = None,
) -> list:
    """Scan must-follow accounts on X, hybrid batch/solo strategy.

    Corp accounts (solo=False) are batched into ONE API call using
    search_x_must_follow_batch (up to 10 handles). Individual accounts
    (solo=True) each get a dedicated search_x_must_follow call for
    maximum reliability.

    Returns a list of dicts: {handle, label, group, items: [x_item, ...]}
    """
    from vendor.last30days import xai_x, normalize

    accounts = config.get("must_follow_accounts", [])
    if not accounts or not l30_config.get("XAI_API_KEY"):
        return []

    model = l30_config.get("xai_model", "grok-4-1-fast")
    results = []

    # Separate into batch (corp) and solo (individual) accounts
    batch_accounts = [a for a in accounts if not a.get("solo")]
    solo_accounts = [a for a in accounts if a.get("solo")]

    # --- Batch call for corp accounts (one API call) ---
    if batch_accounts:
        handles = [a["handle"].lstrip("@") for a in batch_accounts]
        handle_set = {h.lower() for h in handles}
        corp_list = ", ".join(f"@{h}" for h in handles)
        print(f"  [batch] {corp_list}...", end=" ", flush=True)

        try:
            raw = xai_x.search_x_must_follow_batch(
                l30_config["XAI_API_KEY"],
                model,
                handles,
                from_date,
                to_date,
                depth="scan",
            )
            if tracker:
                tracker.record("MustFollow/batch", model, _extract_usage(raw))

            items = xai_x.parse_x_response(raw)
            normalized = normalize.normalize_x_items(items, from_date, to_date)

            # Hard post-filter: only keep items from handles in this batch
            filtered = []
            dropped = 0
            for item in normalized:
                item_author = item.author_handle.lower().lstrip("@")
                if item_author in handle_set:
                    filtered.append(item)
                else:
                    dropped += 1
            if dropped:
                print(f"(dropped {dropped} wrong-author)", end=" ")

            # Filter out replies
            final = []
            for item in filtered:
                text = item.text.strip()
                author = item.author_handle.lower().lstrip("@")
                if text.startswith("@") and not text.lower().startswith(f"@{author}"):
                    continue
                if getattr(item, 'is_reply', False):
                    continue
                final.append(item)

            # Must-follow: NO engagement floor — catch everything
            # (engagement floor is for topic scans only)

            # Distribute items back to per-account results
            per_handle: dict[str, list] = {h.lower(): [] for h in handles}
            for item in final:
                author = item.author_handle.lower().lstrip("@")
                if author in per_handle:
                    per_handle[author].append(item)

            for acct in batch_accounts:
                clean = acct["handle"].lstrip("@").lower()
                results.append({
                    "handle": acct["handle"],
                    "label": acct.get("label", acct["handle"]),
                    "group": acct["group"],
                    "items": per_handle.get(clean, []),
                })

            print(f"→ {len(final)} tweets")

        except Exception as e:
            print(f"error — {e}")
            for acct in batch_accounts:
                results.append({
                    "handle": acct["handle"],
                    "label": acct.get("label", acct["handle"]),
                    "group": acct["group"],
                    "items": [],
                    "error": str(e),
                })

    # --- Solo calls for individual accounts (one API call each) ---
    for acct in solo_accounts:
        handle = acct["handle"].lstrip("@")
        print(f"  [solo] @{handle}...", end=" ", flush=True)

        try:
            raw = xai_x.search_x_must_follow(
                l30_config["XAI_API_KEY"],
                model,
                handle,
                from_date,
                to_date,
                depth="scan",
            )
            if tracker:
                tracker.record(f"MustFollow/@{handle}", model, _extract_usage(raw))

            items = xai_x.parse_x_response(raw)
            normalized = normalize.normalize_x_items(items, from_date, to_date)

            # Hard post-filter: only this handle
            filtered = [
                item for item in normalized
                if item.author_handle.lower().lstrip("@") == handle.lower()
            ]

            # Filter out replies
            final = []
            for item in filtered:
                text = item.text.strip()
                if text.startswith("@") and not text.lower().startswith(f"@{handle.lower()}"):
                    continue
                if getattr(item, 'is_reply', False):
                    continue
                final.append(item)

            # Must-follow: NO engagement floor — catch everything
            # (engagement floor is for topic scans only)

            results.append({
                "handle": acct["handle"],
                "label": acct.get("label", acct["handle"]),
                "group": acct["group"],
                "items": final,
            })

            print(f"→ {len(final)} tweets")

        except Exception as e:
            print(f"error — {e}")
            results.append({
                "handle": acct["handle"],
                "label": acct.get("label", acct["handle"]),
                "group": acct["group"],
                "items": [],
                "error": str(e),
            })

    return results


# (Discovery feed removed — use must-follow for tracked accounts)


# ---------------------------------------------------------------------------
# Prominent AI Voices Scan (single broad search, engagement-gated)
# ---------------------------------------------------------------------------


def run_prominent_ai_scan(
    config: dict,
    l30_config: dict,
    from_date: str,
    to_date: str,
    seen_urls: set,
    tracker: TokenTracker | None = None,
) -> list:
    """Run a single broad X search for high-engagement AI tweets.

    Instead of spending tokens on per-account searches, this does ONE API
    call asking for high-engagement (500+ likes) original tweets from
    prominent AI voices. The xAI model naturally surfaces the most impactful
    posts without needing hardcoded account names.

    Returns a list of XItem objects (already filtered for quality).
    """
    from vendor.last30days import xai_x, normalize, score, dedupe

    if not l30_config.get("XAI_API_KEY"):
        return []

    model = l30_config.get("xai_model", "grok-4-1-fast")

    print(f"  [prominent-ai] Searching for high-engagement AI tweets...", end=" ", flush=True)

    try:
        raw = xai_x.search_x_prominent_ai(
            l30_config["XAI_API_KEY"],
            model,
            from_date,
            to_date,
            depth="scan",
        )
        if tracker:
            tracker.record("ProminentAI", model, _extract_usage(raw))

        items = xai_x.parse_x_response(raw)
        normalized = normalize.normalize_x_items(items, from_date, to_date)
        scored = score.score_x_items(normalized)

        # Filter: must have 500+ likes (the whole point of this scan)
        high_signal = [
            item for item in scored
            if not getattr(item, 'is_reply', False)
            and item.engagement is not None
            and item.engagement.likes is not None
            and item.engagement.likes >= 500
        ]

        # Also filter reply patterns from text
        final = []
        for item in high_signal:
            text = item.text.strip()
            if text.startswith("@") and not text.lower().startswith(f"@{item.author_handle.lower()}"):
                continue
            final.append(item)

        # Dedup against vault
        final = [
            item for item in final
            if item.url not in seen_urls
        ]

        print(f"→ {len(final)} high-signal tweets")
        return final

    except Exception as e:
        print(f"error — {e}")
        return []


# ---------------------------------------------------------------------------
# Feedback Processing (#good / #bad tags)
# ---------------------------------------------------------------------------

def load_feedback(config: dict) -> dict:
    """Load accumulated feedback from feedback.json."""
    if FEEDBACK_FILE.exists():
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for bucket in ("good", "bad"):
                    for entry in data.get(bucket, []):
                        entry["topic"] = _normalize_feedback_topic(entry.get("topic", ""))
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"good": [], "bad": [], "stats": {"total_good": 0, "total_bad": 0}}


def save_feedback(data: dict):
    """Save feedback data to feedback.json."""
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _extract_reason(line: str, tag: str) -> str:
    """Extract the reason text after a #good/#bad tag.

    Examples:
        '#good great long-form analysis'  →  'great long-form analysis'
        '#bad it was a reply'             →  'it was a reply'
        '#good'                           →  ''
    """
    # Find tag position, grab everything after it on the same line
    idx = line.find(tag)
    if idx < 0:
        return ""
    after = line[idx + len(tag):].strip()
    # Stop at next tag or end of line
    after = re.split(r'#\w', after, maxsplit=1)[0].strip()
    # Strip trailing markdown artifacts
    after = after.rstrip('|').strip()
    return after


def _normalize_feedback_topic(topic: str) -> str:
    """Normalize topic labels stored in feedback data."""
    normalized = re.sub(r'\s+', ' ', (topic or '').strip())
    return normalized or "unknown"


def _extract_current_topic(lines: list[str], line_idx: int) -> str:
    """Walk backwards from line_idx to find the nearest ## section header.

    Returns the topic slug if the header matches a known topic section,
    or the raw header text otherwise.
    """
    for j in range(line_idx, -1, -1):
        m = re.match(r'^##\s+(.+)', lines[j])
        if m:
            header = m.group(1).strip()
            # Known sections that aren't topics
            if header.lower() in (
                "rate results", "promote to library", "reading list",
                "today's pow", "vault connections", "efficiency recommendations",
                "feedback insights",
            ):
                return ""
            # Strip emoji suffixes like "Lab Pulse 🧪"
            clean = re.sub(r'[\U0001f300-\U0001faff\u2600-\u27bf]+', '', header).strip()
            return clean
    return ""


def process_feedback_tags(config: dict) -> dict:
    """Scan dailies for #good / #bad tags and accumulate feedback.

    Skips blockquote/instruction lines (starting with >).
    Captures the reason text after the tag (e.g. '#bad it was a reply').
    Identifies which topic section the tagged item belongs to.
    Replaces #good → #good-noted, #bad → #bad-noted so items
    aren't reprocessed. Returns summary of what was found.
    """
    vault._init_fs(config)  # ensure FS-direct I/O is enabled before bulk reads
    fb_config = config.get("feedback_tags", {})
    good_tag = fb_config.get("good_tag", "#good")
    bad_tag = fb_config.get("bad_tag", "#bad")
    suffix = fb_config.get("processed_tag_suffix", "-noted")

    dailies_folder = config.get("dailies_folder", "Research/Dailies")
    feedback_data = load_feedback(config)

    new_good = []
    new_bad = []

    # Scan dailies for feedback tags (including year/month subfolders)
    md_files = sorted(vault._scan_folder_recursive(dailies_folder))
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
            stripped = line.strip()

            # Skip already-processed lines
            if f"{good_tag}{suffix}" in line or f"{bad_tag}{suffix}" in line:
                continue

            # Skip blockquote / instruction lines — these contain template
            # text like '> Tag any item with #good or #bad to give feedback.'
            if stripped.startswith(">"):
                continue

            # Skip YAML frontmatter lines
            if stripped.startswith("---"):
                continue

            # Skip feedback helper text rendered by the report itself.
            if re.search(r'why you tagged items\s+#(?:good|bad)', stripped, re.IGNORECASE):
                continue

            # Extract link info from the line
            link_match = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', line)

            if good_tag in line and f"{good_tag}{suffix}" not in line:
                reason = _extract_reason(line, good_tag)
                topic = _normalize_feedback_topic(_extract_current_topic(lines, i))
                entry = {
                    "date": _extract_date_from_path(filepath),
                    "title": link_match.group(1) if link_match else _clean_title(line),
                    "url": link_match.group(2) if link_match else "",
                    "reason": reason,
                    "topic": topic,
                    "source_file": filepath,
                }
                new_good.append(entry)
                lines[i] = line.replace(good_tag, f"{good_tag}{suffix}")
                modified = True

            if bad_tag in line and f"{bad_tag}{suffix}" not in line:
                reason = _extract_reason(line, bad_tag)
                topic = _normalize_feedback_topic(_extract_current_topic(lines, i))
                entry = {
                    "date": _extract_date_from_path(filepath),
                    "title": link_match.group(1) if link_match else _clean_title(line),
                    "url": link_match.group(2) if link_match else "",
                    "reason": reason,
                    "topic": topic,
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


def _clean_title(line: str) -> str:
    """Extract a clean display title from a markdown line."""
    # Strip list markers, checkboxes, tags
    cleaned = re.sub(r'^[-*]\s*(?:\[[ x]\]\s*)?', '', line.strip())
    # Strip #good/#bad and reason text
    cleaned = re.sub(r'#(?:good|bad)\S*\s*.*$', '', cleaned).strip()
    return cleaned[:80] if cleaned else line[:80]


def _extract_date_from_path(filepath: str) -> str:
    """Extract YYYY-MM-DD from a daily note path."""
    m = re.search(r'(\d{4}-\d{2}-\d{2})', filepath)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Feedback Analysis & Proposals
# ---------------------------------------------------------------------------

# Canonical bad-reason buckets with regex patterns for classification
_BAD_REASON_BUCKETS = [
    ("reply",       [r"reply", r"not\s+an?\s+OP", r"not\s+original", r"response\s+to"]),
    ("low-engagement", [r"low\s+(?:like|engagement)", r"\d+\s+likes?", r"no\s+likes", r"low\s+quality"]),
    ("bot",         [r"bot", r"generated", r"obviously\s+(?:written\s+)?by\s+(?:a\s+)?(?:bot|AI|LLM)", r"spam"]),
    ("self-promo",  [r"promo", r"promoting\s+(?:their|his|her)", r"shill", r"github\s+repo", r"plug"]),
    ("misleading",  [r"mislead", r"fake", r"clickbait", r"bait", r"claim.*mismatch"]),
    ("off-topic",   [r"off.?topic", r"irrelevant", r"not\s+related", r"wrong\s+topic"]),
    ("duplicate",   [r"duplicate", r"already\s+seen", r"repeat", r"dupe"]),
    ("stale",       [r"old", r"stale", r"outdated", r"not\s+new"]),
]

# Good-reason buckets for positive signal classification
_GOOD_REASON_BUCKETS = [
    ("long-form",     [r"long.?form", r"deep\s+dive", r"thread", r"detailed", r"comprehensive"]),
    ("original-research", [r"original", r"research", r"paper", r"arxiv", r"novel"]),
    ("practical",     [r"practical", r"tutorial", r"how.?to", r"example", r"code", r"implementation"]),
    ("insider",       [r"insider", r"first.?hand", r"from\s+(?:the\s+)?team", r"official", r"announcement"]),
    ("high-signal",   [r"signal", r"insight", r"important", r"breaking", r"major"]),
]


def _classify_reason(reason: str, buckets: list[tuple[str, list[str]]]) -> str:
    """Match a reason string against bucket patterns. Returns bucket name or 'unclassified'."""
    if not reason:
        return "unclassified"
    reason_lower = reason.lower()
    for bucket_name, patterns in buckets:
        for pattern in patterns:
            if re.search(pattern, reason_lower):
                return bucket_name
    return "unclassified"


def analyze_feedback(feedback_data: dict, lookback_days: int = 14) -> dict:
    """Analyze accumulated feedback and extract actionable patterns.

    Looks at the last `lookback_days` of feedback entries. Returns a dict with:
      - bad_buckets: {bucket_name: [entries...]}   — classified bad reasons
      - good_buckets: {bucket_name: [entries...]}  — classified good reasons
      - bad_topics: {topic: count}                 — which topics produce bad results
      - good_topics: {topic: count}                — which topics produce good results
      - top_bad_reasons: [(reason, count)]         — most common raw bad reasons
      - top_good_reasons: [(reason, count)]        — most common raw good reasons
      - total_good / total_bad in window
    """
    cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    good_entries = [e for e in feedback_data.get("good", [])
                    if e.get("date", "") >= cutoff and e.get("url")]
    bad_entries = [e for e in feedback_data.get("bad", [])
                   if e.get("date", "") >= cutoff and e.get("url")]

    # Classify bad reasons into buckets
    bad_buckets: dict[str, list] = {}
    for entry in bad_entries:
        bucket = _classify_reason(entry.get("reason", ""), _BAD_REASON_BUCKETS)
        bad_buckets.setdefault(bucket, []).append(entry)

    # Classify good reasons into buckets
    good_buckets: dict[str, list] = {}
    for entry in good_entries:
        bucket = _classify_reason(entry.get("reason", ""), _GOOD_REASON_BUCKETS)
        good_buckets.setdefault(bucket, []).append(entry)

    # Topic distribution
    bad_topics: dict[str, int] = {}
    for entry in bad_entries:
        topic = _normalize_feedback_topic(entry.get("topic", "unknown"))
        bad_topics[topic] = bad_topics.get(topic, 0) + 1

    good_topics: dict[str, int] = {}
    for entry in good_entries:
        topic = _normalize_feedback_topic(entry.get("topic", "unknown"))
        good_topics[topic] = good_topics.get(topic, 0) + 1

    # Most common raw reasons
    bad_reason_counts: dict[str, int] = {}
    for entry in bad_entries:
        r = entry.get("reason", "").strip()
        if r:
            bad_reason_counts[r] = bad_reason_counts.get(r, 0) + 1
    top_bad = sorted(bad_reason_counts.items(), key=lambda x: -x[1])[:5]

    good_reason_counts: dict[str, int] = {}
    for entry in good_entries:
        r = entry.get("reason", "").strip()
        if r:
            good_reason_counts[r] = good_reason_counts.get(r, 0) + 1
    top_good = sorted(good_reason_counts.items(), key=lambda x: -x[1])[:5]

    return {
        "bad_buckets": bad_buckets,
        "good_buckets": good_buckets,
        "bad_topics": bad_topics,
        "good_topics": good_topics,
        "top_bad_reasons": top_bad,
        "top_good_reasons": top_good,
        "total_good": len(good_entries),
        "total_bad": len(bad_entries),
        "lookback_days": lookback_days,
    }


def generate_proposals(analysis: dict, config: dict) -> list[str]:
    """Turn feedback patterns into concrete improvement proposals.

    Each proposal is a markdown string with:
      - What pattern was detected
      - What action could improve results
      - Confidence (based on sample size)

    Returns a list of proposal strings (empty if insufficient data).
    """
    proposals: list[str] = []
    total_bad = analysis["total_bad"]
    total_good = analysis["total_good"]
    bad_buckets = analysis["bad_buckets"]
    good_buckets = analysis["good_buckets"]

    if total_bad + total_good < 3:
        return []  # Not enough data to make meaningful proposals

    # --- Bad-signal proposals ---

    # Reply detection
    reply_count = len(bad_buckets.get("reply", []))
    if reply_count >= 2:
        pct = reply_count / max(total_bad, 1) * 100
        proposals.append(
            f"**Reply leak** — {reply_count}/{total_bad} bad items ({pct:.0f}%) were replies, "
            f"not original posts. The `is_reply` filter + text-pattern detection may need "
            f"strengthening. Consider also filtering posts that start with `@username` "
            f"where the username isn't the author."
        )

    # Bot / spam
    bot_count = len(bad_buckets.get("bot", []))
    if bot_count >= 2:
        pct = bot_count / max(total_bad, 1) * 100
        proposals.append(
            f"**Bot/spam leak** — {bot_count}/{total_bad} bad items ({pct:.0f}%) were bot-generated. "
            f"Consider adding heuristics: very formulaic text patterns, accounts with "
            f"high post frequency, or emoji-heavy engagement-bait openers."
        )

    # Self-promotion
    promo_count = len(bad_buckets.get("self-promo", []))
    if promo_count >= 2:
        pct = promo_count / max(total_bad, 1) * 100
        proposals.append(
            f"**Self-promo leak** — {promo_count}/{total_bad} bad items ({pct:.0f}%) were "
            f"self-promotion (e.g. 'check out my repo', fake official guides). "
            f"The `claim_link_mismatch` spam detector could be extended with new patterns "
            f"from these examples."
        )

    # Low engagement sneaking through
    low_eng = len(bad_buckets.get("low-engagement", []))
    if low_eng >= 2:
        pct = low_eng / max(total_bad, 1) * 100
        proposals.append(
            f"**Low-engagement leak** — {low_eng}/{total_bad} bad items ({pct:.0f}%) had "
            f"suspiciously low engagement. Check if unknown-engagement items are being "
            f"let through instead of dropped. Current floors: "
            f"X={config.get('quality_filters', {}).get('min_engagement', {}).get('x_likes', '?')} likes, "
            f"Reddit={config.get('quality_filters', {}).get('min_engagement', {}).get('reddit_score', '?')} score."
        )

    # Misleading content
    mislead_count = len(bad_buckets.get("misleading", []))
    if mislead_count >= 2:
        proposals.append(
            f"**Misleading content** — {mislead_count} items flagged as misleading/clickbait. "
            f"Add the specific claim patterns from these examples to "
            f"`spam_detection.claim_link_mismatch_patterns` in the quality filters."
        )

    # Topic-specific problems
    if total_bad >= 5:
        for topic, count in sorted(analysis["bad_topics"].items(), key=lambda x: -x[1]):
            if topic == "unknown":
                continue
            topic_pct = count / total_bad * 100
            if topic_pct >= 40 and count >= 3:
                proposals.append(
                    f"**Topic hotspot: {topic}** — {count}/{total_bad} bad items ({topic_pct:.0f}%) "
                    f"come from this topic. Its search queries may be too broad, or "
                    f"the topic attracts more noise. Consider narrowing the query or "
                    f"raising the engagement floor for this topic specifically."
                )
                break  # One topic callout is enough

    # --- Good-signal proposals ---

    # Long-form preference
    longform_count = len(good_buckets.get("long-form", []))
    if longform_count >= 2:
        current_bonus = config.get("quality_filters", {}).get("long_form_bonus", 15)
        proposals.append(
            f"**Long-form wins** — {longform_count}/{total_good} good items were long-form content. "
            f"Current `long_form_bonus` is {current_bonus}. "
            f"Consider increasing it to {current_bonus + 10} to surface more of these."
        )

    # Practical content preference
    practical_count = len(good_buckets.get("practical", []))
    if practical_count >= 2:
        proposals.append(
            f"**Practical content valued** — {practical_count}/{total_good} good items were "
            f"tutorials, how-tos, or code examples. Consider adding bonus scoring for "
            f"posts containing code blocks, 'tutorial', or linking to GitHub repos "
            f"(non-self-promo)."
        )

    # Insider / announcement preference
    insider_count = len(good_buckets.get("insider", []))
    if insider_count >= 2:
        proposals.append(
            f"**Insider content valued** — {insider_count}/{total_good} good items were "
            f"from team members or official accounts. The `priority_accounts` list "
            f"and `lab_accounts` detection are working. Consider expanding the "
            f"must-follow list if specific people keep surfacing as #good."
        )

    # Unclassified feedback (user provides tags but no reasons)
    unclassified_bad = len(bad_buckets.get("unclassified", []))
    unclassified_good = len(good_buckets.get("unclassified", []))
    total_unclassified = unclassified_bad + unclassified_good
    if total_unclassified >= 5 and total_unclassified / max(total_bad + total_good, 1) > 0.5:
        proposals.append(
            f"**Add reasons to feedback** — {total_unclassified}/{total_bad + total_good} "
            f"tagged items have no reason text. Adding a short reason after the tag "
            f"(e.g. `#bad it was a reply`) enables much better pattern detection."
        )

    return proposals


def _render_feedback_insights(analysis: dict, proposals: list[str]) -> list[str]:
    """Render the Feedback Insights section for the daily note."""
    lines = [
        "## Feedback Insights \U0001f50d",
        "",
    ]

    total = analysis["total_good"] + analysis["total_bad"]
    if total == 0:
        lines.extend([
            "> No feedback data yet. Tag items with `#good <reason>` or `#bad <reason>` to start the learning loop.",
            "",
        ])
        return lines

    # Summary line
    lines.append(
        f"> Analyzing **{total}** feedback entries from the last "
        f"**{analysis['lookback_days']}** days "
        f"({analysis['total_good']} good, {analysis['total_bad']} bad)."
    )
    lines.append("")

    # Bad-signal breakdown
    if analysis["total_bad"] > 0 and analysis["bad_buckets"]:
        lines.append("**Why you tagged items #bad:**")
        lines.append("")
        for bucket_name, entries in sorted(
            analysis["bad_buckets"].items(),
            key=lambda x: -len(x[1])
        ):
            count = len(entries)
            pct = count / analysis["total_bad"] * 100
            lines.append(f"- **{bucket_name}**: {count} ({pct:.0f}%)")
        lines.append("")

    # Good-signal breakdown
    if analysis["total_good"] > 0 and analysis["good_buckets"]:
        lines.append("**Why you tagged items #good:**")
        lines.append("")
        for bucket_name, entries in sorted(
            analysis["good_buckets"].items(),
            key=lambda x: -len(x[1])
        ):
            count = len(entries)
            pct = count / analysis["total_good"] * 100
            lines.append(f"- **{bucket_name}**: {count} ({pct:.0f}%)")
        lines.append("")

    # Proposals
    if proposals:
        lines.append("### Proposals")
        lines.append("")
        for i, p in enumerate(proposals, 1):
            lines.append(f"{i}. {p}")
        lines.append("")
    elif total >= 3:
        lines.extend([
            "> Patterns are forming but no strong signals yet. Keep tagging!",
            "",
        ])

    return lines


# ---------------------------------------------------------------------------
# Cost summary + efficiency recommendations (rendered in daily note)
# ---------------------------------------------------------------------------

def _render_cost_summary(tracker: TokenTracker) -> list[str]:
    """Render a compact cost/token summary block for the top of the daily note."""
    ts = tracker.summary_dict()
    by_model = tracker.by_model()
    total_cost = ts.get("cost_usd") or ts.get("estimated_cost_usd", 0)
    cost_label = "Cost" if "cost_usd" in ts else "~Cost"

    lines = [
        f"> **Pipeline {cost_label}** | "
        f"**{ts['api_calls']}** API calls | "
        f"**{ts['total_tokens']:,}** tokens "
        f"({ts['input_tokens']:,} in / {ts['output_tokens']:,} out) | "
        f"**${total_cost:.4f}**",
        ">",
    ]
    # Per-model breakdown on one line
    model_parts = []
    for model, data in sorted(by_model.items()):
        tag = "" if data["has_exact"] else "~"
        model_parts.append(
            f"{model}: {data['calls']}× {data['total']:,}tok {tag}${data['cost']:.4f}"
        )
    lines.append(f"> {' · '.join(model_parts)}")
    lines.append("")
    return lines


def _render_efficiency_recommendations(tracker: TokenTracker, config: dict,
                                        topic_count: int,
                                        mf_account_count: int) -> list[str]:
    """Generate self-improvement recommendations based on this run's usage."""
    lines = [
        "## Efficiency Recommendations",
        "",
        "> Auto-generated analysis of this run's token/cost profile.",
        "",
    ]

    ts = tracker.summary_dict()
    by_model = tracker.by_model()
    total_cost = ts.get("cost_usd") or ts.get("estimated_cost_usd", 0)
    total_tokens = ts["total_tokens"]

    recs: list[str] = []

    # 1. Check if must-follow accounts dominate cost
    mf_tokens = sum(
        c["total"] for c in tracker.calls if c["label"].startswith("MustFollow/")
    )
    mf_cost = sum(
        tracker._call_cost(c)
        for c in tracker.calls if c["label"].startswith("MustFollow/")
    )
    if total_cost > 0 and mf_cost / total_cost > 0.5:
        recs.append(
            f"**Must-follow accounts consume {mf_cost/total_cost:.0%} of total cost** "
            f"({mf_account_count} accounts, ${mf_cost:.4f}). "
            f"Consider batching multiple handles into fewer API calls, or reducing "
            f"the account list to high-signal accounts only."
        )

    # 2. Check output-heavy calls (model generating a lot of text)
    for c in tracker.calls:
        if c["output"] > 0 and c["input"] > 0:
            ratio = c["output"] / c["input"]
            if ratio > 3.0 and c["output"] > 2000:
                recs.append(
                    f"**{c['label']}** has a {ratio:.1f}× output/input ratio "
                    f"({c['output']:,} output tokens). The prompt may be under-constraining "
                    f"the response length. Adding a `max_tokens` cap could save cost."
                )
                break  # One example is enough

    # 3. Per-topic cost outliers
    topic_costs = {}
    for c in tracker.calls:
        if "/" in c["label"] and not c["label"].startswith("MustFollow/") and c["label"] != "Synthesis":
            prefix = c["label"].split("/")[1] if "/" in c["label"] else c["label"]
            topic_costs.setdefault(prefix, 0.0)
            topic_costs[prefix] += tracker._call_cost(c)
    if topic_costs:
        avg_topic_cost = sum(topic_costs.values()) / len(topic_costs)
        for slug, cost in topic_costs.items():
            if avg_topic_cost > 0 and cost > avg_topic_cost * 2:
                recs.append(
                    f"**Topic '{slug}'** costs ${cost:.4f} — "
                    f"{cost/avg_topic_cost:.1f}× the average topic. "
                    f"Its search query may be too broad."
                )

    # 4. Model selection hints
    for model, data in by_model.items():
        if "grok" in model.lower() and data["cost"] > 0:
            avg_per_call = data["cost"] / data["calls"] if data["calls"] > 0 else 0
            if avg_per_call > 0.02:
                recs.append(
                    f"**{model}** averages ${avg_per_call:.4f}/call. "
                    f"If xAI offers a cheaper model with x_search, switching could save "
                    f"${data['cost'] * 0.4:.4f}/run (~40%)."
                )
                break

    # 5. Overall daily budget check
    monthly_est = total_cost * 30
    if monthly_est > 10:
        recs.append(
            f"**Projected monthly cost: ${monthly_est:.2f}**. "
            f"Target is $6/month. Consider reducing `items_per_topic`, "
            f"switching to cheaper models for low-priority topics, "
            f"or scanning fewer must-follow accounts."
        )
    elif monthly_est < 3:
        recs.append(
            f"Projected monthly cost: ${monthly_est:.2f} — well within budget. "
            f"Room to add more topics or deeper scans if desired."
        )

    # 6. Zero-usage calls (API didn't return token counts)
    zero_calls = [c for c in tracker.calls if c["total"] == 0]
    if zero_calls:
        labels = ", ".join(c["label"] for c in zero_calls[:3])
        extra = f" (+{len(zero_calls)-3} more)" if len(zero_calls) > 3 else ""
        recs.append(
            f"**{len(zero_calls)} API calls returned no usage data** ({labels}{extra}). "
            f"Cost estimates may be understated. Check if the API version reports usage."
        )

    if recs:
        for i, rec in enumerate(recs, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")
    else:
        lines.extend([
            "No issues detected — pipeline is running efficiently.",
            "",
        ])

    return lines


# ---------------------------------------------------------------------------
# Vault Connections — wikilink today's note to existing Library notes
# ---------------------------------------------------------------------------

# Map topic slugs → search terms for vault search (tight, specific terms)
_TOPIC_SEARCH_TERMS: dict[str, list[str]] = {
    "agents": ["agentic workflow", "multi-agent", "agent development"],
    "skills": ["agent skill", "SKILL.md", "skillsbench"],
    "models": ["frontier model", "GPT-5", "Claude Opus", "Grok 4"],
    "mcp": ["Model Context Protocol", "MCP server"],
    "rag": ["RAG pipeline", "retrieval augmented", "vector search", "hybrid search"],
}


def _find_vault_connections(topic_slugs: list[str], config: dict) -> dict[str, list[str]]:
    """Search the Obsidian vault for Library notes related to each topic.

    Uses the vendored Obsidian client to search the Library folder.
    Returns {topic_slug: [note_stem, ...]} — note stems are suitable
    for [[wikilink]] syntax.

    No new scripts — uses the same Obsidian CLI wrapper the vault module uses.
    """
    try:
        ob = vault._client()
    except Exception:
        return {}

    library_folder = config.get("library_folder", "Research/Library")
    connections: dict[str, list[str]] = {}

    for slug in topic_slugs:
        terms = _TOPIC_SEARCH_TERMS.get(slug, [slug])
        matched_stems: set[str] = set()

        for term in terms:
            try:
                results = ob.search(term, path=library_folder)
                text = results.text if hasattr(results, "text") else str(results)
                for line in text.strip().split("\n"):
                    line = line.strip()
                    if not line or not line.endswith(".md"):
                        continue
                    # Extract stem (filename without .md)
                    stem = Path(line).stem
                    # Skip the MOC itself — it's linked via frontmatter `up:`
                    if "MOC" in stem:
                        continue
                    matched_stems.add(stem)
            except Exception:
                continue

        if matched_stems:
            # Cap at 5 most relevant notes per topic
            connections[slug] = sorted(matched_stems)[:5]

    return connections


def render_daily_note(
    date_str: str,
    topic_results: list,
    synthesis: dict,
    config: dict,
    must_follow_results: list = None,
    prominent_results: list = None,
    feedback_summary: dict = None,
    feedback_analysis: dict = None,
    feedback_proposals: list[str] = None,
    tracker: TokenTracker | None = None,
) -> str:
    """Render the full daily note markdown."""
    topic_slugs = [tr["topic"].slug for tr in topic_results]
    total_reddit = sum(len(tr["reddit_items"]) for tr in topic_results)
    total_x = sum(len(tr["x_items"]) for tr in topic_results)

    # Count must-follow tweets
    mf_count = sum(len(r["items"]) for r in (must_follow_results or []))
    prom_count = len(prominent_results or [])



    # Find vault connections — wikilink to existing Library notes
    vault_connections = _find_vault_connections(topic_slugs, config)

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

    # Build frontmatter
    fm_lines = [
        "---",
        f"date: {date_str}",
        "type: daily-research",
        f"tags: [{', '.join(topic_slugs)}]",
        "status: unread",
        f"up: \"[[🤖 MOC - AI Agent Development]]\"",
        f"reddit_items: {total_reddit}",
        f"x_items: {total_x}",
        f"must_follow_tweets: {mf_count}",
        f"prominent_voices: {prom_count}",
        f"deep_dives: {len(deep_dives)}",
        f"lab_pulse: {len(lab_pulse_items)}",
    ]
    fm_lines.extend(["---", ""])

    lines = fm_lines + [
        f"# Daily Research — {_format_date(date_str)}",
        "",
    ]

    # Token / cost summary — right after the title
    if tracker and tracker.num_calls > 0:
        lines.extend(_render_cost_summary(tracker))

    # Briefing — the POW moment
    briefing = synthesis.get("briefing", "")
    if briefing:
        lines.extend([
            "## Today's POW",
            "",
            briefing,
            "",
        ])

    # Vault Connections — wikilink to existing Library notes
    if vault_connections:
        lines.extend([
            "## Vault Connections \U0001f517",
            "",
            "> Today's topics link to these existing notes in your vault.",
            "",
        ])
        # Collect all unique stems across all topics for later use
        all_linked = set()
        for slug in topic_slugs:
            stems = vault_connections.get(slug, [])
            if stems:
                # Use the topic's display name from topic_results
                display = slug
                for tr in topic_results:
                    if tr["topic"].slug == slug:
                        display = tr["topic"].display_name
                        break
                links = ", ".join(f"[[{s}]]" for s in stems)
                lines.append(f"- **{display}**: {links}")
                all_linked.update(stems)
        lines.append("")

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
                        text_display = _oneline(text, 200)
                        lines.append(
                            f"- @{acct['handle']}{date_str_item}: {text_display} "
                            f"[{likes}\u2764\ufe0f]({url})"
                        )
                lines.append("")


    # Prominent AI Voices — high-engagement tweets from top AI minds (broad search)
    if prominent_results:
        lines.extend([
            "## Prominent Voices \U0001f399\ufe0f",
            "",
            "> High-engagement tweets (500+ likes) from prominent AI researchers, engineers, and executives.",
            "",
            "| Author | Post | Likes | Link |",
            "|--------|------|-------|------|",
        ])
        # Sort by likes descending for impact
        sorted_prom = sorted(
            prominent_results,
            key=lambda item: (item.engagement.likes if item.engagement and item.engagement.likes else 0),
            reverse=True,
        )
        for item in sorted_prom[:15]:
            likes = item.engagement.likes if item.engagement and item.engagement.likes else 0
            text_short = _oneline(item.text, 100)
            lines.append(
                f"| @{item.author_handle} | {text_short} | {likes}\u2764\ufe0f | [→]({item.url}) |"
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
                text_short = _oneline(item.text, 80)
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
                title = _oneline(item.text, 100)
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

        # Vault see-also — wikilinks to related Library notes
        related_stems = vault_connections.get(topic.slug, [])
        if related_stems:
            see_also = " · ".join(f"[[{s}]]" for s in related_stems[:5])
            lines.extend([f"> See also: {see_also}", ""])

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
                title_short = _oneline(item.title, 60)
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
                text_short = _oneline(item.text, 60)
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
        "> Tag any item with `#good <reason>` or `#bad <reason>` to give feedback.",
        "> Add a short reason after the tag — it powers the learning loop below.",
        "> Examples: `#bad it was a reply` · `#good deep practical tutorial` · `#bad bot-generated spam`",
        "> Next run picks it up, classifies it, and generates improvement proposals.",
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

    # Feedback Insights — pattern analysis + proposals from accumulated feedback
    if feedback_analysis:
        lines.extend(_render_feedback_insights(feedback_analysis, feedback_proposals or []))

    # Efficiency recommendations (at the very end)
    if tracker and tracker.num_calls > 0:
        topic_count = len(topic_results)
        mf_count_accts = len(config.get("must_follow_accounts", []))
        lines.extend(["---", ""])
        lines.extend(_render_efficiency_recommendations(
            tracker, config, topic_count, mf_count_accts,
        ))

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
                "title": _oneline(item.text, 80),
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
    parser.add_argument("--force-rerun", action="store_true", help="Ignore same-day note protection and rerun intentionally")
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
        from vendor.last30days import env as l30_env
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

    if not args.dry_run and not args.force_rerun and vault.daily_exists(config, today):
        print(f"[skip] Daily research note already exists for {today}. Use --force-rerun to run again intentionally.")
        return

    # Run promote pass first (tag-to-library for previous dailies)
    # Load API key early so promote can do LLM enrichment
    from vendor.last30days import env as l30_env
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

    # Analyze accumulated feedback and generate proposals
    feedback_analysis = analyze_feedback(feedback_summary["data"], lookback_days=14)
    feedback_proposals = generate_proposals(feedback_analysis, config)
    if feedback_proposals:
        print(f"[feedback] Generated {len(feedback_proposals)} improvement proposals")

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

    # Load vault dedup set (zero tokens — pure filesystem, single pass)
    print(f"[dedup] Scanning vault for seen URLs and titles...")
    seen_urls, seen_titles = vault.load_seen_dedup(config)
    print(f"[dedup] Found {len(seen_urls)} seen URLs, {len(seen_titles)} seen titles")

    # Date range: last 7 days for daily scan (not 30)
    from vendor.last30days import dates
    from_date, _ = dates.get_date_range(7)
    to_date = today

    # Must-follow: always last 24 hours only
    mf_from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Select models (reuse last30days model selection with caching)
    from vendor.last30days import models as l30_models
    selected_models = l30_models.get_models(l30_config)

    # Initialize token tracker
    tracker = TokenTracker(config.get("cost_rates"))

    # Run topic scans sequentially (to stay within rate limits)
    print(f"\n[scan] Starting {len(all_topics)} topic scans (scan mode)...")
    topic_results = []
    total_errors = []

    for topic in all_topics:
        print(f"  [{topic.slug}] Scanning...", end=" ", flush=True)
        result = run_topic_scan(
            topic, config, l30_config, selected_models,
            from_date, to_date, seen_urls, seen_titles,
            tracker=tracker,
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

    # Must-follow account scan (hybrid batch/solo, no quality filters)
    must_follow_results = []
    mf_accounts = config.get("must_follow_accounts", [])
    if mf_accounts and l30_config.get("XAI_API_KEY"):
        n_batch = sum(1 for a in mf_accounts if not a.get("solo"))
        n_solo = sum(1 for a in mf_accounts if a.get("solo"))
        n_calls = (1 if n_batch else 0) + n_solo
        print(f"\n[must-follow] Scanning {len(mf_accounts)} accounts ({n_batch} batch + {n_solo} solo = {n_calls} calls) | last 24h ({mf_from_date} → {to_date})...")
        must_follow_results = run_must_follow_scan(
            config, l30_config, mf_from_date, to_date,
            tracker=tracker,
        )
        mf_total = sum(len(r["items"]) for r in must_follow_results)
        print(f"[must-follow] Captured {mf_total} tweets from {len(mf_accounts)} accounts")

    # Prominent AI voices scan (single broad search, 500+ likes)
    prominent_results = []
    if l30_config.get("XAI_API_KEY"):
        print(f"\n[prominent-ai] Scanning for high-engagement AI voices | last 24h ({mf_from_date} → {to_date})...")
        prominent_results = run_prominent_ai_scan(
            config, l30_config, mf_from_date, to_date,
            seen_urls,
            tracker=tracker,
        )
        # Add to seen_urls so synthesis doesn't double-count
        for item in prominent_results:
            seen_urls.add(item.url)

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
                tracker=tracker,
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
        prominent_results=prominent_results,
        feedback_summary=feedback_summary,
        feedback_analysis=feedback_analysis,
        feedback_proposals=feedback_proposals,
        tracker=tracker,
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

    # Cost summary (always print — replaces old --costs heuristic)
    ts = tracker.summary_dict()
    total_cost = ts.get("cost_usd") or ts.get("estimated_cost_usd", 0)
    cost_tag = "" if "cost_usd" in ts else "~"
    print(f"\n[tokens] {ts['api_calls']} API calls | {ts['total_tokens']:,} tokens | {cost_tag}${total_cost:.4f}")
    for model, data in tracker.by_model().items():
        tag = "" if data["has_exact"] else "~"
        print(f"  {model}: {data['calls']}× | {data['total']:,} tokens | {tag}${data['cost']:.4f}")

    # Final summary
    total_reddit = sum(len(tr["reddit_items"]) for tr in topic_results)
    total_x = sum(len(tr["x_items"]) for tr in topic_results)
    mf_total = sum(len(r["items"]) for r in must_follow_results)
    prom_total = len(prominent_results)
    print(f"\nDone! {total_reddit}R + {total_x}X + {mf_total}MF + {prom_total}PA items across {len(all_topics)} topics.")


if __name__ == "__main__":
    main()
