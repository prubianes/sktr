# CLI Reference

Every command except `init`, `plugins list`, and `--version` requires a valid
`sktr.yml` or `sktr.yaml`. Use `--config PATH` where supported to select another
configuration file.

## Global options

```bash
sktr --version
sktr --help
sktr --install-completion
sktr --show-completion
```

## `sktr init`

Initialize the current repository.

```bash
sktr init
sktr init --yes
sktr init --preset minimal
sktr init --preset custom
sktr init --ai
sktr init --dry-run
sktr init --force
```

`--yes` accepts non-interactive defaults. `--force` is required to replace an
existing configuration. `--dry-run` prints the generated configuration without
writing it.

## `sktr review`

Analyze a normalized Git diff, enrich its knowledge model, run deterministic
rules, optionally request AI explanation, and write one output.

```bash
sktr review
sktr review --branch
sktr review --base develop
sktr review --commit HEAD~1
sktr review --format markdown --output REVIEW.md
sktr review --format json --output sktr-review.json
sktr review --ai --model gpt-5.6-terra
sktr review --fail-on high
```

The default working-tree scope compares tracked staged and unstaged changes with
`HEAD`. `--branch` and `--base` compare `HEAD` with the merge-base of the selected
base. `--commit` compares one commit with its parent. Commit scope cannot be
combined with branch or base scope.

Formats are `terminal`, `markdown`, and `json`. Output is written before a
`--fail-on` threshold returns exit status `1`.

## `sktr report`

Render a saved JSON artifact without rerunning Git, analyzers, rules, or AI.

```bash
sktr report sktr-review.json
sktr report sktr-review.json --format markdown --output REVIEW.md
```

## `sktr graph`

Generate deterministic Mermaid architecture from the knowledge model.

```bash
sktr graph
sktr graph --scope repository
sktr graph --level file
sktr graph --scope repository --focus orders
sktr graph --scope repository --cycles
sktr graph --scope repository --dependencies-of orders
sktr graph --scope repository --dependents-of orders
```

Only one focused selector may be used at a time. See [Architecture
Graphs](graphs.md) for scope and resolution details.

## Plugin and AI diagnostics

```bash
sktr plugins list
sktr plugins doctor
sktr ai doctor
```

Plugin doctor validates configured names and capabilities. AI doctor reports the
provider, model, and credential source without printing the credential value.

## Exit status

- `0`: command completed and no configured severity gate was reached.
- `1`: an operational failure occurred or a configured severity gate was reached.
- `2`: CLI arguments or command input failed validation.
