from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, TypeVar

import questionary
import typer
from questionary import Choice, Style

from sktr_ai import resolve_openai_api_key
from sktr_core.config import DEFAULT_ENABLED_RULES, DEFAULT_EXCLUDES
from sktr_core.plugins import PluginRegistry

DEFAULT_OUTPUTS = ["terminal", "markdown", "json", "mermaid"]

SKTR_STYLE = Style(
    [
        ("qmark", "fg:#00d7d7 bold"),
        ("question", "bold"),
        ("pointer", "fg:#00d7d7 bold"),
        ("highlighted", "fg:#00d7d7 bold"),
        ("selected", "fg:#00af87"),
        ("answer", "fg:#00af87 bold"),
    ]
)


class InitPreset(StrEnum):
    RECOMMENDED = "recommended"
    MINIMAL = "minimal"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ProjectDetection:
    name: str
    default_base: str
    languages: list[str]
    repository: str


@dataclass(frozen=True)
class InitAnswers:
    preset: InitPreset
    project_name: str
    default_base: str
    analyzers: list[str]
    rules: list[str]
    enabled_rules: list[str]
    outputs: list[str]
    ai_enabled: bool = False
    ai_provider: str | None = None
    ai_model: str | None = None


T = TypeVar("T")


class InitPrompter(Protocol):
    def select(self, message: str, choices: list[tuple[str, T]], default: T) -> T: ...
    def checkbox(self, message: str, choices: list[tuple[str, str]], defaults: list[str]) -> list[str]: ...
    def text(self, message: str, default: str) -> str: ...
    def confirm(self, message: str, default: bool = True) -> bool: ...


class QuestionaryPrompter:
    def select(self, message: str, choices: list[tuple[str, T]], default: T) -> T:
        answer = questionary.select(
            message,
            choices=[Choice(title=title, value=value) for title, value in choices],
            default=default,
            style=SKTR_STYLE,
            qmark="?",
            pointer="›",
        ).ask()
        if answer is None:
            raise typer.Abort()
        return answer

    def checkbox(self, message: str, choices: list[tuple[str, str]], defaults: list[str]) -> list[str]:
        answer = questionary.checkbox(
            message,
            choices=[Choice(title=title, value=value, checked=value in defaults) for title, value in choices],
            style=SKTR_STYLE,
            qmark="?",
            pointer="›",
        ).ask()
        if answer is None:
            raise typer.Abort()
        return list(answer)

    def text(self, message: str, default: str) -> str:
        answer = questionary.text(message, default=default, style=SKTR_STYLE, qmark="?").ask()
        if answer is None:
            raise typer.Abort()
        return str(answer).strip() or default

    def confirm(self, message: str, default: bool = True) -> bool:
        answer = questionary.confirm(message, default=default, style=SKTR_STYLE, qmark="?").ask()
        if answer is None:
            raise typer.Abort()
        return bool(answer)


class TyperPrompter:
    """Fallback for redirected input and test runners without terminal controls."""

    def select(self, message: str, choices: list[tuple[str, T]], default: T) -> T:
        values = {str(value): value for _, value in choices}
        labels = "/".join(values)
        answer = typer.prompt(f"{message} ({labels})", default=str(default))
        while answer not in values:
            typer.secho(f"Choose one of: {labels}", fg=typer.colors.YELLOW)
            answer = typer.prompt(message, default=str(default))
        return values[answer]

    def checkbox(self, message: str, choices: list[tuple[str, str]], defaults: list[str]) -> list[str]:
        typer.echo(message)
        selected: list[str] = []
        for title, value in choices:
            if typer.confirm(f"  {title}?", default=value in defaults):
                selected.append(value)
        return selected

    def text(self, message: str, default: str) -> str:
        return str(typer.prompt(message, default=default))

    def confirm(self, message: str, default: bool = True) -> bool:
        return typer.confirm(message, default=default)


def interactive_prompter() -> InitPrompter:
    if sys.stdin.isatty() and sys.stdout.isatty():
        return QuestionaryPrompter()
    return TyperPrompter()


def detect_project(root: Path | None = None) -> ProjectDetection:
    root = root or Path.cwd()
    return ProjectDetection(
        name=_project_name(root),
        default_base=_default_branch(root),
        languages=_languages(root),
        repository="Git" if (root / ".git").exists() else "directory",
    )


