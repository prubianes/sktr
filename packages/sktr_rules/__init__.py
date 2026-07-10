from sktr_rules.registry import RuleRegistry
from sktr_core.config import RuleConfig
from sktr_core.plugins import PluginMetadata
from sktr_core.version import SKTR_VERSION
from sktr_rules.rules import (
    ForbiddenDependencyRule,
    DependencyCycleRule,
    HighFanOutRule,
    LargeFileChangedRule,
    LargeFunctionDetectedRule,
    NewDependencyDetectedRule,
    MissingTestsRule,
    PublicApiChangedRule,
    default_rules,
    rules_from_config,
)


class DefaultRulesPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="sktr-rules-default",
            version=SKTR_VERSION,
            type="rules",
            description="Default deterministic SKTR rules.",
        )

    def create_rules(self, config: RuleConfig):
        return rules_from_config(config)

__all__ = [
    "DefaultRulesPlugin",
    "ForbiddenDependencyRule",
    "DependencyCycleRule",
    "HighFanOutRule",
    "LargeFileChangedRule",
    "LargeFunctionDetectedRule",
    "NewDependencyDetectedRule",
    "MissingTestsRule",
    "PublicApiChangedRule",
    "RuleRegistry",
    "default_rules",
    "rules_from_config",
]
