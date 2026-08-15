# -*- coding: utf-8 -*-
"""Per-title playback session fields on PlayerMonitor."""

from __future__ import annotations

import threading
import time
from typing import Any

from playback_segment_cache import publish_parse_cache
from prefetch_segment_cache import clear_prefetch_segment_cache
from service_loop_per_show import clear_playback_override_key
from service_loop_skip import clear_last_skipped_segment
from service_segment_processed_cache import clear_segment_processed_cache
from service_segment_prefetch import clear_tv_prefetch_thread_state
from service_sidecar_probe_cache import clear_sidecar_probe_cache
from service_skip_seek_property import clear_skippy_skipping


def init_playback_session(monitor: Any) -> None:
    """Populate skip/parse/toast fields on a new PlayerMonitor."""
    monitor.segment_file_found = False
    monitor.prompted = set()
    monitor.recently_dismissed = set()
    monitor.current_segments = []
    monitor.last_video = None
    monitor.last_time = 0
    monitor.shown_missing_file_toast = False
    monitor.playback_ready = False
    monitor.playback_ready_time = 0
    monitor.play_start_time = 0
    monitor.last_toast_time = 0
    monitor.last_toast_for_file = {}
    monitor.sidecar_probe_cache = {}
    monitor.toast_overlap_shown = False
    monitor.skipped_to_nested_segment = {}
    monitor._last_log_state = {}
    monitor.cleared_parent_dismissals = set()
    monitor.remote_segment_cache = {}
    monitor.segment_parse_cache = None
    monitor.segment_processed_cache = None
    monitor.nested_parent_map = {}
    monitor.online_segments_toast_shown_for_path = None
    monitor.per_show_override_identity = None
    monitor._home_window = None
    monitor.skip_dialog_modal_active = False
    monitor.skippy_skipping_since = None
    monitor.last_skipped_seg_id = None
    monitor.last_skipped_seg_bounds = None
    monitor.last_ask_seg_id = None
    monitor.last_ask_mono = None
    monitor.overlap_editor_opened_for_path = None
    monitor.online_sidecar_save_prompt_suppressed_path = None
    monitor.local_to_online_sync_suppressed_path = None
    clear_prefetch_segment_cache()
    monitor.prefetch_tv_scheduled_path = None
    monitor.prefetch_tv_lock = threading.Lock()
    monitor.prefetch_tv_result = None
    monitor.deferred_remote_probe_lock = threading.Lock()


def reset_playback_session(monitor: Any, *, clear_deferred, log_prefix: str, log_fn) -> None:
    """Clear per-title caches (new video, replay, etc.)."""
    monitor.shown_missing_file_toast = False
    monitor.prompted.clear()
    monitor.recently_dismissed.clear()
    monitor.segment_parse_cache = None
    clear_segment_processed_cache(monitor)
    publish_parse_cache(None)
    monitor.cleared_parent_dismissals.clear()
    monitor.playback_ready = False
    monitor.play_start_time = time.time()
    monitor.last_time = 0
    monitor.last_toast_time = 0
    monitor.skipped_to_nested_segment.clear()
    clear_last_skipped_segment(monitor)
    monitor.last_ask_seg_id = None
    monitor.last_ask_mono = None
    monitor._last_log_state.clear()
    monitor.overlap_editor_opened_for_path = None
    monitor.online_sidecar_save_prompt_suppressed_path = None
    monitor.local_to_online_sync_suppressed_path = None
    monitor.prefetch_tv_scheduled_path = None
    monitor.nested_parent_map = {}
    monitor.online_segments_toast_shown_for_path = None
    clear_playback_override_key(monitor)
    monitor._home_window = None
    clear_tv_prefetch_thread_state(monitor)
    clear_deferred(monitor)
    clear_sidecar_probe_cache(monitor)
    clear_skippy_skipping(monitor)
    log_fn(
        "%s state cleared - recently_dismissed now has %d items"
        % (log_prefix, len(monitor.recently_dismissed))
    )
