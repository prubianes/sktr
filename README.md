# SKTR

SKTR means System Knowledge & Technical Review.

The first product goal is a Python CLI command:

```bash
sktr review
```

This foundation milestone provides the language-agnostic core model, plugin contracts,
a skeletal review pipeline, a placeholder terminal reporter, and tests.

## Configuration

SKTR looks for `sktr.toml`, `sktr.yaml`, or `sktr.yml` in the current directory.

Example `sktr.yaml`:

```yaml
rules:
  forbidden_dependencies:
    - source: "controllers"
      target: "repositories"
```

Equivalent `sktr.toml`:

```toml
[rules]
forbidden_dependencies = [
  { source = "controllers", target = "repositories" },
]
```
