# Development

## Setup

SKTR requires Python 3.13 or newer. Install the locked development environment:

```bash
uv sync
```

Run tests and the local CLI:

```bash
uv run pytest
uv run sktr --help
uv run sktr review
```

## Repository structure

- `apps/cli/sktr_cli`: Typer command surface and initialization flow
- `packages/sktr_core`: models, pipeline, configuration, and plugin contracts
- `packages/sktr_git`: normalized Git review scopes and diffs
- `packages/sktr_python`: Python AST analyzer plugin
- `packages/sktr_javascript`: JavaScript and TypeScript analyzer plugin
- `packages/sktr_java`: Java analyzer plugin
- `packages/sktr_treesitter`: shared deterministic parser adapter
- `packages/sktr_enrichment`: deterministic enrichment pipeline
- `packages/sktr_rules`: rule registry and default deterministic rules
- `packages/sktr_report`: terminal, Markdown, and JSON outputs
- `packages/sktr_graph`: graph model, builder, and Mermaid output
- `packages/sktr_ai`: optional AI provider implementation
- `tests`: unit and CLI integration tests

Core must remain language-agnostic. Language-specific parsing belongs in analyzer
packages, and rules should consume the enriched model instead of parser objects.

## Add a rule

Implement the `Rule` protocol, evaluate `System` plus `ReviewContext`, register it
in a rule pack, and add focused tests. Reusable metrics belong in enrichment, not
inside the rule.

## Add an output

Implement the output contract for `ReviewResult`, provide a plugin factory, and
register it under `sktr.outputs`. Keep output code independent of Git and parsing.

## Add an analyzer

Implement `Analyzer`, populate the language-agnostic knowledge model, expose a
plugin factory, and register it under `sktr.analyzers`. Do not add language
conditionals to core.

## Add an AI provider

Implement `AIProvider`, accept structured `AIReviewContext`, and return the current
AI output model. Providers must degrade to warnings for optional-service failures
and must never expose credentials.

## Validation

Before opening a change:

```bash
uv run pytest
uv build
```

Also exercise `sktr init --yes`, `sktr plugins doctor`, `sktr review`, and
`sktr graph` in a small Git repository when changing CLI behavior.

## Release process

SKTR publishes to PyPI through GitHub Actions trusted publishing. Configure the
PyPI project once with this trusted publisher:

- Owner: `prubianes`
- Repository: `sktr`
- Workflow: `release.yml`
- Environment: `pypi`

Create a protected GitHub environment named `pypi` and require an approval for
deployment. No PyPI token belongs in GitHub secrets or repository files.

For RC1, merge a clean release candidate whose package version is `1.0.0rc1`, wait
for CI to pass, and then create and push the matching tag:

```bash
git tag -a v1.0.0rc1 -m "SKTR v1.0.0rc1"
git push origin v1.0.0rc1
```

The release workflow rejects a tag that does not exactly match the package
version, reruns tests, builds both distributions, verifies the frozen schema is
packaged, and publishes through OIDC. After publication, verify the PyPI project
page and install `sktr` into a new Python 3.13+ environment.

The workflow separates validation and build from publication. Only the final
environment-protected publish job receives `id-token: write`; it downloads the
previous job's immutable workflow artifact and uploads those distributions.

After RC feedback is complete, promote the project to `1.0.0`, restore the
Production/Stable classifier, rerun the full release checklist, and publish the
matching `v1.0.0` tag.
