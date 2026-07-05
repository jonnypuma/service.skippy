# -*- coding: utf-8 -*-
"""Shared player metadata snapshot to avoid duplicate JSON-RPC."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlayerSnapshot:
    player_id: Optional[int] = None
    item: dict = field(default_factory=dict)
    video_path: str = ""
    captured_at: float = 0.0


def set_player_snapshot(monitor, snapshot: Optional[PlayerSnapshot]) -> None:
    if monitor is None:
        return
    monitor._player_snapshot = snapshot


def get_player_snapshot(monitor) -> Optional[PlayerSnapshot]:
    if monitor is None:
        return None
    snap = getattr(monitor, "_player_snapshot", None)
    if isinstance(snap, PlayerSnapshot):
        return snap
    return None


def capture_player_snapshot(player_id, item, video_path) -> PlayerSnapshot:
    return PlayerSnapshot(
        player_id=player_id,
        item=dict(item or {}),
        video_path=str(video_path or ""),
        captured_at=time.time(),
    )


def snapshot_matches_path(snapshot: Optional[PlayerSnapshot], video_path) -> bool:
    if not snapshot or not video_path:
        return False
    if not snapshot.video_path:
        return False
    return snapshot.video_path == video_path
