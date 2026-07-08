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
import copy
import io
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from types import SimpleNamespace
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
# Model auto-resolution — query xAI API for latest available models
# ---------------------------------------------------------------------------

def resolve_xai_model(api_key: str, preferred: str = "grok-4-1-fast") -> str:
    """Query xAI API for available models and return the best one.

    Strategy: prefer the configured model if available, otherwise pick the
    latest grok text/chat model. Filters out image/video/build models.
    Falls back to preferred if the API call fails.
    """
    # Substrings that indicate non-text models (image gen, video gen, build tools)
    _EXCLUDE = ["imagine", "image", "video", "build", "embed"]

    try:
        req = urllib.request.Request(
            "https://api.x.ai/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        models = data.get("data", [])
        if not models:
            return preferred

        # Extract grok text/chat model IDs (exclude image/video/build models)
        grok_models = []
        for m in models:
            mid = m.get("id", "")
            if "grok" not in mid.lower():
                continue
            if any(exc in mid.lower() for exc in _EXCLUDE):
                continue
            grok_models.append(mid)

        if not grok_models:
            return preferred

        # If preferred is available, use it
        if preferred in grok_models:
            return preferred

        # Pick the best model:
        # 1. Prefer non-reasoning variants (cheaper, faster for search tasks)
        # 2. Among remaining, prefer shorter names (e.g. grok-4.3 over grok-4.20-0309-reasoning)
        # 3. Sort by version number descending
        non_reasoning = [m for m in grok_models if "reasoning" not in m and "multi-agent" not in m]
        candidates = non_reasoning if non_reasoning else grok_models
        # Sort: higher version first, shorter name preferred for ties
        candidates.sort(key=lambda m: (m.split("-")[0] if "-" in m else m, -len(m)), reverse=True)
        chosen = candidates[0]
        print(f"[model] Configured model '{preferred}' not found. Available text models: {grok_models}")
        print(f"[model] Selected '{chosen}'")
        return chosen

    except Exception as e:
        print(f"[model] Could not query xAI models API ({e}), using '{preferred}'")
        return preferred


# ---------------------------------------------------------------------------
# Token / cost tracking
# ---------------------------------------------------------------------------

# Default cost rates per 1M tokens (USD) — used ONLY as fallback when the API
# does not return an exact cost.  xAI responses include `cost_in_usd_ticks`
# (exact cost), so rates below are irrelevant for Grok models in practice.
# Override via DEFAULT_COST_RATES dict above.
DEFAULT_COST_RATES = {
    # Anthropic — synthesis
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5":  {"input": 0.80, "output": 4.00},
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
            label:  Human-readable call label (e.g. 'X/agents')
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

# Quality filter defaults. X account membership is derived from pipeline.md,
# not hardcoded here.
DEFAULT_QUALITY_FILTERS = {
    "min_engagement": {"x_likes": 100},
    "long_form_bonus": 15,
    # NOTE: scan-mode tweet text is capped at 2000 chars by parse_x_response;
    # this threshold must stay comfortably below that cap or deep-dive
    # classification becomes unreachable (it was 800 vs a 500-char cap for
    # months — every deep_dives count was 0).
    "long_form_min_chars": 400,
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
        "x": [],
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
    "lab_accounts": {},
}

LAB_GROUP_MAP = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google": "google",
    "meta": "meta",
    "mistral": "mistral",
    "xai": "xai",
}


def _apply_derived_quality_filters(config: dict) -> dict:
    """Populate quality filter account lists from pipeline-defined accounts."""
    qf = copy.deepcopy(config.get("quality_filters") or DEFAULT_QUALITY_FILTERS)

    priority = qf.setdefault("priority_accounts", {})
    priority["x"] = [
        acct["handle"].lstrip("@").lower()
        for acct in config.get("must_follow_accounts", [])
    ]

    lab_accounts: dict[str, list[str]] = {}
    for acct in config.get("must_follow_accounts", []):
        group = (acct.get("group") or "").strip().lower()
        lab_key = LAB_GROUP_MAP.get(group)
        if not lab_key:
            continue
        lab_accounts.setdefault(lab_key, []).append(acct["handle"].lstrip("@").lower())
    qf["lab_accounts"] = lab_accounts

    config["quality_filters"] = qf
    return config


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
    return _apply_derived_quality_filters(_parse_pipeline_md(PIPELINE_MD))


# ---------------------------------------------------------------------------
# Text sanitization for markdown output
# ---------------------------------------------------------------------------

def _oneline(text: str, max_len: int = 120) -> str:
    """Collapse text to a single line safe for markdown list items and links.

    Strips newlines, tabs, pipe chars (break tables), and square brackets
    (break markdown links). Collapses whitespace, then truncates only when
    max_len is a positive integer.
    """
    # Replace newlines/tabs with a space
    t = re.sub(r'[\n\r\t]+', ' ', text)
    # Remove characters that break markdown link syntax or tables
    t = t.replace('[', '').replace(']', '').replace('|', '-')
    # Collapse multiple spaces
    t = re.sub(r' {2,}', ' ', t).strip()
    if max_len and max_len > 0 and len(t) > max_len:
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


# Patterns indicating a tweet is reporting on someone else's work rather than being that work.
# Examples: "X just dropped a 10-step guide", "@boris just published an article", "check out this thread by @Y"
_AMPLIFIER_PATTERNS = [
    r"\bjust\s+(?:dropped|released|published|shared|launched|posted|wrote|announced|put\s+out)\b",
    r"\bjust\s+(?:came\s+out\s+with|dropped\s+a)\b",
    r"\b(?:check\s+out|go\s+read|you\s+(?:need\s+to\s+)?(?:check|read|see|watch))\b",
    r"\bhere(?:'s|\s+is)\s+(?:a\s+)?(?:thread|article|guide|summary|breakdown|writeup|post)\s+(?:by|from)\b",
    r"\bthread\s+by\s+@",
    r"\bsummary\s+(?:of|from)\b",
    r"\bmy\s+notes\s+on\b",
    r"\b@\w+\s+(?:just\s+)?(?:dropped|released|published|wrote|posted|shared|announced)\b",
]

# Counter-signals: explicit first-person experimentation that adds original value.
_NOVEL_ANALYSIS_SIGNALS = [
    r"\bI\s+(?:tested|tried|built|ran|measured|benchmarked|deployed|implemented|reproduced|validated|replicated)\b",
    r"\bI\s+found\s+(?:that\s+)?(?:it|this|the)\b",
    r"\bmy\s+(?:analysis|results|findings|benchmark|experiment|test)\b",
    r"\bhere(?:'s|\s+is)\s+(?:what\s+(?:I\s+found|happened|it\s+does)|my\b)\b",
]

_AMPLIFIER_RE = [re.compile(p, re.IGNORECASE) for p in _AMPLIFIER_PATTERNS]
_NOVEL_RE = [re.compile(p, re.IGNORECASE) for p in _NOVEL_ANALYSIS_SIGNALS]
_NOVEL_ANALYSIS_MIN_CHARS = 600


def _is_amplifier(item) -> bool:
    """Drop tweets that only report someone else's work with no original contribution.

    Catches patterns like "X just dropped a 10-step guide..." or "@Y just published
    an article on...". Exception: long posts (≥600 chars) with first-person analysis
    signals ("I tested", "I built", "I found") are kept — they add genuine value.
    """
    text = item.text.strip()
    if not any(p.search(text) for p in _AMPLIFIER_RE):
        return False
    # Amplifier pattern matched — check for novel-analysis exception
    has_novel = any(p.search(text) for p in _NOVEL_RE)
    is_long = len(text) >= _NOVEL_ANALYSIS_MIN_CHARS
    if has_novel and is_long:
        return False
    return True


def _links_article_domain(item, article_domains: list[str]) -> bool:
    """True if the item's URL or any URL in its text points at a known article/blog domain."""
    item_url = (getattr(item, 'url', '') or "").lower()
    text = (getattr(item, 'text', '') or "").lower()
    all_urls = [item_url] + re.findall(r'https?://\S+', text)
    return any(domain in url for url in all_urls for domain in article_domains)


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

    # Deep dive check — long threads OR posts linking to article domains
    if source == "x":
        if len(item.text) >= long_form_min:
            return "deep-dive"
        if _links_article_domain(item, article_domains):
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

    # --- 0c. Amplifier filtering (drop "X just dropped a guide" signal-laundering) ---
    # Exception: posts linking to a known article domain are kept — they are the
    # primary carriers for the Deep Dives section, and "X just published..." posts
    # that link to the actual article still have reference value.
    _amp_article_domains = [d.lower() for d in qf.get("article_domains", [])]
    result["x_items"] = [
        item for item in result["x_items"]
        if not _is_amplifier(item) or _links_article_domain(item, _amp_article_domains)
    ]

    min_eng = qf.get("min_engagement", {})
    x_likes_floor = min_eng.get("x_likes", 0)

    long_form_bonus = qf.get("long_form_bonus", 0)
    long_form_min_chars = qf.get("long_form_min_chars", 400)
    article_domains = [d.lower() for d in qf.get("article_domains", [])]

    priority = qf.get("priority_accounts", {})
    priority_x = {h.lower() for h in priority.get("x", [])}
    priority_bonus = qf.get("priority_account_bonus", 0)

    # --- 1. Engagement floor (drop low-engagement items) ---
    # Exception: priority/lab accounts bypass engagement floor
    lab_handles = set()
    for handles in qf.get("lab_accounts", {}).values():
        lab_handles.update(h.lower() for h in handles)

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
        for item in result["x_items"]:
            if len(item.text) >= long_form_min_chars:
                item.score = min(100, item.score + long_form_bonus)

    # --- 3. Priority account boost ---
    if priority_bonus > 0:
        for item in result["x_items"]:
            if item.author_handle.lower() in priority_x:
                item.score = min(100, item.score + priority_bonus)

    # --- 4. Classify content (attach category metadata) ---
    for item in result["x_items"]:
        item._category = _classify_content(item, config, "x")

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
        xai_x,
        normalize,
        score,
        dedupe,
        schema,
    )

    result = {
        "topic": topic,
        "x_items": [],
        "errors": [],
    }

    combined_query = topic.display_name

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
    result["x_items"] = [
        item for item in result["x_items"]
        if item.url not in seen_urls
    ]

    return result


