from __future__ import annotations

import json
import logging
from pathlib import Path

from vcase.providers.base import InteractionConstraint, TechnologyPattern

logger = logging.getLogger(__name__)

# Populated at startup — never mutated at runtime
INTERACTION_GRAPH: dict[str, list[InteractionConstraint]] = {}


def load_interaction_graph() -> None:
    """Load all technology interaction constraints into INTERACTION_GRAPH."""
    INTERACTION_GRAPH.clear()
    rules_path = Path(__file__).resolve().parent.parent / "validator" / "specs" / "architecture_rules.json"
    if not rules_path.exists():
        logger.warning(f"Architecture rules file not found at {rules_path}")
        return

    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules", [])
        for rule in rules:
            constraint = InteractionConstraint(
                rule_name=rule["id"],
                allowed_in=(),
                disallowed_in=tuple(rule["forbidden_contexts"]),
                description=rule["description"]
            )
            
            # Map this constraint to related technologies
            techs = []
            text_to_check = (rule["id"] + " " + rule["description"] + " " + str(rule.get("forbidden_call", {}))).lower()
            for tech in ["fastapi", "temporalio", "litellm", "langfuse", "sqlalchemy"]:
                if tech in text_to_check:
                    techs.append(tech)
            
            # Fallbacks
            if "temporal" in text_to_check and "temporalio" not in techs:
                techs.append("temporalio")
            if "sql" in text_to_check and "sqlalchemy" not in techs:
                techs.append("sqlalchemy")
                
            if not techs:
                techs = ["fastapi"]
                
            for tech in techs:
                if tech not in INTERACTION_GRAPH:
                    INTERACTION_GRAPH[tech] = []
                INTERACTION_GRAPH[tech].append(constraint)
                
        logger.info(f"Successfully loaded {len(rules)} rules into interaction graph.")
    except Exception as e:
        logger.error(f"Failed to load interaction graph: {e}")


def get_constraints_for(technology: str) -> list[InteractionConstraint]:
    """Return interaction constraints for a given technology. Returns [] if unknown."""
    if not INTERACTION_GRAPH:
        load_interaction_graph()
    return INTERACTION_GRAPH.get(technology.lower(), [])


def get_active_patterns(technologies: list[str]) -> list[TechnologyPattern]:
    """Return canonical patterns that apply to the detected technology combination."""
    if not INTERACTION_GRAPH:
        load_interaction_graph()

    patterns = []
    techs_set = {t.lower() for t in technologies}

    # Normalize some names
    if "temporal" in techs_set:
        techs_set.add("temporalio")

    # FastAPI + Temporal Pattern
    if "fastapi" in techs_set and "temporalio" in techs_set:
        c = next((x for x in INTERACTION_GRAPH.get("temporalio", []) if x.rule_name == "NO_WORKFLOW_IN_FASTAPI_ROUTE"), None)
        if not c:
            c = next((x for x in INTERACTION_GRAPH.get("fastapi", []) if x.rule_name == "NO_WORKFLOW_IN_FASTAPI_ROUTE"), None)
        if c:
            patterns.append(TechnologyPattern(
                technologies=("fastapi", "temporalio"),
                description="Temporal workflows cannot be executed directly inside FastAPI route handlers.",
                correct_pattern="await client.start_workflow(MyWorkflow.run, ...)",
                incorrect_pattern="@app.post('/workflow')\nasync def handler():\n    await MyWorkflow.run(...) # Directly calling run inside handler",
                constraint=c
            ))

    # LiteLLM + Langfuse Pattern
    if "litellm" in techs_set and "langfuse" in techs_set:
        c = next((x for x in INTERACTION_GRAPH.get("litellm", []) if x.rule_name == "NO_SYNC_LLM_IN_ASYNC_ROUTE"), None)
        if not c:
            c = InteractionConstraint(
                rule_name="NO_SEQUENTIAL_LANGFUSE_LOG",
                allowed_in=("callbacks",),
                disallowed_in=("sequential_flow",),
                description="Langfuse integration with LiteLLM should use callback handlers instead of sequential manual log calls."
            )
        patterns.append(TechnologyPattern(
            technologies=("litellm", "langfuse"),
            description="Langfuse integration with LiteLLM should use callback handlers instead of sequential manual log calls.",
            correct_pattern="litellm.success_callback = ['langfuse']\nawait litellm.acompletion(model='gpt-4', messages=...)",
            incorrect_pattern="res = await litellm.acompletion(...)\nlangfuse.log(res) # Sequential log call instead of callbacks",
            constraint=c
        ))

    # FastAPI + SQLAlchemy Pattern
    if "fastapi" in techs_set and "sqlalchemy" in techs_set:
        c = InteractionConstraint(
            rule_name="NO_MANUAL_DB_SESSION_IN_HANDLER",
            allowed_in=("Depends",),
            disallowed_in=("handler_body",),
            description="SQLAlchemy sessions should not be instantiated manually inside FastAPI route handlers. Use dependency injection."
        )
        patterns.append(TechnologyPattern(
            technologies=("fastapi", "sqlalchemy"),
            description="SQLAlchemy sessions should not be instantiated manually inside FastAPI route handlers.",
            correct_pattern="@router.post('/items')\ndef create_item(db: Session = Depends(get_db)):\n    ...",
            incorrect_pattern="@router.post('/items')\ndef create_item():\n    db = Session() # Manual instantiation inside handler",
            constraint=c
        ))

    return patterns
