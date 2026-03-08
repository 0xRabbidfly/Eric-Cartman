---
name: obsidian-linked-research
description: Fetch a URL, summarize it, and save as a structured research note in the current Obsidian Research/Library taxonomy. Use the master Research Library MOC as the source of truth for tags, folder routing, and freshness updates.
argument-hint: URL to research and save
user-invocable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "1.2.0"
---

# Obsidian Linked Research

## Purpose

Take a URL → fetch its content → generate a structured summary → write a
standalone research note into the active `Research/Library/` taxonomy in the
Obsidian vault.

The library is no longer flat. Notes should be routed into the existing numbered
subfolders and tagged using the vocabulary established by the **master Research
Library MOC** and the vault tag index.

**Tweet/X URLs** get rich content via xAI's `x_search` tool (engagement stats,
thread context, media descriptions). **All other URLs** get plain-text extraction
via HTTP fetch. The **VS Code model** (you, the agent) does all summarization —
no external LLM API call needed for the intelligence step.

Vault writes go through the **obsidian** skill (composable CLI wrapper).

## When to Use

| Trigger | Example |
|---------|---------|
| User shares a URL and wants it saved | "research this: https://..." |
| User says "save this article" | "save this article to obsidian" |
| User says "obsidian research" | "/obsidian-linked-research https://x.com/..." |
| User shares a tweet to capture | "save this tweet: https://x.com/..." |
| User references a link for later | "I want to read this later, save it" |

## Prerequisites

- **Obsidian** must be running with CLI enabled
- **XAI_API_KEY** required for tweet URLs (in `.env`, environment, or `~/.config/last30days/.env`)
- Web URLs work without any API key

## Workflow

### Step 0 — Inspect Taxonomy First

Before fetching or summarizing, inspect the live research taxonomy so you do not
invent a second folder or tag scheme.

Read the master library MOC first:

```powershell
python .github/skills/obsidian/scripts/obsidian.py read --path "Research/Library/00 MOC/🗺️ MOC - Research Library.md"
```

Read any relevant topic MOC only after the master MOC, and only for extra domain
context. Topic MOCs are secondary maps, not the source of truth for canonical tags.

Read the current vault tag index:

```powershell
python -c "import sys; sys.path.insert(0,'.github/skills/obsidian/scripts'); from obsidian import Obsidian; print(Obsidian().tags().text)"
```

List the live research-library note paths so you can see the active buckets:

```powershell
python -c "import sys; sys.path.insert(0,'.github/skills/obsidian/scripts'); from obsidian import Obsidian; print(Obsidian().files(folder='Research/Library', ext='md').text)"
```

Use this routing table unless the live vault has changed again:

| Folder | Use for |
|-------|---------|
| `Research/Library/01 Agent Harnesses & Architecture/` | harnesses, orchestration, control planes, architecture, model/runtime design |
| `Research/Library/02 Skills, IDEs & Agent Tooling/` | skills, Copilot, Claude Code, IDEs, hooks, MCP, tooling |
| `Research/Library/03 Evals, Reliability & Control/` | evals, reliability, governance, testing, review, controls |
| `Research/Library/04 SDLC, Workflow & Strategy/` | SDLC, workflow redesign, consulting POV, product/API strategy |
| `Research/Library/05 Knowledge, RAG & Memory/` | RAG, retrieval, knowledge systems, Obsidian, memory, second brain |

Tagging rules before you write anything:

- Reuse tags already present in the master MOC's `Canonical Tag Guidance` first: `agents`, `ai-agents`, `agent-harnesses`, `skills`, `claude-code`, `copilot`, `mcp`, `evals`, `rag`, `sdlc`, `workflow-design`, `research`
- Prefer an existing vault tag over a new synonym if the meaning is the same
- Normalize to lowercase kebab-case; do not create variants like `AIagents`, `MachineLearning`, or mixed singular/plural duplicates if a canonical form already exists
- Only mint a new canonical tag if both the master MOC and the vault tag index are missing a genuinely useful concept
- Choose one primary library folder per note; do not duplicate the same note across folders

