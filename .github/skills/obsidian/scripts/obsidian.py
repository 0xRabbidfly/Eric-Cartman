"""Obsidian CLI wrapper — composable vault operations.

Thin Python wrapper around the Obsidian CLI (v1.12+).
Requires Obsidian to be running with CLI enabled.

Usage:
    from obsidian import Obsidian

    ob = Obsidian()
    ob.search("meeting notes")
    ob.daily_append("- [ ] Buy groceries")
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union


# ---------------------------------------------------------------------------
# CLI binary discovery
# ---------------------------------------------------------------------------

_OBSIDIAN_BINARY: Optional[str] = None


def _find_obsidian_binary() -> str:
    """Locate the obsidian CLI binary.

    Search order:
    1. OBSIDIAN_CLI env var (explicit override)
    2. 'obsidian' on PATH
    3. Default Windows install location
    """
    global _OBSIDIAN_BINARY
    if _OBSIDIAN_BINARY:
        return _OBSIDIAN_BINARY

    # 1. Env override
    env = os.environ.get("OBSIDIAN_CLI")
    if env and Path(env).exists():
        _OBSIDIAN_BINARY = env
        return _OBSIDIAN_BINARY

    # 2. PATH lookup — Windows needs .com extension explicitly
    for name in ("obsidian.com", "obsidian"):
        try:
            result = subprocess.run(
                [name, "version"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 or result.stdout.strip():
                _OBSIDIAN_BINARY = name
                return _OBSIDIAN_BINARY
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # 3. Default Windows path
    win_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "obsidian" / "Obsidian.com"
    if win_path.exists():
        _OBSIDIAN_BINARY = str(win_path)
        return _OBSIDIAN_BINARY

    raise FileNotFoundError(
        "Obsidian CLI not found. Ensure Obsidian 1.12+ is installed, "
        "CLI is enabled (Settings → General), and Obsidian.com is in the "
        "install folder. Or set OBSIDIAN_CLI env var to the binary path."
    )


# ---------------------------------------------------------------------------
# Vault path discovery (for direct-filesystem writes)
# ---------------------------------------------------------------------------


def _resolve_vault_path(vault_name: Optional[str] = None) -> Optional[Path]:
    """Locate the vault's folder on disk, for direct-filesystem writes.

    Note writes go straight to disk (Obsidian's file watcher reloads them)
    because the Obsidian 1.13.x CLI write path is unreliable — it crashes or
    times out on real note content. Resolution order:

    1. ``OBSIDIAN_VAULT_PATH`` / ``VAULT_PATH`` env override.
    2. Obsidian's own registry ``obsidian.json`` (``%APPDATA%/obsidian`` on
       Windows, the Application Support / ``~/.config`` equivalents elsewhere),
       preferring a vault whose folder name matches ``vault_name``, then the
       currently-open vault, then the most recently used.

    Returns None if nothing resolves (callers fall back to the CLI).
    """
    env = os.environ.get("OBSIDIAN_VAULT_PATH") or os.environ.get("VAULT_PATH")
    if env and Path(env).is_dir():
        return Path(env)

    cfg_dirs = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        cfg_dirs.append(Path(appdata) / "obsidian")
    home = Path.home()
    cfg_dirs.append(home / "Library" / "Application Support" / "obsidian")  # macOS
    cfg_dirs.append(home / ".config" / "obsidian")                          # Linux

    for cfg_dir in cfg_dirs:
        cfg = cfg_dir / "obsidian.json"
        if not cfg.exists():
            continue
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        rows = []
        for meta in (data.get("vaults") or {}).values():
            p = meta.get("path")
            if p and Path(p).is_dir():
                rows.append((bool(meta.get("open")), meta.get("ts", 0), Path(p)))
        if not rows:
            continue
        if vault_name:
            for _open, _ts, p in rows:
                if p.name == vault_name:
                    return p
        rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
        return rows[0][2]

    return None


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CLIResult:
    """Raw result from an Obsidian CLI call."""

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

    def json(self) -> Any:
        """Parse stdout as JSON. Raises ValueError on failure."""
        return json.loads(self.stdout)

    def lines(self) -> List[str]:
        """Split stdout into non-empty lines."""
        return [line for line in self.stdout.strip().splitlines() if line.strip()]

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        status = "ok" if self.ok else f"err({self.returncode})"
        preview = self.text[:80] + "..." if len(self.text) > 80 else self.text
        return f"CLIResult({status}, {preview!r})"


# ---------------------------------------------------------------------------
# Content escaping for the CLI transport
# ---------------------------------------------------------------------------


def _escape_cli_content(value: Any) -> str:
    r"""Escape a ``content`` value for the Obsidian CLI's argv → JSON transport.

    The CLI (``obsidian.com``) forwards its arguments to the running app as a
    JSON array. As of Obsidian 1.13.x it no longer escapes raw control
    characters in that argument, so a ``content`` value containing literal
    newlines/tabs produces invalid JSON and the write crashes in the main
    process (``SyntaxError: Unexpected token ...``).

    The CLI documents that content should use ``\n``/``\t`` escapes ("Use \n
    for newline, \t for tab in content values") and un-escapes exactly those on
    the way in — it does NOT collapse ``\\`` back to ``\``. So we escape only
    the control characters that break the JSON transport (newline, CR, tab) and
    leave backslashes untouched (``obsidian.com`` already escapes ``\`` and
    ``"`` correctly when building the JSON; only raw control chars are the bug).
    Escaping backslashes here would double them on disk.
    """
    s = str(value)
    s = s.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    s = s.replace("\t", "\\t")
    return s


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class Obsidian:
    """Obsidian CLI wrapper.

    Args:
        vault: Vault name to target. If None, uses the currently active vault
               (or the vault matching the current working directory).
        timeout: Default timeout in seconds for CLI calls.
    """

    def __init__(self, vault: Optional[str] = None, timeout: int = 30):
        self._vault = vault
        self._timeout = timeout
        self._binary = _find_obsidian_binary()
        self._vault_path = _resolve_vault_path(vault)

    # ------------------------------------------------------------------
    # Low-level runner
    # ------------------------------------------------------------------

    def run(self, command: str, /, **kwargs: Any) -> CLIResult:
        """Run an arbitrary Obsidian CLI command.

        Args:
            command: CLI command name (e.g. "search", "daily:append").
            **kwargs: Parameters and flags. String values become param=value,
                      True becomes a bare flag, False/None are skipped.

        Returns:
            CLIResult with stdout, stderr, returncode.
        """
        cmd = [self._binary]

        # Vault targeting must come first
        if self._vault:
            cmd.append(f"vault={self._vault}")

        cmd.append(command)

        for key, value in kwargs.items():
            if value is None or value is False:
                continue
            if value is True:
                cmd.append(key)
            else:
                if key == "content":
                    value = _escape_cli_content(value)
                cmd.append(f"{key}={value}")

        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=kwargs.pop("timeout", self._timeout) if "timeout" in kwargs else self._timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return CLIResult(
                stdout=exc.stdout or "",
                stderr=exc.stderr or f"Timeout after {self._timeout}s",
                returncode=-1,
                command=cmd,
            )

        return CLIResult(
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            returncode=proc.returncode,
            command=cmd,
        )

    # ------------------------------------------------------------------
    # Files and folders
    # ------------------------------------------------------------------

    def _disk_path(self, *, path: Optional[str] = None, file: Optional[str] = None) -> Optional[Path]:
        """Resolve a vault-relative path or note name to an absolute Path.

        Returns None when the vault folder is unknown so callers fall back to
        the CLI. Path-based lookups append ``.md`` (the CLI coerces non-.md
        create targets to ``.md``); name-based lookups search the vault.
        """
        if self._vault_path is None:
            return None
        if path:
            rel = path.replace("\\", "/")
            if not rel.lower().endswith(".md"):
                rel += ".md"
            return self._vault_path / rel
        if file:
            stem = Path(file).stem
            direct = self._vault_path / f"{stem}.md"
            if direct.exists():
                return direct
            for p in self._vault_path.rglob(f"{stem}.md"):
                if not any(part in {".trash", ".obsidian", ".git"} for part in p.parts):
                    return p
        return None

    def read(self, file: Optional[str] = None, *, path: Optional[str] = None) -> str:
        """Read a file's contents. Returns the text.

        Reads from disk directly when the vault path is known (fast, and works
        even when the app is busy/unresponsive); falls back to the CLI.
        """
        target = self._disk_path(path=path, file=file)
        if target is not None and target.exists():
            try:
                return target.read_text(encoding="utf-8")
            except OSError:
                pass
        return self.run("read", file=file, path=path).text

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
        """Create (or overwrite) a note.

        Writes directly to disk — Obsidian's file watcher reloads the change —
        because the 1.13.x CLI write path is unreliable on real note content.
        Falls back to the CLI for name/template-based creation or when the
        vault folder can't be resolved.
        """
        if path and template is None:
            target = self._disk_path(path=path)
            if target is not None:
                if target.exists() and not overwrite:
                    return CLIResult(stderr=f"File exists (overwrite=False): {path}", returncode=1)
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content or "", encoding="utf-8", newline="")
                    return CLIResult(stdout=f"Created: {path}")
                except OSError as exc:
                    return CLIResult(stderr=f"Direct write failed: {exc}", returncode=1)
        return self.run(
            "create",
            name=name,
            path=path,
            content=content,
            template=template,
            overwrite=overwrite or None,
            open=open or None,
        )

    def append(
        self,
        content: str,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        inline: bool = False,
    ) -> CLIResult:
        """Append content to a file (direct disk write; CLI fallback)."""
        target = self._disk_path(path=path, file=file)
        if target is not None and target.exists():
            try:
                existing = target.read_text(encoding="utf-8")
                sep = "" if (inline or not existing or existing.endswith("\n")) else "\n"
                target.write_text(existing + sep + content, encoding="utf-8", newline="")
                return CLIResult(stdout=f"Appended: {path or file}")
            except OSError as exc:
                return CLIResult(stderr=f"Direct append failed: {exc}", returncode=1)
        return self.run("append", content=content, file=file, path=path, inline=inline or None)

    def prepend(
        self,
        content: str,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        inline: bool = False,
    ) -> CLIResult:
        """Prepend content after frontmatter (direct disk write; CLI fallback)."""
        target = self._disk_path(path=path, file=file)
        if target is not None and target.exists():
            try:
                existing = target.read_text(encoding="utf-8")
                body = content if inline else content.rstrip("\n") + "\n"
                insert_at = 0
                if existing.startswith("---\n") or existing.startswith("---\r\n"):
                    end = existing.find("\n---", 3)
                    if end != -1:
                        nl = existing.find("\n", end + 1)
                        if nl != -1:
                            insert_at = nl + 1
                new = existing[:insert_at] + body + existing[insert_at:]
                target.write_text(new, encoding="utf-8", newline="")
                return CLIResult(stdout=f"Prepended: {path or file}")
            except OSError as exc:
                return CLIResult(stderr=f"Direct prepend failed: {exc}", returncode=1)
        return self.run("prepend", content=content, file=file, path=path, inline=inline or None)

    def move(
        self,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        to: str,
        make_dirs: bool = True,
    ) -> CLIResult:
        """Move or rename a file. Auto-updates internal links.

        The Obsidian CLI has no mkdir, and ``move`` is a raw filesystem rename
        that fails with ENOENT when the destination folder does not exist.
        With ``make_dirs=True`` (default) we seed the destination folder first
        (see :meth:`ensure_folder`) and retry the move once.
        """
        r = self.run("move", file=file, path=path, to=to)
        if make_dirs and to and self._is_missing_dir_error(r):
            parent = to.replace("\\", "/").rsplit("/", 1)
            if len(parent) == 2:
                self.ensure_folder(parent[0])
                r = self.run("move", file=file, path=path, to=to)
        return r

    @staticmethod
    def _is_missing_dir_error(r: CLIResult) -> bool:
        """True if a call failed because a target folder was missing.

        The CLI returns exit code 0 even on this error, so ``r.ok`` is not
        reliable here — the ENOENT text is the only signal.
        """
        blob = f"{r.stdout} {r.stderr}".lower()
        return "enoent" in blob or "no such file or directory" in blob

    def ensure_folder(self, folder: str) -> None:
        """Ensure a vault folder exists (idempotent).

        The Obsidian CLI exposes no folder-create command, but ``create`` makes
        any missing parent folders. So we seed the folder with a throwaway note
        and immediately delete it. ``folder`` is a vault-relative folder path
        with no filename (e.g. ``Research/Library/10 Crypto, Tokenomics``).
        """
        folder = folder.replace("\\", "/").strip("/")
        if not folder:
            return
        seed = f"{folder}/_obsidian_mkdir_tmp.md"
        self.run("create", path=seed, content="mkdir")
        self.run("delete", path=seed, permanent=True)

    def rename(self, file: Optional[str] = None, *, path: Optional[str] = None, name: str) -> CLIResult:
        """Rename a file (preserving extension). Auto-updates internal links."""
        return self.run("rename", file=file, path=path, name=name)

    def delete(self, file: Optional[str] = None, *, path: Optional[str] = None, permanent: bool = False) -> CLIResult:
        """Delete a file (trash by default)."""
        return self.run("delete", file=file, path=path, permanent=permanent or None)

    def file_info(self, file: Optional[str] = None, *, path: Optional[str] = None) -> CLIResult:
        """Get file metadata (path, size, created, modified)."""
        return self.run("file", file=file, path=path)

    def files(
        self,
        folder: Optional[str] = None,
        ext: Optional[str] = None,
        total: bool = False,
    ) -> CLIResult:
        """List files in the vault."""
        return self.run("files", folder=folder, ext=ext, total=total or None)

    def folders(self, folder: Optional[str] = None, total: bool = False) -> CLIResult:
        """List folders in the vault."""
        return self.run("folders", folder=folder, total=total or None)

    def open(self, file: Optional[str] = None, *, path: Optional[str] = None, newtab: bool = False) -> CLIResult:
        """Open a file in Obsidian."""
        return self.run("open", file=file, path=path, newtab=newtab or None)

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
        format: Literal["text", "json"] = "text",
    ) -> CLIResult:
        """Search vault for text. Returns matching file paths."""
        return self.run(
            "search",
            query=query,
            path=path,
            limit=limit,
            total=total or None,
            case=case or None,
            format=format if format != "text" else None,
        )

    def search_context(
        self,
        query: str,
        *,
        path: Optional[str] = None,
        limit: Optional[int] = None,
        case: bool = False,
        format: Literal["text", "json"] = "text",
    ) -> CLIResult:
        """Search with matching line context (grep-style output)."""
        return self.run(
            "search:context",
            query=query,
            path=path,
            limit=limit,
            case=case or None,
            format=format if format != "text" else None,
        )

    # ------------------------------------------------------------------
    # Daily notes
    # ------------------------------------------------------------------

    def daily(self) -> CLIResult:
        """Open today's daily note."""
        return self.run("daily")

    def daily_path(self) -> str:
        """Get the daily note path (even if not yet created)."""
        return self.run("daily:path").text

    def daily_read(self) -> str:
        """Read today's daily note contents."""
        return self.run("daily:read").text

    def daily_append(self, content: str, *, inline: bool = False, open: bool = False) -> CLIResult:
        """Append content to today's daily note."""
        return self.run("daily:append", content=content, inline=inline or None, open=open or None)

    def daily_prepend(self, content: str, *, inline: bool = False, open: bool = False) -> CLIResult:
        """Prepend content to today's daily note."""
        return self.run("daily:prepend", content=content, inline=inline or None, open=open or None)

    # ------------------------------------------------------------------
    # Properties (frontmatter)
    # ------------------------------------------------------------------

    def properties(
        self,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        active: bool = False,
        format: Literal["yaml", "json", "tsv"] = "yaml",
    ) -> CLIResult:
        """List properties for a file or the whole vault."""
        return self.run(
            "properties",
            file=file,
            path=path,
            active=active or None,
            format=format if format != "yaml" else None,
        )

    def property_read(self, name: str, file: Optional[str] = None, *, path: Optional[str] = None) -> str:
        """Read a single property value."""
        return self.run("property:read", name=name, file=file, path=path).text

    def property_set(
        self,
        name: str,
        value: str,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        type: Optional[str] = None,
    ) -> CLIResult:
        """Set a property on a file."""
        return self.run("property:set", name=name, value=value, file=file, path=path, type=type)

    def property_remove(self, name: str, file: Optional[str] = None, *, path: Optional[str] = None) -> CLIResult:
        """Remove a property from a file."""
        return self.run("property:remove", name=name, file=file, path=path)

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
        sort: Optional[Literal["count", "name"]] = None,
        format: Literal["tsv", "json", "csv"] = "tsv",
    ) -> CLIResult:
        """List tags in the vault or for a specific file."""
        return self.run(
            "tags",
            file=file,
            path=path,
            active=active or None,
            counts=counts or None,
            total=total or None,
            sort=sort,
            format=format if format != "tsv" else None,
        )

    def tag_info(self, name: str, *, verbose: bool = True, total: bool = False) -> CLIResult:
        """Get info about a specific tag (count + file list)."""
        return self.run("tag", name=name, verbose=verbose or None, total=total or None)

    def tags_for_file(
        self,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        counts: bool = False,
        total: bool = False,
    ) -> CLIResult:
        """Get tags for a specific file."""
        return self.run(
            "tags",
            file=file,
            path=path,
            counts=counts or None,
            total=total or None,
            active=True if not file and not path else None,
        )

    # ------------------------------------------------------------------
    # Links / Graph
    # ------------------------------------------------------------------

    def backlinks(
        self,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        counts: bool = False,
        total: bool = False,
        format: Literal["tsv", "json", "csv"] = "tsv",
    ) -> CLIResult:
        """List backlinks to a file."""
        return self.run(
            "backlinks",
            file=file,
            path=path,
            counts=counts or None,
            total=total or None,
            format=format if format != "tsv" else None,
        )

    def links(self, file: Optional[str] = None, *, path: Optional[str] = None, total: bool = False) -> CLIResult:
        """List outgoing links from a file."""
        return self.run("links", file=file, path=path, total=total or None)

    def orphans(self, *, total: bool = False) -> CLIResult:
        """List files with no incoming links."""
        return self.run("orphans", total=total or None)

    def unresolved(self, *, total: bool = False, verbose: bool = False) -> CLIResult:
        """List unresolved (broken) links."""
        return self.run("unresolved", total=total or None, verbose=verbose or None)

    def deadends(self, *, total: bool = False) -> CLIResult:
        """List files with no outgoing links."""
        return self.run("deadends", total=total or None)

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def tasks(
        self,
        *,
        file: Optional[str] = None,
        path: Optional[str] = None,
        todo: bool = False,
        done: bool = False,
        daily: bool = False,
        total: bool = False,
        verbose: bool = False,
        format: Literal["text", "json", "tsv", "csv"] = "text",
    ) -> CLIResult:
        """List tasks in the vault."""
        return self.run(
            "tasks",
            file=file,
            path=path,
            todo=todo or None,
            done=done or None,
            daily=daily or None,
            total=total or None,
            verbose=verbose or None,
            format=format if format != "text" else None,
        )

    def task_toggle(self, *, file: Optional[str] = None, path: Optional[str] = None, line: int) -> CLIResult:
        """Toggle a task's completion status."""
        return self.run("task", file=file, path=path, line=line, toggle=True)

    def task_done(self, *, file: Optional[str] = None, path: Optional[str] = None, line: int) -> CLIResult:
        """Mark a task as done."""
        return self.run("task", file=file, path=path, line=line, done=True)

    def task_todo(self, *, file: Optional[str] = None, path: Optional[str] = None, line: int) -> CLIResult:
        """Mark a task as todo."""
        return self.run("task", file=file, path=path, line=line, todo=True)

    # ------------------------------------------------------------------
    # Outline
    # ------------------------------------------------------------------

    def outline(
        self,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        format: Literal["tree", "md", "json"] = "tree",
    ) -> CLIResult:
        """Show heading structure of a file."""
        return self.run("outline", file=file, path=path, format=format if format != "tree" else None)

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def templates(self, *, total: bool = False) -> CLIResult:
        """List available templates."""
        return self.run("templates", total=total or None)

    def template_read(self, name: str, *, resolve: bool = False, title: Optional[str] = None) -> str:
        """Read a template's content."""
        return self.run("template:read", name=name, resolve=resolve or None, title=title).text

    def template_insert(self, name: str) -> CLIResult:
        """Insert a template into the active file."""
        return self.run("template:insert", name=name)

    # ------------------------------------------------------------------
    # Bookmarks
    # ------------------------------------------------------------------

    def bookmarks(self, *, format: Literal["tsv", "json", "csv"] = "tsv") -> CLIResult:
        """List bookmarks."""
        return self.run("bookmarks", format=format if format != "tsv" else None)

    def bookmark(
        self,
        *,
        file: Optional[str] = None,
        folder: Optional[str] = None,
        search: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
    ) -> CLIResult:
        """Add a bookmark."""
        return self.run("bookmark", file=file, folder=folder, search=search, url=url, title=title)

    # ------------------------------------------------------------------
    # Vault info
    # ------------------------------------------------------------------

    def vault_info(self, *, info: Optional[str] = None) -> CLIResult:
        """Show vault info (name, path, files, folders, size)."""
        return self.run("vault", info=info)

    def vaults(self, *, verbose: bool = True) -> CLIResult:
        """List all known vaults."""
        return self.run("vaults", verbose=verbose or None)

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    def workspace(self) -> CLIResult:
        """Show workspace tree."""
        return self.run("workspace")

    def tabs(self) -> CLIResult:
        """List open tabs."""
        return self.run("tabs")

    def recents(self) -> CLIResult:
        """List recently opened files."""
        return self.run("recents")

    # ------------------------------------------------------------------
    # Word count
    # ------------------------------------------------------------------

    def wordcount(
        self,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        words: bool = False,
        characters: bool = False,
    ) -> CLIResult:
        """Count words and characters."""
        return self.run("wordcount", file=file, path=path, words=words or None, characters=characters or None)

    # ------------------------------------------------------------------
    # Developer / eval
    # ------------------------------------------------------------------

    def eval(self, code: str) -> CLIResult:
        """Execute JavaScript in the Obsidian app context."""
        return self.run("eval", code=code)

    # ------------------------------------------------------------------
    # Convenience / higher-level helpers
    # ------------------------------------------------------------------

    def search_json(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        """Search and return parsed JSON results."""
        r = self.search(query, format="json", **kwargs)
        try:
            return r.json()
        except (json.JSONDecodeError, ValueError):
            return []

    def search_context_json(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        """Search with context and return parsed JSON results."""
        r = self.search_context(query, format="json", **kwargs)
        try:
            return r.json()
        except (json.JSONDecodeError, ValueError):
            return []

    def tags_json(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """Get tags as parsed JSON."""
        r = self.tags(format="json", **kwargs)
        try:
            return r.json()
        except (json.JSONDecodeError, ValueError):
            return []

    def files_list(self, folder: Optional[str] = None, ext: Optional[str] = None) -> List[str]:
        """Get a list of file paths."""
        r = self.files(folder=folder, ext=ext)
        return r.lines()

    def folders_list(self, folder: Optional[str] = None) -> List[str]:
        """Get a list of folder paths."""
        r = self.folders(folder=folder)
        return r.lines()

    def exists(self, file: Optional[str] = None, *, path: Optional[str] = None) -> bool:
        """Check if a file exists in the vault."""
        r = self.run("file", file=file, path=path)
        # CLI returns exit code 0 but prints "Error: File ... not found." for missing files
        if "not found" in r.text.lower():
            return False
        return r.ok

    def daily_tasks(self, *, todo: bool = True) -> CLIResult:
        """Get tasks from today's daily note."""
        return self.tasks(daily=True, todo=todo)


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def obsidian(vault: Optional[str] = None) -> Obsidian:
    """Create an Obsidian client. Shorthand for Obsidian(vault=vault)."""
    return Obsidian(vault=vault)


if __name__ == "__main__":
    import argparse

    # Force UTF-8 for stdin/stdout so piped Unicode (arrows, em-dashes, etc.)
    # survives PowerShell → Python on Windows (default is cp1252).
    if sys.platform == "win32":
        for stream in ("stdin", "stdout", "stderr"):
            s = getattr(sys, stream)
            if hasattr(s, "reconfigure"):
                s.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Obsidian CLI wrapper — pipe-friendly vault operations.",
        epilog=(
            "Content actions (create/append/prepend) read from stdin when "
            "--content is omitted. Use 'raw <cmd> key=value ...' to pass any "
            "Obsidian CLI command straight through."
        ),
    )
    parser.add_argument(
        "action",
        help=(
            "Content: create, append, prepend. Read/list: read, info, search, "
            "search-context, files, folders, tags, tag, backlinks, links, orphans, "
            "tasks, properties, property-read, outline. Mutate: move, rename, "
            "delete, property-set, property-remove. Escape hatch: raw."
        ),
    )
    parser.add_argument("--path", required=False, help="Vault-relative path (e.g. Research/Library/note.md).")
    parser.add_argument("--file", required=False, help="File name (Obsidian title match).")
    parser.add_argument("--vault", required=False, help="Target vault name.")
    parser.add_argument("--content", required=False, help="Inline content (if omitted, reads stdin).")
    parser.add_argument("--to", required=False, help="Destination path for move (missing folders are created).")
    parser.add_argument("--name", required=False, help="New name (rename) or property/tag name.")
    parser.add_argument("--value", required=False, help="Value for property-set.")
    parser.add_argument("--query", required=False, help="Search query (for search/search-context actions).")
    parser.add_argument("--limit", required=False, type=int, help="Result limit for search actions.")
    parser.add_argument("--folder", required=False, help="Folder filter for files/folders.")
    parser.add_argument("--ext", required=False, help="Extension filter for files.")
    parser.add_argument("--format", required=False, choices=["text", "json"], default="text",
                        help="Output format for search/tags/etc.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing file on create.")
    parser.add_argument("--permanent", action="store_true", help="Permanent delete (skip trash).")
    parser.add_argument("--template", required=False, help="Template name for create.")
    parser.add_argument("rest", nargs="*", help="For 'raw': <command> [key=value ...].")

    args = parser.parse_args()
    ob = Obsidian(vault=args.vault)
    action = args.action

    def _emit(result: Union[CLIResult, str]) -> None:
        """Print a result and exit with the right code.

        Some mutating CLI commands (move/delete) return exit 0 even on error,
        so an "Error:" text prefix is also treated as failure.
        """
        if isinstance(result, str):
            print(result)
            sys.exit(0)
        text = result.text
        if text.startswith("Error:") or not result.ok:
            print(f"FAIL: {result.stderr or text}", file=sys.stderr)
            sys.exit(1)
        print(text if text else "OK")
        sys.exit(0)

    if args.action == "info":
        print(ob.vault_info())
        sys.exit(0)

    if args.action == "read":
        print(ob.read(file=args.file, path=args.path))
        sys.exit(0)

    if args.action in {"search", "search-context"}:
        query = args.query
        if not query:
            if not sys.stdin.isatty():
                query = sys.stdin.read().strip()
            else:
                parser.error(f"'{args.action}' needs --query (or query via stdin).")

        if args.action == "search":
            r = ob.search(query, path=args.path, limit=args.limit, format=args.format)
        else:
            r = ob.search_context(query, path=args.path, limit=args.limit, format=args.format)

        if r.ok:
            print(r.text)
            sys.exit(0)

        print(f"FAIL: {r.stderr}", file=sys.stderr)
        sys.exit(1)

    # --- Escape hatch: pass any CLI command straight through -------------
    if action == "raw":
        if not args.rest:
            parser.error("'raw' needs a command, e.g. raw move path=A.md to=B/A.md")
        cmd, *toks = args.rest
        kwargs: Dict[str, Any] = {}
        for tok in toks:
            key, sep, val = tok.partition("=")
            kwargs[key] = val if sep else True
        _emit(ob.run(cmd, **kwargs))

    # --- Read/list actions that print text -------------------------------
    readers = {
        "files": lambda: ob.files(folder=args.folder, ext=args.ext),
        "folders": lambda: ob.folders(folder=args.folder),
        "tags": lambda: ob.tags(format=args.format),
        "backlinks": lambda: ob.backlinks(file=args.file, path=args.path),
        "links": lambda: ob.links(file=args.file, path=args.path),
        "orphans": lambda: ob.orphans(),
        "tasks": lambda: ob.tasks(file=args.file, path=args.path),
        "properties": lambda: ob.properties(file=args.file, path=args.path),
        "outline": lambda: ob.outline(file=args.file, path=args.path),
    }
    if action in readers:
        _emit(readers[action]())

    if action == "tag":
        name = args.name or args.query
        if not name:
            parser.error("'tag' needs --name (the tag, without #).")
        _emit(ob.tag_info(name))

    if action == "property-read":
        if not args.name:
            parser.error("'property-read' needs --name.")
        _emit(ob.property_read(args.name, file=args.file, path=args.path))

    # --- Mutating actions ------------------------------------------------
    if action == "move":
        if not args.to:
            parser.error("'move' needs --to (destination path).")
        _emit(ob.move(file=args.file, path=args.path, to=args.to))

    if action == "rename":
        if not args.name:
            parser.error("'rename' needs --name (new file name).")
        _emit(ob.rename(file=args.file, path=args.path, name=args.name))

    if action == "delete":
        _emit(ob.delete(file=args.file, path=args.path, permanent=args.permanent))

    if action == "property-set":
        if not args.name or args.value is None:
            parser.error("'property-set' needs --name and --value.")
        _emit(ob.property_set(args.name, args.value, file=args.file, path=args.path))

    if action == "property-remove":
        if not args.name:
            parser.error("'property-remove' needs --name.")
        _emit(ob.property_remove(args.name, file=args.file, path=args.path))

    # For create/append/prepend — get content from --content or stdin
    content = args.content
    if content is None:
        if sys.stdin.isatty():
            parser.error(f"'{args.action}' needs content. Pipe via stdin or pass --content.")
        content = sys.stdin.read()

    # Strip UTF-8 BOM that PowerShell injects when piping via heredoc
    content = content.lstrip("\ufeff")

    if args.action == "create":
        r = ob.create(path=args.path, name=args.file, content=content,
                      overwrite=args.overwrite, template=args.template)
    elif args.action == "append":
        r = ob.append(content, file=args.file, path=args.path)
    elif args.action == "prepend":
        r = ob.prepend(content, file=args.file, path=args.path)
    else:
        parser.error(f"Unknown action: {args.action}")

    if r.ok:
        print("OK")
    else:
        print(f"FAIL: {r.stderr}", file=sys.stderr)
        sys.exit(1)
