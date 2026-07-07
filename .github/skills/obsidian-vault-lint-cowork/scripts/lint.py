#!/usr/bin/env python3
"""obsidian-vault-lint-cowork - Cowork-native fork of the weekly vault maintenance pipeline."""
import argparse
import io
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from obsidian import Obsidian
from inventory import collect_inventory, LOG_FOLDER
from fixes import apply_fixes
from connections import discover_connections, format_connections_report, apply_connection_proposals
from moc import reorganize_moc, format_moc_proposals
from recommend import recommend_reading, format_recommendations, render_report_section


def main():
    parser = argparse.ArgumentParser(description="obsidian-vault-lint-cowork - weekly vault maintenance (Cowork-native)")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3, 4, 5], metavar="N")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--stale-days", type=int, default=7)
    args = parser.parse_args()

    run_date = date.today().isoformat()
    ob = Obsidian()
    print(f"[lint] Vault: {ob.vault_path}")

    if args.dry_run:
        print("[lint] DRY RUN - no changes will be written to vault")

    if args.phase == 3 and args.apply:
        _apply_connections(ob, run_date, dry_run=args.dry_run, verbose=args.verbose)
        return

    inv = None
    fix_result = None
    moc_result = None
    conn_proposals = []
    rec_result = None

    if args.phase is None or args.phase == 1:
        print("\n=== Phase 1: Inventory ===")
        inv = collect_inventory(stale_days=args.stale_days, verbose=args.verbose)
        _print_inventory(inv)
        if args.phase == 1:
            return

    if args.phase is None or args.phase == 2:
        print("\n=== Phase 2: Autonomous Fixes ===")
        if inv is None:
            inv = collect_inventory(stale_days=args.stale_days, verbose=args.verbose)
        fix_result = apply_fixes(inv, dry_run=args.dry_run, verbose=args.verbose)
        _print_fixes(fix_result)
        if args.phase == 2:
            return

    if args.phase is None or args.phase == 3:
        print("\n=== Phase 3: Connection Discovery ===")
        if inv is None:
            inv = collect_inventory(stale_days=args.stale_days)
        conn_proposals = discover_connections(inv.orphans, dry_run=args.dry_run, verbose=args.verbose)
        if conn_proposals:
            path = f"{LOG_FOLDER}/vault-lint-{run_date}-connections.md"
            content = format_connections_report(conn_proposals, run_date)
            if not args.dry_run:
                ob.create(path=path, content=content, overwrite=True)
                print(f"[lint] Connection proposals written to: {path}")
            else:
                print(f"[lint] [DRY RUN] {len(conn_proposals)} proposals - not written")
        else:
            print("[lint] No connection proposals generated (no xAI key or no Library orphans)")
        if args.phase == 3:
            return

    if args.phase is None or args.phase == 4:
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
                print(f"[lint] [DRY RUN] {len(moc_result.topic_moc_proposals)} MOC proposals - not written")
        if args.phase == 4:
            return

    if args.phase is None or args.phase == 5:
        print("\n=== Phase 5: Reading Recommendations ===")
        rec_result = recommend_reading(verbose=args.verbose)
        _print_recommendations(rec_result)
        if rec_result.recommendations:
            path = f"{LOG_FOLDER}/vault-lint-{run_date}-reading.md"
            content = format_recommendations(rec_result, run_date)
            if not args.dry_run:
                ob.create(path=path, content=content, overwrite=True)
                print(f"[lint] Reading recommendations written to: {path}")
            else:
                print(f"[lint] [DRY RUN] {len(rec_result.recommendations)} recommendations - not written")
        if args.phase == 5:
            return

    if args.phase is None:
        print("\n=== Phase 6: Report ===")
        report = _build_report(run_date, inv, fix_result, moc_result, conn_proposals, rec_result)
        path = f"{LOG_FOLDER}/vault-lint-{run_date}.md"
        if not args.dry_run:
            ob.create(path=path, content=report, overwrite=True)
            print(f"\n[lint] Report saved to: {path}")
            _git_commit_vault(str(ob.vault_path), run_date)
        else:
            print(f"\n[lint] [DRY RUN] Report not written")
        print("\n" + report)


