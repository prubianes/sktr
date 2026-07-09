from __future__ import annotations

from pathlib import Path
import tomllib

from pydantic import BaseModel, Field

DEFAULT_ENABLED_RULES = [
    "new_dependency",
    "large_file",
    "large_function",
    "forbidden_dependency",
]


class ProjectConfig(BaseModel):
    name: str | None = None
    default_base: str = "main"


class GitConfig(BaseModel):
    default_base_branch: str = "main"


class ReviewConfig(BaseModel):
    default_scope: str = "working_tree"


class PluginsConfig(BaseModel):
    analyzers: list[str] = Field(default_factory=lambda: ["sktr-python"])
    rules: list[str] = Field(default_factory=lambda: ["sktr-rules-default"])
    outputs: list[str] = Field(default_factory=lambda: ["terminal", "markdown", "json", "mermaid"])
    ai_providers: list[str] = Field(default_factory=list)


class AIConfig(BaseModel):
    enabled: bool = False
    provider: str | None = None


class ForbiddenDependency(BaseModel):
    source: str
    target: str
    reason: str | None = None


class LargeFileConfig(BaseModel):
    max_changed_lines: int = 300


class LargeFunctionConfig(BaseModel):
    max_lines: int = 80


class RuleConfig(BaseModel):
    enabled: list[str] = Field(default_factory=lambda: DEFAULT_ENABLED_RULES.copy())
    large_file: LargeFileConfig = Field(default_factory=LargeFileConfig)
    large_function: LargeFunctionConfig = Field(default_factory=LargeFunctionConfig)
    forbidden_dependencies: list[ForbiddenDependency] = Field(default_factory=list)


class SKTRConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    rules: RuleConfig = Field(default_factory=RuleConfig)


def load_config(path: Path | None = None) -> SKTRConfig:
    config_path = path or _default_config_path()
    if not config_path.is_file():
        return SKTRConfig()

    if config_path.suffix in {".yaml", ".yml"}:
        data = _load_simple_yaml(config_path)
    else:
        with config_path.open("rb") as file:
            data = tomllib.load(file)

    config = SKTRConfig.model_validate(data)
    project_data = data.get("project")
    if isinstance(project_data, dict) and project_data.get("default_base"):
        config.git.default_base_branch = config.project.default_base
    return config


def _default_config_path() -> Path:
    for name in ("sktr.yml", "sktr.yaml"):
        path = Path(name)
        if path.is_file():
            return path
    return Path("sktr.yml")


def _load_simple_yaml(path: Path) -> dict[str, object]:
    data: dict[str, object] = {"project": {}, "git": {}, "review": {}, "plugins": {}, "ai": {}, "rules": {}}
    section: str | None = None
    subsection: str | None = None
    current_dependency: dict[str, str] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line or line.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            section, value = _yaml_key_value(stripped)
            if section is None:
                continue
            subsection = None
            current_dependency = None
            if value:
                data[section] = value
            else:
                data.setdefault(section, {})
            continue

        if section in {"project", "git", "review", "ai"}:
            key, value = _yaml_key_value(stripped)
            if key is None:
                continue
            section_data = data.setdefault(section, {})
            assert isinstance(section_data, dict)
            section_data[key] = _coerce_scalar(value)
            continue

        if section != "rules":
            if section == "plugins":
                plugins = data.setdefault("plugins", {})
                assert isinstance(plugins, dict)
                if indent == 2:
                    key, value = _yaml_key_value(stripped)
                    if key is None:
                        continue
                    subsection = key
                    if value:
                        plugins[key] = _coerce_scalar(value)
                    else:
                        plugins.setdefault(key, [])
                    continue
                if stripped.startswith("- ") and subsection is not None:
                    values = plugins.setdefault(subsection, [])
                    assert isinstance(values, list)
                    values.append(_coerce_scalar(stripped[2:]))
            continue

        rules = data.setdefault("rules", {})
        assert isinstance(rules, dict)

        if indent == 2:
            key, value = _yaml_key_value(stripped)
            if key is None:
                continue
            subsection = key
            current_dependency = None
            if key in {"enabled", "forbidden_dependencies"}:
                rules.setdefault(key, [])
            elif value:
                rules[key] = _coerce_scalar(value)
            else:
                rules.setdefault(key, {})
            continue

        if subsection == "enabled" and stripped.startswith("- "):
            enabled = rules.setdefault("enabled", [])
            assert isinstance(enabled, list)
            enabled.append(stripped[2:].strip().strip('"').strip("'"))
            continue

        if subsection == "forbidden_dependencies" and stripped.startswith("- "):
            forbidden = rules.setdefault("forbidden_dependencies", [])
            assert isinstance(forbidden, list)
            current_dependency = {}
            forbidden.append(current_dependency)
            key, value = _yaml_key_value(stripped[2:])
            if key:
                current_dependency[key] = value
            continue

        key, value = _yaml_key_value(stripped)
        if not key:
            continue

        if subsection == "forbidden_dependencies" and current_dependency is not None:
            current_dependency[key] = value
        elif subsection in {"large_file", "large_function"}:
            nested = rules.setdefault(subsection, {})
            assert isinstance(nested, dict)
            nested[key] = _coerce_scalar(value)

    return data


def _yaml_key_value(line: str) -> tuple[str | None, str]:
    if ":" not in line:
        return None, ""
    key, value = line.split(":", 1)
    return key.strip(), value.strip().strip('"').strip("'")


def _coerce_scalar(value: str) -> object:
    normalized = value.strip().strip('"').strip("'")
    if normalized == "null":
        return None
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    if normalized.isdigit():
        return int(normalized)
    return normalized
