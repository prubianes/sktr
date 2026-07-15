# Troubleshooting

## `No SKTR config found`

Run `sktr init` in the repository root or pass an explicit file to a command that
supports it:

```bash
sktr review --config path/to/sktr.yml
```

## `Not inside a Git repository`

Run SKTR from a Git working tree. `sktr review` cannot analyze a plain directory.

## Git cannot prepare a review

Verify the requested base or commit exists locally:

```bash
git branch --all
git rev-parse --verify HEAD~1
```

Fetch a missing remote base and retry with the correct local or remote-tracking
name. Repositories without an initial commit do not have `HEAD`; create the first
commit before reviewing.

## A new file is missing

Working-tree review uses `git diff HEAD`, which does not include untracked files.
Stage the file first:

```bash
git add path/to/new-file
sktr review
```

## Missing or unknown plugin

Inspect installed plugins and validate the configured names:

```bash
sktr plugins list
sktr plugins doctor
```

With the bundled distribution, the analyzer names are `sktr-python`,
`sktr-javascript-typescript`, and `sktr-java`.

## AI Review is unavailable

AI is optional. Check configuration and credential discovery:

```bash
sktr ai doctor
```

Set `SKTR_OPENAI_API_KEY` or use `OPENAI_API_KEY` as a fallback. A provider
warning does not cancel deterministic analysis or affect the score.

## No dependency graph can be generated

The selected files may have no resolvable internal dependencies. Try repository
scope or file level:

```bash
sktr graph --scope repository
sktr graph --scope repository --level file
```

External and unresolved dependencies are intentionally omitted.

## Parse diagnostics appear

Malformed or unsupported source produces an analysis diagnostic, not a finding.
Other files and analyzers continue. Fix the reported syntax or confirm the file
uses a supported extension and language version.

## Installation fails

Confirm that Python 3.13 or newer and Git are available:

```bash
python --version
git --version
```

For this release candidate, install explicitly with:

```bash
python -m pip install --pre sktr==1.0.0rc1
```

Open a public issue with the operating system, Python version, command, and
sanitized error output if the problem remains.

