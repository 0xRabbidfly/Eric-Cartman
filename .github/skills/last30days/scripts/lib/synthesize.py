"""AI synthesis for last30days skill - generates "What I learned" and "KEY PATTERNS" sections."""

import json
from typing import Dict, Any, List, Optional

from . import http, schema

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

SYNTHESIS_PROMPT = """You are a research analyst synthesizing findings from Reddit, X/Twitter, and web sources.

TOPIC: {topic}
DATE RANGE: {from_date} to {to_date}

## SOURCE DATA

### Reddit Threads ({reddit_count} found)
{reddit_summary}

### X Posts ({x_count} found, {x_likes} total likes, {x_reposts} total reposts)
{x_summary}

### Web Sources ({web_count} pages)
{web_summary}

## YOUR TASK

Generate a synthesis in EXACTLY this JSON format:

{{
  "what_i_learned": "2-4 flowing sentences synthesizing key insights. Use specific numbers and quotes where impactful. Connect ideas across sources. Be concrete, not generic.",
  "key_patterns": [
    {{"name": "Pattern Name", "explanation": "Concrete actionable explanation with specifics"}},
    {{"name": "Pattern Name", "explanation": "Concrete actionable explanation with specifics"}},
    {{"name": "Pattern Name", "explanation": "Concrete actionable explanation with specifics"}}
  ],
  "top_voices": {{
    "reddit": ["subreddit1", "subreddit2"],
    "x": ["handle1", "handle2", "handle3"],
    "web": ["domain1.com", "domain2.com"]
  }},
  "topic_summary": "A short 1-sentence summary of the topic for context storage",
  "key_findings_bullets": ["finding1", "finding2", "finding3"]
}}

RULES:
- what_i_learned should be a narrative paragraph, NOT bullet points
- key_patterns should have 3-5 items, each with a bold-worthy name and concrete explanation
- top_voices should list the most authoritative/engaged sources from each platform
- Be SPECIFIC - use actual numbers, prices, percentages from the data
- If data is sparse, say so honestly
- Output ONLY valid JSON, no markdown code blocks"""


def _summarize_reddit(items: List[schema.RedditItem], limit: int = 10) -> str:
    """Create a summary of Reddit items for synthesis."""
    if not items:
        return "No relevant Reddit discussions found."
    
    lines = []
    for item in items[:limit]:
        eng = ""
        if item.engagement:
            parts = []
            if item.engagement.score is not None:
                parts.append(f"{item.engagement.score}pts")
            if item.engagement.num_comments is not None:
                parts.append(f"{item.engagement.num_comments}cmt")
            eng = f" [{', '.join(parts)}]" if parts else ""
        
        lines.append(f"- r/{item.subreddit}: \"{item.title}\"{eng}")
        if item.why_relevant:
            lines.append(f"  Relevance: {item.why_relevant}")
        if item.comment_insights:
            for insight in item.comment_insights[:2]:
                lines.append(f"  Insight: {insight}")
    
    return "\n".join(lines)


def _summarize_x(items: List[schema.XItem], limit: int = 12) -> str:
    """Create a summary of X items for synthesis."""
    if not items:
        return "No relevant X posts found."
    
    lines = []
    for item in items[:limit]:
        eng = ""
        if item.engagement:
            parts = []
            if item.engagement.likes is not None:
                parts.append(f"{item.engagement.likes}likes")
            if item.engagement.reposts is not None:
                parts.append(f"{item.engagement.reposts}rt")
            eng = f" [{', '.join(parts)}]" if parts else ""
        
        # Truncate long text
        text = item.text[:150] + "..." if len(item.text) > 150 else item.text
        lines.append(f"- @{item.author_handle}{eng}: \"{text}\"")
        if item.why_relevant:
            lines.append(f"  Relevance: {item.why_relevant}")
    
    return "\n".join(lines)


def _summarize_web(items: List[schema.WebSearchItem], limit: int = 8) -> str:
    """Create a summary of web items for synthesis."""
    if not items:
        return "No web sources included."
    
    lines = []
    for item in items[:limit]:
        lines.append(f"- {item.source_domain}: \"{item.title}\"")
        if item.snippet:
            snippet = item.snippet[:100] + "..." if len(item.snippet) > 100 else item.snippet
            lines.append(f"  Snippet: {snippet}")
    
    return "\n".join(lines)


def _calculate_x_totals(items: List[schema.XItem]) -> tuple:
    """Calculate total likes and reposts from X items."""
    total_likes = 0
    total_reposts = 0
    for item in items:
        if item.engagement:
            if item.engagement.likes:
                total_likes += item.engagement.likes
            if item.engagement.reposts:
                total_reposts += item.engagement.reposts
    return total_likes, total_reposts