def default_answers(
    detection: ProjectDetection,
    registry: PluginRegistry,
    *,
    preset: InitPreset = InitPreset.RECOMMENDED,
    enable_ai: bool = False,
) -> InitAnswers:
    analyzers = [record.metadata.name for record in registry.by_type("analyzer")]
    rules = [record.metadata.name for record in registry.by_type("rules")]
    installed_outputs = [record.metadata.name for record in registry.by_type("output")]
    if preset == InitPreset.MINIMAL:
        outputs = [name for name in ("terminal", "json") if name in installed_outputs]
        enabled_rules = ["new_dependency", "large_file", "large_function", "forbidden_dependency"]
    else:
        outputs = [name for name in DEFAULT_OUTPUTS if name in installed_outputs]
        enabled_rules = DEFAULT_ENABLED_RULES.copy()
    provider = _default_ai_provider(registry) if enable_ai else None
    return InitAnswers(
        preset=preset,
        project_name=detection.name,
        default_base=detection.default_base,
        analyzers=analyzers,
        rules=rules,
        enabled_rules=enabled_rules,
        outputs=outputs,
        ai_enabled=bool(provider),
        ai_provider=provider,
        ai_model="gpt-5-mini" if provider == "openai" else None,
    )


def prompt_for_answers(
    detection: ProjectDetection,
    registry: PluginRegistry,
    prompter: InitPrompter,
    *,
    preset_override: InitPreset | None = None,
    enable_ai: bool = False,
) -> InitAnswers:
    preset = preset_override or prompter.select(
        "Choose a setup",
        [
            ("Recommended - full deterministic review", InitPreset.RECOMMENDED),
            ("Minimal - terminal and JSON essentials", InitPreset.MINIMAL),
            ("Customize settings", InitPreset.CUSTOM),
        ],
        InitPreset.RECOMMENDED,
    )
    answers = default_answers(detection, registry, preset=preset, enable_ai=enable_ai)
    if preset == InitPreset.CUSTOM:
        answers = _custom_answers(answers, registry, prompter, enable_ai=enable_ai)
    elif preset == InitPreset.RECOMMENDED and not enable_ai:
        answers = _with_ai(answers, registry, prompter)
    return answers


def _custom_answers(
    answers: InitAnswers,
    registry: PluginRegistry,
    prompter: InitPrompter,
    *,
    enable_ai: bool,
) -> InitAnswers:
    project_name = prompter.text("Project name", answers.project_name)
    default_base = prompter.text("Default base branch", answers.default_base)
    enabled_rules = prompter.checkbox(
        "Select deterministic rules",
        [(rule.replace("_", " ").title(), rule) for rule in DEFAULT_ENABLED_RULES],
        answers.enabled_rules,
    )
    outputs = prompter.checkbox(
        "Select output formats",
        [(name, name) for name in _ordered_output_names(registry)],
        answers.outputs,
    )
    if not outputs and registry.get("output", "terminal"):
        outputs = ["terminal"]
    customized = InitAnswers(
        **{
            **answers.__dict__,
            "project_name": project_name,
            "default_base": default_base,
            "enabled_rules": enabled_rules,
            "outputs": outputs,
        }
    )
    return customized if enable_ai else _with_ai(customized, registry, prompter)


def _with_ai(answers: InitAnswers, registry: PluginRegistry, prompter: InitPrompter) -> InitAnswers:
    providers = registry.by_type("ai_provider")
    if not providers or not prompter.confirm("Enable AI Review?", default=False):
        return InitAnswers(**{**answers.__dict__, "ai_enabled": False, "ai_provider": None, "ai_model": None})
    provider = prompter.select(
        "AI provider",
        [(record.metadata.name, record.metadata.name) for record in providers],
        providers[0].metadata.name,
    )
    model = prompter.text("AI model", "gpt-5-mini" if provider == "openai" else "default")
    return InitAnswers(
        **{**answers.__dict__, "ai_enabled": True, "ai_provider": provider, "ai_model": model}
    )


