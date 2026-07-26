# Changelog

All notable changes to SKTR are documented here. Versions follow
[Semantic Versioning](https://semver.org/) and Python package versions follow
[PEP 440](https://peps.python.org/pep-0440/).

## Unreleased

### Added

- English and Spanish deterministic terminal and Markdown report catalogs.
- BCP 47 output-language configuration and `--language` overrides for `init`,
  `review`, and `report`.
- AI overview and recommendation language selection for any valid language tag,
  while preserving canonical machine-readable identifiers.

## 1.0.0 - 2026-07-26

### Added

- Deterministic Git review scopes for working-tree, branch, explicit-base, and
  commit reviews.
- Bundled Python, JavaScript/TypeScript, and Java analyzer plugins.
- Language-agnostic knowledge model with symbols, dependencies, diagnostics,
  visibility, API exposure, enrichment metrics, risk, and review priority.
- Configurable architecture and maintainability rules, including dependency
  boundaries, cycles, fan-out, public API changes, large changes, and test signals.
- Terminal, Markdown, canonical JSON artifact, and Mermaid graph outputs.
- Repository and change dependency graphs with focused traversal and cycle views.
- Optional OpenAI explanations from structured deterministic evidence.
- Anthropic Claude AI review provider with Sonnet, Haiku, Opus, and custom
  model selection.
- Interactive project initialization, plugin discovery, plugin diagnostics,
  exclusions, and CI severity gates.
- Frozen JSON artifact schema `0.1`.
- Python 3.11 and 3.12 support, extending the existing 3.13 and 3.14 matrix.

### Fixed

- Terminal output written with `--output` is now plain text instead of containing
  Rich markup tags.
- Empty reviews now clearly report when no tracked changes are present and
  explain how to include untracked working-tree files.

### Release hardening

- Git command failures now stop reviews instead of producing false clean results.
- YAML configuration uses standards-compliant safe parsing.
- Review artifacts contain RFC 3339 UTC generation timestamps.
- Python 3.11 through 3.14 CI, clean-wheel smoke tests, and schema validation.
- PyPI trusted publishing through an environment-protected GitHub Actions job.

### Known limitations

- Only tracked staged and unstaged files are included in working-tree reviews;
  stage a new file before reviewing it.
- Unresolved third-party dependencies are modeled as external and omitted from
  internal architecture graphs.
- AI is optional and explanatory; it does not add findings or alter risk scores.
- This release does not include GitHub review integration, impact or
  explain commands, dashboards, or automatic code changes.
