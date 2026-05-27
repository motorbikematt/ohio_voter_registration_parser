"""Narrative generation package — per-level template registry + builders."""
from .templates import (
    LEVEL_CONFIGS,
    LEVELS,
    TEMPLATE_VERSION,
    build_metrics_for_level,
    build_narrative,
    metrics_hash,
)
from .llm_enricher import (
    ENRICHER_VERSION,
    captain_hash,
    enrich_one,
    enrich_batch,
    write_captain_narrative,
    is_captain_fresh,
)

__all__ = [
    'LEVEL_CONFIGS',
    'LEVELS',
    'TEMPLATE_VERSION',
    'build_metrics_for_level',
    'build_narrative',
    'metrics_hash',
    'ENRICHER_VERSION',
    'captain_hash',
    'enrich_one',
    'enrich_batch',
    'write_captain_narrative',
    'is_captain_fresh',
]
