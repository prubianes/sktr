# Quickstart

## Install

SKTR requires Python 3.13 or newer and Git.

```bash
python -m pip install --pre sktr==1.0.0rc1
```

This installs the v1.0.0 release candidate. After the final v1 release, the
standard installation command will be `python -m pip install sktr`.

Confirm the installation and discover the available commands:

```bash
sktr --version
sktr --help
```

Every command also has focused help, for example `sktr review --help` and
`sktr graph --help`.

For local development from this repository, use `uv sync` and prefix commands
with `uv run`.

## Initialize a project

Run SKTR inside a Git repository:

```bash
cd your-project
sktr init
```

Interactive setup detects project details and installed plugins. To accept safe
defaults without prompts:

```bash
sktr init --yes
```

SKTR creates `sktr.yml` and will not overwrite an existing configuration unless
you pass `--force`.

## Run the first review

```bash
sktr review
```

The default scope compares staged and unstaged tracked changes with `HEAD`.
Untracked files must be staged before Git includes them in the review.

Review a branch from its merge-base with the configured base branch:

```bash
sktr review --branch
sktr review --base develop
```

Review a specific commit against its parent:

```bash
sktr review --commit HEAD~1
```

Fail CI when a high or critical deterministic finding is present:

```bash
sktr review --format json --output sktr-review.json --fail-on high
```

SKTR writes the selected output before returning the nonzero gate result.

## Generate Markdown

```bash
sktr review --format markdown --output REVIEW.md
```

## Generate JSON

JSON is the canonical, versioned SKTR artifact.

```bash
sktr review --format json --output sktr-review.json
```

Render an existing artifact without rerunning analysis or AI features:

```bash
sktr report sktr-review.json --format markdown --output REVIEW.md
```

## Generate a graph

```bash
sktr graph --format mermaid --output architecture.mmd
sktr graph --scope repository --output repository.mmd
sktr graph --scope repository --dependencies-of orders
```

The default change graph keeps resolved unchanged targets as context. Repository
graphs analyze all non-excluded Git-managed files and highlight the selected
working-tree, branch, or commit change. See [architecture graphs](graphs.md).

## Enable AI features

```bash
export SKTR_OPENAI_API_KEY="your-api-key"
sktr ai doctor
sktr review --ai
sktr review --ai --model gpt-5.6-terra
```

AI is optional. Without it, analyzers, enrichment, rules, scoring, and all output
formats continue to work.
