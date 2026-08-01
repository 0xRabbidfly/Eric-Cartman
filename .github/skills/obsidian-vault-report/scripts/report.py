#!/usr/bin/env python3
"""Obsidian Vault Report Generator.

Searches the Obsidian vault corpus for notes matching a research query,
synthesizes them via xAI API, and writes a structured report to
Research/Reports/.

Usage:
    python report.py "What does our vault say about SDLC transformation?"
    python report.py --query "contradictions about agent architecture" --focus contradictions
    python report.py --query "..." --status draft
    python report.py --query "..." --status published

Zero pip dependencies — stdlib only + xAI Chat API.
"""

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Force UTF-8 on Windows
if sys.platform == "win32":
    for _s in ("stdin", "stdout", "stderr"):
        _stream = getattr(sys, _s)
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
        elif hasattr(_stream, "buffer"):
            setattr(
                sys, _s,
                io.TextIOWrapper(
                    _stream.buffer, encoding="utf-8", errors="replace",
                ),
            )

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

XAI_CHAT_URL = "https://api.x.ai/v1/chat/completions"
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4.5")
DEBUG = os.environ.get("VAULT_REPORT_DEBUG", "").lower() in (
    "1", "true", "yes",
)

SEARCH_DIRS = ["Research/Library", "Research/Dailies", "Podcasts"]
REPORTS_DIR = "Research/Reports"
MOC_PATH = "Research/Library/00 MOC/\U0001f5fa️ MOC - Research Library.md"


def _log(msg: str):
    if DEBUG:
        sys.stderr.write(f"[vault-report] {msg}\n")
        sys.stderr.flush()


def _log_error(msg: str):
    sys.stderr.write(f"[vault-report ERROR] {msg}\n")
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------


def _load_env_file(path: Path) -> Dict[str, str]:
    """Load key=value pairs from a dotenv file."""
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if (
                    value
                    and value[0] in ('"', "'")
                    and value[-1] == value[0]
                ):
                    value = value[1:-1]
                if key and value:
                    env[key] = value
    return env


def _get_xai_key() -> Optional[str]:
    """Resolve XAI_API_KEY from env -> repo .env -> ~/.config/last30days/.env."""
    key = os.environ.get("XAI_API_KEY")
    if key:
        return key
    script_dir = Path(__file__).resolve().parent
    for parent in [script_dir] + list(script_dir.parents):
        env_path = parent / ".env"
        if env_path.exists():
            env = _load_env_file(env_path)
            if env.get("XAI_API_KEY"):
                return env["XAI_API_KEY"]
    config_env = Path.home() / ".config" / "last30days" / ".env"
    env = _load_env_file(config_env)
    return env.get("XAI_API_KEY")


# ---------------------------------------------------------------------------
# Vault path resolution
# ---------------------------------------------------------------------------


