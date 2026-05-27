"""Narrative generation package — per-level template registry + builders."""
from .templates import (
    LEVEL_CONFIGS,
    LEVELS,
    TEMPLATE_VERSION,
    build_metrics_for_level,
    build_narrative,
    metrics_hash,
)

__all__ = [
    'LEVEL_CONFIGS',
    'LEVELS',
    'TEMPLATE_VERSION',
    'build_metrics_for_level',
    'build_narrative',
    'metrics_hash',
]
