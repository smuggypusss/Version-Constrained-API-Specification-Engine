from __future__ import annotations

import logging

from src.providers.base import InteractionConstraint, TechnologyPattern

logger = logging.getLogger(__name__)

# Populated at startup — never mutated at runtime
INTERACTION_GRAPH: dict[str, list[InteractionConstraint]] = {}


def load_interaction_graph() -> None:
    """Load all technology interaction constraints into INTERACTION_GRAPH."""
    ...


def get_constraints_for(technology: str) -> list[InteractionConstraint]:
    """Return interaction constraints for a given technology. Returns [] if unknown."""
    ...


def get_active_patterns(technologies: list[str]) -> list[TechnologyPattern]:
    """Return canonical patterns that apply to the detected technology combination."""
    ...
