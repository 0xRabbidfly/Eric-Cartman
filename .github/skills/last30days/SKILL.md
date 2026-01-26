---
name: last30days
description: Research a topic from the last 30 days on Reddit + X + Web. Use when the user asks "research X", "what's new with X", "last 30 days on X", or wants to understand recent community discussions about a topic. Runs a Python script to fetch real engagement data.
version: 1.0.0
---

# last30days: Research Any Topic from the Last 30 Days

Research ANY topic across Reddit, X, and the web. Surface what people are actually discussing, recommending, and debating right now.

Use cases:
- **Prompting**: "photorealistic people in Nano Banana Pro", "Midjourney prompts", "ChatGPT image generation" → learn techniques, get copy-paste prompts
- **Recommendations**: "best Claude Code skills", "top AI tools" → get a LIST of specific things people mention
- **News**: "what's happening with OpenAI", "latest AI announcements" → current events and updates
- **General**: any topic you're curious about → understand what the community is saying

## Quick Start

Run the research script with the user's topic:

```powershell
python .github/skills/last30days/scripts/last30days.py "[TOPIC]" --emit=compact
```

Options:
- `--quick` → Faster research with fewer sources (8-12 each)
- `--deep` → Comprehensive research (50-70 Reddit, 40-60 X)
- `--emit=json` → Machine-readable output
- `--emit=md` → Full markdown report

## How It Works

1. **Script searches Reddit + X** using OpenAI and xAI APIs (if configured)
2. **Falls back to WebSearch** if no API keys are configured
3. **Scores and ranks results** by relevance, recency, and engagement
4. **Returns structured data** for you to synthesize

## Setup (Optional but Recommended)

The skill works without API keys using WebSearch fallback. For better results with real engagement metrics, configure:

```powershell
# Create config directory and file
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config\last30days"
@"
# last30days API Configuration
# Both keys are optional - skill works with WebSearch fallback

# For Reddit research (uses OpenAI's web_search tool)
OPENAI_API_KEY=your-openai-key

# For X/Twitter research (uses xAI's x_search tool)
XAI_API_KEY=your-xai-key
"@ | Out-File -FilePath "$env:USERPROFILE\.config\last30days\.env" -Encoding UTF8
```

## Parse User Intent

Before running research, identify:

1. **TOPIC**: What they want to learn about
2. **QUERY TYPE**:
   - **RECOMMENDATIONS** - "best X", "top X" → List specific things
   - **NEWS** - "what's happening with X" → Current events
   - **PROMPTING** - "X prompts" → Techniques and examples
   - **GENERAL** - Default → Broad understanding

## After Getting Results

1. **Synthesize** the findings - don't just dump raw data
2. **Weight Reddit/X higher** than web results (engagement signals)
3. **Identify patterns** across multiple sources
4. **Show summary with stats**:

```
✅ Research complete!
├─ 🟠 Reddit: {n} threads │ {sum} upvotes │ {sum} comments
├─ 🔵 X: {n} posts │ {sum} likes │ {sum} reposts
├─ 🌐 Web: {n} pages
└─ Top voices: r/{sub1}, r/{sub2} │ @{handle1}, @{handle2}
```

5. **Invite user's vision**: "Share what you want to create and I'll write a prompt for it"

## Output Interpretation

The script outputs:
- **Research Results**: Ranked list of sources with scores
- **Engagement metrics**: Real upvotes, comments, likes when available
- **Date confidence**: How sure we are about recency
- **Mode indicator**: "both", "reddit-only", "x-only", or "web-only"

## Related Skills

- `project-guide` - For understanding this project's architecture
- `code-review` - For reviewing code changes
