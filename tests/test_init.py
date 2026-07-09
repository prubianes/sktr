from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sktr_cli.main import app

runner = CliRunner()


def test_init_yes_creates_default_config() -> None:
    with _isolated(tmp_path := Path.cwd() / ".tmp-init-test-1"):
        result = runner.invoke(app, ["init", "--yes"])

        assert result.exit_code == 0
        assert "◆ SKTR Init" in result.output
        assert "Project name: sample-app" in result.output
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
        assert "Would you like to use the recommended SKTR defaults?" not in result.output


def test_init_recommended_defaults_prompt() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-5"):
        result = runner.invoke(app, ["init"], input="\n")

        assert result.exit_code == 0
        assert "Would you like to use the recommended SKTR defaults?" in result.output
        assert "✓ Using recommended defaults" in result.output
        assert "name: sample-app" in Path("sktr.yml").read_text(encoding="utf-8")


def test_init_customize_settings() -> None:
    with _isolated(Path.cwd() / ".tmp-init-test-6"):
        result = runner.invoke(
            app,
            ["init"],
            input="\n".join(
                [
                    "n",
                    "orders-api",
                    "develop",
                    "y",
                    "y",
                    "n",
                    "n",
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
