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
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CLIResult:
    """Raw result from an Obsidian CLI call."""

    stdout: str
    stderr: str
    returncode: int
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
                cmd.append(f"{key}={value}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
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

    def read(self, file: Optional[str] = None, *, path: Optional[str] = None) -> str:
        """Read a file's contents. Returns the text."""
        r = self.run("read", file=file, path=path)
        return r.text

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
        """Create a new note."""
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
        """Append content to a file."""
        return self.run("append", content=content, file=file, path=path, inline=inline or None)

    def prepend(
        self,
        content: str,
        file: Optional[str] = None,
        *,
        path: Optional[str] = None,
        inline: bool = False,
    ) -> CLIResult:
        """Prepend content after frontmatter."""
        return self.run("prepend", content=content, file=file, path=path, inline=inline or None)

    def move(self, file: Optional[str] = None, *, path: Optional[str] = None, to: str) -> CLIResult:
        """Move or rename a file. Auto-updates internal links."""
        return self.run("move", file=file, path=path, to=to)

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
        counts: bool = True,
        sort: Optional[Literal["count", "name"]] = None,
        format: Literal["tsv", "json", "csv"] = "tsv",
    ) -> CLIResult:
        """List tags in the vault or for a specific file."""
        return self.run(
            "tags",
            file=file,
            path=path,
            counts=counts or None,
            sort=sort,
            format=format if format != "tsv" else None,
        )

    def tag_info(self, name: str, *, verbose: bool = True) -> CLIResult:
        """Get info about a specific tag (count + file list)."""
        return self.run("tag", name=name, verbose=verbose or None)

    def tags_for_file(self, file: Optional[str] = None, *, path: Optional[str] = None) -> CLIResult:
        """Get tags for a specific file."""
        return self.run("tags", file=file, path=path, active=True if not file and not path else None)

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
    # Quick smoke test
    ob = Obsidian()
    print(f"Binary: {ob._binary}")
    info = ob.vault_info()
    print(f"Vault: {info}")
    print(f"Files: {ob.files(total=True)}")
