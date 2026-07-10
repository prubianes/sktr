from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sktr_cli.main import _build_review_result
from sktr_cli.main import app
from sktr_core.plugins import PluginRegistry
from sktr_git import ReviewScope

runner = CliRunner()


def test_plugin_discovery_finds_builtin_plugins() -> None:
    registry = PluginRegistry.discover()

    assert registry.get("analyzer", "sktr-python") is not None
    assert registry.get("analyzer", "sktr-javascript-typescript") is not None
    assert registry.get("analyzer", "sktr-java") is not None
    assert registry.get("rules", "sktr-rules-default") is not None
    assert registry.get("output", "markdown") is not None
    assert registry.get("output", "mermaid") is not None


def test_plugins_list_shows_grouped_plugins() -> None:
    result = runner.invoke(app, ["plugins", "list"])

    assert result.exit_code == 0
    assert "Analyzers" in result.output
    assert "✓ sktr-python" in result.output
    assert "Rules" in result.output
    assert "✓ sktr-rules-default" in result.output
    assert "Outputs" in result.output
    assert "✓ markdown" in result.output


def test_plugins_doctor_reports_missing_plugin() -> None:
    with _isolated(Path.cwd() / ".tmp-plugin-test-1"):
        Path("sktr.yml").write_text(
            "\n".join(
                [
                    "plugins:",
                    "  analyzers:",
                    "    - missing-analyzer",
                    "  rules:",
                    "    - sktr-rules-default",
                    "  outputs:",
                    "    - terminal",
                ]
            ),
            encoding="utf-8",
        )

        result = runner.invoke(app, ["plugins", "doctor"])

        assert result.exit_code == 1
        assert "Missing analyzer plugin: missing-analyzer" in result.output
        assert "Install the missing plugins or update" in result.output
        assert "sktr plugins list" in result.output


def test_pipeline_construction_from_discovered_plugins() -> None:
    with _isolated(Path.cwd() / ".tmp-plugin-test-2"):
        Path("sktr.yml").write_text(_config(), encoding="utf-8")
        result = _build_review_result(
            scope=ReviewScope.WORKING_TREE,
            base_branch="main",
            commit=None,
            registry=PluginRegistry.discover(),
        )

    assert result.status == "foundation ready"


def test_plugins_doctor_requires_config() -> None:
    with _isolated(Path.cwd() / ".tmp-plugin-test-3"):
        result = runner.invoke(app, ["plugins", "doctor"])

        assert result.exit_code == 1
        assert "No SKTR config found" in result.output


class _isolated:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.previous = Path.cwd()

    def __enter__(self):
        import os
        import shutil

        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir()
        os.chdir(self.path)

    def __exit__(self, exc_type, exc, tb):
        import os
        import shutil

        os.chdir(self.previous)
        shutil.rmtree(self.path)


def _config() -> str:
    return "\n".join(
        [
            "project:",
            "  name: test",
            "  default_base: main",
            "plugins:",
            "  analyzers:",
            "    - sktr-python",
            "  rules:",
            "    - sktr-rules-default",
            "  outputs:",
            "    - terminal",
        ]
    )