def synthesize(
    api_key: str,
    model: str,
    report: schema.Report,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Synthesize research results into "What I learned" and "KEY PATTERNS".
    
    Args:
        api_key: OpenAI API key
        model: Model to use (e.g., "gpt-4o-mini", "gpt-4o")
        report: Research report with Reddit, X, and web data
        timeout: Request timeout in seconds
        
    Returns:
        Dict with:
          - what_i_learned: str
          - key_patterns: List[Dict[str, str]]
          - top_voices: Dict[str, List[str]]
          - topic_summary: str
          - key_findings_bullets: List[str]
    """
    # Calculate totals
    x_likes, x_reposts = _calculate_x_totals(report.x)
    
    # Build prompt
    prompt = SYNTHESIS_PROMPT.format(
        topic=report.topic,
        from_date=report.range_from,
        to_date=report.range_to,
        reddit_count=len(report.reddit),
        reddit_summary=_summarize_reddit(report.reddit),
        x_count=len(report.x),
        x_likes=x_likes,
        x_reposts=x_reposts,
        x_summary=_summarize_x(report.x),
        web_count=len(report.web),
        web_summary=_summarize_web(report.web),
    )
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }
    
    try:
        response = http.post(OPENAI_CHAT_URL, payload, headers=headers, timeout=timeout)
        
        # Parse response
        if "choices" in response and response["choices"]:
            content = response["choices"][0].get("message", {}).get("content", "{}")
            return json.loads(content)
    except Exception as e:
        # Return empty synthesis on error
        return {
            "what_i_learned": f"Research found {len(report.reddit)} Reddit threads and {len(report.x)} X posts about {report.topic}.",
            "key_patterns": [],
            "top_voices": {"reddit": [], "x": [], "web": []},
            "topic_summary": report.topic,
            "key_findings_bullets": [],
            "error": str(e),
        }
    
    return {
        "what_i_learned": "",
        "key_patterns": [],
        "top_voices": {"reddit": [], "x": [], "web": []},
        "topic_summary": report.topic,
        "key_findings_bullets": [],
    }


def generate_stats_tree(
    report: schema.Report,
    synthesis: Dict[str, Any],
) -> str:
    """Generate the stats tree for output.
    
    Args:
        report: Research report
        synthesis: Synthesis results with top_voices
        
    Returns:
        Formatted stats tree string
    """
    lines = []
    
    # Calculate totals
    reddit_pts = sum(
        r.engagement.score or 0 
        for r in report.reddit 
        if r.engagement
    )
    reddit_cmt = sum(
        r.engagement.num_comments or 0 
        for r in report.reddit 
        if r.engagement
    )
    x_likes, x_reposts = _calculate_x_totals(report.x)
    
    lines.append("✅ All agents reported back!")
    
    # Reddit line
    if report.reddit:
        reddit_str = f"├─ 🟠 Reddit: {len(report.reddit)} threads"
        if reddit_pts or reddit_cmt:
            reddit_str += f" │ {reddit_pts:,}+ points │ {reddit_cmt:,}+ comments"
        lines.append(reddit_str)
    elif report.mode in ("both", "reddit-only", "all"):
        lines.append("├─ 🟠 Reddit: 0 threads (no relevant discussions found)")
    
    # X line
    if report.x:
        x_str = f"├─ 🔵 X: {len(report.x)} posts"
        if x_likes or x_reposts:
            x_str += f" │ {x_likes:,} likes │ {x_reposts:,} reposts"
        lines.append(x_str)
    elif report.mode in ("both", "x-only", "all"):
        lines.append("├─ 🔵 X: 0 posts (no relevant posts found)")
    
    # Web line
    if report.web:
        domains = list(set(w.source_domain for w in report.web[:5]))
        web_str = f"├─ 🌐 Web: {len(report.web)}+ pages │ {', '.join(domains[:4])}"
        lines.append(web_str)
    
    # Top voices line
    top_voices = synthesis.get("top_voices", {})
    voice_parts = []
    
    reddit_subs = top_voices.get("reddit", [])
    if reddit_subs:
        # Strip r/ prefix if already present
        subs = [s.lstrip("r/") for s in reddit_subs[:2]]
        voice_parts.append(", ".join(f"r/{s}" for s in subs))
    
    x_handles = top_voices.get("x", [])
    if x_handles:
        # Strip @ prefix if already present
        handles = [h.lstrip("@") for h in x_handles[:3]]
        voice_parts.append(", ".join(f"@{h}" for h in handles))
    
    web_domains = top_voices.get("web", [])
    if web_domains:
        voice_parts.append(", ".join(web_domains[:2]))
    
    if voice_parts:
        lines.append(f"└─ Top voices: {' │ '.join(voice_parts)}")
    
    return "\n".join(lines)


def generate_context_stored(
    report: schema.Report,
    synthesis: Dict[str, Any],
) -> str:
    """Generate the CONTEXT STORED section for output.
    
    Args:
        report: Research report
        synthesis: Synthesis results
        
    Returns:
        Formatted context stored string
    """
    lines = []
    lines.append("📚 CONTEXT STORED - I'm now an expert on this topic.")
    lines.append("")
    lines.append("For the rest of our conversation, I have this research loaded:")
    lines.append("")
    lines.append(f"TOPIC: {report.topic}")
    
    # Key findings
    findings = synthesis.get("key_findings_bullets", [])
    if findings:
        lines.append(f"KEY FINDINGS: {', '.join(findings[:5])}")
    
    lines.append("")
    lines.append(f"What would you like to know about {report.topic}? I can answer questions based on this research—no need for new searches unless you want to explore a different topic.")
    
    return "\n".join(lines)
