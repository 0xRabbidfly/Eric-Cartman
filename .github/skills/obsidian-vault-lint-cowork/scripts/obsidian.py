"""Cowork-native vault adapter — drop-in replacement for the Obsidian CLI wrapper.

The original skill's `obsidian.py` shells out to `obsidian.com` (the Windows
Obsidian binary) for every vault operation. That cannot run inside a Cowork
Linux sandbox. This module re-implements the subset of methods the lint phases
use, by reading the vault's markdown files directly from disk.

Public surface (matches the original's API closely enough that the phase modules
import `Obsidian` from here without other changes):

    ob = Obsidian()
    ob.read(path=...)                     -> str
    ob.create(path=..., content=..., overwrite=True) -> CLIResult
    ob.files(folder=..., ext="md")        -> CLIResult (.lines())
    ob.orphans()                          -> CLIResult (.lines())
    ob.unresolved(verbose=True)           -> CLIResult (.text)
    ob.deadends()                         -> CLIResult (.lines())
    ob.tags(sort="count", format="tsv")   -> CLIResult (.lines())
    ob.search(query, path=..., limit=...) -> CLIResult (.lines())

Methods not used by the lint pipeline are deliberately omitted.

Configuration:
    VAULT_PATH env var — explicit absolute path to vault root.
    If unset, auto-discovers between Windows and Linux-sandbox locations.
"""
from __future__ import annotations

import glob
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


# ---------------------------------------------------------------------------
# Vault discovery
# ---------------------------------------------------------------------------

_VAULT_CANDIDATES = [
    "/sessions/*/mnt/Documents/Obsidian Vault",       # Cowork Linux sandbox
    "C:/Users/nuno_/Documents/Obsidian Vault",         # Windows native
    "Z:/Projects/Eric-Cartman/Research",               # local checkout sibling
]


def _find_vault_path() -> Path:
    explicit = os.environ.get("VAULT_PATH")
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p.resolve()
        raise FileNotFoundError(
            f"VAULT_PATH={explicit!r} does not exist."
        )

    # Glob patterns first (Linux sandbox session paths change between runs)
    for pattern in _VAULT_CANDIDATES:
        if "*" in pattern:
            matches = sorted(glob.glob(pattern))
            if matches:
                return Path(matches[-1]).resolve()
        else:
            p = Path(pattern)
            if p.exists():
                return p.resolve()

    raise FileNotFoundError(
        "Vault not found. Set VAULT_PATH env var to the absolute vault path."
    )


# ---------------------------------------------------------------------------
# Regex / patterns
# ---------------------------------------------------------------------------

# Markdown wikilink: [[target]] or [[target|display]] or [[target#section]]
_WIKILINK_RE = re.compile(r"\[\[([^\]\n]+?)\]\]")

# Inline tag: #word-with-dashes (not inside code spans/blocks — we strip those first)
_TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z][\w/-]*)")
# Strip HTML attribute values so CSS hex codes (#aac, #eef4fb, #bbb) inside
# style="..." or other attrs are not misread as tags.
_HTML_ATTR_RE = re.compile(r'\s(?:style|class|id|color|bgcolor|fill|stroke)\s*=\s*"[^"]*"', re.IGNORECASE)
_HTML_ATTR_RE_SINGLE = re.compile(r"\s(?:style|class|id|color|bgcolor|fill|stroke)\s*=\s*'[^']*'", re.IGNORECASE)


# Fenced code blocks (triple backticks or tildes)
_FENCED_RE = re.compile(r"```[\s\S]*?```|~~~[\s\S]*?~~~", re.MULTILINE)

# Inline code spans
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

# Default skip folders (Obsidian metadata, git, etc.)
_SKIP_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".venv", "__pycache__"}


# ---------------------------------------------------------------------------
# Result type — preserves the original CLIResult shape used by callers
# ---------------------------------------------------------------------------


