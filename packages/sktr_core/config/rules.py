from __future__ import annotations

from pathlib import Path
import tomllib

from pydantic import BaseModel, Field


class ForbiddenDependency(BaseModel):
    source: str
    target: str


class RuleConfig(BaseModel):
    forbidden_dependencies: list[ForbiddenDependency] = Field(default_factory=list)
    large_file_changed_lines: int = 300
    large_function_lines: int = 80


class SKTRConfig(BaseModel):
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

    return SKTRConfig.model_validate(data)


def _default_config_path() -> Path:
    for name in ("sktr.toml", "sktr.yaml", "sktr.yml"):
        path = Path(name)
        if path.is_file():
            return path
    return Path("sktr.toml")


def _load_simple_yaml(path: Path) -> dict[str, object]:
    data: dict[str, object] = {"rules": {"forbidden_dependencies": []}}
    rules = data["rules"]
    assert isinstance(rules, dict)
    forbidden = rules["forbidden_dependencies"]
    assert isinstance(forbidden, list)

    current_dependency: dict[str, str] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("- "):
            current_dependency = {}
            forbidden.append(current_dependency)
            key, value = _yaml_key_value(line[2:])
            if key:
                current_dependency[key] = value
            continue

        key, value = _yaml_key_value(line)
        if not key:
            continue

        if current_dependency is not None and key in {"source", "target"}:
            current_dependency[key] = value
        elif key in {"large_file_changed_lines", "large_function_lines"}:
            rules[key] = int(value)

    return data


def _yaml_key_value(line: str) -> tuple[str | None, str]:
    if ":" not in line:
        return None, ""
    key, value = line.split(":", 1)
    return key.strip(), value.strip().strip('"').strip("'")
