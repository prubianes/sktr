# Outputs

Every review output receives the same `ReviewResult`. Outputs do not access Git,
analyzers, rule implementations, AI providers, or raw parser data.

Terminal and Markdown summaries show review breadth when enrichment identifies
changed production files or modules. Breadth is score metadata, not an issue, and
can make a large review Medium risk even when no deterministic finding exists.
Completed pipeline runs use the status `review complete`.

## Terminal

```bash
sktr review --format terminal
```

Terminal output is optimized for interactive reading and writes to stdout unless
`--output` is provided.

## Markdown

```bash
sktr review --format markdown
sktr review --format markdown --output REVIEW.md
```

Markdown includes summary, score and risk, changed files, grouped findings,
suggested actions, optional AI output, and metadata.

## JSON

```bash
sktr review --format json
sktr review --format json --output sktr-review.json
```

JSON is the canonical SKTR artifact. It contains `schema_version`, metadata,
repository details, summary, changed files, knowledge summaries, issues, rule
results, diagnostics, excluded files, score, risk, the serialized review result,
and optional `ai_review`.

Schema `0.1` is frozen and published at
[`docs/schema/sktr-review-0.1.schema.json`](schema/sktr-review-0.1.schema.json).

Render a saved artifact without rerunning analysis:

```bash
sktr report sktr-review.json --format terminal
sktr report sktr-review.json --format markdown --output REVIEW.md
```

## Mermaid graphs

```bash
sktr graph --format mermaid
sktr graph --format mermaid --output architecture.mmd
sktr graph --level file --output files.mmd
sktr graph --scope repository --output repository.mmd
sktr graph --scope repository --cycles
```

Graphs are generated from modules, files, and dependencies in the knowledge
model. They include isolated nodes, remove duplicate edges, preserve resolved
context targets, and omit unresolved external dependencies. Changed and context
nodes receive distinct Mermaid styles. See [architecture graphs](graphs.md) for
scopes and focused views.
