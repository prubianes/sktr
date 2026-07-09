from sktr_rules.registry import RuleRegistry
from sktr_core.config import RuleConfig
from sktr_core.plugins import PluginMetadata
from sktr_rules.rules import (
    ForbiddenDependencyRule,
    LargeFileChangedRule,
    LargeFunctionDetectedRule,
    NewDependencyDetectedRule,
    default_rules,
    rules_from_config,
)


class DefaultRulesPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="sktr-rules-default",
            version="0.10.0",
            type="rules",
            description="Default deterministic SKTR rules.",
        )

    def create_rules(self, config: RuleConfig):
        return rules_from_config(config)

__all__ = [
    "DefaultRulesPlugin",
    "ForbiddenDependencyRule",
    "LargeFileChangedRule",
    "LargeFunctionDetectedRule",
    "NewDependencyDetectedRule",
    "RuleRegistry",
    "default_rules",
    "rules_from_config",
]
