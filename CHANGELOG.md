# Changelog

All notable changes to SKTR are documented here. Versions follow
[Semantic Versioning](https://semver.org/) and Python package versions follow
[PEP 440](https://peps.python.org/pep-0440/).

## 1.0.0rc1 - 2026-07-14

First public release candidate.

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
- Interactive project initialization, plugin discovery, plugin diagnostics,
  exclusions, and CI severity gates.
- Frozen JSON artifact schema `0.1`.

### Release hardening

- Git command failures now stop reviews instead of producing false clean results.
- YAML configuration uses standards-compliant safe parsing.
- Review artifacts contain RFC 3339 UTC generation timestamps.
- Python 3.13 and 3.14 CI, clean-wheel smoke tests, and schema validation.
- PyPI trusted publishing through an environment-protected GitHub Actions job.

### Known limitations

- Only tracked staged and unstaged files are included in working-tree reviews;
  stage a new file before reviewing it.
- Unresolved third-party dependencies are modeled as external and omitted from
  internal architecture graphs.
- AI is optional and explanatory; it does not add findings or alter risk scores.
- This release candidate does not include GitHub review integration, impact or
  explain commands, dashboards, or automatic code changes.

