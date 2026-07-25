#!/usr/bin/env python3
"""
Obsidian Connection Detector

Detects and classifies relationships between vault notes using xAI API.
Outputs to Research/connections.json inside the vault.
"""

import argparse
import glob
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_PATH = Path(r"C:\Users\nuno_\Documents\Obsidian Vault")
LIBRARY_DIR = VAULT_PATH / "Research" / "Library"
PODCASTS_DIR = VAULT_PATH / "Podcasts"
CONNECTIONS_FILE = VAULT_PATH / "Research" / "connections.json"
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
MODEL = "grok-4.3"
CONFIDENCE_THRESHOLD = 0.6


# ---------------------------------------------------------------------------
# API Key loading
# ---------------------------------------------------------------------------

def load_api_key() -> str:
    """Load xAI API key from environment or .env file."""
    key = os.environ.get("XAI_API_KEY")
    if key:
        return key

    env_file = Path.home() / ".config" / "last30days" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("XAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")

    print("ERROR: XAI_API_KEY not found in environment or ~/.config/last30days/.env")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Note parsing helpers
# ---------------------------------------------------------------------------

def strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter delimited by ---."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].strip()
    return text


def extract_frontmatter(text: str) -> dict:
    """Extract YAML-like frontmatter as a simple key-value dict."""
    meta: dict = {"tags": []}
    if not text.startswith("---"):
        return meta
    end = text.find("---", 3)
    if end == -1:
        return meta
    block = text[3:end].strip()
    for line in block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if k == "tags":
                # tags may be inline comma-separated or YAML list on next lines
                if v:
                    meta["tags"] = [t.strip().strip("#") for t in v.split(",") if t.strip()]
            else:
                meta[k] = v
        elif line.strip().startswith("- ") and meta.get("tags") is not None:
            meta["tags"].append(line.strip()[2:].strip().strip("#"))
    return meta


def extract_title(text: str) -> str:
    """Extract the first H1 heading or fall back to first line."""
    body = strip_frontmatter(text)
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    # Fallback: first non-empty line
    for line in body.splitlines():
        if line.strip():
            return line.strip()[:120]
    return "(untitled)"


