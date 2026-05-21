"""Phase 3 - Connection Discovery: LLM-assisted orphan link suggestions.

Cowork-native fork: imports the local obsidian.py adapter.
xAI key sources: XAI_API_KEY env var only (keyring not available in sandbox).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))
from obsidian import Obsidian

XAI_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_XAI_MODEL = "grok-3"
BATCH_SIZE = 5
TOP_ORPHANS = 20


def get_xai_key() -> str:
    key = os.environ.get("XAI_API_KEY")
    if key:
        return key
    # keyring may not be available in the Cowork sandbox; try anyway
    try:
        import keyring
        return keyring.get_password("automation/xai", "api_key") or ""
    except Exception:
        return ""


def discover_connections(
    orphan_paths: list,
    dry_run: bool = False,
    verbose: bool = False,
) -> list:
    api_key = get_xai_key()
    if not api_key:
        print("[connections] No xAI API key - skipping Phase 3.", file=sys.stderr)
        print("[connections] Set XAI_API_KEY env var to enable.", file=sys.stderr)
        return []

    ob = Obsidian()
    library_orphans = [p for p in orphan_paths if "Research/Library/" in p][:TOP_ORPHANS]

    if not library_orphans:
        if verbose:
            print("[connections] No Library orphans to process.")
        return []

    model = os.environ.get("XAI_MODEL", DEFAULT_XAI_MODEL)
    if verbose:
        print(f"[connections] {len(library_orphans)} orphans, model={model}, batch_size={BATCH_SIZE}")

    proposals = []
    for i in range(0, len(library_orphans), BATCH_SIZE):
        batch = library_orphans[i : i + BATCH_SIZE]
        if verbose:
            print(f"[connections] Batch {i // BATCH_SIZE + 1}/{-(-len(library_orphans) // BATCH_SIZE)}: {len(batch)} notes")
        batch_results = _process_batch(ob, api_key, model, batch, verbose=verbose)
        proposals.extend(batch_results)
        if i + BATCH_SIZE < len(library_orphans):
            time.sleep(1)

    return proposals


def _process_batch(ob: Obsidian, api_key: str, model: str, paths: list, verbose: bool = False) -> list:
    results = []
    for path in paths:
        slug = path.rsplit("/", 1)[-1].replace(".md", "")
        summary = _note_summary(ob, path, chars=300)

        try:
            search_lines = ob.search(slug.replace("-", " "), path="Research/Library", limit=10).lines()
            candidates = [r for r in search_lines if r != path][:8]
        except Exception:
            candidates = []

        if not candidates:
            continue

        candidate_text = "\n".join(
            f"- {c.rsplit('/', 1)[-1].replace('.md', '')}: {_note_summary(ob, c, chars=150)}"
            for c in candidates
        )

        prompt = (
            f"You are a knowledge graph curator. An orphaned research note needs wikilink connections.\n\n"
            f"ORPHAN: {slug}\nSUMMARY: {summary}\n\nCANDIDATES:\n{candidate_text}\n\n"
            f"Return a JSON array of up to 3 objects identifying the most related candidates:\n"
            f'[{{"slug": "candidate-slug", "reason": "one sentence why related"}}]\n\n'
            f"Return ONLY valid JSON, no other text."
        )

        try:
            response = _call_xai(api_key, model, prompt)
            text = response["choices"][0]["message"]["content"].strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            suggestions = json.loads(text)
            if isinstance(suggestions, list) and suggestions:
                results.append({
                    "orphan_path": path,
                    "orphan_slug": slug,
                    "suggested_links": suggestions,
                })
                if verbose:
                    print(f"[connections]   {slug}: {len(suggestions)} suggestion(s)")
        except Exception as e:
            print(f"[connections] Failed for {slug}: {e}", file=sys.stderr)

    return results


def apply_connection_proposals(proposal_path: str, dry_run: bool = False, verbose: bool = False) -> int:
    ob = Obsidian()
    content = ob.read(path=proposal_path)

    sections = re.split(r"^## ", content, flags=re.MULTILINE)
    applied = 0

    for section in sections[1:]:
        lines = section.strip().splitlines()
        if not lines:
            continue
        orphan_slug = lines[0].strip()

        file_match = re.search(r"File: `([^`]+)`", section)
        if not file_match:
            print(f"[apply] Skipping section '{orphan_slug}': no File: line found", file=sys.stderr)
            continue
        orphan_path = file_match.group(1)

        link_slugs = re.findall(r"- \[\[([^\]]+)\]\]", section)
        if not link_slugs:
            print(f"[apply] Skipping section '{orphan_slug}': no [[links]] found", file=sys.stderr)
            continue

        if verbose:
            print(f"[apply] {orphan_slug}: {len(link_slugs)} link(s)")

        try:
            note_content = ob.read(path=orphan_path)
            new_links = "\n".join(f"- [[{s}]]" for s in link_slugs)

            if "## Related" in note_content:
                new_content = note_content.rstrip() + "\n" + new_links
            else:
                new_content = note_content.rstrip() + f"\n\n## Related\n{new_links}"

            if not dry_run:
                ob.create(path=orphan_path, content=new_content, overwrite=True)
            applied += 1
        except Exception as e:
            print(f"[apply] Failed for {orphan_path}: {e}", file=sys.stderr)

    return applied


def format_connections_report(proposals: list, run_date: str) -> str:
    lines = [
        f"# Vault Lint - Connection Proposals - {run_date}",
        "",
        "> Review these suggested wikilinks. To apply after review:",
        "> `python scripts/lint.py --phase 3 --apply`",
        "",
        f"**{len(proposals)} orphaned notes with proposed connections**",
        "",
    ]
    for p in proposals:
        lines += [
            f"## {p['orphan_slug']}",
            f"File: `{p['orphan_path']}`",
            "",
            "Append to **Related** section:",
            "```",
        ]
        for s in p["suggested_links"]:
            lines.append(f"- [[{s['slug']}]] - {s['reason']}")
        lines += ["```", ""]
    return "\n".join(lines)


def _note_summary(ob: Obsidian, path: str, chars: int = 300) -> str:
    try:
        return ob.read(path=path)[:chars].strip().replace("\n", " ")
    except Exception:
        return ""


def _call_xai(api_key: str, model: str, prompt: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        XAI_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    max_attempts = 3
    backoff_seconds = [2, 4, 8]

    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_attempts - 1:
                wait = backoff_seconds[attempt]
                print(f"[connections] Rate limited (429), retrying in {wait}s (attempt {attempt + 1}/{max_attempts})", file=sys.stderr)
                time.sleep(wait)
                continue
            elif e.code >= 500 and attempt < max_attempts - 1:
                wait = backoff_seconds[attempt]
                print(f"[connections] Server error ({e.code}), retrying in {wait}s (attempt {attempt + 1}/{max_attempts})", file=sys.stderr)
                time.sleep(wait)
                continue
            else:
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_attempts - 1:
                wait = backoff_seconds[attempt]
                print(f"[connections] Network error, retrying in {wait}s (attempt {attempt + 1}/{max_attempts}): {e}", file=sys.stderr)
                time.sleep(wait)
                continue
            else:
                raise
