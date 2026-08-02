#!/usr/bin/env python3
"""
obsidian-vault-lint — Weekly vault structural maintenance.

Phases:
  1.  Inventory        (read-only, always runs)
  2.  Fixes            (autonomous writes — safe, reversible)
  3.  Taxonomy repair  (tag normalization + folder move proposals)
  4.  MOC reorg        (autonomous + approval-gated proposals)
  5.  Report           (standalone log in Research/Logs)

Semantic work — connection discovery, thesis clustering, emergent topic
detection — is NOT done here. That belongs to the metabolism pipeline
(obsidian-connection-detector -> obsidian-thesis-tracker ->
obsidian-vault-report) and obsidian-weekly-brain. This skill only keeps the
vault's structure clean.

Usage:
    python scripts/lint.py                       # Full run (all phases)
    python scripts/lint.py --dry-run             # Preview, no writes
    python scripts/lint.py --phase 1             # Inventory only
    python scripts/lint.py --phase 2             # Fixes only
    python scripts/lint.py --phase 3             # Taxonomy repair only
    python scripts/lint.py --phase 4             # MOC reorg only
    python scripts/lint.py --verbose             # Verbose output
    python scripts/lint.py --stale-days 14       # Override stale threshold (default: 7)
"""
import argparse
import io
import subprocess
import sys
from datetime import date
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent.resolve()
SKILLS_ROOT = SCRIPT_DIR.parent.parent

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SKILLS_ROOT / "obsidian" / "scripts"))

from obsidian import Obsidian
from inventory import collect_inventory, LOG_FOLDER
from fixes import apply_fixes
from taxonomy import run_taxonomy_repair, format_taxonomy_report
from moc import reorganize_moc, format_moc_proposals

GIT_EXE = r"C:\Program Files\Git\cmd\git.exe"
DEFAULT_VAULT_PATH = r"C:/Users/nuno_/Documents/Obsidian Vault"



