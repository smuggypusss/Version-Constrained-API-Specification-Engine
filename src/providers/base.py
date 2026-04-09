from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ResolutionTier(int, Enum):
    LOCK_FILE = 1
    DECLARATION = 2
    CONTAINERIZED = 3


class Ecosystem(str, Enum):
    PYTHON = "python"
    NODE = "node"
    RUST = "rust"
    JAVA = "java"
    GO = "go"
    RUBY = "ruby"


class SourceReliability(int, Enum):
    OFFICIAL_DOCS = 4
    GITHUB_RELEASE = 3
    PACKAGE_REGISTRY = 2
    COMMUNITY = 1


@dataclass(frozen=True)
class RawDependency:
    name: str
    version_constraint: str
    ecosystem: Ecosystem


@dataclass(frozen=True)
class ResolvedDependency:
    name: str
    version: str
    ecosystem: Ecosystem
    resolution_tier: ResolutionTier


@dataclass(frozen=True)
class DocSource:
    url: str
    reliability: SourceReliability
    package: str
    version: str


@dataclass(frozen=True)
class ApiParameter:
    name: str
    type_hint: str
    required: bool
    description: str


@dataclass(frozen=True)
class ApiSignature:
    qualified_name: str
    parameters: tuple[ApiParameter, ...]
    return_type: str
    available_since: str
    deprecated: bool = False
    deprecation_note: str = ""


@dataclass(frozen=True)
class ApiIndex:
    package: str
    version: str
    signatures: tuple[ApiSignature, ...]


@dataclass(frozen=True)
class InteractionConstraint:
    rule_name: str
    allowed_in: tuple[str, ...]
    disallowed_in: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class TechnologyPattern:
    technologies: tuple[str, ...]
    description: str
    correct_pattern: str
    incorrect_pattern: str
    constraint: InteractionConstraint


@dataclass
class ValidationViolation:
    rule_name: str
    description: str
    line_number: int | None
    severity: str


@dataclass
class ValidationResult:
    passed: bool
    violations: list[ValidationViolation] = field(default_factory=list)


class EcosystemProvider(ABC):

    @abstractmethod
    def detect(self, repo_path: Path) -> bool:
        """Return True if this provider applies to the repository at repo_path."""

    @abstractmethod
    def parse_dependencies(self, repo_path: Path) -> list[RawDependency]:
        """Extract dependency names and version constraints from manifest files."""

    @abstractmethod
    async def resolve_versions(self, deps: list[RawDependency]) -> list[ResolvedDependency]:
        """Resolve exact compatible versions using registry APIs."""

    @abstractmethod
    def documentation_sources(self, package: str, version: str) -> list[DocSource]:
        """Return ranked documentation source URLs for the given package version."""

    @abstractmethod
    def api_index(self, package: str, version: str) -> ApiIndex:
        """Return structured API signatures and parameters for the given package version."""
