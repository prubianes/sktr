from __future__ import annotations

import json
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any, NoReturn

import typer
from pydantic import ValidationError
from rich.console import Console

from sktr_core.config import SKTRConfig, load_config
from sktr_core.model import IssueSeverity, ReviewResult
from sktr_core.pipeline import ReviewPipeline, filter_git_diff
from sktr_core.plugins import MissingPluginError, PluginRegistry
from sktr_core.version import SKTR_VERSION
from sktr_ai import NullAIProvider, resolve_openai_api_key
from sktr_enrichment import KnowledgeEnrichmentEngine
from sktr_graph import Graph, GraphBuilder, GraphLevel, GraphQuery, GraphScope
from sktr_git import GitProviderError, ReviewScope, SubprocessGitProvider
from sktr_cli.init_flow import (
    InitAnswers,
    InitPreset,
    default_answers,
    detect_project,
    interactive_prompter,
    print_detection,
    print_preview,
    prompt_for_answers,
    render_config,
    validate_answers,
)

app = typer.Typer(
    help="Understand your software before you change it.",
    no_args_is_help=True,
    invoke_without_command=True,
    rich_markup_mode="markdown",
)
plugins_app = typer.Typer(help="List and validate installed SKTR plugins.", no_args_is_help=True)
ai_app = typer.Typer(help="Check whether configured AI features are ready.", no_args_is_help=True)
app.add_typer(plugins_app, name="plugins")
app.add_typer(ai_app, name="ai")

@app.callback()
def main(
    show_version: bool = typer.Option(
        False,
        "--version",
        help="Show the installed SKTR version and exit.",
        is_eager=True,
    ),
) -> None:
    """SKTR - System Knowledge & Technical Review."""
    if show_version:
        typer.echo(f"sktr {SKTR_VERSION}")
        raise typer.Exit()


