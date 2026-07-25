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
MODEL = "grok-4.3"
EVIDENCE_THRESHOLD = 5  # connections needed for "mature" status

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

    def find_clusters(self) -> list[set[str]]:
        """Find connected components using BFS."""
        visited: set[str] = set()
        clusters: list[set[str]] = []

        for node in self.adjacency:
            if node in visited:
                continue
            # BFS from this node
            cluster: set[str] = set()
            queue = [node]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster.add(current)
                for neighbor in self.adjacency[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)
            if len(cluster) >= 2:  # Only meaningful clusters
                clusters.append(cluster)

        return clusters

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
                    elif "tags:" in line:
                        parts = line.split(":", 1)[1].strip()
                        if parts:
                            for t in parts.split(","):
                                t = t.strip().strip("#")
                                if t:
                                    tag_counts[t] += 1

    # Return top tags sorted by frequency
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return [tag for tag, _ in sorted_tags[:5]]


def generate_thesis_statement(
    api_key: str, notes: set[str], edges: list[dict], topics: list[str]
) -> str:
    """Use xAI API to generate a thesis statement for a cluster."""
    # Collect note titles
    note_titles = []
    for slug in list(notes)[:10]:  # Limit to avoid token overflow
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

    # Collect relationship summaries
    rel_summaries = []
    for e in edges[:15]:
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
    }

    try:
        resp = requests.post(XAI_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
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
    for thesis in theses:
        existing_notes = set(thesis.get("notes", []))
        overlap = existing_notes & cluster_notes
        # If more than half the notes overlap, it's the same thesis
        if len(overlap) > len(cluster_notes) * 0.5:
            return thesis
    return None


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_theses(api_key: str) -> dict:
    """Analyze connections and update theses."""
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
    print(f"Found {len(clusters)} note clusters")

    # Load existing theses
    theses_data = load_theses()
    existing_theses = theses_data["theses"]
    today = date.today().isoformat()

    for i, cluster in enumerate(clusters):
        edges = graph.get_cluster_edges(cluster)
        edge_types = count_edge_types(edges)
        topics = extract_dominant_topics(cluster)

        evidence_count = (
            edge_types.get("supports", 0)
            + edge_types.get("extends", 0)
            + edge_types.get("bridges", 0)
        )
        contradiction_count = edge_types.get("contradicts", 0)

        # Check if this cluster matches an existing thesis
        existing = find_existing_thesis(existing_theses, cluster)

        if existing:
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

            # Check for status upgrade
            if existing["status"] == "emerging" and evidence_count >= EVIDENCE_THRESHOLD:
                existing["status"] = "mature"
                print(f"  UPGRADED: Thesis '{existing['id']}' is now mature")

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
            print(f"  NEW thesis {thesis_id}: {statement[:60]}...")

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

    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.auto_report:
        auto_generate_reports()
        return

    # Default: analyze and update
    api_key = load_api_key()
    data = analyze_theses(api_key)
    print_recommendations(data)
    print_status()


if __name__ == "__main__":
    main()