@dataclass
class CLIResult:
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    command: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def text(self) -> str:
        return self.stdout.strip()

    def lines(self) -> List[str]:
        return [ln for ln in self.stdout.strip().splitlines() if ln.strip()]

    def __str__(self) -> str:
        return self.text


# ---------------------------------------------------------------------------
# Obsidian class — drop-in adapter
# ---------------------------------------------------------------------------


class Obsidian:
    """Pure-Python adapter providing the subset of CLI methods used by the
    lint pipeline. Reads/writes the vault directly via the filesystem.
    """

    def __init__(self, vault: Optional[str] = None, timeout: int = 30):
        # `vault` and `timeout` accepted for signature compatibility; unused.
        _ = vault, timeout
        self.vault_path = _find_vault_path()
        # Lazy caches — built on first access
        self._all_md: Optional[List[Path]] = None
        self._slug_to_path: Optional[dict] = None
        self._path_to_links: Optional[dict] = None   # path -> set(slugs referenced)
        self._slug_incoming: Optional[dict] = None   # slug -> count of incoming links

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _abs(self, vault_relative: str) -> Path:
        # Normalize Windows-style separators inside vault-relative paths
        return self.vault_path / vault_relative.replace("\\", "/")

    def _rel(self, p: Path) -> str:
        return p.relative_to(self.vault_path).as_posix()

    def _iter_md_files(self) -> Iterable[Path]:
        if self._all_md is None:
            files: List[Path] = []
            for p in self.vault_path.rglob("*.md"):
                # Skip anything inside a SKIP_DIR
                if any(part in _SKIP_DIRS for part in p.parts):
                    continue
                files.append(p)
            self._all_md = files
        return self._all_md

    # ------------------------------------------------------------------
    # Graph construction (single-pass, cached)
    # ------------------------------------------------------------------

    # Class-level graph cache shared across every Obsidian() instance in a
    # process, keyed by vault path. The full lint pipeline constructs a fresh
    # Obsidian() in each phase; without this, the ~12s graph build ran 3x per
    # run and pushed the whole pipeline past its time budget on large vaults.
    _SHARED_GRAPH: dict = {}

    def _ensure_graph(self) -> None:
        if self._slug_to_path is not None:
            return

        cached = Obsidian._SHARED_GRAPH.get(str(self.vault_path))
        if cached is not None:
            (self._all_md, self._slug_to_path,
             self._path_to_links, self._slug_incoming) = cached
            return

        slug_to_path: dict = {}
        # For ambiguous slugs (multiple files share a basename), keep first; matches
        # how the existing code treats slug -> path as a 1:1 dict.
        for p in self._iter_md_files():
            slug = p.stem
            slug_to_path.setdefault(slug, self._rel(p))

        path_to_links: dict = {}
        slug_incoming: Counter = Counter()

        for p in self._iter_md_files():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                text = ""

            # Strip code spans/blocks so [[...]] inside code isn't counted
            stripped = _FENCED_RE.sub("", text)
            stripped = _INLINE_CODE_RE.sub("", stripped)
            stripped = _HTML_ATTR_RE.sub("", stripped)
            stripped = _HTML_ATTR_RE_SINGLE.sub("", stripped)

            slugs_referenced: set = set()
            for m in _WIKILINK_RE.finditer(stripped):
                raw = m.group(1).strip()
                # Strip display text, section anchor, and leading folder paths
                target = raw.split("|", 1)[0]
                target = target.split("#", 1)[0]
                target = target.split("^", 1)[0]
                target = target.rsplit("/", 1)[-1].strip()
                if not target:
                    continue
                slugs_referenced.add(target)

            rel = self._rel(p)
            path_to_links[rel] = slugs_referenced

            # Don't count self-links as incoming
            self_slug = p.stem
            for s in slugs_referenced:
                if s == self_slug:
                    continue
                # Only count incoming if target resolves to a real file in the vault
                if s in slug_to_path:
                    slug_incoming[s] += 1

        self._slug_to_path = slug_to_path
        self._path_to_links = path_to_links
        self._slug_incoming = slug_incoming
        Obsidian._SHARED_GRAPH[str(self.vault_path)] = (
            self._all_md, slug_to_path, path_to_links, slug_incoming
        )

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def read(self, file: Optional[str] = None, *, path: Optional[str] = None) -> str:
        if path is None and file is None:
            return ""
        if path is not None:
            p = self._abs(path)
        else:
            # `file` could be a basename — resolve via slug index
            self._ensure_graph()
            rel = self._slug_to_path.get(Path(file).stem)
            if rel is None:
                raise FileNotFoundError(f"Note not found by name: {file!r}")
            p = self._abs(rel)
        return p.read_text(encoding="utf-8", errors="replace")

    def create(
        self,
        name: Optional[str] = None,
        *,
        path: Optional[str] = None,
        content: Optional[str] = None,
        template: Optional[str] = None,
        overwrite: bool = False,
        open: bool = False,
    ) -> CLIResult:
        _ = name, template, open  # not used in lint pipeline
        if path is None:
            return CLIResult(stderr="create() requires path=", returncode=1)
        if content is None:
            content = ""

        target = self._abs(path)
        if target.exists() and not overwrite:
            return CLIResult(
                stderr=f"File exists and overwrite=False: {path}",
                returncode=1,
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        # Mutating the vault invalidates the cached graph
        self._invalidate_cache()
        return CLIResult(stdout=f"Wrote {path}\n")

    def _invalidate_cache(self) -> None:
        self._all_md = None
        self._slug_to_path = None
        self._path_to_links = None
        self._slug_incoming = None
        Obsidian._SHARED_GRAPH.pop(str(self.vault_path), None)

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def files(
        self,
        folder: Optional[str] = None,
        ext: Optional[str] = None,
        total: bool = False,
    ) -> CLIResult:
        _ = total
        ext_norm = (ext or "").lstrip(".").lower() or None

        results: List[str] = []
        for p in self._iter_md_files() if (ext_norm in (None, "md")) else self._iter_files(ext_norm):
            rel = self._rel(p)
            if folder and not rel.startswith(folder.rstrip("/") + "/") and rel != folder:
                continue
            results.append(rel)

        results.sort()
        return CLIResult(stdout="\n".join(results) + ("\n" if results else ""))

    def _iter_files(self, ext_norm: str) -> Iterable[Path]:
        """Fallback iteration when ext != md (rare for this pipeline)."""
        for p in self.vault_path.rglob(f"*.{ext_norm}"):
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            yield p

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    def orphans(self, *, total: bool = False) -> CLIResult:
        _ = total
        self._ensure_graph()
        orphan_paths = []
        for slug, rel in self._slug_to_path.items():
            if self._slug_incoming.get(slug, 0) == 0:
                orphan_paths.append(rel)
        orphan_paths.sort()
        return CLIResult(stdout="\n".join(orphan_paths) + ("\n" if orphan_paths else ""))

    def unresolved(self, *, total: bool = False, verbose: bool = False) -> CLIResult:
        _ = total
        self._ensure_graph()

        # Per-file list of broken target slugs
        broken_by_file: List[tuple] = []  # (rel_path, [broken_slugs])
        for rel, slugs in self._path_to_links.items():
            broken = sorted(s for s in slugs if s not in self._slug_to_path)
            if broken:
                broken_by_file.append((rel, broken))

        broken_by_file.sort(key=lambda x: x[0])

        if verbose:
            # Format expected by inventory._parse_unresolved:
            # line not indented = filename
            # indented lines = broken targets
            out_lines: List[str] = []
            for rel, broken in broken_by_file:
                out_lines.append(rel)
                for slug in broken:
                    out_lines.append(f"    {slug}")
            return CLIResult(stdout="\n".join(out_lines) + ("\n" if out_lines else ""))

        # Non-verbose: flat list of unresolved slugs (deduped)
        all_broken = sorted({s for _, slugs in broken_by_file for s in slugs})
        return CLIResult(stdout="\n".join(all_broken) + ("\n" if all_broken else ""))

    def deadends(self, *, total: bool = False) -> CLIResult:
        _ = total
        self._ensure_graph()
        deadends: List[str] = []
        for rel, slugs in self._path_to_links.items():
            if not slugs:
                deadends.append(rel)
        deadends.sort()
        return CLIResult(stdout="\n".join(deadends) + ("\n" if deadends else ""))

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def tags(
        self,
        *,
        file: Optional[str] = None,
        path: Optional[str] = None,
        active: bool = False,
        counts: bool = True,
        total: bool = False,
        sort: Optional[str] = None,
        format: str = "tsv",
    ) -> CLIResult:
        _ = file, path, active, total
        counter: Counter = Counter()
        for p in self._iter_md_files():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            stripped = _FENCED_RE.sub("", text)
            stripped = _INLINE_CODE_RE.sub("", stripped)
            stripped = _HTML_ATTR_RE.sub("", stripped)
            stripped = _HTML_ATTR_RE_SINGLE.sub("", stripped)
            for m in _TAG_RE.finditer(stripped):
                counter[m.group(1)] += 1

        # Also pick up YAML frontmatter `tags:` list — common pattern
        # (best-effort; very simple parser)
        for p in self._iter_md_files():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if not text.startswith("---"):
                continue
            end = text.find("\n---", 4)
            if end < 0:
                continue
            fm = text[4:end]
            for tag in _extract_frontmatter_tags(fm):
                counter[tag] += 1

        if sort == "count":
            items = counter.most_common()
        elif sort == "name":
            items = sorted(counter.items(), key=lambda x: x[0].lower())
        else:
            items = list(counter.items())

        if format == "tsv":
            if counts:
                lines = [f"{name}\t{count}" for name, count in items]
            else:
                lines = [name for name, _ in items]
        elif format == "json":
            import json
            payload = [{"name": n, "count": c} for n, c in items] if counts else [n for n, _ in items]
            return CLIResult(stdout=json.dumps(payload))
        elif format == "csv":
            if counts:
                lines = [f"{name},{count}" for name, count in items]
            else:
                lines = [name for name, _ in items]
        else:
            lines = [f"{name}\t{count}" for name, count in items]

        return CLIResult(stdout="\n".join(lines) + ("\n" if lines else ""))

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        path: Optional[str] = None,
        limit: Optional[int] = None,
        total: bool = False,
        case: bool = False,
        format: str = "text",
    ) -> CLIResult:
        _ = total, format
        if not query:
            return CLIResult(stdout="")

        flags = 0 if case else re.IGNORECASE
        # Treat query as plain text; allow space-separated AND semantics:
        # match if every whitespace-separated token appears.
        tokens = [t for t in query.split() if t]
        if not tokens:
            return CLIResult(stdout="")
        patterns = [re.compile(re.escape(t), flags) for t in tokens]

        results: List[str] = []
        for p in self._iter_md_files():
            rel = self._rel(p)
            if path and not rel.startswith(path.rstrip("/") + "/") and rel != path:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if all(pat.search(text) for pat in patterns):
                results.append(rel)
                if limit and len(results) >= limit:
                    break

        results.sort()
        return CLIResult(stdout="\n".join(results) + ("\n" if results else ""))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_frontmatter_tags(fm: str) -> List[str]:
    """Best-effort parse of YAML frontmatter `tags:` field.

    Handles:
        tags: [foo, bar, baz]
        tags:
          - foo
          - bar
        tags: foo bar
    """
    tags: List[str] = []
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^\s*tags\s*:\s*(.*)$", line)
        if not m:
            i += 1
         