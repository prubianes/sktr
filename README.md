# SKTR

SKTR means System Knowledge & Technical Review.

The first product goal is a Python CLI command:

```bash
sktr review
```

SKTR provides a language-agnostic core model, plugin contracts, deterministic rules,
review scopes, and pluggable outputs.

## Configuration

SKTR looks for `sktr.yml` or `sktr.yaml` in the current directory.

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
