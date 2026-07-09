from __future__ import annotations

from pathlib import Path

from sktr_core.config import DEFAULT_ENABLED_RULES, load_config


def test_load_config_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "sktr.yaml"
    config_path.write_text(
        "\n".join(
            [
                "project:",
                "  name: sample-app",
                "git:",
                "  default_base_branch: develop",
                "rules:",
                "  enabled:",
                "    - new_dependency",
                "    - large_file",
                "    - large_function",
                "    - forbidden_dependency",
                "  large_file:",
                "    max_changed_lines: 300",
                "  large_function:",
                "    max_lines: 80",
                "  forbidden_dependencies:",
                "    - source: \"controllers\"",
                "      target: \"repositories\"",
                "      reason: \"Controllers should access repositories through services.\"",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.project.name == "sample-app"
    assert config.git.default_base_branch == "develop"
    assert config.rules.enabled == [
        "new_dependency",
        "large_file",
        "large_function",
        "forbidden_dependency",
    ]
    assert config.rules.large_file.max_changed_lines == 300
    assert config.rules.large_function.max_lines == 80
    assert len(config.rules.forbidden_dependencies) == 1
    assert config.rules.forbidden_dependencies[0].source == "controllers"
    assert config.rules.forbidden_dependencies[0].target == "repositories"
    assert (
        config.rules.forbidden_dependencies[0].reason
        == "Controllers should access repositories through services."
    )


def test_missing_config_uses_safe_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.yml")

    assert config.project.name is None
    assert config.git.default_base_branch == "main"
    assert config.rules.enabled == DEFAULT_ENABLED_RULES
    assert config.rules.large_file.max_changed_lines == 300
    assert config.rules.large_function.max_lines == 80
    assert config.rules.forbidden_dependencies == []
