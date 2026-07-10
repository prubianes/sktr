from __future__ import annotations

import json
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError
from rich.console import Console

from sktr_core.config import load_config
from sktr_core.model import ReviewResult
from sktr_core.pipeline import ReviewPipeline
from sktr_core.plugins import MissingPluginError, PluginRegistry
from sktr_ai import NullAIProvider, resolve_openai_api_key
from sktr_enrichment import KnowledgeEnrichmentEngine
from sktr_graph import GraphBuilder, GraphLevel
from sktr_git import ReviewScope, SubprocessGitProvider
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

app = typer.Typer(help="System Knowledge & Technical Review.")
plugins_app = typer.Typer(help="Inspect SKTR plugins.")
ai_app = typer.Typer(help="Inspect configured AI providers.")
app.add_typer(plugins_app, name="plugins")
app.add_typer(ai_app, name="ai")

@app.callback()
def main() -> None:
    """System Knowledge & Technical Review."""


@app.command()
def init(
    yes: bool = typer.Option(False, "--yes", "-y", help="Create the default config without prompts."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing config file."),
    preset: InitPreset | None = typer.Option(
        None,
        "--preset",
        help="Setup preset: recommended, minimal, or custom.",
    ),
    enable_ai: bool = typer.Option(False, "--ai", help="Enable the default installed AI provider."),
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
        help="Enable or disable AI Review for this run.",
    ),
) -> None:
    """Analyze the current Git diff and produce an architecture-focused review."""
    config = _require_config()
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
        )
    try:
        selected_output = registry.require("output", output_format).plugin.create_output()
    except MissingPluginError as error:
        raise typer.BadParameter(str(error), param_hint="--format") from error
    selected_output.write(result, str(output) if output is not None else None)


@app.command()
def report(
    artifact: Path = typer.Argument(..., help="JSON review artifact to render."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write output to a file instead of stdout."),
    output_format: str = typer.Option(
        "terminal",
        "--format",
        help="Output format: terminal, json, or markdown.",
    ),
) -> None:
    """Render an existing review artifact without rerunning Git, rules, or AI."""
    _require_config()
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
        raise typer.BadParameter(str(error), param_hint="--format") from error
    selected_output.write(result, str(output) if output is not None else None)


@app.command()
def graph(
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
) -> None:
    """Generate architecture graphs from the SKTR knowledge model."""
    if graph_format != "mermaid":
        raise typer.BadParameter("Unsupported graph format. Supported formats: mermaid.", param_hint="--format")

    config = _require_config()
    registry = PluginRegistry.discover()
    with _progress("Analyzing dependencies and building the graph..."):
        result = _build_review_result(
            scope=ReviewScope.WORKING_TREE,
            base_branch=config.git.default_base_branch,
            commit=None,
            registry=registry,
        )
        dependency_graph = GraphBuilder().build(result.system, level=level)
    try:
        graph_output = registry.require("output", graph_format).plugin.create_output()
    except MissingPluginError as error:
        raise typer.BadParameter(str(error), param_hint="--format") from error
    graph_output.write(dependency_graph, str(output) if output is not None else None)


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
def plugins_doctor() -> None:
    """Validate configured SKTR plugins."""
    config = _require_config()
    registry = PluginRegistry.discover()
    errors = registry.validate_configured(_configured_plugins(config))
    if errors:
        for error in errors:
            typer.echo(f"✗ {error}")
        raise typer.Exit(code=1)
    typer.echo("✓ Plugin configuration is valid.")


@ai_app.command("doctor")
def ai_doctor() -> None:
    """Report AI provider readiness without revealing credentials."""
    config = _require_config()
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
) -> ReviewResult:
    config = _require_config()
    plugin_registry = registry or PluginRegistry.discover()
    analyzers = [
        plugin_registry.require("analyzer", name).plugin.create_analyzer()
        for name in config.plugins.analyzers
    ]
    rules = [
        rule
        for name in config.plugins.rules
        for rule in plugin_registry.require("rules", name).plugin.create_rules(config.rules)
    ]
    run_ai = _ai_enabled(config, ai_override)
    ai_provider = None
    if run_ai:
        provider_name = config.ai.provider or _default_ai_provider_name(plugin_registry)
        if provider_name:
            ai_provider = plugin_registry.require("ai_provider", provider_name).plugin.create_ai_provider(
                model=config.ai.model
            )
        else:
            ai_provider = NullAIProvider()
    git_diff = SubprocessGitProvider(
        scope=scope,
        base_branch=base_branch,
        commit=commit,
    ).current_diff()
    pipeline = ReviewPipeline(
        diff=git_diff,
        analyzers=analyzers,
        enrichment_engine=KnowledgeEnrichmentEngine.default(),
        rules=rules,
        ai_provider=ai_provider,
        run_ai=run_ai,
    )
    return pipeline.run()


def _require_config():
    config_path = _config_path()
    if config_path is None:
        typer.secho("SKTR is not initialized in this directory.", fg=typer.colors.RED, bold=True)
        typer.echo("No sktr.yml or sktr.yaml file was found.")
        typer.echo("Run sktr init to create one.")
        raise typer.Exit(code=1)
    return load_config(config_path)


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


def _default_ai_provider_name(registry: PluginRegistry) -> str | None:
    openai = registry.get("ai_provider", "openai")
    if openai is not None:
        return openai.metadata.name
    providers = registry.by_type("ai_provider")
    return providers[0].metadata.name if providers else None


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
