---
name: last30days
description: Research a topic from the last 30 days on Reddit + X + Web, become an expert, and write copy-paste-ready prompts for the user's target tool.
version: 1.1.0
argument-hint: "[topic] for [tool]" or "[topic]"
---

# last30days: Research Any Topic from the Last 30 Days

Research ANY topic across Reddit, X, and the web. Surface what people are actually discussing, recommending, and debating right now.

**The script now generates AI-synthesized output automatically.** Just run it and display the result.

---

## Quick Start

Run the research script with the user's topic:

```powershell
python .github/skills/last30days/scripts/last30days.py "[TOPIC]" --emit=compact
```

The script will output a fully synthesized response including:
- **What I learned:** - Narrative synthesis paragraph
- **KEY PATTERNS:** - Actionable patterns with bold names
- **Stats tree** - Source counts with engagement totals
- **CONTEXT STORED** - Topic summary for follow-up questions

**Just display the script output directly.** The synthesis is done by AI in the script.

Options:
- `--quick` → Faster research with fewer sources (8-12 each)
- `--deep` → Comprehensive research (50-70 Reddit, 40-60 X)
- `--emit=json` → Machine-readable output with synthesis
- `--emit=md` → Full markdown report

---

## Expected Output Format

The script produces output like this:

```
What I learned:
The Markham housing market is in correction mode with clear downward price pressure. A recent post showed a Markham home selling 300K below 2017 prices, and official data confirms a 6.4% year-over-year decline to an average of ~$1.04M (detached homes averaging $1.39M). York Region inventory is rising—3,782 active listings, up 2.91%—with homes taking about 36 days to sell.

KEY PATTERNS:

- **Price resets are real** - Individual homes selling far below 2017-2022 peaks
- **Inventory is normalizing** - Rising active listings creating buyer negotiation power
- **Regional decline, not isolated** - Markham shares GTA-wide correction dynamics

✅ All agents reported back!
├─ 🟠 Reddit: 0 threads (no relevant discussions found)
├─ 🔵 X: 19 posts │ 12,797 likes │ 2,596 reposts
├─ 🌐 Web: 10+ pages │ wahi.com, zolo.ca, realosophy.com
└─ Top voices: @ManyBeenRinsed, @JonFlynnREstats │ Wahi, Zolo

📚 CONTEXT STORED - I'm now an expert on this topic.

For the rest of our conversation, I have this research loaded:

TOPIC: Markham housing market
KEY FINDINGS: 6.4% YoY decline, homes selling 300K below 2017, York Region inventory up 2.91%

What would you like to know about the Markham market?
```

---

## Use Cases

- **Prompting**: "photorealistic people in Nano Banana Pro", "Midjourney prompts" → learn techniques, get prompts
- **Recommendations**: "best Claude Code skills", "top AI tools" → get a LIST of specific things
- **News**: "what's happening with OpenAI", "latest AI announcements" → current events
- **Market Research**: "Markham housing market", "Toronto condo prices" → real-time data
- **General**: any topic you're curious about → understand what the community is saying

---

## After Displaying Results

Once you show the synthesized output, you are now an **EXPERT** on this topic.

**For follow-up questions:**
- **DO NOT run new searches** - you already have research
- **Answer from what you learned** - cite the sources from the output
- **If they ask for a prompt** - write one using the patterns you learned
- Only do new research if user asks about a DIFFERENT topic

---

- `--quick` → Faster research with fewer sources (8-12 each)
- `--deep` → Comprehensive research (50-70 Reddit, 40-60 X)
- `--emit=json` → Machine-readable output
- `--emit=md` → Full markdown report

## How It Works

## How It Works

1. **Script searches Reddit + X** using OpenAI and xAI APIs (if configured)
2. **AI synthesizes findings** into "What I learned" and "KEY PATTERNS"
3. **Returns formatted output** ready to display to the user

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

## RECOMMENDATIONS Query Type

When the user asks for "best X", "top X", or "what X should I use", look for **specific names** in the synthesis and list them:

```
🏆 Most mentioned:
1. [Specific name] - mentioned {n}x (r/sub, @handle, blog.com)
2. [Specific name] - mentioned {n}x (sources)
3. [Specific name] - mentioned {n}x (sources)

Notable mentions: [other specific things with 1-2 mentions]
```

**BAD** for "best Claude Code skills":
> "Skills are powerful. Keep them under 500 lines."

**GOOD** for "best Claude Code skills":
> "Most mentioned: /commit (5 mentions), remotion skill (4x), git-worktree (3x)"

---

## WHEN USER WANTS A PROMPT: Write ONE Perfect Prompt

Based on what they want to create, write a **single, highly-tailored prompt**.

**If research says to use a specific prompt FORMAT, use it:**
- Research says "JSON prompts" → Write prompt AS JSON
- Research says "structured parameters" → Use key: value format
- Research says "natural language" → Use conversational prose

### Output Format:

```
Here's your prompt for {TARGET_TOOL}:

---

[The actual prompt IN THE FORMAT RESEARCH RECOMMENDS]

---

This uses [1-line explanation of research insight applied].
```

---

## Weighting Rules

- **Reddit/X > Web** - Engagement signals indicate real community validation
- **Recent > Old** - Prefer sources from last 7 days over 30 days
- **High engagement > Low** - 500+ upvotes matters more than 5 upvotes
- **Named authors > Anonymous** - @handles and usernames add credibility

## Output Interpretation

The script outputs:
- **What I learned** - Narrative synthesis paragraph
- **KEY PATTERNS** - Actionable patterns with bold names
- **Stats tree** - Source counts with engagement totals and top voices
- **CONTEXT STORED** - Topic summary for follow-up questions

## Related Skills

- `project-guide` - For understanding this project's architecture
- `code-review` - For reviewing code changes