def main():
    parser = argparse.ArgumentParser(
        description="obsidian-vault-lint — weekly vault structural maintenance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--phase", type=str, choices=["1", "2", "3", "4"], metavar="N",
                        help="Run a specific phase (1, 2, 3, 4) only")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview all changes without writing to vault")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-item detail during each phase")
    parser.add_argument("--stale-days", type=int, default=7,
                        help="Days before a Recently Added MOC entry is considered stale (default: 7)")
    args = parser.parse_args()

    run_date = date.today().isoformat()
    ob = Obsidian()

    if args.dry_run:
        print("[lint] DRY RUN — no changes will be written to vault")

    inv = None
    fix_result = None
    tax_result = None
    moc_result = None

    # -- Phase 1: Inventory -------------------------------------------------------
    if args.phase is None or args.phase == "1":
        print("\n=== Phase 1: Inventory ===")
        inv = collect_inventory(stale_days=args.stale_days, verbose=args.verbose)
        _print_inventory(inv)
        if args.phase == "1":
            return

    # -- Phase 2: Autonomous Fixes ------------------------------------------------
    if args.phase is None or args.phase == "2":
        print("\n=== Phase 2: Autonomous Fixes ===")
        if inv is None:
            inv = collect_inventory(stale_days=args.stale_days, verbose=args.verbose)
        fix_result = apply_fixes(inv, dry_run=args.dry_run, verbose=args.verbose)
        _print_fixes(fix_result)
        if args.phase == "2":
            return

    # -- Phase 3: Taxonomy Repair --------------------------------------------------
    if args.phase is None or args.phase == "3":
        print("\n=== Phase 3: Taxonomy Repair ===")
        if inv is None:
            inv = collect_inventory(stale_days=args.stale_days, verbose=args.verbose)
        tax_result = run_taxonomy_repair(
            similar_tags=inv.similar_tags,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        _print_taxonomy(tax_result)
        if tax_result and _has_taxonomy_proposals(tax_result):
            path = f"{LOG_FOLDER}/vault-lint-{run_date}-taxonomy.md"
            content = format_taxonomy_report(tax_result, run_date)
            if not args.dry_run:
                ob.create(path=path, content=content, overwrite=True)
                print(f"[lint] Taxonomy proposals written to: {path}")
            else:
                print(f"[lint] [DRY RUN] Taxonomy proposals — not written")
        if args.phase == "3":
            return

    # -- Phase 4: MOC Reorganization -----------------------------------------------
    if args.phase is None or args.phase == "4":
        print("\n=== Phase 4: MOC Reorganization ===")
        moc_result = reorganize_moc(dry_run=args.dry_run, verbose=args.verbose)
        _print_moc(moc_result)
        if moc_result.topic_moc_proposals:
            path = f"{LOG_FOLDER}/vault-lint-{run_date}-moc-proposals.md"
            content = format_moc_proposals(moc_result.topic_moc_proposals, run_date)
            if not args.dry_run:
                ob.create(path=path, content=content, overwrite=True)
                print(f"[lint] MOC proposals written to: {path}")
            else:
                print(f"[lint] [DRY RUN] {len(moc_result.topic_moc_proposals)} MOC proposals — not written")
        if args.phase == "4":
            return

    # -- Phase 5: Report -----------------------------------------------------------
    if args.phase is None:
        print("\n=== Phase 5: Report ===")
        report = _build_report(run_date, inv, fix_result, tax_result, moc_result)
        path = f"{LOG_FOLDER}/vault-lint-{run_date}.md"
        if not args.dry_run:
            ob.create(path=path, content=report, overwrite=True)
            print(f"\n[lint] Report saved to: {path}")

            # Git commit after successful full run (non-dry-run only)
            _git_commit_vault(run_date)
        else:
            print(f"\n[lint] [DRY RUN] Report not written")
        print("\n" + report)



def _git_commit_vault(run_date: str):
    """Stage and commit all vault changes after a full lint run.

    Uses the absolute path to git.exe since git may not be on PATH in
    automated/scheduled contexts (e.g. Task Scheduler).
    """
    try:
        vault_path = DEFAULT_VAULT_PATH

        # git add -A
        add_result = subprocess.run(
            [GIT_EXE, "add", "-A"],
            cwd=vault_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30,
        )
        if add_result.returncode != 0:
            print(f"[lint] git add failed: {add_result.stderr.strip()}", file=sys.stderr)
            return

        # git commit
        commit_msg = f"vault-lint: automated maintenance {run_date}"
        commit_result = subprocess.run(
            [GIT_EXE, "commit", "-m", commit_msg],
            cwd=vault_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30,
        )

        if commit_result.returncode == 0:
            print(f"[lint] Git commit successful: {commit_msg}")
            print(f"[lint] {commit_result.stdout.strip()}")
        elif "nothing to commit" in commit_result.stdout:
            print("[lint] Git: nothing to commit (no vault changes)")
        else:
            print(f"[lint] git commit failed: {commit_result.stderr.strip()}", file=sys.stderr)

    except FileNotFoundError:
        print(f"[lint] Git not found at {GIT_EXE} — skipping vault commit", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("[lint] Git command timed out — skipping vault commit", file=sys.stderr)
    except Exception as e:
        print(f"[lint] Git commit failed (non-fatal): {e}", file=sys.stderr)



def _print_inventory(inv):
    print(f"  Orphans:              {inv.orphan_count}")
    print(f"  Library notes:        {inv.library_note_count}")
    print(f"  Missing from MOC:     {len(inv.missing_from_moc)}")
    print(f"  Broken links:         {len(inv.broken_links)} in {len({b['file'] for b in inv.broken_links})} files")
    print(f"  Dead-ends (Research): {inv.deadend_count}")
    print(f"  Stale Recently Added: {len(inv.stale_recently_added)}")
    print(f"  Similar tag pairs:    {len(inv.similar_tags)}")


def _print_fixes(fix_result):
    if fix_result.changes:
        for c in fix_result.changes:
            print(f"  ✓ {c['detail']}")
    else:
        print("  No changes needed")


def _print_taxonomy(tax_result):
    if tax_result.tag_fixes_applied:
        print(f"  ✓ Tag normalization: {tax_result.tag_fixes_applied} notes fixed "
              f"({len(tax_result.tag_fix_details)} individual tags)")
    if tax_result.orphaned_tags:
        unique = len({t["tag"] for t in tax_result.orphaned_tags})
        print(f"  ⚠ Orphaned tags: {unique} tags not in canonical list")
    if tax_result.folder_move_proposals:
        print(f"  ⚠ Folder moves proposed: {len(tax_result.folder_move_proposals)}")
    if not tax_result.changes:
        print("  No taxonomy drift detected")


def _has_taxonomy_proposals(result) -> bool:
    """Check if taxonomy repair produced any proposals worth writing to a file."""
    return bool(
        result.folder_move_proposals
        or result.orphaned_tags
        or result.tag_fix_details
    )


def _print_moc(moc_result):
    if moc_result.changes:
        for c in moc_result.changes:
            print(f"  ✓ {c}")
    else:
        print("  No autonomous changes needed")
    if moc_result.topic_moc_proposals:
        for p in moc_result.topic_moc_proposals:
            print(f"  ⚠ Proposal: new Topic MOC for '{p['section']}' ({p['entry_count']} entries)")



def _build_report(run_date: str, inv, fix_result, tax_result, moc_result) -> str:
    lines = [
        f"# Vault Lint — {run_date}",
        "",
        "## Health Metrics",
    ]
    if inv:
        lines += [
            f"- Orphans: {inv.orphan_count}",
            f"- Library notes: {inv.library_note_count}",
            f"- Missing from Master MOC: {len(inv.missing_from_moc)}",
            f"- Broken links: {len(inv.broken_links)} across {len({b['file'] for b in inv.broken_links})} files",
            f"- Dead-ends in Research: {inv.deadend_count}",
            f"- Stale Recently Added entries: {len(inv.stale_recently_added)}",
            f"- Similar tag pairs flagged: {len(inv.similar_tags)}",
        ]

    lines += ["", "## Autonomous Changes"]
    all_changes = []
    if fix_result:
        all_changes += [c["detail"] for c in fix_result.changes]
    if tax_result:
        all_changes += [c["detail"] for c in tax_result.changes]
    if moc_result:
        all_changes += moc_result.changes
    if all_changes:
        for c in all_changes:
            lines.append(f"- {c}")
    else:
        lines.append("- None")

    lines += ["", "## Pending Review"]
    pending = []
    if tax_result and _has_taxonomy_proposals(tax_result):
        bp_count = len(tax_result.folder_move_proposals)
        pending.append(f"- `vault-lint-{run_date}-taxonomy.md` ({bp_count} folder move proposals)")
    if moc_result and moc_result.topic_moc_proposals:
        pending.append(f"- `vault-lint-{run_date}-moc-proposals.md` ({len(moc_result.topic_moc_proposals)} Topic MOC candidates)")
    if pending:
        lines += pending
    else:
        lines.append("- None")

    if inv and inv.similar_tags:
        lines += ["", "## Similar Tags (Review Manually)"]
        for t in inv.similar_tags[:15]:
            lines.append(f"- `{t['t1']}` ↔ `{t['t2']}` ({t['ratio']:.0%} similar)")

    # Taxonomy repair summary
    if tax_result and tax_result.tag_fix_details:
        lines += ["", "## Taxonomy Repair — Tag Fixes Applied"]
        for fix in tax_result.tag_fix_details[:10]:
            slug = fix["note_path"].rsplit("/", 1)[-1].replace(".md", "")
            lines.append(f"- [[{slug}]]: `{fix['old_tag']}` → `{fix['new_tag']}`")
        if len(tax_result.tag_fix_details) > 10:
            lines.append(f"- ... and {len(tax_result.tag_fix_details) - 10} more")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
