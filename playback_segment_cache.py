# -*- coding: utf-8 -*-
"""Published snapshot of ``monitor.segment_parse_cache`` for non-service code.

``RunScript`` entry points must not ``import service`` — loading ``service.py``
runs its main loop. The service calls :func:`publish_parse_cache` whenever the
cache dict is replaced or cleared.
"""

_snapshot = None


def publish_parse_cache(snapshot):
    """Set or clear the mirrored cache (``None`` when invalidated)."""
    global _snapshot
    _snapshot = snapshot


def get_parse_cache_snapshot():
    """Return the last published cache dict or ``None``."""
    return _snapshot
