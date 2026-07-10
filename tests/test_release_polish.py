from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

import sktr_ai
import sktr_core
import sktr_enrichment
import sktr_git
import sktr_graph
import sktr_java
import sktr_javascript
import sktr_python
import sktr_report
import sktr_rules
import sktr_treesitter
from sktr_cli import main as cli_main
from sktr_core.model import ReviewResult
from sktr_core.plugins.discovery import PluginLoadError, PluginRegistry
from sktr_core.version import SKTR_VERSION

runner = CliRunner()
ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    "arguments,expected",
    [
        (["--help"], "Understand your software before you change it"),
        (["init", "--help"], "without prompts"),
        (["review", "--help"], "--fail-on"),
        (["graph", "--help"], "Graph level: module or file"),
        (["plugins", "--help"], "List and validate installed SKTR plugins"),
        (["ai", "--help"], "Check whether configured AI features are ready"),
    ],
)
def test_cli_help_is_available_and_descriptive(arguments: list[str], expected: str) -> None:
    result = runner.invoke(cli_main.app, arguments)

    assert result.exit_code == 0
    assert expected in result.output


def test_cli_reports_version() -> None:
    result = runner.invoke(cli_main.app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == "sktr 0.18.0"


def test_review_accepts_explicit_config_path(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "custom.yml"
    config_path.write_text("project:\n  name: explicit-config\n", encoding="utf-8")
    received: list[Path | None] = []

    def build(**kwargs) -> ReviewResult:
        received.append(kwargs["config_path"])
        return ReviewResult(status="ready")

    monkeypatch.setattr(cli_main, "_build_review_result", build)
    result = runner.invoke(cli_main.app, ["review", "--config", str(config_path)])

    assert result.exit_code == 0
    assert received == [config_path]


def test_invalid_config_has_actionable_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.yml"
    config_path.write_text("ai:\n  enabled: true\n", encoding="utf-8")

    result = runner.invoke(cli_main.app, ["ai", "doctor", "--config", str(config_path)])

    assert result.exit_code == 1
    assert f"Invalid SKTR config: {config_path}" in result.output
    assert "ai.provider is required" in result.output
    assert "sktr init --force" in result.output
    assert "Traceback" not in result.output


def test_review_outside_git_has_actionable_error(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "sktr.yml").write_text("project:\n  name: no-git\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli_main.app, ["review"])

    assert result.exit_code == 1
    assert "Not inside a Git repository" in result.output
    assert "git init" in result.output
    assert "Traceback" not in result.output


def test_missing_analyzer_has_actionable_error(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "sktr.yml").write_text(
        "plugins:\n  analyzers: []\n  rules: []\n  outputs:\n    - terminal\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli_main.app, ["review"])

    assert result.exit_code == 1
    assert "No analyzer is configured" in result.output
    assert "plugins.analyzers" in result.output


def test_invalid_output_format_lists_available_formats(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "sktr.yml").write_text("project:\n  name: output-test\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli_main,
        "_build_review_result",
        lambda **kwargs: ReviewResult(status="ready"),
    )

    result = runner.invoke(cli_main.app, ["review", "--format", "xml"])

    assert result.exit_code != 0
    assert "Unsupported output format: xml" in result.output
    assert "terminal" in result.output


def test_graph_without_dependencies_explains_next_step(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "sktr.yml").write_text("project:\n  name: graph-test\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli_main,
        "_build_review_result",
        lambda **kwargs: ReviewResult(status="ready"),
    )

    result = runner.invoke(cli_main.app, ["graph"])

    assert result.exit_code == 1
    assert "No dependency graph could be generated" in result.output
    assert "no resolvable dependencies" in result.output


def test_example_config_loads_and_example_project_reviews(tmp_path: Path) -> None:
    example = tmp_path / "python-basic"
    shutil.copytree(ROOT / "examples" / "python-basic", example)
    _git(example, "init")
    _git(example, "config", "user.email", "sktr@example.test")
    _git(example, "config", "user.name", "SKTR Test")
    _git(example, "add", "sktr.yml")
    _git(example, "commit", "-m", "Initialize SKTR")
    _git(example, "add", "controllers", "repositories", "services")

    previous = Path.cwd()
    try:
        import os

        os.chdir(example)
        result = runner.invoke(cli_main.app, ["review"])
    finally:
        os.chdir(previous)

    assert result.exit_code == 0
    assert "Forbidden dependency" in result.output
    assert "controllers/order_controller.py" in result.output
    assert "repositories/order_repository.py" in result.output


@pytest.mark.parametrize(
    "example_name,expected_target",
    [
        ("javascript-typescript-basic", "src/repositories/orderRepository.ts"),
        ("java-basic", "src/main/java/com/sample/repositories/OrderRepository.java"),
    ],
)
def test_bundled_language_examples_review_end_to_end(
    tmp_path: Path,
    example_name: str,
    expected_target: str,
) -> None:
    example = tmp_path / example_name
    shutil.copytree(ROOT / "examples" / example_name, example)
    _git(example, "init")
    _git(example, "config", "user.email", "sktr@example.test")
    _git(example, "config", "user.name", "SKTR Test")
    _git(example, "add", "sktr.yml")
    _git(example, "commit", "-m", "Initialize SKTR")
    _git(example, "add", ".")

    previous = Path.cwd()
    try:
        import os

        os.chdir(example)
        result = runner.invoke(cli_main.app, ["review"])
    finally:
        os.chdir(previous)

    assert result.exit_code == 0
    assert "Forbidden dependency" in result.output
    assert expected_target in result.output


def test_mixed_language_example_artifact_contains_all_languages(tmp_path: Path) -> None:
    example = tmp_path / "mixed-language-ci"
    shutil.copytree(ROOT / "examples" / "mixed-language-ci", example)
    _git(example, "init")
    _git(example, "config", "user.email", "sktr@example.test")
    _git(example, "config", "user.name", "SKTR Test")
    _git(example, "add", "sktr.yml")
    _git(example, "commit", "-m", "Initialize SKTR")
    _git(example, "add", "src")
    artifact = example / "review.json"

    previous = Path.cwd()
    try:
        import os

        os.chdir(example)
        result = runner.invoke(
            cli_main.app,
            ["review", "--format", "json", "--output", str(artifact)],
        )
    finally:
        os.chdir(previous)

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    languages = {
        source_file["language"]
        for module in payload["review_result"]["system"]["modules"]
        for source_file in module["files"]
    }
    assert result.exit_code == 0
    assert languages == {"python", "typescript", "java"}


def test_public_docs_include_release_commands_and_current_ai_field() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    outputs = (ROOT / "docs" / "outputs.md").read_text(encoding="utf-8")

    for command in [
        "pip install sktr",
        "sktr init --yes",
        "sktr review --ai",
        "sktr review --format markdown --output REVIEW.md",
        "sktr review --format json --output sktr-review.json",
        "sktr graph --format mermaid --output architecture.mmd",
    ]:
        assert command in readme
    assert "`ai_review`" in outputs
    assert "ai_summary" not in readme
    assert "ai_advice" not in readme


def test_package_import_smoke() -> None:
    packages = [
        sktr_ai,
        sktr_core,
        sktr_enrichment,
        sktr_git,
        sktr_graph,
        sktr_java,
        sktr_javascript,
        sktr_python,
        sktr_report,
        sktr_rules,
        sktr_treesitter,
    ]

    assert all(package.__name__.startswith("sktr_") for package in packages)


def test_packaging_metadata_matches_release_contract() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)["project"]

    assert project["name"] == "sktr"
    assert project["version"] == "0.18.0"
    assert project["requires-python"] == ">=3.13"
    assert project["readme"] == "README.md"
    assert project["license"] == "MIT"
    assert project["scripts"]["sktr"] == "sktr_cli.main:app"
    assert {"pydantic>=2.0", "pathspec>=0.12", "questionary>=2.1.1", "rich>=13.0", "typer>=0.12"} <= set(
        project["dependencies"]
    )


def test_plugin_load_errors_are_reported_by_doctor_validation() -> None:
    registry = PluginRegistry(
        [],
        [
            PluginLoadError(
                entry_point_name="broken",
                group="sktr.analyzers",
                message="cannot import plugin",
            )
        ],
    )

    assert registry.validate_configured({}) == [
        "Plugin broken could not be loaded from sktr.analyzers: cannot import plugin"
    ]


def test_builtin_plugin_versions_match_package_version() -> None:
    registry = PluginRegistry.discover()

    assert SKTR_VERSION == "0.18.0"
    assert {record.metadata.version for record in registry.records} == {SKTR_VERSION}


def _git(cwd: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
