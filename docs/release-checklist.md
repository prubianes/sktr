# SKTR v1.0 Release Checklist

Implementation milestones are tracked in the [v0.16-v0.18 roadmap](roadmap.md).

## Functionality

- [x] `sktr init --yes` works
- [x] `sktr review` works without AI
- [ ] `sktr review --ai` works with OpenAI configured (requires a live credential check)
- [x] `sktr graph` works
- [x] Markdown output works
- [x] JSON output works
- [x] Config loading works
- [x] Plugin discovery works
- [x] `sktr plugins doctor` works
- [x] `sktr ai doctor` works

## Quality

- [x] Tests pass (`144 passed`)
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
- [x] Version updated (`0.18.0`)
- [x] License included
- [x] Wheel and source distribution build successfully
- [x] Built wheel installs in a clean Python 3.13+ environment
- [x] PyPI publishing process documented

## Publish process

1. Complete this checklist on a release candidate commit.
2. Build with `uv build` and inspect `dist/`.
3. Install the wheel in a clean environment and run CLI smoke tests.
4. Tag the approved commit with the release version.
5. Publish through the project's trusted PyPI release workflow.
6. Verify the PyPI description, installation command, and console entry point.

Do not publish from an uncommitted working tree or embed a PyPI token in project
files, shell history, or CI logs.
