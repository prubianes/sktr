# SKTR v1.1.0 Release Checklist

Multilingual output changes are documented in the
[v1.1.0 changelog](../CHANGELOG.md).

## Functionality

- [x] English deterministic terminal and Markdown reports work
- [x] Spanish deterministic terminal and Markdown reports work
- [x] `sktr init` prompts for the output language
- [x] `sktr init --yes --language es` writes the language configuration
- [x] `sktr review --language` overrides the configured language
- [x] `sktr report --language` localizes deterministic artifact rendering
- [x] OpenAI and Anthropic receive the requested AI prose language
- [x] Unsupported deterministic catalog languages fall back to English
- [x] JSON keys, rule IDs, severities, paths, and schema values remain canonical
- [x] Existing configurations default to English

## Quality

- [x] Full test suite passes (`213 passed` locally)
- [x] English output snapshots remain compatible
- [x] Spanish init and Markdown review smoke tests pass
- [x] BCP 47-style language validation and normalization are tested
- [x] AI language propagation is tested
- [x] Frozen JSON artifact schema `0.1` still validates
- [x] No API keys are stored in config, artifacts, examples, or logs

## Documentation

- [x] README and quickstart describe multilingual output
- [x] Configuration reference documents `output.language`
- [x] CLI reference documents all `--language` options
- [x] AI documentation explains arbitrary-language prose
- [x] Output documentation explains deterministic fallback behavior
- [x] Known limitations describe maintained output catalogs
- [x] Changelog and GitHub release notes are complete
- [x] PyPI logo uses a valid absolute HTTPS URL

## Packaging

- [x] Package and built-in plugin version updated to `1.1.0`
- [x] Python 3.11 through 3.14 remain supported
- [x] Wheel and source distribution build successfully
- [x] Both distributions pass `twine check`
- [x] Built wheel installs and reports `sktr 1.1.0`
- [x] Source distribution contains the frozen JSON Schema
- [x] `dist/` contains only the v1.1.0 wheel and source distribution

## Release authorization

- [ ] Release commit passes GitHub Actions on Python 3.11 through 3.14
- [ ] Protected `pypi` GitHub environment and trusted publisher are verified
- [ ] GitHub private vulnerability reporting is enabled
- [ ] `v1.1.0` tag is created from the approved release commit
- [ ] PyPI description, logo, links, installation, and console entry point are verified

## Publish process

1. Complete this checklist on the final release commit.
2. Clean `dist/`, build with `uv build`, and run `twine check`.
3. Install the wheel in a clean environment and run CLI smoke tests.
4. Push the release commit and wait for the complete CI matrix.
5. Create and push the annotated `v1.1.0` tag.
6. Verify PyPI metadata, the rendered logo, installation, and `sktr --version`.

Do not publish from an uncommitted working tree or embed a PyPI token in project
files, shell history, or CI logs.
