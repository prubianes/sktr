# Contributing to SKTR

Thanks for helping improve deterministic software intelligence.

## Before starting

- Search existing [issues](https://github.com/prubianes/sktr/issues) before
  opening a new one.
- Use an issue to discuss large features, new public contracts, or artifact schema
  changes before implementation.
- Do not include repository source, API keys, or other private data in issues,
  fixtures, logs, or screenshots.

## Development setup

SKTR requires Python 3.13 or newer, Git, and
[uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/prubianes/sktr.git
cd sktr
uv sync
uv run pytest
```

Run the local CLI with `uv run sktr`. The complete development architecture is
documented in [docs/development.md](docs/development.md).

## Design requirements

- Keep `sktr_core`, enrichment, rules, outputs, graphing, and AI context
  language-agnostic.
- Put language-specific parsing and resolution inside analyzer plugins.
- Add deterministic detection or enrichment before asking AI to explain it.
- Make rules consume the normalized knowledge model and review context, never raw
  parser nodes.
- Preserve artifact schema `0.1`; incompatible artifact changes require a new
  schema version.
- Do not expose credentials in diagnostics, logs, fixtures, or error messages.

## Pull requests

Keep changes focused and include tests proportional to their behavior and risk.
Before opening a pull request, run:

```bash
uv run pytest
uv build
git diff --check
```

Describe the behavior changed, tests performed, and any compatibility or artifact
impact. CI repeats the suite and package smoke tests on Python 3.13 and 3.14.

For vulnerabilities, do not open a public issue; follow [SECURITY.md](SECURITY.md).

