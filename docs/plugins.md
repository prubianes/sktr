# Plugins

SKTR keeps its core language-agnostic by discovering implementations through
Python package entry points.

## Entry point groups

| Group | Capability |
|---|---|
| `sktr.analyzers` | Build a `System` knowledge model from normalized review context |
| `sktr.rules` | Evaluate enriched knowledge and return deterministic issues |
| `sktr.outputs` | Write review results or graphs |
| `sktr.ai_providers` | Produce optional AI-powered output from structured context |

An analyzer package can declare:

```toml
[project.entry-points."sktr.analyzers"]
python = "sktr_python:PythonAnalyzerPlugin"
```

The loaded plugin exposes metadata containing `name`, `version`, `type`, and
`description`, plus the factory required by its group.

## Inspect plugins

```bash
sktr plugins list
sktr plugins doctor
```

`list` groups successfully loaded plugins by capability. `doctor` checks that
configured plugins exist, loaded successfully, and expose the required factory.
Errors name the missing plugin and the configuration section to update.

## Distribute analyzers separately

Python, JavaScript/TypeScript, and Java analyzers are bundled with SKTR and need
no additional installation. Third-party analyzers can still be independent
Python distributions: they register the same entry point and become available
when installed in the SKTR environment.

## Add a plugin

1. Implement the relevant protocol from `sktr_core.plugins`.
2. Wrap it in a plugin factory with valid metadata.
3. Register the factory under the matching entry point group.
4. Install the package in the same environment as SKTR.
5. Add its metadata name to `sktr.yml` and run `sktr plugins doctor`.

The review pipeline receives created plugins from the registry; it does not
import language analyzers or providers directly.
