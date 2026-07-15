# Architecture Graphs

`sktr graph` builds deterministic Mermaid diagrams from SKTR's normalized
Knowledge Model. It never asks AI to infer dependencies and ignores unresolved
external imports.

## Graph scope

Review changed code and retain resolved unchanged targets as context:

```bash
sktr graph --scope changes
```

Analyze the repository and highlight files or modules in the selected Git diff:

```bash
sktr graph --scope repository --output architecture.mmd
```

`changes` is the default. Repository snapshots include Git-tracked files and
non-ignored untracked files, then apply `review.exclude` before analysis.

## Review scope

Graph scope selects how much code becomes a node. Review scope selects which
nodes are marked as changed:

```bash
sktr graph --branch
sktr graph --branch --base develop
sktr graph --commit HEAD~1
sktr graph --scope repository --commit HEAD~1
```

For a commit repository graph, SKTR reads repository context from that commit.

## Level and focused views

```bash
sktr graph --level module
sktr graph --level file
sktr graph --scope repository --focus orders
sktr graph --scope repository --dependencies-of orders
sktr graph --scope repository --dependents-of payments
sktr graph --scope repository --cycles
```

`--focus` returns the selected node and its direct incoming and outgoing
neighbors. Dependency and dependent views traverse the full reachable graph.
`--cycles` keeps only nodes and edges that participate in a dependency cycle.
These four focused options are mutually exclusive.

File graphs use module subgraphs. Changed nodes have a solid green border;
unchanged context nodes have a dashed neutral border. Isolated nodes remain in
the diagram, duplicate edges are removed, and output ordering is stable.

Large graphs are easier to inspect from a file or with a focused view:

```bash
sktr graph --scope repository --level file --output files.mmd
```
