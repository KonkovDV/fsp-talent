"""All item families and the per-specialization test blueprint."""
from __future__ import annotations

from app.items import Family
from app.items.families import algorithms, concepts, embedded, javascript, ml, network, python_code, security, sql_query

FAMILIES: dict[str, Family] = {f.id: f for f in [
    python_code.FAMILY, sql_query.FAMILY, algorithms.OPS, algorithms.GRAPH, javascript.FAMILY, security.FAMILY,
    network.FAMILY, ml.FAMILY, embedded.FAMILY, concepts.BANK, concepts.HTTP_FAMILY,
]}

# Target share of each topic in a session. "concept" is also hard-capped at 30 % (CONCEPT_MAX_SHARE).
BLUEPRINTS: dict[str, dict[str, float]] = {
    "backend":   {"python": 0.30, "sql": 0.25, "algorithms": 0.20, "network": 0.05, "concept": 0.20},
    "fullstack": {"javascript": 0.25, "python": 0.15, "sql": 0.20, "algorithms": 0.20, "concept": 0.20},
    "frontend":  {"javascript": 0.50, "algorithms": 0.30, "concept": 0.20},
    "mobile":    {"javascript": 0.35, "algorithms": 0.30, "embedded": 0.15, "concept": 0.20},
    "ml":        {"ml": 0.40, "python": 0.20, "sql": 0.15, "algorithms": 0.10, "concept": 0.15},
    "devops":    {"network": 0.35, "security": 0.20, "python": 0.20, "algorithms": 0.05, "concept": 0.20},
    "security":  {"security": 0.40, "network": 0.20, "python": 0.15, "embedded": 0.05, "concept": 0.20},
    "embedded":  {"embedded": 0.45, "algorithms": 0.25, "python": 0.10, "network": 0.05, "concept": 0.15},
}
SPECIALIZATIONS = tuple(BLUEPRINTS)
CONCEPT_MAX_SHARE = 0.30


def families_for(spec: str) -> list[Family]:
    """Only the specialization's own families: a backend test never mixes in embedded items."""
    topics = BLUEPRINTS[spec]
    return [f for f in FAMILIES.values() if spec in f.specs and f.topic in topics]