### Step 1 — Fetch Content

Run the fetch script to retrieve URL content:

```powershell
python .github/skills/obsidian-linked-research/scripts/fetch.py "<url>"
```

The script outputs JSON to stdout:

**For tweets:**
```json
{
  "type": "tweet",
  "url": "https://x.com/...",
  "text": "Full tweet/thread text",
  "author_handle": "username",
  "author_name": "Display Name",
  "date": "2026-03-01",
  "engagement": {"likes": 150, "reposts": 30, "replies": 12, "quotes": 5},
  "thread_context": "...",
  "is_thread": false,
  "media_descriptions": ["..."],
  "image_urls": ["https://pbs.twimg.com/media/..."],
  "article_content": "Full article text if X Article detected",
  "article_title": "Article title if X Article"
}
```

**For web pages:**
```json
{
  "type": "web",
  "url": "https://...",
  "title": "Page Title",
  "content": "Plain text content (up to 8000 chars)",
  "image_urls": ["https://example.com/hero.jpg", "https://example.com/diagram.png"]
}
```

The `image_urls` array includes OG images and meaningful `<img>` tags found in the
page (tracking pixels, favicons, and tiny icons are filtered out). Use Step 3b to
download them into the vault.

If the result contains an `"error"` key, report it to the user and stop.

**If `"needs_browser": true`**: The tweet contains an X Article that requires
JavaScript rendering. **Do NOT use `fetch_webpage`** — it cannot render X Article
pages. Instead, use the Playwright browser tools:

1. Navigate to the **tweet URL** (not the article URL — X Article URLs redirect
   to a "not supported" page):
   ```
   browser_navigate(url=tweet_url)
   ```
2. Wait for content to load (X Articles take a few seconds to render):
   ```
   browser_wait_for(time=5000)
   ```
3. The browser snapshot (returned by `wait_for`) contains the full article text
   in the accessibility tree. Extract the article content from the snapshot YAML.

Use the returned content as the article body for summarization. Combine it with
the tweet metadata (author, engagement) already in the fetch result.

**Extracting images from browser content**: Use `browser_evaluate` to extract
`pbs.twimg.com` image URLs from the DOM (the snapshot YAML won't include `src`
attributes):

```
browser_evaluate(function="() => { return JSON.stringify(Array.from(document.querySelectorAll('img')).filter(i => i.src && i.src.includes('pbs.twimg.com') && !i.src.includes('_bigger')).map(i => i.src)); }")
```

Then download the images using:

```powershell
python -c "import sys; sys.path.insert(0,'.github/skills/obsidian-linked-research/scripts'); from fetch import download_images; import json; r=download_images(['url1','url2'], '<vault_path>/Research/Library/attachments', '{slug}'); print(json.dumps(r))"
```

Close the browser when done: `browser_close()`

### Step 2 — Summarize (You, the Agent)

Using the fetched content, generate a **deep, structured analysis** — not a shallow
summary. Do NOT call an external API — use your own reasoning.

**Quality bar**: Study the existing notes in the target `Research/Library/`
subfolder for reference.
Good notes are section-by-section breakdowns with tables, code examples, specific
details, and "Relevance to This Repo" sections. They read like comprehensive
technical references, not tweet-length summaries.

Think through the content and produce this structure internally:

