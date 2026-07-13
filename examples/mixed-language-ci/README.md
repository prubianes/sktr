# Mixed-Language CI Example

This project demonstrates all bundled analyzers in one review and writes the
artifact before applying the configured high-severity gate.

```bash
cp -R examples/mixed-language-ci /tmp/sktr-mixed-language-ci
cd /tmp/sktr-mixed-language-ci
git init
git add sktr.yml
git commit -m "Initialize SKTR"
git add src
sktr review --format json --output sktr-review.json
```

The Python, TypeScript, and Java files should all appear in the knowledge model.

Generate a mixed-language repository graph or inspect one dependency neighborhood:

```bash
sktr graph --scope repository --output architecture.mmd
sktr graph --scope repository --focus web
```
