"""Type aliases and vendor protocol definitions for configuration tooling."""

from __future__ import annotations

from typing import IO, Protocol, TypedDict

# Config dictionaries that originate from TOML/YAML parsing.
type ConfigMap = dict[str, object]


class AnalyzerFinding(TypedDict, total=False):
    """Summary of a single analyzer observation."""

    file_path: str
    description: str
    severity: str
    recommendation: str


class DependencySummary(TypedDict, total=False):
    """Aggregated dependency analysis metadata."""

    manager: str
    packages: list[str]
    conflicts: list[str]
    migration_needed: bool


class TemplateMergePlan(TypedDict, total=False):
    """High-level description of template-driven merge operations."""

    file_path: str
    section: str
    description: str


class TomlLoader(Protocol):
    """Subset of TOML loader functionality relied upon in the core modules."""

    def load(self, __fp: IO[bytes], /) -> ConfigMap: ...

    def loads(self, __s: str, /) -> ConfigMap: ...


class TomlWriter(Protocol):
    """Subset of TOML writer functionality (tomli_w)."""

    def dumps(self, __obj: ConfigMap, /) -> str: ...


class YamlModule(Protocol):
    """Subset of PyYAML functions required by Secuority."""

    def safe_load(self, __stream: str | IO[str], /) -> object: ...

    def dump(
        self,
        __data: object,
        /,
        *,
        default_flow_style: bool = ...,
        sort_keys: bool = ...,
        allow_unicode: bool = ...,
    ) -> str: ...
