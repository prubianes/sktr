from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sktr_cli.main import app
from sktr_cli.init_flow import (
    InitPreset,
    ProjectDetection,
    default_answers,
    prompt_for_answers,
    render_config,
    validate_answers,
)
from sktr_core.plugins import PluginRegistry

runner = CliRunner()


def test_init_yes_creates_default_config() -> None:
    with _isolated(tmp_path := Path.cwd() / ".tmp-init-test-1"):
        Path("pyproject.toml").write_text('[project]\nname = "sample-app"\n', encoding="utf-8")
        result = runner.invoke(app, ["init", "--yes"])

        assert result.exit_code == 0
        assert "◆ SKTR Init" in result.output
        assert "Detected project" in result.output
        assert "Name:           sample-app" in result.output
        assert "Plugin configuration is valid" in result.output
        assert "Next steps:" in result.output
        assert "sktr plugins doctor" in result.output
        config = Path("sktr.yml").read_text(encoding="utf-8")
        assert "project:" in config
        assert "name: sample-app" in config
        assert "sktr-python" in config


def test_init_refuses_overwrite() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-2"):
        Path("sktr.yml").write_text("existing: true\n", encoding="utf-8")

        result = runner.invoke(app, ["init", "--yes"])

        assert result.exit_code != 0
        assert "SKTR is already initialized." in result.output
        assert "already exists" in result.output
        assert Path("sktr.yml").read_text(encoding="utf-8") == "existing: true\n"


def test_init_force_overwrites() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-3"):
        Path("sktr.yml").write_text("existing: true\n", encoding="utf-8")

        result = runner.invoke(app, ["init", "--yes", "--force"])

        assert result.exit_code == 0
        assert "plugins:" in Path("sktr.yml").read_text(encoding="utf-8")


def test_init_yes_does_not_prompt() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-4"):
        result = runner.invoke(app, ["init", "--yes"], input="")

        assert result.exit_code == 0
        assert "Choose a setup" not in result.output
        assert "Create sktr.yml with this configuration?" not in result.output


def test_init_recommended_defaults_prompt() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-5"):
        result = runner.invoke(app, ["init"], input="\n\n\n")

        assert result.exit_code == 0
        assert "Choose a setup" in result.output
        assert "Enable AI Review?" in result.output
        assert "Configuration" in result.output
        assert "Create sktr.yml with this configuration?" in result.output


def test_init_customize_settings() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-6"):
        result = runner.invoke(
            app,
            ["init"],
            input="\n".join(
                [
                    "custom",
                    "orders-api",
                    "develop",
                    *([""] * 8),
                    "y",
                    "y",
                    "n",
                    "n",
                    "y",
                    "",
                    "__custom__",
                    "gpt-5-mini",
                    "y",
                ]
            )
            + "\n",
        )

        assert result.exit_code == 0
        config = Path("sktr.yml").read_text(encoding="utf-8")
        assert "name: orders-api" in config
        assert "default_base: develop" in config
        assert "    - terminal" in config
        assert "    - markdown" in config
        assert "    - json" not in config
        assert "    - mermaid" not in config
        assert "enabled: true" in config
        assert "provider: openai" in config
        assert "model: gpt-5-mini" in config


def test_init_can_leave_ai_disabled_interactively() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-7"):
        result = runner.invoke(app, ["init"], input="\n\n\n")

        assert result.exit_code == 0
        config = Path("sktr.yml").read_text(encoding="utf-8")
        assert "enabled: false" in config
        assert "provider:" not in config
        assert "model:" not in config


def test_init_minimal_preset_selects_essential_outputs() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-8"):
        result = runner.invoke(app, ["init", "--yes", "--preset", "minimal"])

        assert result.exit_code == 0
        config = Path("sktr.yml").read_text(encoding="utf-8")
        assert "    - terminal" in config
        assert "    - json" in config
        assert "    - markdown" not in config
        assert "    - mermaid" not in config


def test_init_dry_run_does_not_write_config() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-9"):
        result = runner.invoke(app, ["init", "--yes", "--dry-run"])

        assert result.exit_code == 0
        assert "Dry run - no file was written." in result.output
        assert "project:" in result.output
        assert not Path("sktr.yml").exists()


def test_init_yes_can_enable_detected_ai_provider_without_prompts(monkeypatch) -> None:
    monkeypatch.setenv("SKTR_OPENAI_API_KEY", "not-printed")
    with _isolated(Path.cwd() / ".tmp-init-test-10"):
        result = runner.invoke(app, ["init", "--yes", "--ai"])

        assert result.exit_code == 0
        config = Path("sktr.yml").read_text(encoding="utf-8")
        assert "enabled: true" in config
        assert "provider: openai" in config
        assert "model: gpt-5.6-terra" in config
        assert "not-printed" not in result.output


def test_init_openai_model_profiles_include_fast_balanced_quality_and_custom() -> None:
    from sktr_ai import DEFAULT_OPENAI_MODEL, OPENAI_MODEL_PROFILES

    assert DEFAULT_OPENAI_MODEL == "gpt-5.6-terra"
    assert [model for _, model in OPENAI_MODEL_PROFILES] == [
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.6-sol",
    ]


def test_interactive_init_can_select_luna_profile() -> None:
    class Prompter:
        def confirm(self, message: str, default: bool = True) -> bool:
            return True

        def select(self, message, choices, default):
            if message == "AI provider":
                return "openai"
            if message == "OpenAI model":
                return "gpt-5.6-luna"
            return default

        def checkbox(self, message, choices, defaults):
            return defaults

        def text(self, message: str, default: str) -> str:
            return default

    answers = prompt_for_answers(
        ProjectDetection(name="app", default_base="main", languages=["Python"], repository="Git"),
        PluginRegistry.discover(),
        Prompter(),
        preset_override=InitPreset.RECOMMENDED,
    )

    assert answers.ai_model == "gpt-5.6-luna"


def test_default_config_remains_valid_when_no_plugins_are_discovered() -> None:
    registry = PluginRegistry([])
    answers = default_answers(
        ProjectDetection(name="empty-app", default_base="main", languages=[], repository="directory"),
        registry,
        preset=InitPreset.RECOMMENDED,
    )

    config = render_config(answers)

    assert validate_answers(answers, registry) == []
    assert "analyzers: []" in config
    assert "outputs: []" in config


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
