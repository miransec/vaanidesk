# Screenshots (capture plan)

This directory holds **real** UI screenshots for the public README and portfolio demos.

Do **not** commit fabricated product UI images. Until captures exist, leave placeholders only.

## Suggested files

| File | Capture target | Route / notes |
|------|----------------|---------------|
| `01-home.png` | Home / brand first viewport | `/` |
| `02-multilingual-chat.png` | Hinglish or Hindi chat turn + workflow panel | `/chat` as `demo-anya` |
| `03-policy-citations.png` | Policy answer with **Citations** list visible | `/chat` — return policy query |
| `04-confirmation.png` | Sensitive cancel confirmation (Approve / Deny) | `/chat` — cancel `VD-10001` |
| `05-voice-workflow.png` | Voice section: transcript review / mock STT badges | `/chat` — Mock STT/TTS panel |
| `06-channels.png` | Channels / simulator surface | `/channels` |
| `07-knowledge.png` | Knowledge interface | `/knowledge` |
| `08-evaluations.png` | Evaluation run results (113 cases) | `/admin/evaluations` |
| `09-observability.png` | Observability / metrics admin | `/admin/observability` |
| `10-account-auth.png` | Account sessions / Sign out | `/account` after JWT login |

Optional later: channel attachment upload UI if you want to illustrate multimodal **transport** without implying a vision model.

## Capture guidelines

- Use the Docker or local stack with seed data loaded.
- Prefer desktop Chromium at ~1440×900; crop chrome noise.
- Blur any real emails or tokens if you ever use non-demo accounts.
- Keep filenames stable so README image links do not churn.

## README embedding (after capture)

```markdown
![Home](docs/assets/screenshots/01-home.png)
```

Until then, the root README links here instead of broken image tags.
