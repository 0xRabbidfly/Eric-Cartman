"""Obsidian CLI ↔ wrapper sync audit.

Compares the live Obsidian CLI's command inventory against obsidian.py
to surface new commands, new parameters, and deprecated items after a
CLI upgrade.

Usage:
    # Show coverage report in terminal
    python .github/skills/obsidian/scripts/cli_sync.py

    # Save manifest (snapshot of current CLI state)
    python .github/skills/obsidian/scripts/cli_sync.py --save

    # Diff against saved manifest (what changed since last sync)
    python .github/skills/obsidian/scripts/cli_sync.py --diff

    # Machine-readable JSON output
    python .github/skills/obsidian/scripts/cli_sync.py --json

    # Generate a Markdown upgrade guide for the AI to follow
    python .github/skills/obsidian/scripts/cli_sync.py --guide
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
WRAPPER_PATH = SCRIPT_DIR / "obsidian.py"
MANIFEST_PATH = SCRIPT_DIR / ".cli-manifest.json"
SKILL_DIR = SCRIPT_DIR.parent


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class CLIParam:
    """A parameter or flag on a CLI command."""

    name: str
    description: str = ""
    required: bool = False
    values: Optional[str] = None  # e.g. "json|tsv|csv"


@dataclass
class CLICommand:
    """A command in the Obsidian CLI."""

    name: str
    description: str = ""
    params: List[CLIParam] = field(default_factory=list)
    category: str = ""  # e.g. "Developer"

    @property
    def param_names(self) -> Set[str]:
        return {p.name for p in self.params}


@dataclass
class WrapperMethod:
    """A method in obsidian.py that wraps a CLI command."""

    method_name: str
    cli_command: str  # the string passed to self.run()
    params: Set[str] = field(default_factory=set)  # kwargs passed through
    line_number: int = 0


@dataclass
class SyncReport:
    """Full audit result."""

    cli_version: str
    wrapper_version_tag: str  # from manifest or "unknown"
    total_cli_commands: int
    total_wrapped: int
    coverage_pct: float
    wrapped_commands: List[str]
    unwrapped_commands: List[str]
    missing_params: Dict[str, List[str]]  # command -> [param, ...]
    extra_methods: List[str]  # wrapper methods with no CLI match
    categories: Dict[str, List[str]]  # category -> [commands]


# ---------------------------------------------------------------------------
# CLI introspection
# ---------------------------------------------------------------------------


def get_cli_version() -> str:
    """Get the installed Obsidian CLI version."""
    try:
        r = subprocess.run(
            ["obsidian", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Try .com on Windows
        try:
            r = subprocess.run(
                ["obsidian.com", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "unknown"


def parse_cli_help(help_text: str) -> List[CLICommand]:
    """Parse `obsidian help` output into structured commands."""
    commands: List[CLICommand] = []
    current_cmd: Optional[CLICommand] = None
    current_category = ""

    for line in help_text.splitlines():
        # Category headers like "Developer:"
        if re.match(r"^[A-Z][a-z]+.*:$", line.strip()):
            current_category = line.strip().rstrip(":")
            continue

        # Command line: 2-space indent, starts with word
        cmd_match = re.match(r"^  ([a-z][a-z0-9:_]*)(\s{2,}(.+))?$", line)
        if cmd_match:
            if current_cmd:
                commands.append(current_cmd)
            current_cmd = CLICommand(
                name=cmd_match.group(1),
                description=(cmd_match.group(3) or "").strip(),
                category=current_category,
            )
            continue

        # Parameter line: 4-space indent
        param_match = re.match(
            r'^    ([a-z][a-zA-Z0-9_]*)(?:=(?:<[^>]+>|"([^"]+)"))?(\s+- (.+))?$',
            line,
        )
        if param_match and current_cmd:
            name = param_match.group(1)
            desc = (param_match.group(4) or "").strip()
            required = "(required)" in desc
            # Extract value options like "json|tsv|csv"
            values_match = re.search(r"=([a-z|]+)", line)
            values = values_match.group(1) if values_match else None
            current_cmd.params.append(
                CLIParam(name=name, description=desc, required=required, values=values)
            )
            continue

    if current_cmd:
        commands.append(current_cmd)

    return commands


def get_cli_commands() -> List[CLICommand]:
    """Run `obsidian help` and parse the full command inventory."""
    for binary in ("obsidian", "obsidian.com"):
        try:
            r = subprocess.run(
                [binary, "help"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode == 0 or r.stdout.strip():
                return parse_cli_help(r.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return []


# ---------------------------------------------------------------------------
# Wrapper introspection (static analysis of obsidian.py)
# ---------------------------------------------------------------------------


def parse_wrapper() -> List[WrapperMethod]:
    """Parse obsidian.py to find all self.run() calls and their mappings."""
    source = WRAPPER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(WRAPPER_PATH))

    methods: List[WrapperMethod] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        # Skip private/dunder methods and __init__
        if node.name.startswith("_") or node.name == "run":
            continue

        # Find self.run(...) calls inside the method
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            # Check for self.run(...)
            if (
                isinstance(child.func, ast.Attribute)
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "self"
                and child.func.attr == "run"
            ):
                # First positional arg is the CLI command string
                cli_cmd = ""
                if child.args:
                    arg = child.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        cli_cmd = arg.value

                # Collect keyword argument names (params forwarded to CLI)
                params = set()
                for kw in child.keywords:
                    if kw.arg and kw.arg not in ("timeout",):
                        params.add(kw.arg)

                if cli_cmd:
                    methods.append(
                        WrapperMethod(
                            method_name=node.name,
                            cli_command=cli_cmd,
                            params=params,
                            line_number=node.lineno,
                        )
                    )
                break  # Only care about the first self.run() per method

    return methods


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------


def build_report(
    cli_commands: List[CLICommand],
    wrapper_methods: List[WrapperMethod],
    cli_version: str,
) -> SyncReport:
    """Compare CLI commands against wrapper methods."""
    cli_by_name = {c.name: c for c in cli_commands}
    wrapped_cmds = {m.cli_command for m in wrapper_methods}

    # Grouped by category
    categories: Dict[str, List[str]] = {}
    for cmd in cli_commands:
        cat = cmd.category or "General"
        categories.setdefault(cat, []).append(cmd.name)

    # Unwrapped = CLI commands with no wrapper method
    unwrapped = sorted(set(cli_by_name.keys()) - wrapped_cmds)
    wrapped = sorted(wrapped_cmds & set(cli_by_name.keys()))

    # Missing params = CLI params not forwarded by the wrapper
    missing_params: Dict[str, List[str]] = {}
    for method in wrapper_methods:
        if method.cli_command in cli_by_name:
            cli_cmd = cli_by_name[method.cli_command]
            cli_param_names = cli_cmd.param_names
            wrapped_params = method.params
            missing = sorted(cli_param_names - wrapped_params)
            if missing:
                missing_params[method.cli_command] = missing

    # Extra methods = wrapper methods whose CLI command doesn't exist
    extra = sorted(
        m.method_name
        for m in wrapper_methods
        if m.cli_command not in cli_by_name
    )

    total_cli = len(cli_commands)
    total_wrapped = len(wrapped)
    coverage = (total_wrapped / total_cli * 100) if total_cli else 0

    return SyncReport(
        cli_version=cli_version,
        wrapper_version_tag="",
        total_cli_commands=total_cli,
        total_wrapped=total_wrapped,
        coverage_pct=round(coverage, 1),
        wrapped_commands=wrapped,
        unwrapped_commands=unwrapped,
        missing_params=missing_params,
        extra_methods=extra,
        categories=categories,
    )


# ---------------------------------------------------------------------------
# Manifest (snapshot) management
# ---------------------------------------------------------------------------


def save_manifest(cli_commands: List[CLICommand], cli_version: str) -> Path:
    """Save current CLI state as a JSON manifest for future diffing."""
    data = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "cli_version": cli_version,
        "commands": {
            cmd.name: {
                "description": cmd.description,
                "category": cmd.category,
                "params": {
                    p.name: {
                        "description": p.description,
                        "required": p.required,
                        "values": p.values,
                    }
                    for p in cmd.params
                },
            }
            for cmd in cli_commands
        },
    }
    MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return MANIFEST_PATH


def load_manifest() -> Optional[Dict[str, Any]]:
    """Load a previously saved manifest."""
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def diff_manifests(
    old: Dict[str, Any], new_cmds: List[CLICommand], new_version: str
) -> Dict[str, Any]:
    """Diff a saved manifest against the current CLI state."""
    old_cmds = old.get("commands", {})
    new_by_name = {c.name: c for c in new_cmds}

    added_commands = sorted(set(new_by_name.keys()) - set(old_cmds.keys()))
    removed_commands = sorted(set(old_cmds.keys()) - set(new_by_name.keys()))

    added_params: Dict[str, List[str]] = {}
    removed_params: Dict[str, List[str]] = {}

    for name in sorted(set(old_cmds.keys()) & set(new_by_name.keys())):
        old_params = set(old_cmds[name].get("params", {}).keys())
        new_params = new_by_name[name].param_names
        ap = sorted(new_params - old_params)
        rp = sorted(old_params - new_params)
        if ap:
            added_params[name] = ap
        if rp:
            removed_params[name] = rp

    return {
        "old_version": old.get("cli_version", "unknown"),
        "new_version": new_version,
        "old_synced_at": old.get("synced_at", "unknown"),
        "added_commands": added_commands,
        "removed_commands": removed_commands,
        "added_params": added_params,
        "removed_params": removed_params,
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def format_report_text(report: SyncReport) -> str:
    """Human-readable coverage report."""
    lines = [
        "=" * 60,
        "  Obsidian CLI ↔ Wrapper Sync Report",
        "=" * 60,
        f"  CLI version:   {report.cli_version}",
        f"  Commands:      {report.total_wrapped}/{report.total_cli_commands} wrapped ({report.coverage_pct}%)",
        "",
    ]

    if report.unwrapped_commands:
        lines.append("── Unwrapped Commands (new or intentionally skipped) ──")
        # Group by category
        cat_map: Dict[str, List[str]] = {}
        for cmd in report.unwrapped_commands:
            for cat, cmds in report.categories.items():
                if cmd in cmds:
                    cat_map.setdefault(cat, []).append(cmd)
                    break
            else:
                cat_map.setdefault("Uncategorized", []).append(cmd)
        for cat in sorted(cat_map):
            lines.append(f"  [{cat}]")
            for cmd in cat_map[cat]:
                lines.append(f"    • {cmd}")
        lines.append("")

    if report.missing_params:
        lines.append("── Missing Parameters (wrapped cmd, unwrapped params) ──")
        for cmd, params in sorted(report.missing_params.items()):
            lines.append(f"  {cmd}: {', '.join(params)}")
        lines.append("")

    if report.extra_methods:
        lines.append("── Extra Wrapper Methods (no CLI match) ──")
        for m in report.extra_methods:
            lines.append(f"  • {m}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def format_diff_text(diff: Dict[str, Any]) -> str:
    """Human-readable diff report."""
    lines = [
        "=" * 60,
        "  Obsidian CLI Upgrade Diff",
        "=" * 60,
        f"  Previous: {diff['old_version']} (synced {diff['old_synced_at']})",
        f"  Current:  {diff['new_version']}",
        "",
    ]

    if diff["added_commands"]:
        lines.append("── New Commands ──")
        for cmd in diff["added_commands"]:
            lines.append(f"  + {cmd}")
        lines.append("")

    if diff["removed_commands"]:
        lines.append("── Removed Commands ──")
        for cmd in diff["removed_commands"]:
            lines.append(f"  - {cmd}")
        lines.append("")

    if diff["added_params"]:
        lines.append("── New Parameters ──")
        for cmd, params in sorted(diff["added_params"].items()):
            lines.append(f"  {cmd}: +{', '.join(params)}")
        lines.append("")

    if diff["removed_params"]:
        lines.append("── Removed Parameters ──")
        for cmd, params in sorted(diff["removed_params"].items()):
            lines.append(f"  {cmd}: -{', '.join(params)}")
        lines.append("")

    if not any(
        diff[k]
        for k in ("added_commands", "removed_commands", "added_params", "removed_params")
    ):
        lines.append("  No changes detected since last sync.")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def format_upgrade_guide(
    report: SyncReport,
    cli_commands: List[CLICommand],
    diff: Optional[Dict[str, Any]] = None,
) -> str:
    """Markdown upgrade guide an AI agent can follow to update the wrapper."""
    cli_by_name = {c.name: c for c in cli_commands}
    lines = [
        "# Obsidian Skill Upgrade Guide",
        "",
        f"**CLI version**: {report.cli_version}",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Coverage**: {report.total_wrapped}/{report.total_cli_commands} ({report.coverage_pct}%)",
        "",
    ]

    if diff:
        lines.append("## What Changed Since Last Sync")
        lines.append("")
        if diff["added_commands"]:
            lines.append("### New Commands")
            lines.append("")
            for cmd in diff["added_commands"]:
                c = cli_by_name.get(cmd)
                desc = f" — {c.description}" if c else ""
                lines.append(f"- `{cmd}`{desc}")
            lines.append("")
        if diff["removed_commands"]:
            lines.append("### Removed Commands")
            lines.append("")
            for cmd in diff["removed_commands"]:
                lines.append(f"- `{cmd}` (remove from wrapper)")
            lines.append("")
        if diff["added_params"]:
            lines.append("### New Parameters on Existing Commands")
            lines.append("")
            for cmd, params in sorted(diff["added_params"].items()):
                lines.append(f"- `{cmd}`: {', '.join(f'`{p}`' for p in params)}")
            lines.append("")

    # Task list for unwrapped commands
    if report.unwrapped_commands:
        lines.append("## Unwrapped Commands to Evaluate")
        lines.append("")
        lines.append("Decide for each: **wrap** (add method to obsidian.py) or **skip** (intentional).")
        lines.append("")
        for cmd in report.unwrapped_commands:
            c = cli_by_name.get(cmd)
            if c:
                desc = c.description
                params_str = ", ".join(
                    f"`{p.name}`{'*' if p.required else ''}"
                    for p in c.params
                )
                lines.append(f"- [ ] `{cmd}` — {desc}")
                if params_str:
                    lines.append(f"      Params: {params_str}")
            else:
                lines.append(f"- [ ] `{cmd}`")
        lines.append("")

    # Missing params
    if report.missing_params:
        lines.append("## Missing Parameters on Wrapped Commands")
        lines.append("")
        lines.append("These CLI parameters exist but aren't forwarded by the wrapper method.")
        lines.append("")
        for cmd, params in sorted(report.missing_params.items()):
            c = cli_by_name.get(cmd)
            lines.append(f"### `{cmd}`")
            for p_name in params:
                if c:
                    p = next((x for x in c.params if x.name == p_name), None)
                    if p:
                        lines.append(f"- [ ] `{p_name}` — {p.description}")
                        continue
                lines.append(f"- [ ] `{p_name}`")
            lines.append("")

    lines.append("## After Updating")
    lines.append("")
    lines.append("1. Update `obsidian.py` with new/changed methods")
    lines.append("2. Update the Quick Reference in `SKILL.md`")
    lines.append("3. Update `README.md` method table if categories changed")
    lines.append("4. Run `python .github/skills/obsidian/scripts/cli_sync.py --save` to snapshot")
    lines.append("5. Commit with: `feat(obsidian): sync wrapper with CLI vX.Y.Z`")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Audit Obsidian CLI ↔ wrapper coverage and track upgrades.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save current CLI state as manifest for future diffing.",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Diff current CLI against saved manifest.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of text.",
    )
    parser.add_argument(
        "--guide",
        action="store_true",
        help="Generate Markdown upgrade guide.",
    )
    args = parser.parse_args()

    # Gather data
    cli_version = get_cli_version()
    if cli_version == "unknown":
        print("ERROR: Could not reach Obsidian CLI. Is Obsidian running?", file=sys.stderr)
        sys.exit(1)

    cli_commands = get_cli_commands()
    if not cli_commands:
        print("ERROR: Could not parse CLI help output.", file=sys.stderr)
        sys.exit(1)

    wrapper_methods = parse_wrapper()
    report = build_report(cli_commands, wrapper_methods, cli_version)

    # --save: snapshot current state
    if args.save:
        path = save_manifest(cli_commands, cli_version)
        print(f"Manifest saved: {path}")
        print(f"  CLI version: {cli_version}")
        print(f"  Commands:    {len(cli_commands)}")
        return

    # --diff: compare against manifest
    diff_data = None
    if args.diff:
        manifest = load_manifest()
        if not manifest:
            print("No manifest found. Run with --save first.", file=sys.stderr)
            sys.exit(1)
        diff_data = diff_manifests(manifest, cli_commands, cli_version)

    # --json output
    if args.json_output:
        output: Dict[str, Any] = {
            "report": {
                "cli_version": report.cli_version,
                "total_cli_commands": report.total_cli_commands,
                "total_wrapped": report.total_wrapped,
                "coverage_pct": report.coverage_pct,
                "unwrapped_commands": report.unwrapped_commands,
                "missing_params": report.missing_params,
                "extra_methods": report.extra_methods,
            }
        }
        if diff_data:
            output["diff"] = diff_data
        print(json.dumps(output, indent=2))
        return

    # --guide: markdown upgrade guide
    if args.guide:
        print(format_upgrade_guide(report, cli_commands, diff_data))
        return

    # Default: text report
    if diff_data:
        print(format_diff_text(diff_data))
        print()
    print(format_report_text(report))


if __name__ == "__main__":
    main()
