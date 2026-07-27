# SKTR v1.1.0

SKTR 1.1.0 introduces multilingual reviews, allowing teams to receive
deterministic reports and AI explanations in their preferred language.

## What's new

### English and Spanish reports

SKTR now provides complete deterministic output catalogs for:

- English (`en`)
- Spanish (`es`)

Terminal and Markdown reports localize summaries, risk levels, findings,
diagnostics, suggested actions, review metadata, and empty-review guidance.

```bash
sktr review --language es
sktr review --format markdown --language es --output REVIEW.md
```

### AI explanations in any language

When AI review is enabled, a supported BCP 47-style language tag can be
requested:

```bash
sktr review --ai --language es
sktr review --ai --language pt-BR
sktr review --ai --language ja
```

OpenAI and Anthropic Claude are instructed to write human-readable explanations
and recommendations in the requested language while preserving paths, rule IDs,
severities, module names, and code symbols.

For languages without a deterministic SKTR catalog, the report structure
remains in English while AI explanations use the requested language.

### Language-aware initialization

Interactive setup now asks which review language to use:

```bash
sktr init
```

Non-interactive initialization supports the same setting:

```bash
sktr init --yes --language es
```

The generated configuration stores the selection:

```yaml
output:
  language: es
```

### Per-command overrides

The configured language can be overridden without editing `sktr.yml`:

```bash
sktr review --language es
sktr report sktr-review.json --language es
```

Changing the language while rendering an existing artifact localizes
deterministic report text but does not regenerate or translate AI prose already
stored in that artifact.

## Stable automation contract

Multilingual output does not change SKTR's machine-readable contract:

- JSON Schema remains at version `0.1`.
- JSON keys remain canonical English.
- Rule IDs and severity values remain unchanged.
- Paths, module names, and code identifiers are never translated.
- Risk scores and deterministic findings are identical across languages.
- The requested language is recorded in review metadata.

## Packaging

- Fixed the project logo on PyPI by using an absolute, release-pinned HTTPS
  asset URL.
- Added a release check to prevent unsupported relative image URLs from reaching
  package metadata.

## Upgrade

SKTR requires Python 3.11 or newer.

```bash
python -m pip install --upgrade sktr==1.1.0
sktr --version
```

Existing configurations continue to work and default to English. Add
`output.language` only when a different language is desired.

## Quality

- 213 automated tests passing.
- English output compatibility and snapshots preserved.
- Spanish initialization and Markdown review smoke-tested.
- AI language propagation tested across the shared provider pipeline.
- Canonical JSON artifact behavior remains unchanged.

**Full changelog:** [`v1.0.0...v1.1.0`](https://github.com/prubianes/sktr/compare/v1.0.0...v1.1.0)
