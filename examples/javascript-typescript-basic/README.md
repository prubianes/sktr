# JavaScript and TypeScript Example

The staged TypeScript controller imports a repository directly and violates the
configured architecture boundary.

```bash
cp -R examples/javascript-typescript-basic /tmp/sktr-typescript-basic
cd /tmp/sktr-typescript-basic
git init
git add sktr.yml package.json
git commit -m "Initialize SKTR"
git add src
sktr review
sktr graph --level file --output architecture.mmd
sktr graph --scope repository --level file --focus src/controllers/orderController.ts
```

The report should include a high-severity `Forbidden dependency` finding.
