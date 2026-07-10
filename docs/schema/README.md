# SKTR Review Artifact Schema

`sktr-review-0.1.schema.json` is the frozen JSON Schema for SKTR's canonical
review artifact. Additive optional fields may be introduced without changing the
schema version. Removing fields, changing field types, or changing semantics
requires a new schema version.

Artifacts retain the legacy top-level `score`, `risk`, and embedded
`review_result` fields for compatibility. Consumers should prefer `summary` and
the normalized top-level collections for new integrations.
