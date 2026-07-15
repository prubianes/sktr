# SKTR Roadmap Through v0.20

SKTR's path to v1 delivered two bundled language analyzers, froze the automation
contract, and turned dependency graphing into a useful architecture view. v0.16
delivered JavaScript and TypeScript analysis, v0.17 added Java, v0.18 added CI
gates, exclusions, diagnostics, and artifact schema stability, v0.19 added
repository-context graphs, and v0.20 made API exposure, logical modules, React
metrics, Java relationships, and testing signals evidence-based. All detection
remains deterministic and all analyzers remain isolated entry-point plugins
behind the language-agnostic Knowledge Model.

This opening summary is intentionally self-contained so it can be copied into a
planning conversation without the rest of the repository context.

## v1.0.0rc1: Public Release Candidate

Goal: validate the complete v1 contract with real projects before declaring the
final stable release.

- [x] Promote package and built-in plugin metadata to `1.0.0rc1`.
- [x] Fail clearly when Git cannot resolve or prepare the selected review scope.
- [x] Use standards-compliant safe YAML loading and preserve existing configs.
- [x] Emit one RFC 3339 UTC timestamp across every output from a review run.
- [x] Build and validate wheel and source distributions on Python 3.13 and 3.14.
- [x] Add least-privilege trusted publishing through a protected GitHub
  environment.
- [x] Publish public CLI, troubleshooting, limitations, contribution, security,
  and release-history documentation.
- [ ] Complete external CI, trusted-publisher, tag, and PyPI verification from
  the [release checklist](release-checklist.md).

Acceptance: the exact `v1.0.0rc1` tag passes CI, publishes through PyPI trusted
publishing, installs into a clean environment, and produces a schema-valid
artifact from a real repository.

## v0.16: JavaScript and TypeScript

Goal: make SKTR useful for modern web and Node.js projects without weakening its
plugin boundaries.

- [x] Bundle the `sktr-javascript-typescript` analyzer plugin.
- [x] Parse JavaScript, JSX, TypeScript, and TSX with official Tree-sitter grammars.
- [x] Extract ES imports/re-exports, CommonJS dependencies, classes, interfaces,
  type aliases, functions, named arrow functions, and methods.
- [x] Resolve relative modules, index files, extensions, and workspace packages.
- [x] Normalize source module, target module, target path, and dependency scope
  in the core model and migrate Python to the same contract.
- [x] Add malformed-file, baseline, deterministic-rule, and workspace tests.
- [x] Add a runnable JavaScript/TypeScript example.

Acceptance: a mixed Python/TypeScript diff can run through the unchanged
pipeline, enrichment, rules, reports, graphing, and AI context.

## v0.17: Java

Goal: support common Maven and Gradle repository layouts using the normalized
analyzer contract introduced in v0.16.

- [x] Bundle the `sktr-java` analyzer plugin using the official Java grammar.
- [x] Extract packages, imports, static imports, classes, interfaces, enums,
  records, constructors, and methods.
- [x] Resolve repository classes and classify JDK versus third-party imports.
- [x] Recognize main and test Java source roots.
- [x] Add malformed-file, baseline, static-import, and deterministic-rule tests.
- [x] Add a runnable Maven-style Java example.

Acceptance: Java knowledge flows through existing enrichment, rules, outputs,
graphs, and AI without language-specific branches outside the analyzer plugin.

## v0.18: V1 Readiness

Goal: make deterministic review reliable in CI and freeze the first public
artifact contract.

- [x] Add config and CLI severity gates with `review.fail_on` and `--fail-on`.
- [x] Add Git-ignore-style `review.exclude` patterns with safe generated/build
  defaults and support an explicit empty list.
- [x] Filter excluded files before analyzers, enrichment, and rules while
  preserving excluded paths in review metadata and artifacts.
- [x] Add score-neutral, language-agnostic analysis diagnostics.
- [x] Render diagnostics in terminal and Markdown and serialize them in JSON.
- [x] Freeze artifact schema `0.1` and publish its JSON Schema.
- [x] Centralize package and built-in plugin version metadata.
- [x] Add mixed-language, CI, schema, and clean-package validation.

