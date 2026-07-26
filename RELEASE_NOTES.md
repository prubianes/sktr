# SKTR v1.0.0

SKTR 1.0.0 is the first stable release of **System Knowledge & Technical
Review**: a language-agnostic CLI that turns Git changes into deterministic,
structured software-review evidence.

SKTR identifies changed symbols and dependencies, applies architecture and
maintainability rules, prioritizes review risk, and produces artifacts for both
people and automation. Optional AI features explain the evidence without adding
findings or changing scores.

## Highlights

- Review working-tree changes, branches, explicit bases, or individual commits.
- Analyze Python, JavaScript, JSX, TypeScript, TSX, and Java projects.
- Detect dependency boundaries, cycles, fan-out, public API changes, large
  changes, and missing test signals.
- Generate terminal, Markdown, canonical JSON, and Mermaid graph output.
- Explore repository and change dependency graphs with focused traversal and
  cycle views.
- Use optional OpenAI or Anthropic Claude explanations and recommendations.
- Configure plugin discovery, exclusions, diagnostics, and CI severity gates.
- Integrate against the frozen `0.1` JSON artifact schema.

## AI provider support

SKTR supports OpenAI and Anthropic Claude, including Sonnet, Haiku, Opus, and
custom model selection. Credentials are read from environment variables and are
never stored in project configuration or printed in output.

```bash
# OpenAI
export SKTR_OPENAI_API_KEY="your-api-key"

# Anthropic
export SKTR_ANTHROPIC_API_KEY="your-api-key"
```

Use `sktr ai doctor` to verify the selected provider and credentials before
running `sktr review --ai`.

## Install

SKTR requires Python 3.11 or newer and supports Python 3.11 through 3.14.

```bash
python -m pip install sktr==1.0.0
sktr --version
```

Initialize SKTR inside a Git repository and run the first review:

```bash
sktr init --yes
sktr review
```

## Release hardening

- Git command failures stop reviews instead of producing false clean results.
- Empty reviews clearly distinguish a clean tracked scope from untracked files.
- Terminal reports written with `--output` contain plain text without Rich
  markup.
- YAML configuration uses standards-compliant safe parsing.
- JSON artifacts contain RFC 3339 UTC generation timestamps.
- CI covers Python 3.11 through 3.14, clean-wheel smoke tests, and schema
  validation.
- Release artifacts are published through PyPI trusted publishing.

## Known limitations

- Working-tree reviews include tracked staged and unstaged files. Stage a new
  file before reviewing it.
- Unresolved third-party dependencies are modeled as external and omitted from
  internal architecture graphs.
- AI is optional and explanatory; it does not add findings or alter risk scores.
- GitHub review integration, impact and explain commands, dashboards, and
  automatic code changes are not part of this release.

For configuration and examples, see the
[quickstart](https://github.com/prubianes/sktr/blob/main/docs/quickstart.md) and
[documentation](https://github.com/prubianes/sktr/tree/main/docs). Please report
reproducible problems through the
[issue tracker](https://github.com/prubianes/sktr/issues).

See the [full changelog](https://github.com/prubianes/sktr/blob/v1.0.0/CHANGELOG.md)
for complete release details.
