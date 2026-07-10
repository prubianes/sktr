# SKTR Roadmap Through v0.18

SKTR's path to v1 adds two bundled language analyzers and then freezes the
automation contract. v0.16 delivers JavaScript and TypeScript analysis, v0.17
adds Java, and v0.18 adds CI gates, exclusions, diagnostics, and artifact schema
stability. All detection remains deterministic and all analyzers remain isolated
entry-point plugins behind the language-agnostic Knowledge Model.

This opening summary is intentionally self-contained so it can be copied into a
planning conversation without the rest of the repository context.

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
- [x] Centralize version `0.18.0` across built-in plugin metadata.
- [x] Add mixed-language, CI, schema, and clean-package validation.

Acceptance: CI receives stable output before a severity-gate exit, parse failures
cannot cancel unrelated files, and every generated artifact validates against
`docs/schema/sktr-review-0.1.schema.json`.

## Deferred Until After V1

- `tsconfig` path aliases
- Additional AI providers
- GitHub integration
- Impact and explain commands
- Dashboards and editor extensions
- Automatic code modifications