def _resolve_vault_path() -> Path:
    """Locate the Obsidian vault folder on disk.

    Resolution order:
    1. OBSIDIAN_VAULT_PATH / VAULT_PATH env var
    2. Obsidian's own obsidian.json config registry
    3. Hardcoded default
    """
    env = os.environ.get("OBSIDIAN_VAULT_PATH") or os.environ.get("VAULT_PATH")
    if env and Path(env).is_dir():
        return Path(env)

    cfg_dirs: List[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        cfg_dirs.append(Path(appdata) / "obsidian")
    home = Path.home()
    cfg_dirs.append(home / "Library" / "Application Support" / "obsidian")
    cfg_dirs.append(home / ".config" / "obsidian")

    for cfg_dir in cfg_dirs:
        cfg = cfg_dir / "obsidian.json"
        if not cfg.exists():
            continue
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        rows: List[Tuple[bool, int, Path]] = []
        for meta in (data.get("vaults") or {}).values():
            p = meta.get("path")
            if p and Path(p).is_dir():
                rows.append(
                    (bool(meta.get("open")), meta.get("ts", 0), Path(p))
                )
        if not rows:
            continue
        rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
        return rows[0][2]

    default = Path(r"C:\Users\nuno_\Documents\Obsidian Vault")
    if default.is_dir():
        return default

    raise FileNotFoundError(
        "Obsidian vault not found. Set OBSIDIAN_VAULT_PATH or VAULT_PATH env var."
    )


# ---------------------------------------------------------------------------
# HTTP helper (stdlib only)
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_DELAY = 1.0


class HTTPError(Exception):
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        body: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _http_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = 120,
    retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    """Make an HTTP request and return parsed JSON."""
    headers = headers or {}
    headers.setdefault("User-Agent", "obsidian-vault-report/1.0")

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
                resp_body = resp.read().decode("utf-8")
                _log(f"Response: {resp.status} ({len(resp_body)} bytes)")
                return json.loads(resp_body) if resp_body else {}
        except urllib.error.HTTPError as e:
            err_body = None
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            _log(f"HTTP {e.code}: {e.reason}")
            last_error = HTTPError(
                f"HTTP {e.code}: {e.reason}", e.code, err_body,
            )
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
            last_error = HTTPError(
                f"Connection error: {type(e).__name__}: {e}",
            )
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

    if last_error:
        raise last_error
    raise HTTPError("Request failed with no error details")


# ---------------------------------------------------------------------------
# xAI Chat API
# ---------------------------------------------------------------------------


def _call_xai_chat(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str:
    """Call xAI Chat Completions API and return the assistant message text."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": XAI_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "reasoning_effort": "high",
    }
    resp = _http_request("POST", XAI_CHAT_URL, headers=headers, json_data=payload)

    choices = resp.get("choices", [])
    if not choices:
        raise HTTPError("No choices in xAI response")
    return choices[0].get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Vault search (filesystem-based)
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80]


def _extract_frontmatter(content: str) -> Dict[str, Any]:
    """Extract YAML frontmatter from a markdown file as a dict."""
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    # Simple YAML-ish parser (no PyYAML dependency)
    result: Dict[str, Any] = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                items = [
                    v.strip().strip("\"'")
                    for v in val[1:-1].split(",")
                    if v.strip()
                ]
                result[key] = items
            elif val.startswith("- "):
                result.setdefault(key, []).append(val[2:].strip())
            else:
                result[key] = val.strip("\"'")
        elif line.startswith("- ") and result:
            last_key = list(result.keys())[-1]
            if isinstance(result[last_key], list):
                result[last_key].append(line[2:].strip())
    return result


def _extract_body(content: str) -> str:
    """Extract the body text (everything after frontmatter)."""
    if not content.startswith("---"):
        return content
    end = content.find("\n---", 3)
    if end == -1:
        return content
    body_start = content.find("\n", end + 1)
    if body_start == -1:
        return ""
    return content[body_start:].strip()


def _note_slug(filepath: Path) -> str:
    """Get the wikilink-ready slug from a filepath (stem without extension)."""
    return filepath.stem


def _score_match(
    query_terms: List[str], title: str, tags: List[str], body: str,
) -> float:
    """Score how well a note matches the query. Higher = better match."""
    title_lower = title.lower()
    body_lower = body.lower()
    tags_lower = " ".join(t.lower() for t in tags)
    score = 0.0

    for term in query_terms:
        term_lower = term.lower()
        # Title match (highest weight)
        if term_lower in title_lower:
            score += 3.0
        # Tag match
        if term_lower in tags_lower:
            score += 2.0
        # Body match -- count occurrences, cap at 5
        count = body_lower.count(term_lower)
        score += min(count, 5) * 0.5

    # Bonus for multi-term matches (more terms matched = more relevant)
    terms_found = sum(
        1
        for t in query_terms
        if t.lower() in f"{title_lower} {tags_lower} {body_lower}"
    )
    if len(query_terms) > 1 and terms_found > 1:
        score += terms_found * 1.5

    return score


def search_vault(
    vault_path: Path,
    query: str,
    max_results: int = 30,
) -> List[Dict[str, Any]]:
    """Search the vault for notes matching the query.

    Uses filesystem glob + regex matching on titles, tags, and body text.
    Returns a list of dicts with keys: path, slug, title, tags, score, content, folder.
    """
    # Build search terms from the query -- remove common stop words
    stop_words = {
        "what", "does", "our", "vault", "say", "about", "the", "a", "an", "is",
        "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
        "did", "will", "would", "could", "should", "may", "might", "shall",
        "can", "need", "dare", "ought", "used", "to", "of", "in", "for", "on",
        "with", "at", "by", "from", "as", "into", "through", "during", "before",
        "after", "above", "below", "between", "out", "off", "over", "under",
        "again", "further", "then", "once", "here", "there", "when", "where",
        "why", "how", "all", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "no", "nor", "not", "only", "own", "same",
        "so", "than", "too", "very", "and", "but", "or", "if", "while",
        "find", "contradictions", "write", "report", "synthesize", "strategy",
    }
    raw_terms = re.findall(r"\w+", query.lower())
    query_terms = [t for t in raw_terms if t not in stop_words and len(t) > 2]

    # Also keep multi-word phrases from the query (bigrams)
    if len(raw_terms) >= 2:
        for i in range(len(raw_terms) - 1):
            bigram = f"{raw_terms[i]} {raw_terms[i + 1]}"
            if raw_terms[i] not in stop_words or raw_terms[i + 1] not in stop_words:
                query_terms.append(bigram)

    if not query_terms:
        _log_error(f"No meaningful search terms extracted from query: {query}")
        return []

    _log(f"Search terms: {query_terms}")

    results: List[Dict[str, Any]] = []
    searched = 0
    skipped_dirs = {".trash", ".obsidian", ".git", "node_modules", "__pycache__"}

    for search_dir_name in SEARCH_DIRS:
        search_dir = vault_path / search_dir_name
        if not search_dir.is_dir():
            _log(f"Search dir not found: {search_dir}")
            continue

        for md_file in search_dir.rglob("*.md"):
            # Skip hidden/system directories
            if any(part in skipped_dirs for part in md_file.parts):
                continue
            # Skip MOC files (they're indexes, not source material)
            if "MOC" in md_file.name and md_file.name.startswith(
                ("\U0001f4cd", "\U0001f5fa")
            ):
                continue

            searched += 1
            try:
                content = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            fm = _extract_frontmatter(content)
            body = _extract_body(content)
            title = md_file.stem
            tags = fm.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]

            score = _score_match(query_terms, title, tags, body)
            if score > 0:
                # Determine which search dir this came from
                try:
                    rel = md_file.relative_to(vault_path)
                    folder = str(rel.parent).replace("\\", "/")
                except ValueError:
                    folder = "unknown"

                results.append({
                    "path": str(md_file),
                    "rel_path": str(md_file.relative_to(vault_path)).replace("\\", "/"),
                    "slug": _note_slug(md_file),
                    "title": title,
                    "tags": tags,
                    "score": score,
                    "content": content,
                    "body": body[:6000],  # Cap body for API context
                    "folder": folder,
                    "frontmatter": fm,
                })

    _log(f"Searched {searched} files, found {len(results)} matches")

    # Sort by score descending, return top N
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results]


# ---------------------------------------------------------------------------
# Synthesis prompt
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = (
    "You are a research analyst synthesizing knowledge from an Obsidian "
    "vault corpus. Your task is to create a structured, analytical report "
    "that goes BEYOND summarizing individual notes -- you must connect "
    "ideas across sources, identify patterns, surface contradictions, and "
    "provide original analytical perspective.\n\n"
    "Rules:\n"
    "- Be ANALYTICAL, not summarative. Add perspective the individual "
    "notes don't have.\n"
    "- Every claim must reference its source note using [[wikilink]] format.\n"
    "- Contradictions are valuable -- surface them prominently.\n"
    "- Knowledge gaps are valuable -- they tell the reader what to research next.\n"
    "- The executive summary should be standalone -- readable without the full report.\n"
    "- Use specific quotes, numbers, and data points from the source notes.\n"
    "- Group findings by theme, not by source note.\n"
    "- Output in markdown format matching the template provided."
)

SYNTHESIS_USER_PROMPT = """## Research Question

{query}

## Focus Mode

{focus_description}

## Source Notes ({source_count} matched from vault)

{source_summaries}

## Instructions

Write a structured research report answering the research question above.
Use ONLY information from the source notes provided. Follow this exact structure:

### Executive Summary
3-5 sentences synthesizing the key findings.
This should be standalone -- readable without the full report.

### Key Findings
Numbered list of 5-8 key findings.
Each must reference its source note with [[wikilink-slug]].

### Analysis
Group findings into 2-4 thematic sections. Each section should:
- Have a descriptive heading
- Connect multiple source notes
- Provide analytical perspective beyond what any single note says
- Use [[wikilinks]] for every claim

### Contradictions & Open Questions
List any contradictions between source notes, and open questions
the vault hasn't answered yet.

### Recommendations
3-5 actionable recommendations based on the analysis.

### Knowledge Gaps
What the vault does NOT cover that would strengthen this analysis.
Be specific about what research would fill these gaps.

### Sources Table
A markdown table with columns: Note (as [[wikilink]]), Section, Key Claim.
Include every source note that contributed to the report.

Output the report body ONLY (no frontmatter -- that will be added separately).
Start with the Executive Summary heading."""

FOCUS_DESCRIPTIONS = {
    "full": (
        "Full synthesis -- connect, analyze, and distill all relevant knowledge."
    ),
    "contradictions": (
        "Contradiction-focused analysis -- prioritize conflicting claims, "
        "competing frameworks, and unresolved tensions between sources."
    ),
    "quick": (
        "Quick synthesis -- lighter analysis, focus on the top findings "
        "and executive summary."
    ),
    "strategy": (
        "Strategy-focused synthesis -- emphasize actionable recommendations, "
        "competitive implications, and decision frameworks."
    ),
}


def _build_source_summaries(notes: List[Dict[str, Any]]) -> str:
    """Build the source summaries block for the synthesis prompt."""
    parts = []
    for i, note in enumerate(notes, 1):
        tags_str = ", ".join(note["tags"]) if note["tags"] else "none"
        body_preview = note["body"][:4000]  # Cap per-note to keep within context
        parts.append(
            f"### Source {i}: [[{note['slug']}]]\n"
            f"**File:** {note['rel_path']}\n"
            f"**Tags:** {tags_str}\n"
            f"**Match Score:** {note['score']:.1f}\n\n"
            f"{body_preview}\n"
        )
    return "\n---\n\n".join(parts)


def synthesize_report(
    api_key: str,
    query: str,
    notes: List[Dict[str, Any]],
    focus: str = "full",
) -> str:
    """Call xAI to synthesize the report body from matched notes."""
    focus_desc = FOCUS_DESCRIPTIONS.get(focus, FOCUS_DESCRIPTIONS["full"])
    source_summaries = _build_source_summaries(notes)

    user_prompt = SYNTHESIS_USER_PROMPT.format(
        query=query,
        focus_description=focus_desc,
        source_count=len(notes),
        source_summaries=source_summaries,
    )

    _log(f"Calling xAI for synthesis ({len(notes)} sources, focus={focus})")
    _log(f"User prompt length: {len(user_prompt)} chars")

    return _call_xai_chat(
        api_key=api_key,
        system_prompt=SYNTHESIS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,
    )


# ---------------------------------------------------------------------------
# Report rendering & writing
# ---------------------------------------------------------------------------


def _build_frontmatter(
    query: str,
    source_count: int,
    status: str,
    topic_tags: List[str],
) -> str:
    """Build YAML frontmatter for the report."""
    now = datetime.now(timezone.utc)
    tags_list = ["report"] + topic_tags
    tags_yaml = "\n".join(f"  - {t}" for t in tags_list)

    return (
        f"---\n"
        f"type: report\n"
        f"status: {status}\n"
        f"tags:\n{tags_yaml}\n"
        f"created: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"sources: {source_count}\n"
        f'query: "{query}"\n'
        f"source-skill: obsidian-vault-report\n"
        f"---\n"
    )


def _extract_topic_tags(query: str, notes: List[Dict[str, Any]]) -> List[str]:
    """Extract topic tags from the query and top-scoring notes."""
    tag_counts: Dict[str, int] = {}
    for note in notes[:5]:
        for tag in note.get("tags", []):
            tag = tag.strip().lower()
            if tag and tag not in ("report", "moc", "research"):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    common_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    result = [t for t, c in common_tags if c >= 2]
    if len(result) < 3:
        for t, _ in common_tags:
            if t not in result:
                result.append(t)
            if len(result) >= 3:
                break
    return result[:5]


def _build_header(query: str, source_count: int) -> str:
    """Build the report header block (below frontmatter, above synthesis body)."""
    now = datetime.now(timezone.utc)
    title = _query_to_title(query)
    return (
        f"# {title}\n\n"
        f"**Query:** {query}\n"
        f"**Sources:** {source_count} vault notes analyzed\n"
        f"**Date:** {now.strftime('%Y-%m-%d')}\n\n"
        f"---\n\n"
    )


def _query_to_title(query: str) -> str:
    """Convert a research query into a report title."""
    title = query.strip().rstrip("?")
    for prefix in [
        "what does our vault say about",
        "what do we know about",
        "synthesize findings about",
        "write a report on",
        "research paper on",
        "strategy paper on",
        "strategy doc on",
    ]:
        if title.lower().startswith(prefix):
            title = title[len(prefix):].strip()
            break
    return title.title() if title else "Vault Report"


def write_report(
    vault_path: Path,
    query: str,
    report_body: str,
    source_count: int,
    notes: List[Dict[str, Any]],
    status: str = "draft",
    slug_override: Optional[str] = None,
) -> Path:
    """Write the report to Research/Reports/ and return the file path."""
    slug = slug_override or _slugify(_query_to_title(query))
    if not slug:
        slug = _slugify(query)

    reports_dir = vault_path / REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)

    filepath = reports_dir / f"{slug}.md"

    topic_tags = _extract_topic_tags(query, notes)
    frontmatter = _build_frontmatter(query, source_count, status, topic_tags)
    header = _build_header(query, source_count)

    full_content = frontmatter + "\n" + header + report_body

    filepath.write_text(full_content, encoding="utf-8")
    _log(f"Report written to: {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# MOC registration
# ---------------------------------------------------------------------------


def update_moc(
    vault_path: Path, report_slug: str, report_title: str, query: str,
) -> bool:
    """Add the report to the Master MOC's Reports section.

    Looks for a ## Reports section. If it doesn't exist, creates one at the end.
    Adds a wikilink entry for the new report.
    Returns True if the MOC was updated, False on error.
    """
    moc_path = vault_path / MOC_PATH
    if not moc_path.exists():
        _log(f"MOC not found at {moc_path}, skipping registration")
        return False

    try:
        content = moc_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        _log_error(f"Failed to read MOC: {e}")
        return False

    entry = f"- [[{report_slug}|{report_title}]] — {query}\n"

    # Check if already registered
    if f"[[{report_slug}" in content:
        _log(f"Report already in MOC: {report_slug}")
        return True

    # Find ## Reports section
    reports_section = re.search(r"^## Reports\s*\n", content, re.MULTILINE)
    if reports_section:
        insert_pos = reports_section.end()
        new_content = content[:insert_pos] + entry + content[insert_pos:]
    else:
        new_content = content.rstrip() + "\n\n## Reports\n\n" + entry

    try:
        moc_path.write_text(new_content, encoding="utf-8")
        _log(f"Registered report in MOC: {report_slug}")
        return True
    except OSError as e:
        _log_error(f"Failed to update MOC: {e}")
        return False


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthesis reports from the Obsidian vault corpus.",
        epilog=(
            "Examples:\n"
            '  python report.py "What does our vault say about SDLC transformation?"\n'
            '  python report.py --query "agent architecture" --focus contradictions\n'
            '  python report.py --query "harness engineering" --status published\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query_positional", nargs="?", help="Research question (positional)",
    )
    parser.add_argument("--query", "-q", help="Research question (named)")
    parser.add_argument(
        "--focus", "-f",
        choices=["full", "contradictions", "quick", "strategy"],
        default="full",
        help="Analysis focus mode (default: full)",
    )
    parser.add_argument(
        "--status", "-s",
        choices=["draft", "published"],
        default="draft",
        help="Report status (default: draft)",
    )
    parser.add_argument("--slug", help="Override the report filename slug")
    parser.add_argument("--thesis-id", help="Thesis ID from thesis tracker (for provenance tracking)")
    parser.add_argument(
        "--max-sources", type=int, default=20,
        help="Maximum source notes to include (default: 20)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Search only -- show matching notes without generating a report",
    )
    parser.add_argument(
        "--emit",
        choices=["path", "json", "md"],
        default="path",
        help="Output mode: path (filepath only), json (full metadata), md (report content)",
    )

    args = parser.parse_args()

    # Resolve the query
    query = args.query or args.query_positional
    if not query:
        parser.error("A research question is required (positional arg or --query)")

    # Resolve vault path
    try:
        vault_path = _resolve_vault_path()
    except FileNotFoundError as e:
        _log_error(str(e))
        sys.exit(1)

    _log(f"Vault path: {vault_path}")
    print(f"[vault-report] Searching vault: {vault_path}", file=sys.stderr)

    # --- SEARCH ---
    notes = search_vault(vault_path, query, max_results=args.max_sources)
    if not notes:
        _log_error(f"No matching notes found for query: {query}")
        print(json.dumps({"error": "No matching notes found", "query": query}))
        sys.exit(1)

    print(f"[vault-report] Found {len(notes)} matching notes", file=sys.stderr)
    for n in notes[:5]:
        print(f"  [{n['score']:.1f}] {n['slug']} ({n['folder']})", file=sys.stderr)
    if len(notes) > 5:
        print(f"  ... and {len(notes) - 5} more", file=sys.stderr)

    # --- DRY RUN ---
    if args.dry_run:
        result = {
            "query": query,
            "matches": [
                {
                    "slug": n["slug"],
                    "score": n["score"],
                    "folder": n["folder"],
                    "tags": n["tags"],
                }
                for n in notes
            ],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    # --- RESOLVE API KEY ---
    api_key = _get_xai_key()
    if not api_key:
        _log_error(
            "XAI_API_KEY not found. Set it in environment, .env file, "
            "or ~/.config/last30days/.env"
        )
        sys.exit(1)

    # --- SYNTHESIZE ---
    print(
        f"[vault-report] Synthesizing report (focus={args.focus})...",
        file=sys.stderr,
    )
    try:
        report_body = synthesize_report(
            api_key=api_key,
            query=query,
            notes=notes,
            focus=args.focus,
        )
    except HTTPError as e:
        _log_error(f"xAI API error: {e}")
        if e.body:
            _log_error(f"Response body: {e.body[:500]}")
        sys.exit(1)

    if not report_body or len(report_body.strip()) < 100:
        _log_error("Synthesis returned empty or too-short report")
        sys.exit(1)

    # --- WRITE ---
    print("[vault-report] Writing report...", file=sys.stderr)
    report_path = write_report(
        vault_path=vault_path,
        query=query,
        report_body=report_body,
        source_count=len(notes),
        notes=notes,
        status=args.status,
        slug_override=args.slug,
    )

    # --- REGISTER in MOC ---
    title = _query_to_title(query)
    slug = report_path.stem
    moc_ok = update_moc(vault_path, slug, title, query)
    if moc_ok:
        print("[vault-report] Registered in Master MOC", file=sys.stderr)
    else:
        print("[vault-report] MOC registration skipped or failed", file=sys.stderr)

    # --- OUTPUT ---
    if args.emit == "path":
        print(str(report_path))
    elif args.emit == "json":
        result = {
            "path": str(report_path),
            "slug": slug,
            "title": title,
            "query": query,
            "status": args.status,
            "focus": args.focus,
            "source_count": len(notes),
            "moc_registered": moc_ok,
            "sources": [
                {"slug": n["slug"], "score": n["score"], "folder": n["folder"]}
                for n in notes
            ],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.emit == "md":
        print(report_path.read_text(encoding="utf-8"))

    print(f"[vault-report] Done: {report_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