@app.command()
def init(
    yes: bool = typer.Option(False, "--yes", "-y", help="Create the default config without prompts."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing config file."),
    preset: InitPreset | None = typer.Option(
        None,
        "--preset",
        help="Setup preset: recommended, minimal, or custom.",
    ),
    enable_ai: bool = typer.Option(False, "--ai", help="Enable AI features in the generated config."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview configuration without writing sktr.yml."),
) -> None:
    """Initialize SKTR configuration in the current project."""
    config_path = Path("sktr.yml")
    if _config_path() is not None and not force and not dry_run:
        typer.secho("SKTR is already initialized.", fg=typer.colors.YELLOW, bold=True)
        typer.echo("sktr.yml or sktr.yaml already exists in this directory.")
        typer.echo("Use sktr init --force to overwrite it.")
        raise typer.Exit(code=1)

    _print_init_header()
    detection = detect_project()
    registry = PluginRegistry.discover()
    print_detection(detection)
    if yes:
        answers = default_answers(
            detection,
            registry,
            preset=preset or InitPreset.RECOMMENDED,
            enable_ai=enable_ai,
        )
    else:
        prompter = interactive_prompter()
        while True:
            answers = prompt_for_answers(
                detection,
                registry,
                prompter,
                preset_override=preset,
                enable_ai=enable_ai,
            )
            print_preview(answers)
            if prompter.confirm("Create sktr.yml with this configuration?", default=True):
                break
            typer.echo()
            typer.secho("Edit configuration", fg=typer.colors.CYAN, bold=True)
            preset = None

    errors = validate_answers(answers, registry)
    if errors:
        for error in errors:
            typer.secho(f"✗ {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    content = render_config(answers)
    if dry_run:
        print_preview(answers)
        typer.secho("Dry run - no file was written.", fg=typer.colors.YELLOW)
        typer.echo()
        typer.echo(content, nl=False)
        return

    config_path.write_text(content, encoding="utf-8")
    _print_init_success(config_path, answers=answers)


@app.command()
def review(
    config_file: Path | None = typer.Option(
        None,
        "--config",
        help="Load configuration from this YAML file.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write output to a file instead of stdout.",
    ),
    output_format: str = typer.Option(
        "terminal",
        "--format",
        help="Output format: terminal, json, or markdown.",
    ),
    branch: bool = typer.Option(
        False,
        "--branch",
        help="Review the current branch against its merge-base with the base branch.",
    ),
    base: str | None = typer.Option(
        None,
        "--base",
        help="Base branch for branch review. Defaults to config or main.",
    ),
    commit: str | None = typer.Option(
        None,
        "--commit",
        help="Review a commit against its parent.",
    ),
    ai: bool | None = typer.Option(
        None,
        "--ai/--no-ai",
        help="Enable or disable AI features for this review.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Override the configured AI model for this review.",
    ),
    fail_on: IssueSeverity | None = typer.Option(
        None,
        "--fail-on",
        help="Exit nonzero when a finding meets this severity.",
    ),
) -> None:
    """Review changed code using deterministic architecture analysis."""
    config = _require_config(config_file)
    registry = PluginRegistry.discover()
    scope = _review_scope(branch=branch, base=base, commit=commit)
    base_branch = base or config.git.default_base_branch
    with _progress("Analyzing changes and preparing the review..."):
        result = _build_review_result(
            scope=scope,
            base_branch=base_branch,
            commit=commit,
            registry=registry,
            ai_override=ai,
            model_override=model,
            config_path=config_file,
        )
    try:
        selected_output = registry.require("output", output_format).plugin.create_output()
    except MissingPluginError as error:
        raise typer.BadParameter(_unsupported_output_message(registry, output_format), param_hint="--format") from error
    selected_output.write(result, str(output) if output is not None else None)
    threshold = fail_on or _configured_fail_on(config)
    if threshold is not None and _meets_failure_threshold(result, threshold):
        raise typer.Exit(code=1)


@app.command()
def report(
    artifact: Path = typer.Argument(..., help="JSON review artifact to render."),
    config_file: Path | None = typer.Option(None, "--config", help="Load configuration from this YAML file."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write output to a file instead of stdout."),
    output_format: str = typer.Option(
        "terminal",
        "--format",
        help="Output format: terminal, json, or markdown.",
    ),
) -> None:
    """Render an existing review artifact without rerunning Git, rules, or AI."""
    _require_config(config_file)
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        result_payload = payload.get("review_result", payload)
        result = ReviewResult.model_validate(result_payload)
    except (OSError, json.JSONDecodeError, ValidationError, AttributeError) as error:
        raise typer.BadParameter(f"Invalid SKTR review artifact: {error}", param_hint="artifact") from error

    registry = PluginRegistry.discover()
    try:
        selected_output = registry.require("output", output_format).plugin.create_output()
    except MissingPluginError as error:
        raise typer.BadParameter(_unsupported_output_message(registry, output_format), param_hint="--format") from error
    selected_output.write(result, str(output) if output is not None else None)


@app.command()
def graph(
    config_file: Path | None = typer.Option(
        None,
        "--config",
        help="Load configuration from this YAML file.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write graph output to a file instead of stdout.",
    ),
    graph_format: str = typer.Option(
        "mermaid",
        "--format",
        help="Graph output format. Currently only mermaid is supported.",
    ),
    level: GraphLevel = typer.Option(
        GraphLevel.MODULE,
        "--level",
        help="Graph level: module or file.",
    ),
    graph_scope: GraphScope = typer.Option(
        GraphScope.CHANGES,
        "--scope",
        help="Graph source: reviewed changes or the repository.",
    ),
    branch: bool = typer.Option(
        False,
        "--branch",
        help="Graph the current branch against its merge-base with the base branch.",
    ),
    base: str | None = typer.Option(
        None,
        "--base",
        help="Base branch for changed-node context. Defaults to config or main.",
    ),
    commit: str | None = typer.Option(
        None,
        "--commit",
        help="Graph a commit against its parent.",
    ),
    focus: str | None = typer.Option(None, "--focus", help="Show one node and its direct neighborhood."),
    cycles: bool = typer.Option(False, "--cycles", help="Show only dependency cycles."),
    dependencies_of: str | None = typer.Option(
        None, "--dependencies-of", help="Show all transitive dependencies of a node."
    ),
    dependents_of: str | None = typer.Option(
        None, "--dependents-of", help="Show all transitive dependents of a node."
    ),
) -> None:
    """Generate a dependency graph from changes or repository architecture."""
    config = _require_config(config_file)
    registry = PluginRegistry.discover()
    _validate_graph_request(graph_format, focus, cycles, dependencies_of, dependents_of)
    review_scope = _review_scope(branch=branch, base=base, commit=commit)
    with _progress("Analyzing dependencies and building the graph..."):
        dependency_graph = _build_graph_for_request(
            config_file=config_file,
            registry=registry,
            graph_scope=graph_scope,
            review_scope=review_scope,
            base_branch=base or config.git.default_base_branch,
            commit=commit,
            level=level,
        )
        dependency_graph = _select_graph_view(
            dependency_graph,
            focus=focus,
            cycles=cycles,
            dependencies_of=dependencies_of,
            dependents_of=dependents_of,
        )
    _write_graph(dependency_graph, registry, graph_format, output)


def _validate_graph_request(
    graph_format: str,
    focus: str | None,
    cycles: bool,
    dependencies_of: str | None,
    dependents_of: str | None,
) -> None:
    if graph_format != "mermaid":
        raise typer.BadParameter(
            "Unsupported graph format. Supported formats: mermaid.",
            param_hint="--format",
        )
    selectors = [focus is not None, cycles, dependencies_of is not None, dependents_of is not None]
    if sum(selectors) > 1:
        raise typer.BadParameter(
            "Use only one of --focus, --cycles, --dependencies-of, or --dependents-of."
        )


def _build_graph_for_request(
    *,
    config_file: Path | None,
    registry: PluginRegistry,
    graph_scope: GraphScope,
    review_scope: ReviewScope,
    base_branch: str,
    commit: str | None,
    level: GraphLevel,
) -> Graph:
    change_result = _build_review_result(
        scope=review_scope,
        base_branch=base_branch,
        commit=commit,
        registry=registry,
        ai_override=False,
        config_path=config_file,
    )
    graph_result = change_result
    if graph_scope == GraphScope.REPOSITORY:
        graph_result = _build_repository_result(
            registry=registry,
            config_path=config_file,
            revision=commit if review_scope == ReviewScope.COMMIT else None,
        )
    return GraphBuilder().build(
        graph_result.system,
        level=level,
        changed_files=set(change_result.context.changed_files),
    )


def _select_graph_view(
    graph: Graph,
    *,
    focus: str | None,
    cycles: bool,
    dependencies_of: str | None,
    dependents_of: str | None,
) -> Graph:
    query = GraphQuery()
    try:
        if focus is not None:
            return query.focus(graph, focus)
        if cycles:
            return query.cycles(graph)
        if dependencies_of is not None:
            return query.dependencies_of(graph, dependencies_of)
        if dependents_of is not None:
            return query.dependents_of(graph, dependents_of)
        return graph
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def _write_graph(
    graph: Graph,
    registry: PluginRegistry,
    graph_format: str,
    output: Path | None,
) -> None:
    if not graph.nodes:
        _fail(
            "No dependency graph could be generated.\n\n"
            "SKTR found no resolvable dependencies or matching internal nodes for this graph.\n\n"
            "Try `sktr graph --scope repository` or choose a different focused view."
        )
    if len(graph.nodes) > 100 and output is None:
        typer.echo(
            f"Graph contains {len(graph.nodes)} nodes; consider --focus or --output.",
            err=True,
        )
    try:
        graph_output = registry.require("output", graph_format).plugin.create_output()
    except MissingPluginError as error:
        raise typer.BadParameter(str(error), param_hint="--format") from error
    graph_output.write(graph, str(output) if output is not None else None)


@plugins_app.command("list")
def plugins_list() -> None:
    """List installed SKTR plugins."""
    registry = PluginRegistry.discover()
    sections = [
        ("Analyzers", "analyzer"),
        ("Rules", "rules"),
        ("Outputs", "output"),
        ("AI Providers", "ai_provider"),
    ]
    for title, plugin_type in sections:
        typer.echo(title)
        records = registry.by_type(plugin_type)
        if not records:
            typer.echo("  (none)")
            continue
        for record in records:
            typer.echo(f"  ✓ {record.metadata.name}")


@plugins_app.command("doctor")
def plugins_doctor(
    config_file: Path | None = typer.Option(None, "--config", help="Load configuration from this YAML file."),
) -> None:
    """Validate configured SKTR plugins."""
    config = _require_config(config_file)
    registry = PluginRegistry.discover()
    errors = registry.validate_configured(_configured_plugins(config))
    if errors:
        for error in errors:
            typer.echo(f"✗ {error}")
        typer.echo()
        typer.echo("Install the missing plugins or update the `plugins` section in sktr.yml.")
        typer.echo("Run `sktr plugins list` to see plugins available in this environment.")
        raise typer.Exit(code=1)
    typer.echo("✓ Plugin configuration is valid.")


@ai_app.command("doctor")
def ai_doctor(
    config_file: Path | None = typer.Option(None, "--config", help="Load configuration from this YAML file."),
) -> None:
    """Report AI provider readiness without revealing credentials."""
    config = _require_config(config_file)
    provider = config.ai.provider
    if not config.ai.enabled or provider is None:
        typer.echo("AI provider: not configured")
        return

    typer.echo(f"AI provider: {provider}")
    if config.ai.model:
        typer.echo(f"AI model: {config.ai.model}")
    if provider not in {"openai", "sktr-openai"}:
        typer.echo("API key: not checked for this provider")
        return

    resolution = resolve_openai_api_key()
    if resolution.source is None:
        typer.echo("API key: missing")
        typer.echo()
        typer.echo("Set SKTR_OPENAI_API_KEY or OPENAI_API_KEY, then run `sktr ai doctor` again.")
    else:
        typer.echo(f"API key: found via {resolution.source}")


def _review_scope(*, branch: bool, base: str | None, commit: str | None) -> ReviewScope:
    if commit is not None and (branch or base is not None):
        raise typer.BadParameter("--commit cannot be combined with --branch or --base")
    if commit is not None:
        return ReviewScope.COMMIT
    if branch or base is not None:
        return ReviewScope.BRANCH
    return ReviewScope.WORKING_TREE


def _progress(message: str, *, console: Any | None = None) -> AbstractContextManager[Any]:
    target = console or Console(stderr=True)
    if not target.is_terminal:
        return nullcontext()
    return target.status(f"[cyan]{message}[/cyan]", spinner="dots")


def _build_review_result(
    *,
    scope: ReviewScope,
    base_branch: str,
    commit: str | None,
    registry: PluginRegistry | None = None,
    ai_override: bool | None = None,
    model_override: str | None = None,
    config_path: Path | None = None,
) -> ReviewResult:
    config = _require_config(config_path)
    plugin_registry = registry or PluginRegistry.discover()
    if not config.plugins.analyzers:
        _fail(
            "No analyzer is configured.\n\n"
            "SKTR needs at least one analyzer to build the knowledge model.\n\n"
            "Run `sktr init --force` or add an installed analyzer under `plugins.analyzers`."
        )
    try:
        analyzers = [
            plugin_registry.require("analyzer", name).plugin.create_analyzer()
            for name in config.plugins.analyzers
        ]
        rules = [
            rule
            for name in config.plugins.rules
            for rule in plugin_registry.require("rules", name).plugin.create_rules(config.rules)
        ]
    except MissingPluginError as error:
        _fail(_missing_plugin_message(error))
    run_ai = _ai_enabled(config, ai_override)
    ai_provider = None
    if run_ai:
        provider_name = config.ai.provider or _default_ai_provider_name(plugin_registry)
        if provider_name:
            try:
                provider_plugin = plugin_registry.require("ai_provider", provider_name).plugin
            except MissingPluginError as error:
                _fail(_missing_plugin_message(error))
            ai_provider = provider_plugin.create_ai_provider(model=model_override or config.ai.model)
        else:
            ai_provider = NullAIProvider()
    git_provider = SubprocessGitProvider(
        scope=scope,
        base_branch=base_branch,
        commit=commit,
    )
    try:
        repository_root = git_provider.repository_root()
    except GitProviderError as error:
        _fail(f"Git could not prepare this review: {error}")
    if repository_root is None:
        _fail(
            "Not inside a Git repository.\n\n"
            "SKTR reviews Git changes and cannot determine a diff here.\n\n"
            "Run this command inside a Git repository, or initialize one with `git init`."
        )
    try:
        git_diff = filter_git_diff(git_provider.current_diff(), config.review.exclude)
    except GitProviderError as error:
        _fail(f"Git could not prepare this review: {error}")
    pipeline = ReviewPipeline(
        diff=git_diff,
        analyzers=analyzers,
        enrichment_engine=KnowledgeEnrichmentEngine.default(),
        rules=rules,
        ai_provider=ai_provider,
        run_ai=run_ai,
    )
    return pipeline.run()


def _build_repository_result(
    *,
    registry: PluginRegistry | None = None,
    config_path: Path | None = None,
    revision: str | None = None,
) -> ReviewResult:
    config = _require_config(config_path)
    plugin_registry = registry or PluginRegistry.discover()
    try:
        analyzers = [
            plugin_registry.require("analyzer", name).plugin.create_analyzer()
            for name in config.plugins.analyzers
        ]
    except MissingPluginError as error:
        _fail(_missing_plugin_message(error))
    git_provider = SubprocessGitProvider()
    try:
        snapshot = filter_git_diff(
            git_provider.repository_snapshot(revision=revision),
            config.review.exclude,
        )
    except GitProviderError as error:
        _fail(f"Git could not prepare this graph: {error}")
    return ReviewPipeline(diff=snapshot, analyzers=analyzers).run()


def _require_config(path: Path | None = None) -> SKTRConfig:
    config_path = path or _config_path()
    if config_path is None or not config_path.is_file():
        typer.secho("No SKTR config found.", fg=typer.colors.RED, bold=True)
        typer.echo()
        typer.echo("SKTR commands need a sktr.yml or sktr.yaml configuration file.")
        typer.echo()
        typer.echo("Run:")
        typer.echo("  sktr init")
        typer.echo()
        typer.echo("Or pass one explicitly:")
        typer.echo("  sktr review --config path/to/sktr.yml")
        raise typer.Exit(code=1)
    try:
        return load_config(config_path)
    except (OSError, ValidationError, ValueError) as error:
        typer.secho(f"Invalid SKTR config: {config_path}", fg=typer.colors.RED, bold=True)
        typer.echo()
        typer.echo(str(error))
        typer.echo()
        typer.echo("Fix the file, or regenerate it with `sktr init --force`.")
        raise typer.Exit(code=1) from error


def _config_path() -> Path | None:
    for name in ("sktr.yml", "sktr.yaml"):
        path = Path(name)
        if path.is_file():
            return path
    return None


def _configured_plugins(config) -> dict[str, list[str]]:
    configured = {
        "analyzer": config.plugins.analyzers,
        "rules": config.plugins.rules,
        "output": config.plugins.outputs,
        "ai_provider": config.plugins.ai_providers,
    }
    if config.ai.enabled and config.ai.provider:
        configured["ai_provider"] = [*configured["ai_provider"], config.ai.provider]
    return configured


def _ai_enabled(config, override: bool | None) -> bool:
    if override is False:
        return False
    if override is True:
        return True
    return config.ai.enabled


def _configured_fail_on(config: SKTRConfig) -> IssueSeverity | None:
    return config.review.fail_on


def _meets_failure_threshold(result: ReviewResult, threshold: IssueSeverity) -> bool:
    order = {
        IssueSeverity.INFO: 0,
        IssueSeverity.LOW: 1,
        IssueSeverity.MEDIUM: 2,
        IssueSeverity.HIGH: 3,
        IssueSeverity.CRITICAL: 4,
    }
    return any(order[issue.severity] >= order[threshold] for issue in result.issues)


def _default_ai_provider_name(registry: PluginRegistry) -> str | None:
    openai = registry.get("ai_provider", "openai")
    if openai is not None:
        return openai.metadata.name
    providers = registry.by_type("ai_provider")
    return providers[0].metadata.name if providers else None


def _missing_plugin_message(error: MissingPluginError) -> str:
    config_key = {
        "analyzer": "plugins.analyzers",
        "rules": "plugins.rules",
        "output": "plugins.outputs",
        "ai_provider": "ai.provider",
    }.get(error.plugin_type, "plugins")
    return (
        f"Missing {error.plugin_type} plugin: {error.name}.\n\n"
        f"Install the plugin or remove `{error.name}` from `{config_key}` in sktr.yml.\n\n"
        "Run `sktr plugins list` to see installed plugins."
    )


def _unsupported_output_message(registry: PluginRegistry, output_format: str) -> str:
    available = ", ".join(record.metadata.name for record in registry.by_type("output")) or "none"
    return f"Unsupported output format: {output_format}. Available formats: {available}."


def _fail(message: str) -> NoReturn:
    typer.secho("Error:", fg=typer.colors.RED, bold=True, err=True)
    typer.echo(message, err=True)
    raise typer.Exit(code=1)


def _print_init_header() -> None:
    typer.echo()
    typer.secho("◆ SKTR Init", fg=typer.colors.CYAN, bold=True)
    typer.echo("System Knowledge & Technical Review")
    typer.echo("Set up deterministic architecture review for this project.")
    typer.echo()


def _print_init_success(config_path: Path, *, answers: InitAnswers) -> None:
    typer.secho(f"✓ Created {config_path}", fg=typer.colors.GREEN, bold=True)
    typer.secho("✓ Plugin configuration is valid", fg=typer.colors.GREEN)
    typer.echo()
    typer.echo("Enabled:")
    typer.echo(f"  analyzers: {', '.join(answers.analyzers) or 'none'}")
    typer.echo(f"  rules:     {', '.join(answers.rules) or 'none'}")
    typer.echo(f"  outputs:   {', '.join(answers.outputs) or 'none'}")
    ai_label = (
        f"{answers.ai_provider} ({answers.ai_model})"
        if answers.ai_enabled
        else "disabled"
    )
    typer.echo(f"  AI:        {ai_label}")
    typer.echo()
    typer.echo("Next steps:")
    typer.echo("  sktr plugins doctor")
    typer.echo("  sktr review")
    typer.echo("  sktr review --ai")
    typer.echo("  sktr review --format markdown --output REVIEW.md")
