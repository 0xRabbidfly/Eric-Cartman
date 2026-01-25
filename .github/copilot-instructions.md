# Copilot Instructions — Canada AI Hub Portal

## Purpose
This repository will contain an internal CGI Canada “AI Hub Portal” web app:
- Modern portal UI (English/French) that primarily links to approved SharePoint content (no duplication).
- Global search and an AI assistant that answers with links/citations to approved sources.
- Later: Sales enablement AI tools (summarize/tailor) using approved collateral only.

## Tech Stack (selected)
- Frontend: Next.js (React) + TypeScript
- Hosting: Azure App Service (Linux) — single deploy (UI + API in one app)
- Auth: Microsoft Entra ID (Azure AD) with delegated access (user context)
- Data/search sources: Microsoft Graph + SharePoint Online
- AI (future): Azure OpenAI + Azure AI Search (RAG), with strict governance/audit
- UI: Fluent UI (preferred) and accessible patterns

## Non‑Negotiables
- Do not add external/public access paths. This is internal-only.
- Do not bypass SharePoint/M365 permissions. All results must be security-trimmed.
- Never put secrets/tokens in client-side code, localStorage, or logs.
- Never send non-approved or highly confidential content (e.g., RFPs/responses) to LLMs.
- Prefer minimal, maintainable solutions over clever abstractions.

## Project Conventions
- Language: TypeScript everywhere (no new JS files unless required).
- Next.js:
  - Prefer App Router (`app/`) and Server Components by default.
  - Use `"use client"` only when necessary (interactivity, hooks, browser APIs).
  - Keep server-only code in server contexts (route handlers, server actions, `lib/server/*`).
- Styling/UI:
  - Prefer Fluent UI components and tokens.
  - Meet WCAG basics: keyboard nav, focus states, ARIA for custom controls.
  - **Styling ownership**: Each component should have ONE source of truth for its styles:
    - Use CSS Modules (`.module.css`) co-located with the component for scoped styles.
    - Use global CSS (`globals.css`) only for design tokens, resets, and true utility classes.
    - Use inline styles only for truly dynamic values computed from props (e.g., `style={{ color: themeColor }}`).
  - Never duplicate the same CSS property in both inline styles and CSS classes—it creates untraceable specificity bugs.
- Internationalization:
  - All user-visible strings must be localizable (EN/FR).
  - Do not hardcode English copy in components.

## Code Style, Naming, Clean Code
- Use clear, descriptive names; avoid abbreviations unless they’re domain-standard.
- Keep functions small and single-purpose; prefer pure helpers for business logic.
- Naming conventions:
  - React components: `PascalCase`
  - Hooks: `useThing`
  - Variables/functions: `camelCase`
  - Types/interfaces: `PascalCase` (`SearchResult`, `GraphDriveItem`)
  - Constants: `SCREAMING_SNAKE_CASE` only for true constants.
- File conventions:
  - React components in `.tsx`; shared types in `.ts`.
  - Route segments under `app/` should be lowercase (kebab-case is acceptable).

## React + TypeScript Best Practices
- Default to Server Components; do not fetch portal data in the browser when it can be fetched on the server.
- Avoid unnecessary client state libraries. Use:
  - URL state (search params) for navigation/filter state
  - React state for local UI state
  - Server actions / route handlers for mutations and data access
- TypeScript:
  - Avoid `any`; prefer generics, `unknown` + narrowing, and explicit return types for exported functions.
  - Prefer discriminated unions for API result states (success/error) instead of throwing across boundaries.
- UI components:
  - Prefer Fluent UI components over custom controls.
  - Ensure keyboard accessibility and visible focus states.
- Strings:
  - All visible copy must come from an i18n/messages layer (EN/FR).
  - Do not embed user-facing strings inside utility functions.

## Errors & Logging
- Handle errors deliberately:
  - UI: show a user-safe message with a retry path when possible.
  - API: return structured errors (no stack traces) and correct status codes.
- Logging:
  - Never log tokens, authorization headers, raw documents, or sensitive content.
  - Prefer a correlation/request id pattern for troubleshooting.

## Authentication & Authorization
- Use Entra ID (OIDC).
- Prefer a server-side session model with httpOnly secure cookies.
- Use delegated user tokens for Microsoft Graph so results are permission-trimmed.
- Do not call Microsoft Graph directly from the browser unless it is explicitly safe and uses a short-lived token obtained via approved flow.
- For server calls to Graph, implement On-Behalf-Of (OBO) or equivalent delegated flow.

## Microsoft Graph / SharePoint Access
- Centralize Graph calls in a small service layer (e.g., `lib/server/graph/*`).
- Validate inputs and enforce allow-lists for:
  - SharePoint site IDs/URLs
  - Document libraries / drives
  - Content types
- Always return results with canonical links back to SharePoint/portal pages.

## Search & Assistant Behavior
- Search/assistant responses must be:
  - Short and actionable
  - Link-first (deep links to the right SharePoint page/doc)
  - Clear about uncertainty and scope
- If adding “direct answers”, include citations/links to sources used.
- When implementing RAG:
  - Use Azure AI Search for retrieval; keep the prompt grounded in retrieved snippets.
  - Enforce content allow-listing and audit logging.

## API Design (Next.js route handlers)
- Implement backend endpoints under `app/api/*`.
- Keep API responses stable and typed.
- Use appropriate status codes and structured error bodies.
- Never expose internal stack traces to the client.

## Security
- Sanitize and validate all user input (query strings, uploaded docs, parameters).
- Use secure headers and strict CSP where feasible.
- Log safely: do not log tokens, raw documents, or personal data.
- Prefer managed identity + Key Vault for secrets in Azure; locally use `.env.local` (never commit).

## Performance
- Target page load < 2s for typical portal navigation.
- Avoid client-side data waterfalls; prefer server-side fetching.
- Cache safe, non-user-specific data (e.g., navigation structure) with clear TTL.
- Do not cache user-specific/permissioned content in shared caches.

## Testing, Linting, Quality Gates
- Prefer small, testable functions and typed contracts.
- Add unit tests for any non-trivial business logic (search adapters, parsing, ranking).
- For UI, add lightweight component tests when logic is non-trivial.
- Before finishing a change, run the repo’s validation scripts (if present):
  - `npm run lint`
  - `npm run test`
  - `npm run build`

## Working in this Repo (Windows-friendly)
- Avoid bash-only scripts; commands should run in PowerShell and CI.
- Use cross-platform tooling (`node` scripts) for automation.

## Change Hygiene
- Keep changes focused on the requested task.
- Do not reformat unrelated files.
- Update or add minimal documentation only when it directly supports maintainability.
- If you introduce a new dependency, justify it and prefer well-maintained, widely-used packages.