```json
{
  "title": "Clear, descriptive title for the note",
  "slug": "kebab-case-filename-slug (3-6 words, no special chars)",
  "library_bucket": "01 Agent Harnesses & Architecture | 02 Skills, IDEs & Agent Tooling | 03 Evals, Reliability & Control | 04 SDLC, Workflow & Strategy | 05 Knowledge, RAG & Memory",
  "library_path": "Research/Library/<bucket>/<slug>.md",
  "author": "@handle or Author Name",
  "source": "x|reddit|blog|article|github",
  "core_thesis": "1-2 sentences capturing the central argument or claim",
  "sections": [
    {
      "heading": "Section heading from the article",
      "content": "Detailed breakdown — preserve key arguments, lists, code, tables, quotes"
    }
  ],
  "key_takeaways_table": [
    {"lesson": "Short label", "detail": "Specific explanation"}
  ],
  "relevance_to_repo": "2-4 sentences on how this connects to Eric Cartman / the user's workflow",
  "related_notes": ["[[Note Title 1]]", "[[Note Title 2]]"],
  "master_moc_section": "The existing section in the master Research Library MOC this note belongs under",
  "topic_moc": "Optional topic MOC to update secondarily, if one clearly applies",
  "tag_rationale": "Short note on which tags were reused from the master MOC/tag index and whether any new canonical tag is truly needed",
  "tags": ["tag1", "tag2", "tag3"]
}
```

**Summarization rules:**
- `slug`: lowercase, hyphens only, 3-6 words, no special chars
- `library_bucket`: choose exactly one existing library folder based on the dominant theme
- `library_path`: always point at `Research/Library/<bucket>/<slug>.md`
- `tags`: lowercase, 4-7 tags, topically relevant, hyphens in multi-word, with existing vault tags preferred over new inventions
- `sections`: Preserve the article's own structure. Include code blocks, tables,
  numbered lists, and blockquotes from the original. DO NOT flatten rich content
  into bullet points.
- `key_takeaways_table`: 4-8 rows. Each "lesson" is a short label; "detail" is
  the specific, non-obvious insight. Avoid generic platitudes.
- `relevance_to_repo`: Connect the content to this repo's architecture, skills,
  or workflow patterns. Be specific.
- `related_notes`: Use `[[wiki-link]]` format to connect to other Library notes.
- `master_moc_section`: prefer an existing folder section in `🗺️ MOC - Research Library`; also use `Recently Added`
- `topic_moc`: optional; only set this if the note clearly belongs to a subordinate topic MOC such as `🤖 MOC - AI Agent Development`
- `tag_rationale`: explicitly check the master MOC and `Obsidian().tags().text` output before deciding to introduce any new canonical tag
- `source`: detect from URL (`x.com`→x, `reddit.com`→reddit, `github.com`→github, else→article)
- `author`: extract from content or URL. "Unknown" if not identifiable
- For tweets: incorporate engagement stats and thread context

### Step 3 — Compose Note

Assemble the markdown. The note should be **comprehensive enough to replace
reading the original** — a full technical reference, not a summary card.

Use this template as a starting point, but adapt sections to match the content:

````markdown
---
type: research-note
source: {source}
author: "{author}"
url: {url}
date_found: {today YYYY-MM-DD}
date_saved: {today YYYY-MM-DD}
tags: [{comma-separated tags}]
status: unread
---

# {title}

**Author**: {author}
**Published**: {date}
**Views**: {views if known}
**Source**: {url}
**Engagement**: ❤️ {likes} 🔁 {reposts} 💬 {replies} 📝 {quotes}

---

## Core Thesis

{1-2 sentences: the central argument or finding}

---

## {Section 1 Heading from Article}

