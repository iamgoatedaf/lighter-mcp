# Lighter MCP — documentation site

This folder is a [Mintlify](https://mintlify.com) project. The contents
get deployed automatically by Mintlify whenever they're pushed to the
`main` branch on GitHub.

## Local preview

Requires Node.js ≥ 20.17.

```bash
# from the repo root
cd website
npm install
npm run dev
# open http://localhost:3000
```

The CLI watches the folder and live-reloads on every save.

## Project layout

```
website/
├── docs.json                  # site config (theme, navigation, branding)
├── index.mdx                  # landing page (hero + cards)
├── logo/                      # logo rendered in the header
├── favicon.png
├── get-started/               # onboarding pages
├── tools/                     # MCP tool reference (one page per family)
├── reference/                 # internals: safety, confirmations, audit, CLI
├── adapters/                  # per-agent setup (Cursor, Claude, Codex, …)
├── guides/                    # end-to-end walkthroughs
└── security/                  # threat model + disclaimer
```

## Deployment

1. Sign in at [mintlify.com/start](https://mintlify.com/start) and link
   the repo. Mintlify installs a GitHub App that auto-deploys every
   push that touches `website/`.
2. Your site is reachable at `https://<your-project>.mintlify.app`
   immediately after the first build.
3. Optional: attach a custom domain (e.g. `docs.lighter-mcp.xyz`) from
   the Mintlify dashboard.

## Editing rules

- All content pages are MDX (`.mdx`). Frontmatter requires `title` and
  `description`.
- Use built-in components (`<Card>`, `<CardGroup>`, `<Steps>`,
  `<Tabs>`, `<CodeGroup>`, `<Note>`, `<Warning>`, `<ParamField>`,
  `<ResponseField>`, …) — they're already styled by the theme.
- Cross-page links are relative to the docs root (`/tools/read`, not
  `/tools/read.mdx`).
- Run `npm run broken-links` before opening a PR.

## Source of truth

When tool behavior, schemas, or safety semantics change in the Python
code, update the corresponding Mintlify page in the same PR.