def extract_key_claims(text: str, max_chars: int = 500) -> str:
    """Extract key claims: first 500 chars of each Key Ideas item, or first paragraphs."""
    body = strip_frontmatter(text)

    # Try to find a "Key Ideas" or "Key Takeaways" section
    key_section_pattern = re.compile(
        r"^##\s+(Key Ideas|Key Takeaways|Main Points|Summary)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = key_section_pattern.search(body)
    if match:
        section_start = match.end()
        # Read until next heading
        next_heading = re.search(r"^##\s+", body[section_start:], re.MULTILINE)
        section_end = section_start + next_heading.start() if next_heading else len(body)
        section = body[section_start:section_end].strip()
        return section[:max_chars]

    # Fallback: first max_chars of body text (skip headings)
    paragraphs = []
    for line in body.splitlines():
        if line.strip() and not line.strip().startswith("#"):
            paragraphs.append(line.strip())
    return " ".join(paragraphs)[:max_chars]


def get_summary(text: str, max_chars: int = 500) -> str:
    """Get first 500 chars after frontmatter for summary."""
    body = strip_frontmatter(text)
    return body[:max_chars].strip()


def note_slug(path: Path) -> str:
    """Convert a note path to a slug relative to the vault."""
    try:
        rel = path.relative_to(VAULT_PATH)
    except ValueError:
        rel = path
    return str(rel).replace("\\", "/").replace(".md", "")


def extract_keywords(text: str) -> set:
    """Extract simple keywords from text for matching."""
    body = strip_frontmatter(text).lower()
    # Remove markdown formatting
    body = re.sub(r"[#*\[\](){}|`>_~]", " ", body)
    words = set(re.findall(r"\b[a-z]{4,}\b", body))
    # Remove very common words
    stopwords = {
        "this", "that", "with", "from", "have", "been", "were", "they",
        "their", "would", "could", "should", "about", "which", "when",
        "what", "there", "these", "those", "some", "other", "into",
        "more", "also", "than", "then", "only", "very", "just", "like",
        "each", "make", "made", "will", "does", "done", "much", "many",
        "most", "such", "well", "back", "even", "still", "after", "before",
        "being", "over", "between", "through", "under", "around",
    }
    return words - stopwords


# ---------------------------------------------------------------------------
# Vault scanning
# ---------------------------------------------------------------------------

def find_library_notes() -> list[Path]:
    """Find all markdown files in the Library and Podcasts directories."""
    notes = []
    if LIBRARY_DIR.exists():
        notes.extend(LIBRARY_DIR.rglob("*.md"))
    else:
        print(f"WARNING: Library directory not found: {LIBRARY_DIR}")
    if PODCASTS_DIR.exists():
        # Include podcast notes but skip transcript files and show indexes
        for p in PODCASTS_DIR.rglob("*.md"):
            if "/transcripts/" not in str(p).replace("\\", "/") and p.stat().st_size > 2000:
                notes.append(p)
    return sorted(notes)


def find_recent_notes(n: int) -> list[Path]:
    """Find the N most recently modified notes in Library + Podcasts."""
    notes = find_library_notes()
    notes.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return notes[:n]


def find_candidates(source_path: Path, source_text: str) -> list[Path]:
    """Find candidate notes that might relate to the source note."""
    source_meta = extract_frontmatter(source_text)
    source_tags = set(source_meta.get("tags", []))
    source_keywords = extract_keywords(source_text)

    candidates = []
    all_notes = find_library_notes()

    for note_path in all_notes:
        if note_path.resolve() == source_path.resolve():
            continue

        try:
            candidate_text = note_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Check tag overlap
        candidate_meta = extract_frontmatter(candidate_text)
        candidate_tags = set(candidate_meta.get("tags", []))
        tag_overlap = source_tags & candidate_tags

        # Check keyword overlap
        candidate_keywords = extract_keywords(candidate_text)
        keyword_overlap = source_keywords & candidate_keywords
        overlap_ratio = len(keyword_overlap) / max(len(source_keywords), 1)

        # Include if tags overlap or significant keyword overlap
        if tag_overlap or overlap_ratio > 0.15:
            candidates.append(note_path)

    return candidates


# ---------------------------------------------------------------------------
# xAI API classification
# ---------------------------------------------------------------------------

def classify_relationship(
    api_key: str, title_a: str, summary_a: str, title_b: str, summary_b: str
) -> dict | None:
    """Call xAI API to classify the relationship between two notes."""
    prompt = f"""Given these two notes, classify their relationship:

Note A: {title_a} — {summary_a}

Note B: {title_b} — {summary_b}

Classify as one of:
- supports: Note B provides evidence for claims in Note A
- contradicts: Note B conflicts with claims in Note A
- extends: Note B builds on ideas from Note A in a new direction
- bridges: Note B connects Note A to a previously unrelated topic
- unrelated: No meaningful connection

Return JSON only, no other text: {{"relationship": "supports|contradicts|extends|bridges|unrelated", "confidence": 0.0-1.0, "explanation": "one sentence"}}"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a research assistant that classifies relationships between notes. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            XAI_API_URL, data=data, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        result = json.loads(content)
        return result
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  WARNING: API call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Connections file management
# ---------------------------------------------------------------------------

def load_connections() -> dict:
    """Load existing connections from JSON file."""
    if CONNECTIONS_FILE.exists():
        try:
            data = json.loads(CONNECTIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "connections" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"connections": []}


def save_connections(data: dict) -> None:
    """Save connections to JSON file."""
    CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONNECTIONS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def connection_exists(data: dict, source: str, target: str) -> bool:
    """Check if a connection between source and target already exists."""
    for conn in data["connections"]:
        if (conn["source"] == source and conn["target"] == target) or \
           (conn["source"] == target and conn["target"] == source):
            return True
    return False


# ---------------------------------------------------------------------------
# Connection section in notes
# ---------------------------------------------------------------------------

def add_connections_section(note_path: Path, connections: list[dict]) -> None:
    """Add or update a ## Connections section at the end of a note."""
    text = note_path.read_text(encoding="utf-8")

    # Build connections section
    lines = ["\n## Connections\n"]
    for conn in connections:
        icon = {
            "supports": "+",
            "contradicts": "!",
            "extends": "->",
            "bridges": "<->",
        }.get(conn["relationship"], "?")
        target_name = conn["target"].split("/")[-1]
        lines.append(
            f"- [{icon}] **{conn['relationship']}** [[{target_name}]] "
            f"(confidence: {conn['confidence']:.0%}) — {conn['explanation']}"
        )
    section_text = "\n".join(lines) + "\n"

    # Remove existing Connections section if present
    pattern = re.compile(r"\n## Connections\n.*", re.DOTALL)
    text = pattern.sub("", text)

    text = text.rstrip() + "\n" + section_text
    note_path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main detection logic
# ---------------------------------------------------------------------------

def detect_connections(
    source_path: Path,
    api_key: str,
    add_section: bool = True,
) -> list[dict]:
    """Detect connections for a single note."""
    source_text = source_path.read_text(encoding="utf-8")
    source_title = extract_title(source_text)
    source_summary = get_summary(source_text)
    source_slug = note_slug(source_path)

    print(f"\nAnalyzing: {source_title}")
    print(f"  Path: {source_path}")

    candidates = find_candidates(source_path, source_text)
    print(f"  Found {len(candidates)} candidate notes")

    data = load_connections()
    new_connections = []

    for candidate_path in candidates:
        target_slug = note_slug(candidate_path)

        # Skip if connection already recorded
        if connection_exists(data, source_slug, target_slug):
            continue

        try:
            candidate_text = candidate_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        candidate_title = extract_title(candidate_text)
        candidate_summary = get_summary(candidate_text)

        print(f"  Classifying: {source_title} <-> {candidate_title} ... ", end="")

        result = classify_relationship(
            api_key, source_title, source_summary, candidate_title, candidate_summary
        )

        if result is None:
            print("FAILED")
            continue

        relationship = result.get("relationship", "unrelated")
        confidence = float(result.get("confidence", 0.0))
        explanation = result.get("explanation", "")

        if relationship == "unrelated" or confidence < CONFIDENCE_THRESHOLD:
            print(f"{relationship} ({confidence:.0%}) - skipped")
            continue

        print(f"{relationship} ({confidence:.0%})")

        connection = {
            "source": source_slug,
            "target": target_slug,
            "relationship": relationship,
            "confidence": confidence,
            "explanation": explanation,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        data["connections"].append(connection)
        new_connections.append(connection)

    if new_connections:
        save_connections(data)
        print(f"  Saved {len(new_connections)} new connections")

        if add_section:
            # Gather all connections involving this source
            all_source_connections = [
                c for c in data["connections"]
                if c["source"] == source_slug or c["target"] == source_slug
            ]
            add_connections_section(source_path, all_source_connections)
            print(f"  Updated Connections section in note")
    else:
        print(f"  No new connections found")

    return new_connections


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Detect and classify relationships between Obsidian vault notes."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--note", type=str,
        help="Path to a specific note (relative to vault root or absolute)",
    )
    group.add_argument(
        "--scan-recent", type=int, metavar="N",
        help="Scan the N most recently modified Library notes",
    )
    group.add_argument(
        "--scan-all", action="store_true",
        help="Full corpus scan (expensive)",
    )
    parser.add_argument(
        "--no-section", action="store_true",
        help="Do not add/update Connections section in notes",
    )

    args = parser.parse_args()
    api_key = load_api_key()
    add_section = not args.no_section

    total_new = 0

    if args.note:
        note_path = Path(args.note)
        if not note_path.is_absolute():
            note_path = VAULT_PATH / note_path
        if not note_path.exists():
            print(f"ERROR: Note not found: {note_path}")
            sys.exit(1)
        results = detect_connections(note_path, api_key, add_section)
        total_new = len(results)

    elif args.scan_recent:
        notes = find_recent_notes(args.scan_recent)
        print(f"Scanning {len(notes)} recent notes...")
        for note_path in notes:
            results = detect_connections(note_path, api_key, add_section)
            total_new += len(results)

    elif args.scan_all:
        notes = find_library_notes()
        print(f"Full corpus scan: {len(notes)} notes (this may take a while)...")
        for note_path in notes:
            results = detect_connections(note_path, api_key, add_section)
            total_new += len(results)

    # Summary
    print(f"\n{'='*60}")
    print(f"Connection detection complete.")
    print(f"  New connections found: {total_new}")
    data = load_connections()
    print(f"  Total connections in tracker: {len(data['connections'])}")
    print(f"  Connections file: {CONNECTIONS_FILE}")


if __name__ == "__main__":
    main()
