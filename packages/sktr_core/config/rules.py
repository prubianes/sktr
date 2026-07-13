from __future__ import annotations

from pathlib import Path
import tomllib

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml
from yaml import YAMLError
from sktr_core.model import IssueSeverity

DEFAULT_ENABLED_RULES = [
    "new_dependency",
    "large_file",
    "large_function",
    "forbidden_dependency",
    "dependency_cycle",
    "high_fan_out",
    "public_api_change",
    "missing_tests",
]

DEFAULT_EXCLUDES = [
    "node_modules/",
    ".venv/",
    "venv/",
    "dist/",
    "build/",
    "target/",
    "coverage/",
    "*.min.js",
    "*.generated.*",
]


class ProjectConfig(BaseModel):
    name: str | None = None
    default_base: str = "main"


class GitConfig(BaseModel):
    default_base_branch: str = "main"


class ReviewConfig(BaseModel):
    default_scope: str = "working_tree"
    fail_on: IssueSeverity | None = None
    exclude: list[str] = Field(default_factory=lambda: DEFAULT_EXCLUDES.copy())


class PluginsConfig(BaseModel):
    analyzers: list[str] = Field(
        default_factory=lambda: ["sktr-python", "sktr-javascript-typescript", "sktr-java"]
    )
    rules: list[str] = Field(default_factory=lambda: ["sktr-rules-default"])
    outputs: list[str] = Field(default_factory=lambda: ["terminal", "markdown", "json", "mermaid"])
    ai_providers: list[str] = Field(default_factory=list)


class AIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    provider: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "AIConfig":
        if self.enabled and not self.provider:
            raise ValueError("ai.provider is required when ai.enabled is true")
        if not self.enabled and (self.provider is not None or self.model is not None):
            raise ValueError("ai.provider and ai.model must be omitted when ai.enabled is false")
        return self


class ForbiddenDependency(BaseModel):
    source: str
    target: str
    reason: str | None = None


class LargeFileConfig(BaseModel):
    max_changed_lines: int = 300


class LargeFunctionConfig(BaseModel):
    max_lines: int = 80


class FanOutConfig(BaseModel):
    max_modules: int = 8


class RuleConfig(BaseModel):
    enabled: list[str] = Field(default_factory=lambda: DEFAULT_ENABLED_RULES.copy())
    large_file: LargeFileConfig = Field(default_factory=LargeFileConfig)
    large_function: LargeFunctionConfig = Field(default_factory=LargeFunctionConfig)
    fan_out: FanOutConfig = Field(default_factory=FanOutConfig)
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
        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except YAMLError as error:
            raise ValueError(f"Invalid YAML: {error}") from error
        if loaded is None:
            data: dict[str, object] = {}
        elif isinstance(loaded, dict):
            data = loaded
        else:
            raise ValueError("SKTR configuration must be a YAML mapping")
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