SYNTHESIS_MODEL = "claude-sonnet-4-6"  # kept as fallback reference
CLAUDE_CLI = r"C:\Users\nuno_\.local\bin\claude.exe"  # kept as fallback reference


def _call_xai_chat(api_key: str, model: str, prompt: str, max_tokens: int = 4096) -> tuple[str, dict | None]:
    """Call xAI chat completions API directly. Returns (content_text, usage_dict)."""
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.x.ai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = data.get("usage")
    return content, usage


def _extract_json_object(text: str) -> dict | None:
    """Robustly extract a JSON object from text that may contain prose or code fences."""
    # Strip markdown code fences
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    # Try direct parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    # Find first { and last } — extract the JSON object
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace >= 0 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def synthesize_all(
    topic_results: list,
    from_date: str,
    to_date: str,
    tracker: TokenTracker | None = None,
    api_key: str = "",
    model: str = "grok-4.3",
) -> dict:
    """Single batched synthesis call across all topics using Claude CLI (Max account)."""

    # Build per-topic summaries
    sections = []
    for tr in topic_results:
        topic = tr["topic"]
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
        if x_lines:
            section += "X:\n" + "\n".join(x_lines) + "\n"
        else:
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
- Output ONLY valid JSON, no prose before or after"""

    max_retries = 2
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            content, usage = _call_xai_chat(api_key, model, prompt, max_tokens=4096)
            if tracker and usage:
                tracker.record("Synthesis", model, usage)
            if not content:
                last_error = "empty response from API"
                if attempt < max_retries:
                    print(f"[synth] Attempt {attempt+1} failed: no output, retrying...")
                    continue
                return {"briefing": f"Synthesis failed after {max_retries+1} attempts: {last_error}", "topics": [], "error": last_error}
            print(f"[synth] xAI synthesis done (attempt {attempt+1})")
            parsed = _extract_json_object(content)
            if parsed and "briefing" in parsed:
                return parsed
            # JSON extraction failed — retry
            preview = content[:200].replace('\n', '\\n')
            last_error = f"Could not extract valid JSON from output ({len(content)} chars): {preview}"
            if attempt < max_retries:
                print(f"[synth] Attempt {attempt+1} failed: {last_error}, retrying...")
                continue
            return {"briefing": f"Synthesis failed: {last_error}", "topics": [], "error": last_error}
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                print(f"[synth] Attempt {attempt+1} failed: {e}, retrying...")
                continue
    return {"briefing": f"Synthesis failed after {max_retries+1} attempts: {last_error}", "topics": [], "error": last_error}


# ---------------------------------------------------------------------------
# Must-Follow Account Scanning (hybrid batch/solo)
# ---------------------------------------------------------------------------

# Minimum text length for must-follow tweets (after stripping URLs/mentions)
_MF_MIN_SUBSTANCE_CHARS = 40

# Patterns indicating a tweet is just a social reaction, not research-relevant
_MF_LOW_SUBSTANCE_PATTERNS = [
    re.compile(r'^[\U0001f300-\U0001faff☀-➿‍️\s]+$'),  # pure emoji
    re.compile(r'^(?:lm[fa]+o|haha|wow|nice|ty|thanks|thank you|congrats|yep|yes|no|agreed|exactly|this|same|100%|real|true|fr|w$)', re.IGNORECASE),
    re.compile(r'^(?:glad you|great meeting|good to see|nice to meet|was great|had a great|so glad)', re.IGNORECASE),
]


def _filter_must_follow_substance(items: list) -> list:
    """Drop must-follow tweets that lack substance (reactions, emojis, social chat).

    Keeps tweets that are either:
    - Long enough to contain real content (40+ chars after stripping URLs/mentions)
    - Contain a URL (likely sharing something worth reading)
    """
    filtered = []
    for item in items:
        text = item.text.strip()
        # Always keep if the tweet contains a non-x.com URL (sharing an article/resource)
        urls_in_text = re.findall(r'https?://\S+', text)
        external_urls = [u for u in urls_in_text if 'x.com/' not in u and 'twitter.com/' not in u]
        if external_urls:
            filtered.append(item)
            continue
        # Strip URLs and @mentions for substance check
        clean = re.sub(r'https?://\S+', '', text)
        clean = re.sub(r'@\w+', '', clean).strip()
        # Check minimum length
        if len(clean) < _MF_MIN_SUBSTANCE_CHARS:
            continue
        # Check low-substance patterns
        if any(p.match(clean) for p in _MF_LOW_SUBSTANCE_PATTERNS):
            continue
        filtered.append(item)
    return filtered


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

            # Substance filter: drop low-value posts (reactions, emojis, social chat)
            final = _filter_must_follow_substance(final)

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

            print(f"-> {len(final)} tweets")

        except Exception as e:
            print(f"error - {e}")
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

            # Substance filter: drop low-value posts (reactions, emojis, social chat)
            final = _filter_must_follow_substance(final)

            # Must-follow: NO engagement floor — catch everything
            # (engagement floor is for topic scans only)

            results.append({
                "handle": acct["handle"],
                "label": acct.get("label", acct["handle"]),
                "group": acct["group"],
                "items": final,
            })

            print(f"-> {len(final)} tweets")

        except Exception as e:
            print(f"error - {e}")
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
    call asking for high-engagement original tweets from prominent AI
    voices. The like floor comes from pipeline.md (`prominent_ai_min_likes`,
    default 500) and is enforced twice: in the search query the model runs
    (min_faves) and in the post-filter below.

    Returns a list of XItem objects (already filtered for quality).
    """
    from vendor.last30days import xai_x, normalize, score, dedupe

    if not l30_config.get("XAI_API_KEY"):
        return []

    model = l30_config.get("xai_model", "grok-4-1-fast")
    try:
        min_likes = int(config.get("prominent_ai_min_likes", 500) or 500)
    except (TypeError, ValueError):
        min_likes = 500

    print(f"  [prominent-ai] Searching for high-engagement AI tweets ({min_likes}+ likes)...", end=" ", flush=True)

    try:
        raw = xai_x.search_x_prominent_ai(
            l30_config["XAI_API_KEY"],
            model,
            from_date,
            to_date,
            depth="scan",
            min_likes=min_likes,
        )
        if tracker:
            tracker.record("ProminentAI", model, _extract_usage(raw))

        items = xai_x.parse_x_response(raw)

        # The model sometimes answers {"items": []} even though its searches
        # found candidates (url_citations attached to the response). Retry
        # once — an independent sample usually recovers the run.
        if not items:
            n_hits = len(xai_x._extract_citation_urls(raw))
            if n_hits > 0:
                print(f"(empty despite {n_hits} search hits — retrying)", end=" ", flush=True)
                raw = xai_x.search_x_prominent_ai(
                    l30_config["XAI_API_KEY"],
                    model,
                    from_date,
                    to_date,
                    depth="scan",
                    min_likes=min_likes,
                )
                if tracker:
                    tracker.record("ProminentAI/retry", model, _extract_usage(raw))
                items = xai_x.parse_x_response(raw)
                if not items:
                    print("(retry also empty)", end=" ", flush=True)

        normalized = normalize.normalize_x_items(items, from_date, to_date)
        scored = score.score_x_items(normalized)

        # Filter: drop replies, and drop items only when likes are KNOWN and
        # below the floor. The model's x_search query already enforces
        # min_faves, so items with unverifiable engagement are kept — the old
        # behavior (drop unknowns) plus a "500+ non-negotiable" prompt made
        # the model return empty lists whenever counts weren't visible.
        high_signal = [
            item for item in scored
            if not getattr(item, 'is_reply', False)
            and not (
                item.engagement is not None
                and item.engagement.likes is not None
                and item.engagement.likes < min_likes
            )
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

        print(f"-> {len(final)} high-signal tweets")
        return final

    except Exception as e:
        print(f"error - {e}")
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
            f"let through instead of dropped. Current floor: "
            f"X={config.get('quality_filters', {}).get('min_engagement', {}).get('x_likes', '?')} likes."
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
# Self-Healing Pipeline — 4 levels of automatic recovery
# ---------------------------------------------------------------------------

def validate_note(note_content: str) -> list[str]:
    """Level 2: Check rendered note for quality issues after writing.

    Returns a list of issue keys (empty = all good):
      'pow_failed'     — synthesis text contains a failure message
      'news_missing'   — no News section rendered
      'note_too_sparse' — fewer than 5 non-boilerplate content lines
    """
    issues = []
    if "Synthesis failed" in note_content or "Synthesis failed" in note_content:
        issues.append("pow_failed")
    if "## News" not in note_content:
        issues.append("news_missing")
    # Count real content lines (not frontmatter, blockquotes, headers, dividers)
    content_lines = [
        l for l in note_content.split("\n")
        if l.strip()
        and not l.strip().startswith("---")
        and not l.strip().startswith(">")
        and not l.strip().startswith("#")
        and not l.strip().startswith("|--")
    ]
    if len(content_lines) < 5:
        issues.append("note_too_sparse")
    return issues


def detect_drift(config: dict, lookback_days: int = 30) -> list[dict]:
    """Level 3: Scan recent dailies for multi-day metric decay.

    Reads YAML frontmatter from the last N daily notes and flags any
    tracked metric that has been 0 for 3+ consecutive days, reporting the
    true streak length and the last non-zero date within the lookback
    window (a 7-day lookback made months-old breakage read as a week old).
    Also detects repeated synthesis failures (last 7 days).

    Returns a list of warning dicts (empty = healthy):
      {"metric": <frontmatter key or "_synth"/"_total">, "label": str,
       "streak": int, "message": <markdown string>}
    The structured fields let the renderer reconcile each warning against
    TODAY's counts — a warning about past zeros in a note whose own run
    just produced items reads as a false alarm otherwise.
    """
    warnings = []
    vault_path = Path(config.get("vault_path", ""))
    dailies_folder = config.get("dailies_folder", "Research/Dailies")

    # Collect frontmatter metrics from recent notes (newest first)
    metrics_history = []
    for i in range(1, lookback_days + 1):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        year, month = date[:4], date[5:7]
        note_path = vault_path / dailies_folder / year / month / f"{date}.md"
        if not note_path.exists():
            continue
        try:
            text = note_path.read_text(encoding="utf-8")
            fm = {}
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    for line in text[3:end].strip().split("\n"):
                        if ":" in line:
                            k, v = line.split(":", 1)
                            k, v = k.strip(), v.strip()
                            try:
                                fm[k] = int(v)
                            except ValueError:
                                fm[k] = v
            fm["_date"] = date
            fm["_has_synth_failure"] = "Synthesis failed" in text
            metrics_history.append(fm)
        except Exception:
            continue

    if len(metrics_history) < 3:
        return warnings

    # Check each metric for consecutive zeros (newest first)
    tracked_metrics = [
        ("prominent_voices", "Prominent Voices"),
        ("deep_dives", "Deep Dives"),
        ("lab_pulse", "Lab Pulse"),
        ("x_items", "Research Feed (X)"),
        ("must_follow_tweets", "Must Follow"),
    ]
    for key, label in tracked_metrics:
        consecutive_zeros = 0
        for fm in metrics_history:
            val = fm.get(key, -1)
            if isinstance(val, int) and val == 0:
                consecutive_zeros += 1
            else:
                break
        if consecutive_zeros >= 3:
            last_nonzero = next(
                (fm["_date"] for fm in metrics_history[consecutive_zeros:]
                 if isinstance(fm.get(key), int) and fm.get(key) > 0),
                None,
            )
            if consecutive_zeros >= len(metrics_history):
                streak = f"0 for all {consecutive_zeros} days checked"
            else:
                streak = f"0 for {consecutive_zeros} consecutive days"
            tail = (
                f" (last non-zero: {last_nonzero})" if last_nonzero
                else f" (no non-zero value in the last {len(metrics_history)} notes)"
            )
            warnings.append({
                "metric": key,
                "label": label,
                "streak": consecutive_zeros,
                "message": (
                    f"**{label}** was {streak}"
                    f" — possible filter, search query, or API issue{tail}"
                ),
            })

    # Check for repeated synthesis failures (recent window only)
    recent = metrics_history[:7]
    synth_failures = sum(1 for fm in recent if fm.get("_has_synth_failure"))
    if synth_failures >= 3:
        warnings.append({
            "metric": "_synth",
            "label": "POW synthesis",
            "streak": synth_failures,
            "message": (
                f"**POW synthesis** failed {synth_failures}/{len(recent)} "
                f"recent days — check model availability or API auth"
            ),
        })

    # Check for consistently low total items
    total_items = [
        fm.get("x_items", 0) + fm.get("must_follow_tweets", 0) + fm.get("news_items", 0)
        for fm in metrics_history[:5]
        if isinstance(fm.get("x_items", 0), int)
    ]
    if total_items and all(t < 3 for t in total_items):
        warnings.append({
            "metric": "_total",
            "label": "Total content",
            "streak": len(total_items),
            "message": (
                f"**Total content** has been very low ({total_items}) for the "
                f"last {len(total_items)} days — API may be degraded"
            ),
        })

    return warnings


def auto_repair_config(config: dict, resolved_model: str):
    """Level 4: Update pipeline.md when configured model was deprecated.

    If the model resolver found a different model than what's in pipeline.md,
    update the config file so future runs don't need to re-resolve.
    Only updates if the current setting isn't 'auto'.
    """
    if not PIPELINE_MD.exists():
        return

    text = PIPELINE_MD.read_text(encoding="utf-8")
    configured = config.get("xai_model", "")

    # Don't update if set to 'auto' — that's intentional
    if not configured or configured == "auto":
        return

    if configured != resolved_model:
        old_line = f"- xai_model: {configured}"
        new_line = f"- xai_model: {resolved_model}"
        if old_line in text:
            text = text.replace(old_line, new_line)
            PIPELINE_MD.write_text(text, encoding="utf-8")
            print(f"[heal] Auto-updated pipeline.md: xai_model {configured} → {resolved_model}")


def _render_health_warnings(
    warnings: list[dict],
    today_counts: dict | None = None,
    synth_ok: bool = False,
) -> list[str]:
    """Render pipeline health section, reconciled against TODAY's results.

    A metric that was 0 on previous days but produced items in this run is
    reported as recovered, not warned about — otherwise the first healthy
    note after a fix still carries stale alarms.
    """
    if not warnings:
        return []
    today_counts = today_counts or {}
    rendered = []
    for w in warnings:
        metric = w.get("metric")
        if metric in today_counts:
            n = today_counts[metric]
            if n > 0:
                rendered.append(
                    f"✅ **{w['label']}** recovered today ({n} item{'s' if n != 1 else ''}) "
                    f"— was 0 for the previous {w['streak']} day(s)"
                )
            else:
                rendered.append(f"{w['message']} — still 0 today")
        elif metric == "_synth" and synth_ok:
            rendered.append(
                f"✅ **POW synthesis** succeeded today — had failed "
                f"{w['streak']}/7 recent days before this run"
            )
        else:
            rendered.append(w["message"])
    lines = [
        "## Pipeline Health ⚠️",
        "",
        "> Auto-detected signals from recent daily runs, reconciled against today's results:",
        "",
    ]
    for r in rendered:
        lines.append(f"- {r}")
    lines.append("")
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


# ---------------------------------------------------------------------------
# Google News RSS
# ---------------------------------------------------------------------------


def _fetch_google_news_topic(query: str, max_items: int = 10, max_age_days: int = 7) -> list:
    """Fetch Google News RSS for a single query. Returns list of article dicts.

    Only returns items published within the last `max_age_days` days.
    """
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        items = []
        for item_el in root.findall(".//item")[:max_items * 2]:  # fetch extra to compensate for date filter
            title = item_el.findtext("title", "").strip()
            link = item_el.findtext("link", "").strip()
            pub_date = item_el.findtext("pubDate", "").strip()
            source_el = item_el.find("source")
            source = source_el.text.strip() if source_el is not None else ""
            raw_desc = item_el.findtext("description", "")
            description = re.sub(r"<[^>]+>", " ", raw_desc).strip()
            description = re.sub(r"\s{2,}", " ", description)[:200]

            # Date filter: only keep items from the last max_age_days
            try:
                dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except ValueError:
                pass  # keep items with unparseable dates

            items.append({
                "title": title,
                "url": link,
                "source": source,
                "pub_date": pub_date,
                "description": description,
                "query": query,
            })
            if len(items) >= max_items:
                break
        return items
    except Exception as e:
        print(f"  [news] Error fetching '{query}': {e}")
        return []


def _score_news_with_llm(items: list, api_key: str = "", model: str = "grok-4.3") -> list:
    """Use xAI API to score, deduplicate, and select top 10 news items for relevance."""
    if not items:
        return []

    item_lines = []
    for i, item in enumerate(items, 1):
        desc = f": {item['description'][:120]}" if item.get("description") else ""
        item_lines.append(f"{i}. [{item.get('source', '')}] {item['title']}{desc}")

    prompt = (
        "You are scoring AI news headlines for relevance to an AI practitioner focused on: "
        "agent development, LLM models, MCP (Model Context Protocol), RAG, and AI-assisted SDLC.\n\n"
        "IMPORTANT: Many items may cover the SAME story from different outlets. "
        "Group items by story first, then pick only the BEST item (highest quality source) per story. "
        "Do NOT return multiple items about the same event.\n\n"
        "Score each UNIQUE story 1-10 for relevance. Return ONLY a JSON array of the top 10:\n"
        '[{"index": 1, "score": 9, "also_covered_by": ["Source2", "Source3"]}, ...]\n\n'
        "The 'also_covered_by' field lists other sources covering the same story (use the source name from brackets). "
        "Only include stories with score >= 5. Sort by score descending.\n\n"
        "Items:\n" + "\n".join(item_lines)
    )

    try:
        content, _usage = _call_xai_chat(api_key, model, prompt, max_tokens=2048)
        content = content.strip()
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        # Robust extraction: find the JSON array
        first_bracket = content.find('[')
        last_bracket = content.rfind(']')
        if first_bracket >= 0 and last_bracket > first_bracket:
            content = content[first_bracket:last_bracket + 1]
        rankings = json.loads(content)
        scored = []
        for r in rankings[:10]:
            idx = r.get("index", 0) - 1  # 1-based → 0-based
            if 0 <= idx < len(items):
                item = dict(items[idx])
                item["llm_score"] = r.get("score", 0)
                also = r.get("also_covered_by", [])
                if also:
                    item["also_covered_by"] = also
                scored.append(item)
        return sorted(scored, key=lambda x: x.get("llm_score", 0), reverse=True)
    except Exception as e:
        print(f"  [news] LLM scoring failed: {e}")
        return items[:10]


# General AI backfill queries used when topic-specific news yields < 10 items
_GENERAL_AI_QUERIES = [
    "artificial intelligence news",
    "AI breakthrough",
    "machine learning latest",
]


def fetch_google_news(topics: list, config: dict, api_key: str = "", model: str = "grok-4.3") -> list:
    """Fetch Google News RSS across all topics, LLM-score, return top 10.

    Only includes articles from the last 7 days.  If topic-specific queries
    yield fewer than 10 scored items, backfills with general AI news.
    """
    all_items = []
    seen_urls: set[str] = set()

    for topic in topics:
        query = f"{topic.display_name} AI"
        items = _fetch_google_news_topic(query, max_items=10, max_age_days=7)
        for item in items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                all_items.append(item)
        print(f"  [news/{topic.slug}] {len(items)} articles (last 7 days)")

    if not all_items:
        # Nothing from topics — try general queries directly
        for gq in _GENERAL_AI_QUERIES:
            items = _fetch_google_news_topic(gq, max_items=10, max_age_days=7)
            for item in items:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    all_items.append(item)
            print(f"  [news/general] {len(items)} articles for '{gq}'")
        if not all_items:
            return []

    print(f"  [news] Scoring {len(all_items)} articles via xAI API...")
    scored = _score_news_with_llm(all_items, api_key=api_key, model=model)

    # Backfill: if fewer than 10 scored items, fetch general AI news
    if len(scored) < 10:
        shortfall = 10 - len(scored)
        print(f"  [news] Only {len(scored)} topic items — backfilling {shortfall} from general AI news...")
        backfill_items = []
        for gq in _GENERAL_AI_QUERIES:
            items = _fetch_google_news_topic(gq, max_items=10, max_age_days=7)
            for item in items:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    backfill_items.append(item)
        if backfill_items:
            extra_scored = _score_news_with_llm(backfill_items, api_key=api_key, model=model)
            scored.extend(extra_scored[:shortfall])
            print(f"  [news] Backfilled {min(len(extra_scored), shortfall)} general AI articles")

    return scored[:10]


def render_daily_note(
    date_str: str,
    topic_results: list,
    synthesis: dict,
    config: dict,
    must_follow_results: list = None,
    prominent_results: list = None,
    news_items: list = None,
    feedback_summary: dict = None,
    feedback_analysis: dict = None,
    feedback_proposals: list[str] = None,
    tracker: TokenTracker | None = None,
    health_warnings: list[str] = None,
) -> str:
    """Render the full daily note markdown."""
    topic_slugs = [tr["topic"].slug for tr in topic_results]
    total_x = sum(len(tr["x_items"]) for tr in topic_results)

    # Count must-follow tweets
    mf_count = sum(len(r["items"]) for r in (must_follow_results or []))
    prom_count = len(prominent_results or [])
    news_count = len(news_items or [])

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

    # Lab Pulse also draws from must-follow results: the dedicated per-account
    # scan is the reliable source for lab posts — broad topic scans almost
    # never surface posts authored by the labs themselves (lab_pulse sat at 0
    # for months when topic scans were the only source).
    _lab_seen_urls = {getattr(item, 'url', '') for item, _, _ in lab_pulse_items}
    _mf_topic = SimpleNamespace(slug="must-follow", display_name="Must Follow")
    for r in (must_follow_results or []):
        group_key = (r.get("group") or "").strip().lower()
        if group_key not in LAB_GROUP_MAP:
            continue
        for item in r.get("items", []):
            url = getattr(item, 'url', '')
            if url and url in _lab_seen_urls:
                continue
            _lab_seen_urls.add(url)
            lab_pulse_items.append((item, _mf_topic, 'x'))

    # Highest engagement first — the render caps at 10 rows
    lab_pulse_items.sort(
        key=lambda t: (t[0].engagement.likes if t[0].engagement and t[0].engagement.likes else 0),
        reverse=True,
    )

    # Build frontmatter
    fm_lines = [
        "---",
        f"date: {date_str}",
        "type: daily-research",
        f"tags: [{', '.join(topic_slugs)}]",
        "status: unread",
        f"up: \"[[🤖 MOC - AI Agent Development]]\"",
        f"x_items: {total_x}",
        f"must_follow_tweets: {mf_count}",
        f"prominent_voices: {prom_count}",
        f"deep_dives: {len(deep_dives)}",
        f"lab_pulse: {len(lab_pulse_items)}",
        f"news_items: {news_count}",
    ]
    fm_lines.extend(["---", ""])

    lines = fm_lines + [
        f"# Daily Research — {_format_date(date_str)}",
        "",
    ]

    # Token / cost summary — right after the title
    if tracker and tracker.num_calls > 0:
        lines.extend(_render_cost_summary(tracker))

    # Pipeline health warnings (Level 3: drift detection), reconciled
    # against what THIS run actually produced
    if health_warnings:
        _today_counts = {
            "x_items": total_x,
            "must_follow_tweets": mf_count,
            "prominent_voices": prom_count,
            "deep_dives": len(deep_dives),
            "lab_pulse": len(lab_pulse_items),
        }
        _briefing = synthesis.get("briefing", "")
        _synth_ok = bool(_briefing) and "Synthesis failed" not in _briefing
        lines.extend(_render_health_warnings(health_warnings, _today_counts, _synth_ok))

    # Briefing — the POW moment (Level 1: omit section if synthesis failed)
    briefing = synthesis.get("briefing", "")
    if briefing and "Synthesis failed" not in briefing:
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
                        text_display = _oneline(text, 280)
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
            f"> High-engagement tweets ({config.get('prominent_ai_min_likes', 500)}+ likes) from prominent AI researchers, engineers, and executives.",
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
            text_short = _oneline(item.text, 280)
            lines.append(
                f"| @{item.author_handle} | {text_short} | {likes}\u2764\ufe0f | [→]({item.url}) |"
            )
        lines.append("")

    # News — top stories, deduplicated by story (one headline per event)
    if news_items:
        lines.extend([
            "## News \U0001f4f0",
            "",
        ])
        for i, item in enumerate(news_items[:10], 1):
            title = _oneline(item.get("title", ""), 0)
            source = _oneline(item.get("source", ""), 0)
            raw_date = item.get("pub_date", "")
            try:
                dt = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S %Z")
                pub_short = dt.strftime("%b %d")
            except ValueError:
                pub_short = raw_date[:12]
            url = item.get("url", "")
            also = item.get("also_covered_by", [])
            also_str = f" *(also: {', '.join(also[:3])})*" if also else ""
            lines.append(f"{i}. [{title}]({url}) — {source}, {pub_short}{also_str}")
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
                text_short = _oneline(item.text, 280)
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
            # Cap the link title — scan text can now run to 2000 chars
            title = _oneline(item.text, 200)
            lines.append(f"- [ ] [{title}]({item.url}) — @{item.author_handle} #{topic.slug}")
        lines.append("")

    # Unified research table: reading list + per-topic items merged
    topic_synths = {t.get("slug", ""): t for t in synthesis.get("topics", [])}

    # Topic synthesis summaries (compact)
    has_any_synth = False
    for tr in topic_results:
        topic = tr["topic"]
        synth = topic_synths.get(topic.slug, {})
        headline = synth.get("headline", "")
        key_points = synth.get("key_points", [])
        if headline or key_points:
            if not has_any_synth:
                lines.extend(["---", "", "## Topic Summaries", ""])
                has_any_synth = True
            if headline:
                lines.append(f"**{topic.display_name}** — {headline}")
            else:
                lines.append(f"**{topic.display_name}**")
            for kp in key_points:
                lines.append(f"- {kp}")
            lines.append("")

    # Build single merged table from all topic items, ranked by weighted score
    reading_list = _build_reading_list(topic_results, config)
    if reading_list:
        lines.extend([
            "---",
            "",
            "## Research Feed",
            "",
            "| # | Topic | Post | Author | Link |",
            "|---|-------|------|--------|------|",
        ])
        for i, item in enumerate(reading_list, 1):
            topic_tag = item['topic_slug']
            title = _oneline(item['title'], 0)
            author = item['summary']
            url = item['url']
            lines.append(
                f"| {i} | {topic_tag} | {title} | {author} | [→]({url}) |"
            )
        lines.append("")
    else:
        lines.extend(["*No new research results today.*", ""])

    # Footer — compact tag instructions
    lines.extend([
        "---",
        "",
        "> **Tags:** `#keep` → promote to Library | `#good <reason>` / `#bad <reason>` → feedback loop",
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

    # Efficiency recommendations — only render if there are actual issues
    if tracker and tracker.num_calls > 0:
        topic_count = len(topic_results)
        mf_count_accts = len(config.get("must_follow_accounts", []))
        recs = _render_efficiency_recommendations(
            tracker, config, topic_count, mf_count_accts,
        )
        # Only include if there are actual recommendations (not just "No issues")
        has_recs = any("**" in line for line in recs)
        if has_recs:
            lines.extend(["---", ""])
            lines.extend(recs)

    return "\n".join(lines)


def _build_reading_list(topic_results: list, config: dict) -> list:
    """Build a merged, ranked reading list across all topics."""
    max_items = config.get("reading_list_max", 15)
    all_items = []

    for tr in topic_results:
        topic = tr["topic"]
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


class _TeeStream(io.TextIOBase):
    """Mirror writes to the original stream and a log file.

    The scheduled task invokes run.py directly (bypassing run-scheduled.ps1),
    which left nightly runs with no log at all — errors like a failing scan
    vanished. This guarantees a per-run log regardless of how the script is
    launched. Log-file write errors are swallowed so logging can never break
    the pipeline itself.
    """

    def __init__(self, stream, logfile):
        self._stream = stream
        self._logfile = logfile

    def write(self, s):
        try:
            self._stream.write(s)
        except (UnicodeEncodeError, OSError):
            pass
        try:
            self._logfile.write(s)
        except (ValueError, OSError):
            pass
        return len(s)

    def flush(self):
        for f in (self._stream, self._logfile):
            try:
                f.flush()
            except (ValueError, OSError):
                pass


def _setup_run_logging() -> Path | None:
    """Tee stdout/stderr to logs/daily-research-<timestamp>.log; prune logs >30 days old."""
    logs_dir = SKILL_DIR / "logs"
    try:
        logs_dir.mkdir(exist_ok=True)
        for old in logs_dir.glob("daily-research-*.log"):
            age_days = (datetime.now() - datetime.fromtimestamp(old.stat().st_mtime)).days
            if age_days > 30:
                old.unlink()
        log_path = logs_dir / f"daily-research-{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.log"
        logfile = open(log_path, "w", encoding="utf-8", errors="replace")
    except OSError:
        return None
    sys.stdout = _TeeStream(sys.stdout, logfile)
    sys.stderr = _TeeStream(sys.stderr, logfile)
    return log_path


def main():
    parser = argparse.ArgumentParser(description="Daily research pipeline → Obsidian")
    parser.add_argument("--topic", help="Run only this topic slug (e.g., agents)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + score, print to stdout only")
    parser.add_argument("--promote-only", action="store_true", help="Only run #keep → Library pass")
    parser.add_argument("--show-dedup", action="store_true", help="Show all seen URLs from vault")
    parser.add_argument("--costs", action="store_true", help="Show estimated token costs after run")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--force-rerun", action="store_true", help="Ignore same-day note protection and rerun intentionally")
    parser.add_argument("--note-suffix", default="", help="Append a suffix to the output note filename (e.g. '_new' → 2026-04-20_new.md). Bypasses same-day protection.")
    parser.add_argument("--test-synth", action="store_true", help="Test synthesis with mock data and exit")
    args = parser.parse_args()

    log_path = _setup_run_logging()
    if log_path:
        print(f"[log] Run log: {log_path}")

    # --test-synth: call synthesize_all with mock data and exit
    if args.test_synth:
        from types import SimpleNamespace
        mock_item = SimpleNamespace(
            text="Anthropic released Claude 4 with 200K context and new tool use features today.",
            author_handle="AnthropicAI",
            engagement=SimpleNamespace(likes=1200),
            url="https://x.com/AnthropicAI/status/mock",
        )
        mock_topic = SimpleNamespace(slug="agents", display_name="AI Agents")
        mock_result = {"topic": mock_topic, "x_items": [mock_item]}
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"[test-synth] Calling synthesize_all with mock data...")
        result = synthesize_all([mock_result], today, today)
        if "error" in result:
            print(f"[test-synth] FAILED: {result['error']}")
        else:
            print(f"[test-synth] SUCCESS")
            print(f"  POW: {result.get('briefing', '')[:120]}...")
            print(f"  lab_pulse: {result.get('lab_pulse_summary', '')[:80]}...")
            topics = result.get("topics", [])
            print(f"  topics: {len(topics)} returned")
        return

    # Load config
    config = load_config()
    today = datetime.now().strftime("%Y-%m-%d")
    note_date_key = today + args.note_suffix  # used for filename; today kept for dedup/date logic

    # --show-dedup: just dump URLs and exit
    if args.show_dedup:
        seen = vault.load_seen_urls(config)
        print(f"Seen URLs in vault: {len(seen)}")
        for url in sorted(seen):
            print(f"  {url}")
        return

    # --promote-only: just run promotion pass and exit
    if args.promote_only:
        from vendor.last30days import env as l30_env
        l30_config = l30_env.get_config()

        promoted = promote.promote_items(
            config, dry_run=args.dry_run,
        )
        if promoted:
            print(f"Promoted {len(promoted)} items to Library:")
            for item in promoted:
                path = item.get('library_path', item['topic_slug'])
                print(f"  [{item['topic_slug']}] {item['title']} -> {path}")
        else:
            print("No #keep items found to promote.")
        return

    # Enable debug
    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"

    if not args.dry_run and not args.force_rerun and not args.note_suffix and vault.daily_exists(config, today):
        print(f"[skip] Daily research note already exists for {today}. Use --force-rerun to run again intentionally.")
        return

    # Run promote pass first (tag-to-library for previous dailies)
    from vendor.last30days import env as l30_env
    l30_config = l30_env.get_config()

    promoted = promote.promote_items(config)
    if promoted:
        print(f"[promote] Moved {len(promoted)} items to Library")

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

    if not l30_config.get("XAI_API_KEY"):
        print("Error: No XAI_API_KEY found. Set it in ~/.config/last30days/.env", file=sys.stderr)
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

    # Prominent voices: last 48 hours — a 24h window plus vault dedup starved
    # the section (viral tweets found yesterday get deduped, and too few new
    # ones cross the like floor within a single day). Dedup handles repeats.
    prom_from_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    # Select models (reuse last30days model selection with caching)
    from vendor.last30days import models as l30_models
    selected_models = l30_models.get_models(l30_config)

    # Auto-resolve xAI model: check API for latest available
    configured_xai = l30_config.get("xai_model") or config.get("xai_model", "grok-4-1-fast")
    if configured_xai == "auto":
        configured_xai = "grok-4-1-fast"  # default seed for auto-resolution
    resolved_xai = resolve_xai_model(l30_config["XAI_API_KEY"], configured_xai)
    if resolved_xai != configured_xai:
        print(f"[model] xAI model resolved: {configured_xai} → {resolved_xai}")
    l30_config["xai_model"] = resolved_xai

    # Level 4: Auto-repair config if model changed
    auto_repair_config(config, resolved_xai)

    # Level 3: Detect cross-day metric drift
    print("[health] Checking recent daily notes for drift...")
    health_warnings = detect_drift(config)
    if health_warnings:
        print(f"[health] Detected {len(health_warnings)} issue(s) in recent notes (reconciled against today's results in the note):")
        for w in health_warnings:
            print(f"  ⚠ {w['message']}")
    else:
        print("[health] All metrics healthy")

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
        x_count = len(result["x_items"])
        print(f"-> {x_count}X items (new)")
        topic_results.append(result)
        total_errors.extend(result["errors"])

        # Add found URLs to seen set to dedup across topics
        for item in result["x_items"]:
            seen_urls.add(item.url)

    # Show errors if any
    if total_errors:
        print(f"\n[warn] {len(total_errors)} errors during scan:")
        for err in total_errors:
            print(f"  ! {err}")

    # Level 1: Resilient step execution — each step recovers independently

    # Must-follow account scan (hybrid batch/solo, no quality filters)
    must_follow_results = []
    mf_accounts = config.get("must_follow_accounts", [])
    if mf_accounts and l30_config.get("XAI_API_KEY"):
        n_batch = sum(1 for a in mf_accounts if not a.get("solo"))
        n_solo = sum(1 for a in mf_accounts if a.get("solo"))
        n_calls = (1 if n_batch else 0) + n_solo
        print(f"\n[must-follow] Scanning {len(mf_accounts)} accounts ({n_batch} batch + {n_solo} solo = {n_calls} calls) | last 24h ({mf_from_date} -> {to_date})...")
        try:
            must_follow_results = run_must_follow_scan(
                config, l30_config, mf_from_date, to_date,
                tracker=tracker,
            )
            mf_total = sum(len(r["items"]) for r in must_follow_results)
            print(f"[must-follow] Captured {mf_total} tweets from {len(mf_accounts)} accounts")
        except Exception as e:
            print(f"[heal] Must-follow scan failed ({e}) — continuing without it")

    # Prominent AI voices scan (single broad search, engagement floor from config)
    prominent_results = []
    if l30_config.get("XAI_API_KEY"):
        print(f"\n[prominent-ai] Scanning for high-engagement AI voices | last 48h ({prom_from_date} -> {to_date})...")
        try:
            prominent_results = run_prominent_ai_scan(
                config, l30_config, prom_from_date, to_date,
                seen_urls,
                tracker=tracker,
            )
            # Add to seen_urls so synthesis doesn't double-count
            for item in prominent_results:
                seen_urls.add(item.url)
        except Exception as e:
            print(f"[heal] Prominent AI scan failed ({e}) — continuing without it")

    # Google News RSS — top 10 LLM-scored articles across all topics
    print(f"\n[news] Fetching Google News RSS for {len(all_topics)} topics...")
    try:
        news_items = fetch_google_news(all_topics, config, api_key=l30_config["XAI_API_KEY"], model=resolved_xai)
        print(f"[news] Selected {len(news_items)} articles")
    except Exception as e:
        news_items = []
        print(f"[heal] News fetch failed ({e}) — continuing without news")

    # Synthesize (single batched Claude CLI call — uses Max account, no API key)
    synthesis = {}
    total_items = sum(len(tr["x_items"]) for tr in topic_results)
    if total_items > 0:
        print(f"\n[synth] Synthesizing {total_items} items across {len(all_topics)} topics via xAI API ({resolved_xai})...")
        synthesis = synthesize_all(
            topic_results,
            from_date,
            to_date,
            tracker=tracker,
            api_key=l30_config["XAI_API_KEY"],
            model=resolved_xai,
        )
        if synthesis.get("briefing"):
            print(f"[synth] Briefing: {synthesis['briefing'][:120]}...")
        if synthesis.get("error"):
            print(f"[synth] Error: {synthesis['error']}", file=sys.stderr)
    else:
        print("\n[synth] No new items to synthesize")
        synthesis = {"briefing": "No new research results today.", "topics": []}

    # Render daily note
    note_content = render_daily_note(
        today, topic_results, synthesis, config,
        must_follow_results=must_follow_results,
        prominent_results=prominent_results,
        news_items=news_items,
        feedback_summary=feedback_summary,
        feedback_analysis=feedback_analysis,
        feedback_proposals=feedback_proposals,
        tracker=tracker,
        health_warnings=health_warnings,
    )

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - would write this to vault:")
        print("=" * 60)
        print(note_content)
        return

    # Write to vault via Obsidian CLI
    filepath = vault.write_daily_note(config, note_date_key, note_content, overwrite=args.force_rerun)
    print(f"\n[vault] Written -> {filepath}")

    # Level 2: Post-write validation — check note quality and attempt repair
    validation_issues = validate_note(note_content)
    if validation_issues:
        print(f"\n[validate] Issues detected: {validation_issues}")
        repaired = False
        # Attempt repair: re-run synthesis if POW failed
        if "pow_failed" in validation_issues and total_items > 0:
            print("[validate] Attempting synthesis repair with fallback model...")
            # Try a different model variant
            fallback_models = ["grok-4.20-0309-non-reasoning", "grok-4.3", resolved_xai]
            # Remove the model we already tried
            fallback_models = [m for m in fallback_models if m != resolved_xai]
            for fb_model in fallback_models[:2]:
                print(f"[validate] Trying fallback model: {fb_model}")
                repair_synth = synthesize_all(
                    topic_results, from_date, to_date,
                    tracker=tracker,
                    api_key=l30_config["XAI_API_KEY"],
                    model=fb_model,
                )
                if repair_synth.get("briefing") and "Synthesis failed" not in repair_synth.get("briefing", ""):
                    print(f"[validate] Synthesis repaired with {fb_model}")
                    synthesis = repair_synth
                    note_content = render_daily_note(
                        today, topic_results, synthesis, config,
                        must_follow_results=must_follow_results,
                        prominent_results=prominent_results,
                        news_items=news_items,
                        feedback_summary=feedback_summary,
                        feedback_analysis=feedback_analysis,
                        feedback_proposals=feedback_proposals,
                        tracker=tracker,
                        health_warnings=health_warnings,
                    )
                    filepath = vault.write_daily_note(config, note_date_key, note_content, overwrite=True)
                    print(f"[validate] Repaired note written -> {filepath}")
                    repaired = True
                    break
            if not repaired:
                print("[validate] All fallback models failed — note shipped without POW")
    else:
        print("[validate] Note passed all quality checks")

    # Cost summary (always print — replaces old --costs heuristic)
    ts = tracker.summary_dict()
    total_cost = ts.get("cost_usd") or ts.get("estimated_cost_usd", 0)
    cost_tag = "" if "cost_usd" in ts else "~"
    print(f"\n[tokens] {ts['api_calls']} API calls | {ts['total_tokens']:,} tokens | {cost_tag}${total_cost:.4f}")
    for model, data in tracker.by_model().items():
        tag = "" if data["has_exact"] else "~"
        print(f"  {model}: {data['calls']}× | {data['total']:,} tokens | {tag}${data['cost']:.4f}")

    # Final summary
    total_x = sum(len(tr["x_items"]) for tr in topic_results)
    mf_total = sum(len(r["items"]) for r in must_follow_results)
    prom_total = len(prominent_results)
    news_total = len(news_items)
    print(f"\nDone! {total_x}X + {mf_total}MF + {prom_total}PA + {news_total}News items across {len(all_topics)} topics.")


if __name__ == "__main__":
    main()
