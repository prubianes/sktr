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
