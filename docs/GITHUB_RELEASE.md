# GitHub public release metadata (VaaniDesk v1.0.0)

Use these values when creating or updating the public portfolio repository. They describe the **implemented** v1.0.0 surface.

## Repository name

```text
vaanidesk
```

## Description (About panel)

```text
Multilingual AI customer-support platform with controlled agents, hybrid RAG, secure business actions and production-grade evaluation.
```

## Topics (focused set)

```text
ai-agents
rag
fastapi
pgvector
multilingual-ai
llm-security
nextjs
postgresql
ai-evaluation
docker
```

Optional extras if GitHub allows more without clutter: `playwright`, `typescript`, `redis`.

Do **not** add a topic claiming a live MCP server until `mcp_server/` ships.

## Visibility

- Prefer **private** until you complete a final human review of screenshots and About text.
- When ready: set **public**, attach annotated tag `v1.0.0`, and paste release notes from [`CHANGELOG.md`](../CHANGELOG.md) / [`docs/RELEASE_NOTES_v1.0.0.md`](./RELEASE_NOTES_v1.0.0.md).

## Homepage URL

Leave empty until a public demo is hosted. Local Compose URLs are for developers only.

## README CI badge

After the repo exists under your account, replace `OWNER` in `README.md`:

```markdown
[![CI](https://github.com/OWNER/vaanidesk/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/vaanidesk/actions/workflows/ci.yml)
```

## Release title

```text
VaaniDesk v1.0.0
```

## Release assets

Optional: none required. Source tag is sufficient for a portfolio repo. Do not attach `.env` or credential files.
