# Configuration

SKTR loads `sktr.yml` or `sktr.yaml` from the current directory. Commands that
support it can load another file with `--config path/to/sktr.yml`.

Generate a valid configuration with:

```bash
sktr init
sktr init --yes
```

## Complete example

```yaml
project:
  name: sample-app
  default_base: main

review:
  default_scope: working_tree
  fail_on: null
  exclude:
    - node_modules/
    - .venv/
    - dist/
    - build/
    - target/

plugins:
  analyzers:
    - sktr-python
    - sktr-javascript-typescript
    - sktr-java
  rules:
    - sktr-rules-default
  outputs:
    - terminal
    - markdown
    - json
    - mermaid

rules:
  enabled:
    - new_dependency
    - large_file
    - large_function
    - forbidden_dependency
    - dependency_cycle
    - high_fan_out
    - public_api_change
    - missing_tests
  large_file:
    max_changed_lines: 300
  large_function:
    max_lines: 80
  fan_out:
    max_modules: 8
  forbidden_dependencies:
    - source: controllers
      target: repositories
      reason: Controllers should access repositories through services.

ai:
  enabled: false
```

To enable OpenAI-powered features, replace the final section with:

```yaml
ai:
  enabled: true
  provider: openai
  model: gpt-5-mini
```

Do not store API keys in `sktr.yml`.

## Sections

### `project`

- `name`: project name used in metadata and reports.
- `default_base`: branch used by `sktr review --branch` when `--base` is omitted.

### `review`

- `default_scope`: currently generated as `working_tree`. Use `--branch`, `--base`,
  or `--commit` to select another scope for one review.
- `fail_on`: optional CI threshold: `info`, `low`, `medium`, `high`, or `critical`.
- `exclude`: Git-ignore-style paths removed before analysis and rules. Set this to
  `[]` to disable the generated defaults.

### `plugins`

- `analyzers`: analyzer plugins used to build the knowledge model.
- `rules`: deterministic rule packs.
- `outputs`: output plugins expected to be installed and checked by the plugin doctor.
- `ai_providers`: optional additional provider plugins.

Run `sktr plugins list` to inspect installed plugins and `sktr plugins doctor` to
validate the configuration.

### `rules`

- `enabled`: rule keys to execute. Omitted rules are disabled.
- `large_file.max_changed_lines`: changed-line threshold for a large change.
- `large_function.max_lines`: estimated symbol-size threshold.
- `fan_out.max_modules`: maximum distinct internal module dependencies.
- `forbidden_dependencies`: disallowed source-to-target module patterns with an
  optional human-readable reason.

Rules consume the enriched knowledge model, not raw Python AST objects.

### `ai`

- `enabled`: whether AI features run by default.
- `provider`: installed provider name; required when enabled.
- `model`: provider model override.

When `enabled` is `false`, omit `provider` and `model`. Use `--ai`, `--no-ai`, and
`--model` for one-run overrides.

## Invalid configuration

SKTR reports the file path and validation problem without a traceback. Fix the
file or regenerate it:

```bash
sktr init --force
```
