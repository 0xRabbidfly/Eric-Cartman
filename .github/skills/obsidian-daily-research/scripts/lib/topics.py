"""Topic registry for daily research pipeline.

Each topic defines search queries optimized for Reddit and X discovery.
Topics are loaded from config.json but can be overridden at runtime.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Topic:
    """A research topic track."""
    slug: str
    display_name: str
    reddit_queries: List[str]
    x_queries: List[str]
    weight: float = 1.0  # Score multiplier for prioritization

    def get_combined_query(self, source: str = "reddit") -> str:
        """Get a single search string for the given source."""
        queries = self.reddit_queries if source == "reddit" else self.x_queries
        return " OR ".join(f'"{q}"' for q in queries) if queries else self.display_name


# Default topic definitions
DEFAULT_TOPICS: List[Topic] = [
    Topic(
        slug="agents",
        display_name="Agent Development",
        reddit_queries=[
            "AI agent framework",
            "agentic coding",
            "Claude agent",
            "Codex agent",
            "agent loop",
            "tool use AI",
        ],
        x_queries=[
            "AI agent",
            "agentic coding",
            "Claude agent",
            "Codex agent",
            "agent framework",
            "computer use agent",
        ],
        weight=1.2,
    ),
    Topic(
        slug="skills",
        display_name="Agent Skills & Tools",
        reddit_queries=[
            "agent skill",
            "copilot skill",
            "SKILL.md",
            "MCP skill",
            "Claude custom tool",
        ],
        x_queries=[
            "agent skills",
            "copilot skill",
            "MCP tool",
            "Claude custom skill",
            "AI agent tool",
        ],
        weight=1.1,
    ),
    Topic(
        slug="models",
        display_name="Frontier Model Releases",
        reddit_queries=[
            "GPT-5",
            "Claude 4",
            "Gemini 2",
            "new AI model release",
            "frontier model benchmark",
            "LLM comparison",
        ],
        x_queries=[
            "GPT-5",
            "Claude 4",
            "Gemini model",
            "frontier model",
            "new AI model",
            "LLM benchmark",
        ],
        weight=1.0,
    ),
    Topic(
        slug="mcp",
        display_name="MCP & Tool Use",
        reddit_queries=[
            "model context protocol",
            "MCP server",
            "MCP tool",
            "tool use pattern",
            "function calling LLM",
        ],
        x_queries=[
            "model context protocol",
            "MCP server",
            "MCP tool",
            "tool use",
            "function calling AI",
        ],
        weight=1.0,
    ),
    Topic(
        slug="rag",
        display_name="RAG & AI Search",
        reddit_queries=[
            "RAG pipeline",
            "AI search",
            "vector search",
            "retrieval augmented generation",
            "embedding model",
            "knowledge retrieval",
        ],
        x_queries=[
            "RAG pipeline",
            "AI search",
            "vector database",
            "retrieval augmented",
            "embedding search",
        ],
        weight=0.9,
    ),
]


def load_topics(config: dict) -> List[Topic]:
    """Load topics from config, falling back to defaults.

    Config can override topics via a 'topics' list of dicts with keys:
    slug, display_name, reddit_queries, x_queries, weight
    """
    topics_data = config.get("topics")
    if not topics_data:
        return DEFAULT_TOPICS

    topics = []
    for t in topics_data:
        topics.append(Topic(
            slug=t["slug"],
            display_name=t["display_name"],
            reddit_queries=t.get("reddit_queries", []),
            x_queries=t.get("x_queries", []),
            weight=t.get("weight", 1.0),
        ))
    return topics


def get_topic_by_slug(topics: List[Topic], slug: str) -> Optional[Topic]:
    """Find a topic by its slug."""
    for t in topics:
        if t.slug == slug:
            return t
    return None
