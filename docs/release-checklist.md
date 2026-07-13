# SKTR v1.0 Release Checklist

Implementation milestones are tracked in the [v0.16-v0.20 roadmap](roadmap.md).

## Functionality

- [x] `sktr init --yes` works
- [x] `sktr review` works without AI
- [x] `sktr review --ai` works with OpenAI configured (live credential verified by project owner)
- [x] `sktr graph` works
- [x] Repository and change graph scopes pass the v0.19 acceptance checks
- [x] Focused, cycle, dependency, and dependent graph views work
- [x] Markdown output works
- [x] JSON output works
- [x] Config loading works
- [x] Plugin discovery works
- [x] `sktr plugins doctor` works
- [x] `sktr ai doctor` works

## Quality

- [x] Tests pass (`190 passed` locally; CI verifies Python 3.13 and 3.14)
- [x] Type checks pass, if configured (no type checker configured)
- [x] Lint passes, if configured (no linter configured)
- [x] No API keys in examples
- [x] No secrets in logs
- [x] Helpful errors for missing config
- [x] Helpful errors for missing plugins
- [x] Helpful warning for missing API key

## Documentation

- [x] README updated
- [x] Quickstart complete
- [x] Configuration docs complete
- [x] Plugin docs complete
- [x] AI docs complete
- [x] Output docs complete

## Packaging

- [x] Package metadata reviewed
- [x] CLI entry point works
- [x] Version updated (`1.0.0`)
- [x] License included
- [x] Wheel and source distribution build successfully
- [x] Built wheel installs in a clean Python 3.13+ environment
- [x] PyPI publishing process documented
- [x] CI and trusted-publishing workflows added
- [x] Frozen JSON Schema included in the source distribution manifest

## Release authorization

- [ ] Release-candidate commit passes GitHub Actions on Python 3.13 and 3.14
- [ ] Protected `pypi` GitHub environment and PyPI trusted publisher verified
- [ ] `v1.0.0` tag created from the approved release-candidate commit
- [ ] PyPI package, description, links, and console entry point verified

## Publish process

1. Complete this checklist on a release candidate commit.
2. Build with `uv build` and inspect `dist/`.
3. Install the wheel in a clean environment and run CLI smoke tests.
4. Tag the approved commit with the release version.
5. Push the matching version tag to publish through the trusted PyPI workflow.
6. Verify the PyPI description, installation command, and console entry point.

Do not publish from an uncommitted working tree or embed a PyPI token in project
files, shell history, or CI logs.