{Detailed content — preserve tables, code blocks, lists, quotes from original.
Include specific numbers, tool names, people. Don't flatten into generic bullets.}

## {Section 2 Heading}

{Continue for each major section of the source material...}

---

## Key Takeaways

| Lesson | Detail |
|--------|--------|
| {short label} | {specific, non-obvious insight} |
| ... | ... |

---

## Relevance to This Repo

{2-4 sentences connecting this to Eric Cartman's architecture, skills, or
the user's workflow. Be specific about what to keep, change, or investigate.}

---

## Related

- [[Note Title 1]] · [[Note Title 2]]
- External source: {url}

## Images

{if images present}

## My Notes


````

**Formatting rules:**
- Use `---` horizontal rules between major sections for visual scanability
- Preserve code blocks with language hints (```bash, ```json, etc.)
- Use tables for structured comparisons (don't convert tables to bullet lists)
- Use blockquotes (`>`) for direct quotes from the source
- Include `**bold**` for key terms and emphasis as in the original
- `## Related` should use `[[wiki-links]]` to connect to other Library notes
- Keep the frontmatter compatible with existing research notes in the chosen folder

And if it's a thread, add a Thread Context section before Summary:

```markdown
## Thread Context

{thread_context}
```

**If images are present**, add an Images section before My Notes:

```markdown
## Images

![[{slug}-1.jpg]]
*{media_description_1}*

![[{slug}-2.png]]
*{media_description_2}*
```

Use `![[filename]]` (Obsidian wiki-link embed) for each image. If
`media_descriptions` are available, add them as italic captions below each image.

### Step 3b — Download Images

If the fetch result contains `image_urls`, download them to the vault's
attachment folder. First, discover the vault path:

```powershell
python -c "import sys; sys.path.insert(0,'.github/skills/obsidian/scripts'); from obsidian import Obsidian; print(Obsidian().vault_info().text)"
```

Parse the vault path from the output, then download images:

```powershell
python .github/skills/obsidian-linked-research/scripts/fetch.py "<url>" --download-images "<vault_path>/Research/Library/attachments" --slug "{slug}"
```

Or if you already have the fetch result and just need to download, call Python
directly:

```powershell
python -c "import sys; sys.path.insert(0,'.github/skills/obsidian-linked-research/scripts'); from fetch import download_images; download_images({image_urls_list}, '<vault_path>/Research/Library/attachments', '{slug}')"
```

Images will be saved as `{slug}-1.jpg`, `{slug}-2.png`, etc.
Use `![[{slug}-1.jpg]]` in the note to embed them.

### Step 4 — Write to Vault

Pipe the composed note to the obsidian skill:

```powershell
@'
{full markdown content}
'@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Research/Library/{library_bucket}/{slug}.md"
```

**Note**: `obsidian.py create` produces no stdout on success. Verify the write:

```powershell
python .github/skills/obsidian/scripts/obsidian.py read --path "Research/Library/{library_bucket}/{slug}.md" 2>&1 | Select-Object -First 6
```

If the first few lines match your frontmatter, the write succeeded.

If the path already exists, append `-2`, `-3`, etc. to the slug.
Check first:

```powershell
python .github/skills/obsidian/scripts/obsidian.py read --path "Research/Library/{library_bucket}/{slug}.md" 2>$null
```

If that returns content, increment the suffix.

### Step 5 — Update the Master MOC

After the note exists, refresh the **master Research Library MOC** as part of the
same run unless doing so would require a major restructure.

At minimum:

- add the note to the relevant folder section if it is useful for navigation
- append or refresh an entry under `Recently Added`
- keep the one-line description current and specific

If the master MOC would need a larger restructure, stop after creating the note and
suggest a separate `obsidian-vault-linker` refresh.

If the incoming report justifies a new canonical tag:

- add the new tag to `Canonical Tag Guidance`
- normalize away obvious duplicates instead of adding a synonym
- only promote the tag if it is durable and likely to organize multiple future notes

For lightweight sync, append a short block to the master MOC:

```powershell
@'

## Recently Added

- [[{slug}|{title}]] — {one-line why this note matters}
- Tags: #{tag1} #{tag2} #{tag3}
'@ | python .github/skills/obsidian/scripts/obsidian.py append --path "Research/Library/00 MOC/🗺️ MOC - Research Library.md"
```

If a topic MOC clearly applies, update it secondarily after the master MOC is
current. The master MOC remains authoritative for canonical tags and library-wide freshness.

### Step 6 — Open in Obsidian

```powershell
python -c "import sys; sys.path.insert(0,'.github/skills/obsidian/scripts'); from obsidian import Obsidian; ob=Obsidian(); ob.open('Research/Library/{library_bucket}/{slug}')"
```

### Step 7 — Confirm

Report to the user:
- Note title and path
- Brief summary (1-2 sentences)
- Tag list
- Whether the master MOC was updated, and whether any topic MOC was also updated
- Obsidian link: `obsidian://open?vault=Obsidian%20Vault&file=Research%2FLibrary%2F{library_bucket_urlencoded}%2F{slug}`

### Step 8 — Reflection (composable)

Invoke the `skill-reflection` skill with the following context:

- **Calling skill**: `obsidian-linked-research`
- **SKILL.md path**: `.github/skills/obsidian-linked-research/SKILL.md`
- **Steps completed**: list each step with pass/fail/skipped
- **Friction notes**: any workarounds, retries, unexpected errors, or manual interventions

The reflection skill will analyze the run and produce improvement recommendations.

## Output Format

The output is a `Research/Library/<bucket>/{slug}.md` file in the Obsidian vault,
following the enriched note template above. The format matches the existing
library pages and respects the live MOC/tag taxonomy already in the vault.

## Rules

1. **Never skip the fetch step** — always run `fetch.py` even if you think you know the content
2. **Never call an external LLM API** for summarization — use your own model (VS Code)
3. **Always pipe through the obsidian skill** for vault writes — never write files directly
4. **Always use `@'...'@`** (single-quoted heredoc) when piping to obsidian.py
5. **Handle fetch errors gracefully** — if fetch returns an error, tell the user and suggest alternatives
6. **Deduplicate** — check if a note with a similar slug already exists before creating
7. **UTF-8** — the fetch script handles Windows UTF-8 automatically; for the pipe, ensure `$OutputEncoding = [System.Text.Encoding]::UTF8` if needed
8. **Zero pip deps** — `fetch.py` uses only Python stdlib
9. **Read the master MOC first** — tag and folder decisions must be based on the live `Research/Library/00 MOC/🗺️ MOC - Research Library.md`
10. **Prefer existing tags** — reuse the master MOC's canonical lowercase kebab-case tags before introducing a new one
11. **Keep the master MOC fresh** — update it with every successful research-note addition unless the change truly requires larger curation work
12. **Use topic MOCs secondarily** — they are optional supporting maps, not the authoritative taxonomy source

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `obsidian` | Composable vault wrapper — used for all vault writes |
| `obsidian-daily-research` | Automated daily pipeline — produces `Research/Dailies/` notes with `#keep` tags that get promoted to `Research/Library/` |
| `last30days` | Research skill — shares xAI API patterns and `.env` key cascade |
| `content-research-writer` | Long-form writing partner — can use Library notes as sources |

## Architecture

```
User: "research this: <url>"
          │
          ▼
┌─────────────────────────┐
│  Read master MOC        │  ← Determine folder + canonical tags
│  + tag index + library  │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  fetch.py <url>         │  ← Python stdlib only
│  ├─ Tweet? → xAI API   │     (x_search tool, grok-4-1-fast)
│  └─ Web?  → urllib      │     (HTML strip, plain text)
└──────────┬──────────────┘
           │ JSON stdout
           ▼
┌─────────────────────────┐
│  Agent (VS Code model)  │  ← Summarize, structure, compose
│  ├─ Generate summary    │
│  ├─ Compose markdown    │
│  └─ Pipe to obsidian.py │
└──────────┬──────────────┘
           │ heredoc pipe
           ▼
┌─────────────────────────┐
│  obsidian.py create     │  ← CLI wrapper (composable)
│  └─ Research/Library/   │
│     <bucket>/{slug}.md  │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Update master MOC      │  ← Keep library map and tags current
│  (+ topic MOC if needed)│
└─────────────────────────┘
```
