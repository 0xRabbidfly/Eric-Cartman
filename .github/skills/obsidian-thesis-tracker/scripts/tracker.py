#!/usr/bin/env python3
"""
Obsidian Thesis Tracker

Tracks emerging theses across vault notes by analyzing connection clusters.
Reads from Research/connections.json, writes to Research/theses.json.
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_PATH = Path(r"C:\Users\nuno_\Documents\Obsidian Vault")
CONNECTIONS_FILE = VAULT_PATH / "Research" / "connections.json"
THESES_FILE = VAULT_PATH / "Research" / "theses.json"
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
MODEL = "grok-4.5"
EVIDENCE_THRESHOLD = 5  # connections needed for "mature" status
MIN_CLUSTER_SIZE = 3    # fewer notes than this isn't a thesis, it's a pair
MAX_CLUSTER_SIZE = 70   # larger than this gets recursively split. Louvain at
                        # resolution 1.0 gives ~8 communities of 6-64 notes on the
                        # current graph; splitting below ~60 produced near-duplicate
                        # theses ("harness > model" eight different ways).
MIN_EVIDENCE_FOR_THESIS = 3  # supporting/extending edges needed to even be "emerging"

CLAUDE_CLI = r"C:\Users\nuno_\.local\bin\claude.exe"

VAULT_REPORT_SCRIPT = Path(
    r"Z:\Projects\Eric-Cartman\.github\skills\obsidian-vault-report\scripts\report.py"
)


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
# Data loading
# ---------------------------------------------------------------------------

def load_connections() -> list[dict]:
    """Load connections from the connections.json file."""
    if not CONNECTIONS_FILE.exists():
        print(f"WARNING: Connections file not found: {CONNECTIONS_FILE}")
        print("  Run obsidian-connection-detector first to generate connections.")
        return []
    try:
        data = json.loads(CONNECTIONS_FILE.read_text(encoding="utf-8"))
        return data.get("connections", [])
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: Failed to read connections file: {e}")
        return []


def load_theses() -> dict:
    """Load existing theses from JSON file."""
    if THESES_FILE.exists():
        try:
            data = json.loads(THESES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "theses" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"theses": []}


def save_theses(data: dict) -> None:
    """Save theses to JSON file."""
    THESES_FILE.parent.mkdir(parents=True, exist_ok=True)
    THESES_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Graph building and clustering
# ---------------------------------------------------------------------------

def _louvain(nodes: list[str], weights: dict, resolution: float = 1.0,
             max_passes: int = 20) -> list[set[str]]:
    """Pure-Python Louvain community detection (no networkx dependency).

    Two phases repeated until modularity stops improving:
      1. local moving — each node joins the neighbouring community that gives
         the largest modularity gain;
      2. aggregation — communities become super-nodes and phase 1 repeats.
    Deterministic given sorted `nodes`.
    """
    # Current-level graph: node -> {neighbor: weight}
    g = {n: dict(weights.get(n, {})) for n in nodes}
    # Each current-level node maps to the set of original nodes it contains
    members = {n: {n} for n in nodes}

    m2 = sum(sum(nb.values()) for nb in g.values())  # 2m (each edge counted twice)
    if m2 == 0:
        return [{n} for n in nodes]

    while True:
        # ---- Phase 1: local moving ----
        comm = {n: n for n in g}                      # node -> community id
        deg = {n: sum(nb.values()) for n, nb in g.items()}
        tot = dict(deg)                               # community -> total degree

        improved_any = False
        for _ in range(max_passes):
            moved = False
            for n in sorted(g):
                c_old = comm[n]
                k_n = deg[n]
                # weights from n to each neighbouring community (self-loops
                # count toward degree but are not a link to a neighbour)
                to_comm: dict[str, float] = defaultdict(float)
                for nb, w in g[n].items():
                    if nb != n:
                        to_comm[comm[nb]] += w
                # remove n from its community
                tot[c_old] -= k_n
                best_c, best_gain = c_old, 0.0
                base = to_comm.get(c_old, 0.0) - resolution * tot[c_old] * k_n / m2
                for c, w_in in sorted(to_comm.items()):
                    gain = (w_in - resolution * tot[c] * k_n / m2) - base
                    if gain > best_gain + 1e-12:
                        best_c, best_gain = c, gain
                tot[best_c] += k_n
                if best_c != c_old:
                    comm[n] = best_c
                    moved = True
                    improved_any = True
            if not moved:
                break

        if not improved_any:
            break

        # ---- Phase 2: aggregation ----
        new_members: dict[str, set[str]] = defaultdict(set)
        for n, c in comm.items():
            new_members[c] |= members[n]
        new_g: dict[str, dict[str, float]] = {c: defaultdict(float) for c in new_members}
        for n, nb in g.items():
            cn = comm[n]
            for m_, w in nb.items():
                cm = comm[m_]
                new_g[cn][cm] += w  # cn == cm becomes a self-loop (kept for degree)
        if len(new_g) == len(g):  # no aggregation happened
            break
        g = {c: dict(nb) for c, nb in new_g.items()}
        members = dict(new_members)

    return sorted((set(s) for s in members.values()), key=lambda s: (-len(s), sorted(s)[0]))


class ConnectionGraph:
    """Simple undirected graph for connection analysis."""

    def __init__(self):
        self.adjacency: dict[str, set[str]] = defaultdict(set)
        self.edges: list[dict] = []

    def add_edge(self, connection: dict) -> None:
        """Add a connection as an edge."""
        src = connection["source"]
        tgt = connection["target"]
        rel = connection.get("relationship", "unrelated")

        # Only consider meaningful connections
        if rel in ("supports", "contradicts", "extends", "bridges"):
            self.adjacency[src].add(tgt)
            self.adjacency[tgt].add(src)
            self.edges.append(connection)

    # -- Weighted edges for community detection -----------------------------
    # confidence is the edge weight; "bridges" edges deliberately span domains,
    # so they are down-weighted to keep them from gluing communities together.
    _REL_WEIGHT = {"supports": 1.0, "extends": 1.0, "contradicts": 1.0, "bridges": 0.4}

    def _weights(self) -> dict[str, dict[str, float]]:
        w: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for e in self.edges:
            s, t = e["source"], e["target"]
            if s == t:
                continue
            wt = float(e.get("confidence", 0.5)) * self._REL_WEIGHT.get(e.get("relationship"), 1.0)
            w[s][t] += wt
            w[t][s] += wt
        return w

    def find_clusters(self, max_size: int = MAX_CLUSTER_SIZE, min_size: int = MIN_CLUSTER_SIZE) -> list[set[str]]:
        """Find topical communities with Louvain modularity optimisation.

        Connected components stop working once the graph is dense (1,600+
        connections collapse 300+ notes into one component), so we optimise
        modularity instead and recursively split anything still over max_size.
        Deterministic: nodes are visited in sorted order, no randomness.
        """
        weights = self._weights()
        nodes = sorted(weights.keys())
        if not nodes:
            return []

        communities = _louvain(nodes, weights)

        # Recursively split oversized communities at a higher resolution.
        out: list[set[str]] = []
        for comm in communities:
            out.extend(self._split_if_large(comm, weights, max_size, depth=0))

        return [c for c in out if len(c) >= min_size]

    def _split_if_large(self, comm: set[str], weights, max_size: int, depth: int) -> list[set[str]]:
        if len(comm) <= max_size or depth >= 4:
            return [comm]
        sub_w = {n: {m: w for m, w in weights[n].items() if m in comm} for n in comm}
        sub_nodes = sorted(comm)
        subs = _louvain(sub_nodes, sub_w, resolution=1.0 + 0.5 * (depth + 1))
        if len(subs) <= 1:  # couldn't split further
            return [comm]
        out: list[set[str]] = []
        for s in subs:
            out.extend(self._split_if_large(s, weights, max_size, depth + 1))
        return out

    def get_cluster_edges(self, cluster: set[str]) -> list[dict]:
        """Get all edges within a cluster."""
        return [
            e for e in self.edges
            if e["source"] in cluster and e["target"] in cluster
        ]


# ---------------------------------------------------------------------------
# Cluster analysis
# ---------------------------------------------------------------------------

def count_edge_types(edges: list[dict]) -> dict[str, int]:
    """Count edges by relationship type."""
    counts: dict[str, int] = defaultdict(int)
    for edge in edges:
        counts[edge.get("relationship", "unknown")] += 1
    return dict(counts)


def extract_dominant_topics(cluster_notes: set[str]) -> list[str]:
    """Extract dominant tags/topics from cluster notes."""
    tag_counts: dict[str, int] = defaultdict(int)

    for note_slug in cluster_notes:
        note_path = VAULT_PATH / (note_slug + ".md")
        if not note_path.exists():
            continue
        try:
            text = note_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Extract tags from frontmatter
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                block = text[3:end]
                for line in block.splitlines():
                    line = line.strip()
                    if line.startswith("- "):
                        tag = line[2:].strip().strip("#")
                        if tag:
                            tag_counts[tag] += 1
                    elif line.startswith("tags:"):
                        parts = line.split(":", 1)[1].strip().strip("[]")
                        if parts:
                            for t in parts.split(","):
                                t = t.strip().strip("#").strip("\"'")
                                if t:
                                    tag_counts[t] += 1

    # Return top tags sorted by frequency
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return [tag for tag, _ in sorted_tags[:5]]


def generate_thesis_statement(
    api_key: str, notes: set[str], edges: list[dict], topics: list[str]
) -> str:
    """Use xAI API to generate a thesis statement for a cluster."""
    # Collect note titles — the most-connected notes in the cluster, so a
    # 60-note community is described by its centre, not an arbitrary sample.
    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1
    ranked = sorted(notes, key=lambda n: (-degree.get(n, 0), n))
    note_titles = []
    for slug in ranked[:15]:  # Limit to avoid token overflow
        note_path = VAULT_PATH / (slug + ".md")
        if note_path.exists():
            try:
                text = note_path.read_text(encoding="utf-8")
                # Get title
                body = text
                if body.startswith("---"):
                    end = body.find("---", 3)
                    if end != -1:
                        body = body[end + 3:].strip()
                for line in body.splitlines():
                    if line.strip().startswith("# "):
                        note_titles.append(line.strip()[2:])
                        break
            except (OSError, UnicodeDecodeError):
                pass

    # Collect relationship summaries — highest-confidence edges first
    rel_summaries = []
    for e in sorted(edges, key=lambda e: -float(e.get("confidence", 0)))[:20]:
        rel_summaries.append(
            f"  {e['source'].split('/')[-1]} --[{e['relationship']}]--> "
            f"{e['target'].split('/')[-1]}: {e.get('explanation', '')}"
        )

    prompt = f"""Based on these interconnected research notes and their relationships, generate a single thesis statement (one sentence) that captures the emerging argument or insight.

