# -*- coding: utf-8 -*-
"""Remote intro/recap lookup facade (TheIntroDB + IntroDB.app + TMDB).

Implementation lives in remote_http, remote_tmdb, remote_library, remote_lookup.
"""
from remote_http import (  # noqa: F401
    ADDON_ID,
    INTRODB_SEGMENTS_URL,
    ONLINE_MERGE_INTRODB_FIRST,
    ONLINE_MERGE_THEINTRODB_FIRST,
    REMOTE_LOOKUP_TIMEOUT,
    REMOTE_SEGMENT_PAYLOAD_KEYS,
    THEINTRODB_BASE_URL,
    TMDB_API3_BASE,
    fetch_remote_json,
    jsonrpc,
    normalize_imdb_id,
    normalize_numeric_id,
    parse_int,
)
from remote_library import (  # noqa: F401
    build_movie_context,
    build_tv_episode_context,
    build_upload_context,
    episode_runtime_seconds_for_prefetch,
    get_active_video_player_id,
    get_enriched_item_for_path,
    get_enriched_playing_item,
    get_show_imdb_id,
    library_title_identity,
    paths_refer_to_same_video,
    playback_duration_seconds_for_upload,
    resolve_tv_library_successor_episode_item,
)
from remote_lookup import (  # noqa: F401
    build_tv_cache_key,
    fetch_introdb_segments,
    fetch_remote_movie_segments,
    fetch_remote_tv_segments,
    fetch_remote_tv_segments_core,
    fetch_theintrodb_segments,
    merge_remote_segments,
    normalize_remote_segment_window,
    normalize_skip_window,
)
from remote_tmdb import (  # noqa: F401
    _get_tmdb_api_key,
)