def validate_answers(answers: InitAnswers, registry: PluginRegistry) -> list[str]:
    configured = {
        "analyzer": answers.analyzers,
        "rules": answers.rules,
        "output": answers.outputs,
        "ai_provider": [answers.ai_provider] if answers.ai_enabled and answers.ai_provider else [],
    }
    return registry.validate_configured(configured)


def render_config(answers: InitAnswers) -> str:
    return f"""project:
  name: {answers.project_name}
  default_base: {answers.default_base}
review:
  default_scope: working_tree
  fail_on: null
  exclude:{_yaml_list(DEFAULT_EXCLUDES)}
plugins:
  analyzers:{_yaml_list(answers.analyzers)}
  rules:{_yaml_list(answers.rules)}
  outputs:{_yaml_list(answers.outputs)}
rules:
  enabled:{_yaml_list(answers.enabled_rules)}
ai:
  enabled: {str(answers.ai_enabled).lower()}
{_ai_details(answers)}"""


def print_detection(detection: ProjectDetection) -> None:
    typer.secho("Detected project", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"  Name:           {detection.name}")
    typer.echo(f"  Repository:     {detection.repository}")
    typer.echo(f"  Default branch: {detection.default_base}")
    typer.echo(f"  Languages:      {', '.join(detection.languages) or 'unknown'}")
    typer.echo()


def print_preview(answers: InitAnswers) -> None:
    typer.secho("Configuration", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"  Preset:    {answers.preset.value}")
    typer.echo(f"  Project:   {answers.project_name}")
    typer.echo(f"  Base:      {answers.default_base}")
    typer.echo(f"  Analyzers: {', '.join(answers.analyzers) or 'none'}")
    typer.echo(f"  Rule packs:{' ' if answers.rules else ''}{', '.join(answers.rules) or 'none'}")
    typer.echo(f"  Rules:     {len(answers.enabled_rules)} enabled")
    typer.echo(f"  Outputs:   {', '.join(answers.outputs) or 'none'}")
    ai = f"{answers.ai_provider} ({answers.ai_model})" if answers.ai_enabled else "disabled"
    typer.echo(f"  AI Review: {ai}")
    if answers.ai_enabled and answers.ai_provider == "openai":
        key = resolve_openai_api_key()
        source = f"found via {key.source}" if key.source else "missing"
        typer.echo(f"  API key:   {source}")
    typer.echo()


def _project_name(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            name = data.get("project", {}).get("name")
            if isinstance(name, str) and name:
                return name
        except (OSError, tomllib.TOMLDecodeError):
            pass
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            name = json.loads(package_json.read_text(encoding="utf-8")).get("name")
            if isinstance(name, str) and name:
                return name
        except (OSError, json.JSONDecodeError):
            pass
    return root.name or "sample-app"


def _default_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().removeprefix("origin/")
    except OSError:
        pass
    return "main"


def _languages(root: Path) -> list[str]:
    languages: list[str] = []
    if (root / "pyproject.toml").is_file() or any(root.glob("*.py")):
        languages.append("Python")
    if (root / "package.json").is_file():
        languages.append("TypeScript/JavaScript")
    if (root / "pom.xml").is_file() or (root / "build.gradle").is_file():
        languages.append("Java")
    return languages


def _default_ai_provider(registry: PluginRegistry) -> str | None:
    openai = registry.get("ai_provider", "openai")
    if openai:
        return openai.metadata.name
    providers = registry.by_type("ai_provider")
    return providers[0].metadata.name if providers else None


def _ordered_output_names(registry: PluginRegistry) -> list[str]:
    installed = {record.metadata.name for record in registry.by_type("output")}
    known = [name for name in DEFAULT_OUTPUTS if name in installed]
    additional = sorted(installed - set(known))
    return [*known, *additional]


def _yaml_list(values: list[str]) -> str:
    if not values:
        return " []"
    return "\n" + "\n".join(f"    - {_yaml_scalar(value)}" for value in values)


def _yaml_scalar(value: str) -> str:
    if value.startswith(("*", "!", "&")) or ": " in value or " #" in value:
        return json.dumps(value)
    return value


def _ai_details(answers: InitAnswers) -> str:
    if not answers.ai_enabled:
        return ""
    provider = answers.ai_provider or ""
    model = f"\n  model: {answers.ai_model}" if answers.ai_model else ""
    return f"  provider: {provider}{model}\n"
