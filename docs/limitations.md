# Known Limitations

SKTR 1.0.0rc1 intentionally favors deterministic, reviewable evidence over broad
heuristic coverage.

- Working-tree reviews include tracked staged and unstaged changes. Untracked
  files must be staged first.
- Python analysis uses the standard `ast` parser. JavaScript, TypeScript, TSX,
  JSX, and Java use bundled Tree-sitter grammars.
- JavaScript and TypeScript resolve relative imports, index files, workspace
  packages, and `tsconfig` `baseUrl` and `paths`. Unresolved bare packages remain
  external.
- Java resolves repository packages and common Maven/Gradle source roots. JDK
  and unresolved third-party imports remain external.
- Dependency graphs contain only cleanly resolved internal edges. Their absence
  does not prove two modules are independent at runtime.
- Size, fan-out, test, and review-priority metrics are deterministic review
  signals, not proof of a defect.
- AI receives structured review context and explains existing evidence. It does
  not detect findings, change scores, or affect severity-gate exits.
- GitHub review integration, impact and explain commands, dashboards, editor
  integrations, and automatic code changes are deferred until after v1.

Report reproducible false positives or missing deterministic evidence through
the [issue tracker](https://github.com/prubianes/sktr/issues).