Note titles: {', '.join(note_titles)}
Dominant topics: {', '.join(topics)}

Relationships:
{chr(10).join(rel_summaries)}

Respond with just the thesis statement, nothing else."""

    # Try Claude CLI first (free on Max)
    try:
        import subprocess
        system = "You are a research analyst. Generate concise thesis statements."
        combined = f"{system}\n\n{prompt}"
        result = subprocess.run(
            [CLAUDE_CLI, "--print"],
            input=combined,  # stdin: avoids Windows' ~32K command-line limit
            capture_output=True, text=True, encoding="utf-8", timeout=300,
        )
        content = result.stdout.strip()
        if content and "Failed to authenticate" not in content:
            print("  [claude] Thesis statement generated")
            return content
        print(f"  [claude-cli] Failed, falling back to xAI: {result.stderr[:100]}")
    except Exception as e:
        print(f"  [claude-cli] Error ({e}), falling back to xAI")

    # Fall back to xAI API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a research analyst. Generate concise thesis statements."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "reasoning_effort": "high",
    }

    try:
        resp = requests.post(XAI_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        print("  [xai-fallback] Thesis statement generated")
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError) as e:
        print(f"  WARNING: Thesis generation failed: {e}")
        return f"Cluster of {len(notes)} notes on: {', '.join(topics[:3])}"


# ---------------------------------------------------------------------------
# Thesis management
# ---------------------------------------------------------------------------

def generate_thesis_id(existing_theses: list[dict]) -> str:
    """Generate the next thesis ID."""
    max_num = 0
    for t in existing_theses:
        tid = t.get("id", "")
        if tid.startswith("thesis-"):
            try:
                num = int(tid.split("-")[1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                pass
    return f"thesis-{max_num + 1:03d}"


def find_existing_thesis(theses: list[dict], cluster_notes: set[str]) -> dict | None:
    """Find an existing thesis that overlaps significantly with this cluster."""
    best, best_score = None, 0.0
    for thesis in theses:
        existing_notes = set(thesis.get("notes", []))
        if not existing_notes:
            continue
        overlap = existing_notes & cluster_notes
        # Match if the cluster still contains most of the thesis's original
        # notes (thesis survived the graph growing around it), or vice versa.
        # The old rule (>50% of the *cluster*) silently orphaned theses as
        # soon as their cluster gained new notes.
        score = max(len(overlap) / len(existing_notes), len(overlap) / max(len(cluster_notes), 1))
        if score >= 0.5 and score > best_score:
            best, best_score = thesis, score
    return best


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_theses(api_key: str, dry_run: bool = False) -> dict:
    """Analyze connections and update theses.

    dry_run: print what clusters would become theses, without calling any
    model or writing theses.json.
    """
    connections = load_connections()
    if not connections:
        print("No connections to analyze.")
        return load_theses()

    # Build graph
    graph = ConnectionGraph()
    for conn in connections:
        graph.add_edge(conn)

    # Find clusters
    clusters = graph.find_clusters()
    print(f"Found {len(clusters)} note clusters (community detection, "
          f"{MIN_CLUSTER_SIZE}-{MAX_CLUSTER_SIZE} notes each)")

    # Load existing theses
    theses_data = load_theses()
    existing_theses = theses_data["theses"]
    today = date.today().isoformat()
    matched_ids: set[str] = set()

    for i, cluster in enumerate(clusters):
        edges = graph.get_cluster_edges(cluster)
        edge_types = count_edge_types(edges)

        evidence_count = (
            edge_types.get("supports", 0)
            + edge_types.get("extends", 0)
            + edge_types.get("bridges", 0)
        )
        contradiction_count = edge_types.get("contradicts", 0)

        # Check if this cluster matches an existing thesis
        existing = find_existing_thesis(existing_theses, cluster)

        if not existing and evidence_count < MIN_EVIDENCE_FOR_THESIS:
            continue  # too thin to be a thesis yet

        topics = extract_dominant_topics(cluster)

        if dry_run:
            tag = f"EXISTING {existing['id']}" if existing else "NEW"
            anchors = sorted(cluster, key=lambda n: -sum(1 for e in edges if n in (e["source"], e["target"])))[:3]
            print(f"\n  [{tag}] {len(cluster)} notes, {evidence_count} evidence, "
                  f"{contradiction_count} contradictions; topics: {', '.join(topics)}")
            for a in anchors:
                print(f"      - {a.split('/')[-1]}")
            if existing:
                matched_ids.add(existing["id"])
            continue

        if existing:
            matched_ids.add(existing["id"])
            # If the cluster has grown a lot since the statement was written,
            # the statement probably describes a subset. Regenerate, keep the old.
            prev_n = len(existing.get("notes", [])) or 1
            if len(cluster) >= 3 * prev_n:
                print(f"  Cluster for {existing['id']} grew {prev_n}->{len(cluster)} notes; regenerating statement")
                new_stmt = generate_thesis_statement(api_key, cluster, edges, topics)
                if new_stmt and not new_stmt.startswith("Cluster of "):
                    existing["previous_statement"] = existing.get("statement", "")
                    existing["statement"] = new_stmt
            # Update existing thesis
            existing["notes"] = sorted(cluster)
            existing["connections"] = [
                {"source": e["source"], "target": e["target"],
                 "relationship": e["relationship"]}
                for e in edges
            ]
            existing["evidence_count"] = evidence_count
            existing["contradiction_count"] = contradiction_count
            existing["last_updated"] = today

            # Check for status upgrade (also re-adopts orphaned / legacy
            # "draft-generated" theses whose cluster re-formed)
            if existing["status"] in ("emerging", "orphaned", "draft-generated"):
                if evidence_count >= EVIDENCE_THRESHOLD:
                    if existing["status"] != "mature":
                        print(f"  UPGRADED: Thesis '{existing['id']}' is now mature")
                    existing["status"] = "mature"
                else:
                    existing["status"] = "emerging"

            print(f"  Updated thesis {existing['id']}: {existing['statement'][:60]}...")
        else:
            # Generate thesis statement via API
            statement = generate_thesis_statement(api_key, cluster, edges, topics)

            status = "mature" if evidence_count >= EVIDENCE_THRESHOLD else "emerging"
            thesis_id = generate_thesis_id(existing_theses)

            new_thesis = {
                "id": thesis_id,
                "statement": statement,
                "status": status,
                "evidence_count": evidence_count,
                "contradiction_count": contradiction_count,
                "notes": sorted(cluster),
                "connections": [
                    {"source": e["source"], "target": e["target"],
                     "relationship": e["relationship"]}
                    for e in edges
                ],
                "first_detected": today,
                "last_updated": today,
                "report_path": None,
            }
            existing_theses.append(new_thesis)
            matched_ids.add(thesis_id)
            print(f"  NEW thesis {thesis_id}: {statement[:60]}...")

    # Theses whose cluster dissolved: mark, don't delete (the weekly brain
    # surfaces these as DECAYING rather than silently dropping them).
    for t in existing_theses:
        if t.get("id") not in matched_ids and t.get("status") not in ("orphaned", "archived"):
            t["status"] = "orphaned"
            t["last_updated"] = today
            print(f"  ORPHANED: {t['id']} no longer maps to a cluster")

    if dry_run:
        print(f"\n[dry-run] {len(existing_theses)} theses on disk; "
              f"{len(matched_ids)} matched a cluster; nothing written.")
        return theses_data

    save_theses(theses_data)
    return theses_data


# ---------------------------------------------------------------------------
# Status display
# ---------------------------------------------------------------------------

def print_status() -> None:
    """Print current thesis status."""
    data = load_theses()
    theses = data.get("theses", [])

    if not theses:
        print("No theses tracked yet. Run without --status to analyze connections.")
        return

    print(f"\n{'='*70}")
    print(f"  THESIS STATUS  ({len(theses)} theses tracked)")
    print(f"{'='*70}\n")

    for t in theses:
        status_icon = {
            "emerging": "[~]",
            "mature": "[*]",
            "draft-generated": "[v]",
        }.get(t["status"], "[?]")

        print(f"  {status_icon} {t['id']} — {t['status'].upper()}")
        print(f"      Statement: {t['statement']}")
        print(f"      Evidence: {t['evidence_count']} supporting | "
              f"{t['contradiction_count']} contradicting")
        print(f"      Notes: {len(t.get('notes', []))} | "
              f"First seen: {t['first_detected']} | "
              f"Updated: {t['last_updated']}")

        if t.get("report_path"):
            print(f"      Report: {t['report_path']}")

        # Flags
        if t["status"] == "mature" and not t.get("report_path"):
            print(f"      >> Ready for report generation")
        if t["contradiction_count"] >= 2:
            print(f"      !! Unresolved contradictions worth investigating")
        print()

    print(f"{'='*70}")


# ---------------------------------------------------------------------------
# Auto-report generation
# ---------------------------------------------------------------------------

def auto_generate_reports() -> None:
    """Auto-generate reports for mature theses that don't have one yet."""
    data = load_theses()
    theses = data.get("theses", [])
    generated = 0

    for thesis in theses:
        if thesis["status"] != "mature":
            continue
        if thesis.get("report_path"):
            continue

        print(f"\nGenerating report for: {thesis['statement'][:60]}...")

        if VAULT_REPORT_SCRIPT.exists():
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(VAULT_REPORT_SCRIPT),
                        "--query", thesis["statement"],
                        "--thesis-id", thesis["id"],
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    # Try to extract report path from output
                    for line in result.stdout.splitlines():
                        if "Report saved" in line or "report" in line.lower():
                            # Attempt to find a path in the output
                            parts = line.split(":")
                            if len(parts) >= 2:
                                candidate = parts[-1].strip()
                                if candidate.endswith(".md"):
                                    thesis["report_path"] = candidate
                                    break

                    thesis["status"] = "draft-generated"
                    generated += 1
                    print(f"  Report generated for {thesis['id']}")
                    if result.stdout:
                        print(f"  Output: {result.stdout[:200]}")
                else:
                    print(f"  ERROR generating report: {result.stderr[:200]}")
            except subprocess.TimeoutExpired:
                print(f"  ERROR: Report generation timed out")
            except Exception as e:
                print(f"  ERROR: {e}")
        else:
            print(
                f"  Vault report script not found at: {VAULT_REPORT_SCRIPT}"
            )
            print(
                f"  Run manually: python {VAULT_REPORT_SCRIPT} "
                f"--query \"{thesis['statement']}\" "
                f"--thesis-id {thesis['id']}"
            )

    if generated:
        save_theses(data)
        print(f"\nGenerated {generated} report(s)")
    else:
        print("\nNo mature theses pending report generation.")


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def print_recommendations(data: dict) -> None:
    """Print actionable recommendations after analysis."""
    theses = data.get("theses", [])
    recs = []

    for t in theses:
        if t["status"] == "mature" and not t.get("report_path"):
            recs.append(
                f"  REPORT: Thesis '{t['statement'][:50]}...' has enough evidence. "
                f"Run:\n    python {VAULT_REPORT_SCRIPT} "
                f"--query \"{t['statement']}\" --thesis-id {t['id']}"
            )
        if t["contradiction_count"] >= 2:
            recs.append(
                f"  INVESTIGATE: Thesis '{t['statement'][:50]}...' "
                f"has {t['contradiction_count']} unresolved contradictions."
            )

    if recs:
        print(f"\nRecommendations:")
        for r in recs:
            print(r)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Track emerging theses across Obsidian vault notes."
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print current thesis status without re-analyzing",
    )
    parser.add_argument(
        "--auto-report", action="store_true",
        help="Auto-generate reports for mature theses",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show the clusters that would become theses; no model calls, no writes",
    )

    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.auto_report:
        auto_generate_reports()
        return

    if args.dry_run:
        analyze_theses(api_key="", dry_run=True)
        return

    # Default: analyze and update
    api_key = load_api_key()
    data = analyze_theses(api_key)
    print_recommendations(data)
    print_status()


if __name__ == "__main__":
    main()
