# Python Basic Example

This example contains three small modules. The added controller imports a
repository directly, violating the boundary configured in `sktr.yml`.

Copy it outside the SKTR source repository, create a baseline commit, and stage
the violating controller as the change under review:

```bash
cp -R examples/python-basic /tmp/sktr-python-basic
cd /tmp/sktr-python-basic
git init
git add sktr.yml
git commit -m "Initialize SKTR"
git add controllers repositories services
sktr review
```

The report should include a high-severity `Forbidden dependency` finding for
`controllers/order_controller.py` importing `repositories/order_repository.py`.

Generate artifacts from the same deterministic result:

```bash
sktr review --format markdown --output REVIEW.md
sktr review --format json --output sktr-review.json
sktr graph --format mermaid --output architecture.mmd
sktr graph --scope repository --dependencies-of controllers
```

The example keeps AI disabled and does not require credentials.
