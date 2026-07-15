# AI Features

SKTR can use an AI provider to explain deterministic findings and recommend
focused actions. AI is optional and is not the primary detector.

The provider receives structured SKTR context: knowledge summary, grouped issues,
priority findings, module metrics, changed-file metadata, and dependency edges.
It does not receive the full raw repository source or raw Git diff.

## OpenAI setup

Set an API key in the environment:

```bash
export SKTR_OPENAI_API_KEY="your-api-key"
sktr ai doctor
sktr review --ai
```

Resolution order:

1. `SKTR_OPENAI_API_KEY`
2. `OPENAI_API_KEY`

If both exist, the SKTR-specific variable wins. Keys are never stored in config,
included in artifacts, or printed by diagnostics.

## Configuration

```yaml
ai:
  enabled: true
  provider: openai
  model: gpt-5.6-terra
```

Select a model for one review:

```bash
sktr review --ai --model gpt-5.6-sol
```

Interactive init offers these OpenAI profiles:

| Profile | Model | Intended use |
|---|---|---|
| Balanced (recommended) | `gpt-5.6-terra` | Architecture review with a quality/cost balance |
| Fast | `gpt-5.6-luna` | Frequent and high-volume reviews |
| Best quality | `gpt-5.6-sol` | Difficult, quality-first reviews |
| Custom | User-provided | Snapshots, aliases, or future models |

SKTR does not restrict manual model IDs. Older existing configurations continue
to load, while new OpenAI configurations default to Terra.

Disable configured AI features for one review:

```bash
sktr review --no-ai
```

## Diagnostics

```bash
sktr ai doctor
```

The doctor prints the provider, model, and environment variable where a key was
found. It never prints the value. If the key is missing, reviews continue and
include a warning instead of crashing.

## Output

When enabled, the current structured AI output is stored in the JSON artifact's
`ai_review` field and rendered in terminal and Markdown reports. Documentation
uses generic AI terminology because provider capabilities may evolve independently
of the deterministic analysis model.
