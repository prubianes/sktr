# Analyzer Semantics

SKTR analyzers translate language syntax into the same normalized Knowledge
Model. Rules consume normalized visibility, API exposure, module boundaries,
dependencies, and metrics without branching on language.

## Public API exposure

Public API removals require positive analyzer evidence. Unknown visibility is
never treated as a High-severity API break.

- JavaScript and TypeScript use direct exports, default exports, export lists,
  re-exports, and CommonJS assignments.
- Java uses public/protected, package-private, and private modifiers. A method is
  externally exposed only when its containing type is also exposed.
- Python uses public naming and underscore conventions.

Private local helpers can still contribute to maintainability metrics, but their
removal is not a public API finding.

## JavaScript and TypeScript modules

NPM package identity and logical module identity are separate. Nested workspace
packages retain their package names; a root package is divided into logical
directories such as `app/api/admin`, `components/history`, and
`components/keypad`.

Relative imports, workspace packages, index files, extensions, and `tsconfig`
`baseUrl`/`paths` aliases resolve to internal dependency targets. Next.js route
groups remain in file paths while logical module names omit grouping-only
parenthesized segments.

Function metrics include body lines, approximate complexity, statement count,
nested functions, JSX ratio, and semantic role. Mostly declarative UI components
receive a higher size threshold; large or complex components and imperative
handlers remain findings.

## Java modules

Java analysis records package and Maven/Gradle build-module context, visibility,
annotations, imports, static imports, inheritance, and interface implementation.
Repository classes are resolved from working-tree or historical snapshot
contents, while JDK and unresolved third-party dependencies remain external.

## Review context

The missing-tests rule runs only when SKTR detects repository test files,
framework configuration, or analyzer evidence such as a JavaScript test script.
A repository without test infrastructure does not receive a missing-test issue.

Large analyzed source changes remain Medium findings. Large stylesheet,
configuration, or other unanalyzed-file changes are Low review-surface findings,
not automatic maintainability defects.
