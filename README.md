# SKTR

SKTR means System Knowledge & Technical Review.

The first product goal is a Python CLI command:

```bash
sktr review
```

SKTR provides a language-agnostic core model, plugin contracts, deterministic
knowledge enrichment, deterministic rules, review scopes, and pluggable outputs.

## Configuration

SKTR looks for `sktr.yml` or `sktr.yaml` in the current directory.

Create a config interactively:

```bash
sktr init
```

Create the default config without prompts:

```bash
sktr init --yes
```

Use a preset:

```bash
sktr init --preset recommended
sktr init --preset minimal
sktr init --preset custom
```

Enable the default installed AI provider in non-interactive setup:

```bash
sktr init --yes --ai
```

Preview the detected project and generated YAML without writing a file:

```bash
sktr init --yes --dry-run
```

Interactive setup detects project metadata and installed plugins, provides
arrow-key menus and checkbox selection, previews the final configuration, and
validates plugin capabilities before writing `sktr.yml`. API keys remain in
environment variables and are never written to configuration.

Overwrite an existing config:

```bash
sktr init --force
```

Example `sktr.yml`:

```yaml
project:
  name: sample-app
rules:
  enabled:
    - new_dependency
    - large_file
    - large_function
    - forbidden_dependency
  large_file:
    max_changed_lines: 300
  large_function:
    max_lines: 80
  forbidden_dependencies:
    - source: "controllers"
      target: "repositories"
      reason: "Controllers should access repositories through services."
```

## Review Scopes

By default, SKTR reviews the current working tree against `HEAD`:

```bash
sktr review
```

Review the current branch against the merge-base with the configured base branch:

```bash
sktr review --branch
```

Use an explicit base branch:

```bash
sktr review --base develop
```

Review one commit against its parent:

```bash
sktr review --commit HEAD~1
```

## Outputs

Write terminal output to stdout:

```bash
sktr review --format terminal
```

Write JSON to stdout:

```bash
sktr review --format json
```

Write Markdown to stdout:

```bash
sktr review --format markdown
```

Write JSON or Markdown to a file:

```bash
sktr review --format json --output sktr-review.json
sktr review --format markdown --output REVIEW.md
```

JSON output is the canonical SKTR analysis artifact. It includes schema version,
metadata, repository info, summary score/risk, changed files, knowledge model
summary, issues, executed rules, and backward-compatible review fields.

Markdown output is a deterministic review document with a summary, risk score,
changed-file table, grouped issues, architecture and maintainability findings,
suggestions, and metadata.

### Risk score

The score starts at 100 and deterministic findings subtract severity-weighted
penalties. Repeated findings from the same rule and category are capped so a
large diff cannot reach zero through repetition alone. Informational findings
and the number of changed files do not reduce the score; changed-file count
represents review effort, not architectural risk. Independent risk categories
accumulate, while each category has its own cap.

Risk levels are low (85-100), medium (65-84), high (40-64), and critical
(0-39).

## Knowledge Enrichment

Before rules run, SKTR enriches the Knowledge Model with deterministic engineering
metadata:

- file, symbol, dependency, and module metrics
- risk indicators
- review priority
- knowledge summary

Rules and future AI providers consume this enriched model instead of raw parser
data.

## Graphs

Generate a Mermaid dependency graph from the SKTR knowledge model:

```bash
sktr graph
sktr graph --level module
sktr graph --level file
sktr graph --format mermaid --output architecture.mmd
```

## Plugins

SKTR discovers plugins through Python entry points:

- `sktr.analyzers`
- `sktr.rules`
- `sktr.outputs`
- `sktr.ai_providers`

List installed plugins:

```bash
sktr plugins list
```

Validate configured plugins:

```bash
sktr plugins doctor
```

## AI Review

SKTR can add one optional AI Review containing a concise overview and prioritized
recommendations based only on structured deterministic findings.

```yaml
ai:
  enabled: true
  provider: openai
  model: gpt-5-mini
```

When disabled, the configuration is simply:

```yaml
ai:
  enabled: false
```

Use `--ai` or `--no-ai` to override the configured behavior for one run. OpenAI
credentials are resolved from `SKTR_OPENAI_API_KEY` and then `OPENAI_API_KEY`;
keys are never stored in `sktr.yml`.
