from __future__ import annotations

from collections.abc import Iterable

from sktr_core.plugins import Rule


class RuleRegistry:
    def __init__(self, rules: Iterable[Rule] | None = None) -> None:
        self._rules: dict[str, Rule] = {}
        for rule in rules or []:
            self.register(rule)

    def register(self, rule: Rule) -> None:
        self._rules[rule.id] = rule

    def all(self) -> list[Rule]:
        return list(self._rules.values())
