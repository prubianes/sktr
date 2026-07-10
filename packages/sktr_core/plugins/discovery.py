from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any

from pydantic import BaseModel

PLUGIN_GROUPS = {
    "analyzer": "sktr.analyzers",
    "rules": "sktr.rules",
    "output": "sktr.outputs",
    "ai_provider": "sktr.ai_providers",
}


class PluginMetadata(BaseModel):
    name: str
    version: str
    type: str
    description: str


@dataclass(frozen=True)
class PluginRecord:
    entry_point_name: str
    group: str
    metadata: PluginMetadata
    plugin: Any


@dataclass(frozen=True)
class PluginLoadError:
    entry_point_name: str
    group: str
    message: str


class PluginRegistry:
    def __init__(self, records: list[PluginRecord], load_errors: list[PluginLoadError] | None = None) -> None:
        self.records = records
        self.load_errors = load_errors or []

    @classmethod
    def discover(cls) -> "PluginRegistry":
        records: list[PluginRecord] = []
        load_errors: list[PluginLoadError] = []
        discovered = entry_points()
        for plugin_type, group in PLUGIN_GROUPS.items():
            for entry_point in discovered.select(group=group):
                try:
                    plugin = entry_point.load()()
                    metadata = plugin.metadata()
                except Exception as error:
                    load_errors.append(
                        PluginLoadError(
                            entry_point_name=entry_point.name,
                            group=group,
                            message=str(error) or error.__class__.__name__,
                        )
                    )
                    continue
                if metadata.type != plugin_type:
                    metadata = metadata.model_copy(update={"type": plugin_type})
                records.append(
                    PluginRecord(
                        entry_point_name=entry_point.name,
                        group=group,
                        metadata=metadata,
                        plugin=plugin,
                    )
                )
        return cls(records, load_errors)

    def by_type(self, plugin_type: str) -> list[PluginRecord]:
        return [record for record in self.records if record.metadata.type == plugin_type]

    def get(self, plugin_type: str, name: str) -> PluginRecord | None:
        for record in self.by_type(plugin_type):
            if record.metadata.name == name or record.entry_point_name == name:
                return record
        return None

    def require(self, plugin_type: str, name: str) -> PluginRecord:
        record = self.get(plugin_type, name)
        if record is None:
            raise MissingPluginError(plugin_type=plugin_type, name=name)
        return record

    def validate_configured(self, configured: dict[str, list[str]]) -> list[str]:
        errors = [
            f"Plugin {error.entry_point_name} could not be loaded from {error.group}: {error.message}"
            for error in self.load_errors
        ]
        for plugin_type, names in configured.items():
            for name in names:
                record = self.get(plugin_type, name)
                if record is None:
                    errors.append(f"Missing {plugin_type} plugin: {name}")
                    continue
                try:
                    self._validate_capability(record)
                except AttributeError as error:
                    errors.append(f"Plugin {record.metadata.name} is missing capability: {error}")
        return errors

    def _validate_capability(self, record: PluginRecord) -> None:
        if record.metadata.type == "analyzer":
            getattr(record.plugin, "create_analyzer")
        elif record.metadata.type == "rules":
            getattr(record.plugin, "create_rules")
        elif record.metadata.type == "output":
            getattr(record.plugin, "create_output")
        elif record.metadata.type == "ai_provider":
            getattr(record.plugin, "create_ai_provider")


class MissingPluginError(Exception):
    def __init__(self, *, plugin_type: str, name: str) -> None:
        super().__init__(f"Missing {plugin_type} plugin: {name}")
        self.plugin_type = plugin_type
        self.name = name
