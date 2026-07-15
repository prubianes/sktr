# CI Integration

SKTR's own GitHub Actions CI runs the test and packaging matrix on Python 3.13
and 3.14. The release workflow uses PyPI trusted publishing; its setup and tag
procedure are documented in [development.md](development.md#release-process).

SKTR can write a canonical artifact and fail a job based only on deterministic
issue severity:

```bash
sktr review \
  --branch \
  --format json \
  --output sktr-review.json \
  --fail-on high
```

The report is written before SKTR exits with status `1`. AI warnings and analysis
diagnostics do not trigger the gate because they are not deterministic issues.

Set a project default in `sktr.yml`:

```yaml
review:
  default_scope: working_tree
  fail_on: high
  exclude:
    - node_modules/
    - .venv/
    - dist/
    - build/
    - target/
    - coverage/
    - "*.min.js"
    - "*.generated.*"
```

An explicit `exclude: []` disables defaults. Excluded paths are removed before
analysis and rules but remain listed in the JSON artifact for auditability.

Validate an artifact against the frozen schema with any JSON Schema 2020-12
validator using `docs/schema/sktr-review-0.1.schema.json`.

## GitHub Actions example

Commit `sktr.yml` so CI and local reviews use the same rules. Branch reviews
need the base branch and merge-base history, so checkout must use
`fetch-depth: 0`.

```yaml
name: SKTR review

on:
  pull_request:

permissions:
  contents: read

jobs:
  architecture-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install SKTR RC1
        run: python -m pip install --pre sktr==1.0.0rc1
      - name: Review pull request
        run: >-
          sktr review --branch --base origin/${{ github.event.pull_request.base.ref }}
          --no-ai --format json --output sktr-review.json --fail-on high
      - name: Upload SKTR artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: sktr-review
          path: sktr-review.json
          if-no-files-found: error
```

The output file is written before a severity-gate failure, and `if: always()`
preserves it for inspection. Keep AI disabled in required deterministic gates;
run an additional optional AI review only when the repository has intentionally
configured credentials and secret access.