Acceptance: CI receives stable output before a severity-gate exit, parse failures
cannot cancel unrelated files, and every generated artifact validates against
`docs/schema/sktr-review-0.1.schema.json`.

## v0.19: Architecture Graph Intelligence

Goal: evolve `sktr graph` from a changed-files dependency diagram into an
architecture view that can explain a change in the context of the repository.

- [x] Add `--scope changes|repository`, keeping `changes` backward compatible
  and making repository analysis available without changing review semantics.
- [x] Include unchanged internal dependency targets as context nodes and
  visually distinguish changed files and modules.
- [x] Support working-tree, branch, explicit-base, and commit graph scopes with
  the same CLI semantics as `sktr review`.
- [x] Render isolated nodes, stable node identifiers, module subgraphs for
  file-level diagrams, and dependency type or scope labels where useful.
- [x] Add `--focus MODULE`, `--cycles`, `--dependencies-of MODULE`, and
  `--dependents-of MODULE` views for targeted architecture exploration.
- [x] Preserve deterministic ordering, deduplicate edges, and ignore unresolved
  external dependencies.
- [x] Keep graph construction language-agnostic and consume only the normalized
  Knowledge Model, enrichment metadata, and normalized Git review context.
- [x] Add terminal guidance for empty graphs and oversized repository graphs.
- [x] Document change graphs versus repository graphs with Python, TypeScript,
  Java, and mixed-language examples.
- [x] Add tests for repository context, changed-node styling, isolated nodes,
  review scopes, cycles, focused traversal, mixed languages, and deterministic
  Mermaid snapshots.
- [x] Add OpenAI model profiles to interactive init: GPT-5.6 Terra as the
  recommended default, Luna for efficient reviews, Sol for quality-first
  reviews, and an unrestricted custom model ID option.
- [x] Compare normalized baseline module edges so new import paths do not create
  false architecture-dependency findings.
- [x] Measure executable symbol bodies, refactor oversized command/report
  orchestration, and keep large-function guidance responsibility-neutral.
- [x] Add bounded review-breadth scoring for production files, modules, public
  API changes, and large diffs without turning breadth into an issue.
- [x] Deduplicate deterministic suggestions covered by AI recommendations and
  replace the foundation status with `review complete`.

Acceptance: `sktr graph --scope repository` produces a stable architecture map,
`sktr graph --scope changes` explains reviewed changes without dropping their
unchanged internal targets, and focused graph commands return the expected
dependency neighborhood across all bundled analyzers.

## v0.20: Analyzer Precision

Goal: eliminate language-heuristic false positives and make React/Next.js and
Java architecture signals trustworthy enough for v1.

- [x] Add language-agnostic symbol visibility and API exposure to the Knowledge
  Model and require positive exposure evidence for public API findings.
- [x] Detect JS/TS direct, default, listed, re-exported, and CommonJS exports so
  private React helpers are never classified as public APIs.
- [x] Separate npm package identity from logical application modules and support
  Next.js route groups plus `tsconfig` `baseUrl`/`paths` aliases.
- [x] Add normalized component role, JSX ratio, statement count, nesting, and
  complexity metrics with a calibrated declarative-component size threshold.
- [x] Add Java visibility, annotations, inheritance/implementation dependencies,
  and Maven/Gradle build-module context.
- [x] Require repository evidence of test infrastructure before emitting a
  missing-test finding.
- [x] Reframe large unanalyzed-file changes as Low review surfaces while keeping
  large analyzed source changes at Medium.
- [x] Escape dynamic terminal content so bracketed Next.js route paths render
  exactly as stored by Git.
- [x] Add Storyvote-shaped regression tests and validate the real branch review.

Acceptance: the Storyvote branch review contains no false public API removals,
reports multiple logical modules, preserves `app/[rooms]` paths, resolves local
aliases, and treats the change as maintainability/test review rather than a High
architecture break.

## Deferred Until After V1

- Additional AI providers
- GitHub integration
- Impact and explain commands
- Dashboards and editor extensions
- Automatic code modifications
