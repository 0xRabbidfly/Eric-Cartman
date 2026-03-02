---
name: obsidian-linked-research
description: Fetch a URL, summarize it, and save as a structured research note in Obsidian Research/Library/. Use when user shares a link and says "research this", "save this article", "save this to obsidian", or "/obsidian-linked-research".
argument-hint: URL to research and save
user-invokable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Obsidian Linked Research

## Purpose

Take a URL → fetch its content → generate a structured summary → write a
standalone research note to `Research/Library/` in the Obsidian vault.

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
  "content": "Plain text content (up to 8000 chars)"
}
```

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

**Quality bar**: Study the existing notes in `Research/Library/` for reference.
Good notes are section-by-section breakdowns with tables, code examples, specific
details, and "Relevance to This Repo" sections. They read like comprehensive
technical references, not tweet-length summaries.

Think through the content and produce this structure internally:

```json
{
  "title": "Clear, descriptive title for the note",
  "slug": "kebab-case-filename-slug (3-6 words, no special chars)",
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
  "tags": ["tag1", "tag2", "tag3"]
}
```

**Summarization rules:**
- `slug`: lowercase, hyphens only, 3-6 words, no special chars
- `tags`: lowercase, 4-6 tags, topically relevant, hyphens in multi-word
- `sections`: Preserve the article's own structure. Include code blocks, tables,
  numbered lists, and blockquotes from the original. DO NOT flatten rich content
  into bullet points.
- `key_takeaways_table`: 4-8 rows. Each "lesson" is a short label; "detail" is
  the specific, non-obvious insight. Avoid generic platitudes.
- `relevance_to_repo`: Connect the content to this repo's architecture, skills,
  or workflow patterns. Be specific.
- `related_notes`: Use `[[wiki-link]]` format to connect to other Library notes.
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

**Author**: {author} ([profile link](url))
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
- [External link description](url)

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
'@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Research/Library/{slug}.md"
```

**Note**: `obsidian.py create` produces no stdout on success. Verify the write:

```powershell
python .github/skills/obsidian/scripts/obsidian.py read --path "Research/Library/{slug}.md" 2>&1 | Select-Object -First 3
```

If the first few lines match your frontmatter, the write succeeded.

If the path already exists, append `-2`, `-3`, etc. to the slug.
Check first:

```powershell
python .github/skills/obsidian/scripts/obsidian.py read --path "Research/Library/{slug}.md" 2>$null
```

If that returns content, increment the suffix.

### Step 5 — Open in Obsidian

```powershell
python -c "import sys; sys.path.insert(0,'.github/skills/obsidian/scripts'); from obsidian import Obsidian; ob=Obsidian(); ob.open('Research/Library/{slug}')"
```

### Step 6 — Confirm

Report to the user:
- Note title and path
- Brief summary (1-2 sentences)
- Tag list
- Obsidian link: `obsidian://open?vault=Obsidian%20Vault&file=Research%2FLibrary%2F{slug}`

### Step 7 — Reflection (composable)

Invoke the `skill-reflection` skill with the following context:

- **Calling skill**: `obsidian-linked-research`
- **SKILL.md path**: `.github/skills/obsidian-linked-research/SKILL.md`
- **Steps completed**: list each step with pass/fail/skipped
- **Friction notes**: any workarounds, retries, unexpected errors, or manual interventions

The reflection skill will analyze the run and produce improvement recommendations.

## Output Format

The output is a `Research/Library/{slug}.md` file in the Obsidian vault, following
the enriched note template above. The format matches the existing Library pages
created by `obsidian-daily-research`'s promote pass.

## Rules

1. **Never skip the fetch step** — always run `fetch.py` even if you think you know the content
2. **Never call an external LLM API** for summarization — use your own model (VS Code)
3. **Always pipe through the obsidian skill** for vault writes — never write files directly
4. **Always use `@'...'@`** (single-quoted heredoc) when piping to obsidian.py
5. **Handle fetch errors gracefully** — if fetch returns an error, tell the user and suggest alternatives
6. **Deduplicate** — check if a note with a similar slug already exists before creating
7. **UTF-8** — the fetch script handles Windows UTF-8 automatically; for the pipe, ensure `$OutputEncoding = [System.Text.Encoding]::UTF8` if needed
8. **Zero pip deps** — `fetch.py` uses only Python stdlib

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
└─────────────────────────┘
```
