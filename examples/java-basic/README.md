# Java Example

This Maven-style project stages a controller that imports a repository directly.

```bash
cp -R examples/java-basic /tmp/sktr-java-basic
cd /tmp/sktr-java-basic
git init
git add sktr.yml pom.xml
git commit -m "Initialize SKTR"
git add src
sktr review
sktr graph --output architecture.mmd
```

The report should include a high-severity `Forbidden dependency` finding.