def _git_commit_vault(vault_path: str, run_date: str):
    git = shutil.which("git")
    if not git:
        print("[lint] git not on PATH - skipping vault commit", file=sys.stderr)
        return
    if not (Path(vault_path) / ".git").exists():
        print(f"[lint] {vault_path} is not a git repo - skipping commit", file=sys.stderr)
        return
    try:
        add_result = subprocess.run([git, "add", "-A"], cwd=vault_path, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if add_result.returncode != 0:
            print(f"[lint] git add failed: {add_result.stderr.strip()}", file=sys.stderr)
            return
        commit_msg = f"vault-lint: automated maintenance {run_date}"
        commit_result = subprocess.run([git, "commit", "-m", commit_msg], cwd=vault_path, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if commit_result.returncode == 0:
            print(f"[lint] Git commit successful: {commit_msg}")
            print(f"[lint] {commit_result.stdout.strip()}")
        elif "nothing to commit" in commit_result.stdout:
            print("[lint] Git: nothing to commit (no vault changes)")
        else:
            print(f"[lint] git commit failed: {commit_result.stderr.strip()}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("[lint] Git command timed out - skipping vault commit", file=sys.stderr)
    except Exception as e:
        print(f"[lint] Git commit failed (non-fatal): {e}", file=sys.stderr)


def _apply_connections(ob, run_date, dry_run, verbose):
    log_files = ob.files(folder=LOG_FOLDER, ext="md").lines()
    proposal_files = sorted([f for f in log_files if "connections" in f])
    if not proposal_files:
        print("[lint] No connection proposal files found in Research/Logs")
        return
    latest = proposal_files[-1]
    print(f"[lint] Applying proposals from: {latest}")
    count = apply_connection_proposals(latest, dry_run=dry_run, verbose=verbose)
    verb = "Would apply" if dry_run else "Applied"
    print(f"[lint] {verb} connections to {count} notes")


def _print_inventory(inv):
    orphan_noise = inv.orphans_unscoped_count - inv.orphan_count
    broken_noise = inv.broken_links_unscoped_count - len(inv.broken_links)
    print(f"  Orphans:              {inv.orphan_count}" + (f"  (filtered {orphan_noise} out-of-scope as noise)" if orphan_noise else ""))
    print(f"  Library notes:        {inv.library_note_count}")
    print(f"  Missing from MOC:     {len(inv.missing_from_moc)}")
    print(f"  Broken links:         {len(inv.broken_links)} in {len({b['file'] for b in inv.broken_links})} files" + (f"  (filtered {broken_noise} out-of-scope as noise)" if broken_noise else ""))
    print(f"  Dead-ends (Research): {inv.deadend_count}")
    print(f"  Stale Recently Added: {len(inv.stale_recently_added)}")
    print(f"  Similar tag pairs:    {len(inv.similar_tags)}")


def _print_fixes(fix_result):
    if fix_result.changes:
        for c in fix_result.changes:
            print(f"  ✓ {c['detail']}")
    else:
        print("  No changes needed")


def _print_moc(moc_result):
    if moc_result.changes:
        for c in moc_result.changes:
            print(f"  ✓ {c}")
    else:
        print("  No autonomous changes needed")
    if moc_result.topic_moc_proposals:
        for p in moc_result.topic_moc_proposals:
            print(f"  ⚠ Proposal: new Topic MOC for '{p['section']}' ({p['entry_count']} entries)")


def _print_recommendations(rec_result):
    if not rec_result.recommendations:
        print("  No recommendations (no dated Library notes matched interests)")
        return
    for i, r in enumerate(rec_result.recommendations, 1):
        matched = ", ".join(r.matched_interests) if r.matched_interests else "-"
        print(f"  {i}. {r.title}  [{r.date_saved} · {r.status}]")
        print(f"       interests: {matched}")


def _build_report(run_date, inv, fix_result, moc_result, conn_proposals, rec_result=None):
    lines = [f"# Vault Lint - {run_date}", "", "## Health Metrics"]
    if inv:
        orphan_noise = inv.orphans_unscoped_count - inv.orphan_count
        broken_noise = inv.broken_links_unscoped_count - len(inv.broken_links)
        orphan_suffix = f" *(scoped; {orphan_noise} out-of-scope filtered)*" if orphan_noise else ""
        broken_suffix = f" *(scoped; {broken_noise} out-of-scope filtered)*" if broken_noise else ""
        lines += [
            f"- Orphans: {inv.orphan_count}{orphan_suffix}",
            f"- Library notes: {inv.library_note_count}",
            f"- Missing from Master MOC: {len(inv.missing_from_moc)}",
            f"- Broken links: {len(inv.broken_links)} across {len({b['file'] for b in inv.broken_links})} files{broken_suffix}",
            f"- Dead-ends in Research: {inv.deadend_count}",
            f"- Stale Recently Added entries: {len(inv.stale_recently_added)}",
            f"- Similar tag pairs flagged: {len(inv.similar_tags)}",
        ]

    lines += ["", "## Autonomous Changes"]
    all_changes = []
    if fix_result:
        all_changes += [c["detail"] for c in fix_result.changes]
    if moc_result:
        all_changes += moc_result.changes
    if all_changes:
        for c in all_changes:
            lines.append(f"- {c}")
    else:
        lines.append("- None")

    lines += ["", "## Pending Review"]
    pending = []
    if conn_proposals:
        pending.append(f"- `vault-lint-{run_date}-connections.md` ({len(conn_proposals)} proposed connections)")
    if moc_result and moc_result.topic_moc_proposals:
        pending.append(f"- `vault-lint-{run_date}-moc-proposals.md` ({len(moc_result.topic_moc_proposals)} Topic MOC candidates)")
    if pending:
        lines += pending
    else:
        lines.append("- None")

    if rec_result and rec_result.recommendations:
        lines += render_report_section(rec_result)

    if inv and inv.similar_tags:
        lines += ["", "## Similar Tags (Review Manually)"]
        for t in inv.similar_tags[:15]:
            lines.append(f"- `{t['t1']}` ↔ `{t['t2']}` ({t['ratio']:.0%} similar)")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
