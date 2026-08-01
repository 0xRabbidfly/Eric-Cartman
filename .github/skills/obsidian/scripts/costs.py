"""Centralized cost logging for all Obsidian skills.

Usage from any skill:
    from costs import log_cost
    log_cost("daily-research", "grok-4.5", api_calls=15, tokens=120000, cost_usd=0.28)
"""
import json
from datetime import datetime
from pathlib import Path

COSTS_FILE = Path(r"C:\Users\nuno_\Documents\Obsidian Vault\Research\costs-log.json")

def log_cost(skill: str, model: str, api_calls: int = 0, tokens: int = 0, cost_usd: float = 0.0):
    """Append a cost entry to the centralized log."""
    data = []
    if COSTS_FILE.exists():
        try:
            data = json.loads(COSTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = []

    data.append({
        "timestamp": datetime.now().isoformat(),
        "skill": skill,
        "model": model,
        "api_calls": api_calls,
        "tokens": tokens,
        "cost_usd": round(cost_usd, 4),
    })

    # Keep last 500 entries to prevent unbounded growth
    if len(data) > 500:
        data = data[-500:]

    COSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    COSTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
