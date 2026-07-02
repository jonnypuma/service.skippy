"""Chapter XML / EDL / embedded chapter parsing and segment source cache."""

import copy
import json
import time
import xml.etree.ElementTree as ET

import xbmc
import xbmcvfs

from playback_segment_cache import publish_parse_cache
from remote_segments import (
    fetch_remote_movie_segments,
    fetch_remote_tv_segments,
)
from segment_editor_parser import dedupe_overlapping_same_label_segments, normalize_matroska_chapter_xml_text
from segment_item import SegmentItem
from service_online_policy import _normalize_segment_source_priority
from service_deferred_remote_probe import (
    pop_deferred_remote_for_playback,
    schedule_deferred_remote_probe,
)
from service_segment_prefetch import schedule_tv_successor_prefetch
from service_sidecar_paths import (
    _chapter_xml_paths_to_try,
    _edl_paths_to_try,
    _sidecar_signature,
    local_chapter_or_edl_file_exists,
)
from settings_utils import (
    addon_get_bool,
    addon_get_setting_text,
    get_addon,
    get_edl_type_map,
    log,
    log_service_detail,
    normalize_label,
)


def _log_seg_detail(msg):
    log_service_detail(msg, tag="segments")


def _invoke_local_to_online_sync(
    path,
    playback_type,
    local_list,
    local_file_found,
    online_lookup_enabled,
    remote_list,
    segment_monitor,
    segment_player,
    on_local_to_online_sync_check,
    addon,
):
    if not on_local_to_online_sync_check or not local_list or not local_file_found:
        return
    try:
        from service_local_to_online_sync import (
            probe_remote_segments_for_sync,
            sync_local_to_online_enabled,
        )
    except Exception as exc:
        log("⚠ Local→online sync import failed: %s" % exc)
        return
    if not sync_local_to_online_enabled(addon):
        return
    if remote_list:
        remote_for_sync = list(remote_list)
    else:
        remote_for_sync = probe_remote_segments_for_sync(
            playback_type, segment_monitor, segment_player
        )
    on_local_to_online_sync_check(
        path, playback_type, local_list, remote_for_sync, segment_monitor
    )


def hms_to_seconds(hms):
    h, m, s = hms.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def safe_file_read(*paths):
    for path in paths:
        if path:
            _log_seg_detail(f"📂 Attempting to read: {path}")
            exists_result = False
            try:
                exists_result = xbmcvfs.exists(path)
                _log_seg_detail(f"📂 xbmcvfs.exists('{path}') = {exists_result}")
            except Exception as ex:
                _log_seg_detail(f"📂 xbmcvfs.exists('{path}') raised: {ex}")
            try:
                f = xbmcvfs.File(path)
                content = f.read()
                f.close()
                if isinstance(content, bytes):
                    content = content.decode("utf-8", errors="replace")
                if content:
                    _log_seg_detail(f"✅ Successfully read file: {path}")
                    return content
                else:
                    if exists_result:
                        log(f"⚠ File exists but read returned empty: {path}")
                    else:
                        _log_seg_detail(
                            f"⚠ File was empty (exists={exists_result}): {path}"
                        )
            except Exception as e:
                log(f"❌ Failed to read {path}: {e}")
    return None


def _source_settings_signature(addon, playback_type):
    if not addon:
        return ()
    if playback_type == "episode":
        keys = (
            "tv_use_local_chapter_edl",
            "tv_use_online_segment_lookup",
            "tv_segment_source_priority",
            "tv_online_merge_priority",
        )
    elif playback_type == "movie":
        keys = (
            "movie_use_local_chapter_edl",
            "movie_use_online_segment_lookup",
            "movie_segment_source_priority",
            "movie_online_merge_priority",
        )
    else:
        keys = ()
    shared = (
        "use_embedded_chapters_fallback",
        "custom_segment_keywords",
        "ignore_internal_edl_actions",
        "edl_action_mapping",
        "save_online_segments_to_chapters_xml",
        "save_online_segments_format",
        "save_online_chapters_existing_policy",
    )
    return tuple((key, addon_get_setting_text(addon, key, "")) for key in keys + shared)


def _clone_segments(segments):
    cloned = []
    for seg in segments or []:
        item = copy.copy(seg)
        item.next_segment_start = None
        item.next_segment_info = None
        cloned.append(item)
    return cloned


def _chapter_window_overlap(s1, e1, s2, e2, tol=1.5):
    return not (e1 + tol <= s2 or e2 + tol <= s1)


def _parse_chapter_xml_string(xml_data):
    """Return SegmentItems from chapter XML text (Matroska-style); empty list on failure."""
    if not xml_data:
        return []
    xml_data = normalize_matroska_chapter_xml_text(xml_data)
    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        log("⚠️ chapter XML parse (sidecar save): %s" % e)
        return []
    out = []
    for atom in root.findall(".//ChapterAtom"):
        raw_label = atom.findtext(".//ChapterDisplay/ChapterString", default="")
        label = normalize_label(raw_label)
        start = atom.findtext("ChapterTimeStart")
        end = atom.findtext("ChapterTimeEnd")
        if start and end:
            try:
                out.append(
                    SegmentItem(
                        hms_to_seconds(start),
                        hms_to_seconds(end),
                        label,
                        source="xml",
                    )
                )
            except Exception:
                continue
    return dedupe_overlapping_same_label_segments(out)


def parse_chapters(video_path, update_monitor=True, segment_monitor=None):
    paths_to_try = _chapter_xml_paths_to_try(video_path)

    if segment_monitor is not None:
        from service_sidecar_probe_cache import resolve_sidecar_paths

        probe = resolve_sidecar_paths(video_path, segment_monitor)
        if probe.probed and not probe.chapter_path:
            if update_monitor:
                segment_monitor.segment_file_found = False
                log("🚫 No chapter XML file found — segment_file_found set to False")
            return None

    _log_seg_detail(f"🔍 Attempting chapter XML paths: {paths_to_try}")

    if update_monitor:
        if segment_monitor is None:
            raise TypeError(
                "parse_chapters(..., update_monitor=True) requires segment_monitor="
            )
        any_xml = False
        seen_exist = set()
        for path in paths_to_try:
            if not path or path in seen_exist:
                continue
            seen_exist.add(path)
            try:
                if xbmcvfs.exists(path):
                    any_xml = True
                    break
            except Exception:
                continue
        segment_monitor.segment_file_found = any_xml
        if not any_xml:
            log("🚫 No chapter XML file found — segment_file_found set to False")
            return None
        _log_seg_detail(
            "✅ Chapter XML sidecar present — segment_file_found set to True"
        )

    seen_paths = set()
    for path in paths_to_try:
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        try:
            exists_result = False
            try:
                exists_result = xbmcvfs.exists(path)
            except Exception:
                pass
            if not exists_result:
                continue
            f = xbmcvfs.File(path)
            xml_data = f.read()
            f.close()
            if isinstance(xml_data, bytes):
                xml_data = xml_data.decode("utf-8", errors="replace")
            if not xml_data or not xml_data.strip():
                continue
            _log_seg_detail(f"✅ Successfully read file: {path}")
        except Exception as e:
            log(f"❌ Failed to read {path}: {e}")
            continue

        xml_norm = normalize_matroska_chapter_xml_text(xml_data)
        try:
            root = ET.fromstring(xml_norm)
        except Exception as e:
            _log_seg_detail(f"❌ XML parse failed for {path}: {e}")
            continue

        result = []
        for atom in root.findall(".//ChapterAtom"):
            raw_label = atom.findtext(".//ChapterDisplay/ChapterString", default="")
            label = normalize_label(raw_label)
            start = atom.findtext("ChapterTimeStart")
            end = atom.findtext("ChapterTimeEnd")
            if start and end:
                result.append(
                    SegmentItem(
                        hms_to_seconds(start),
                        hms_to_seconds(end),
                        label,
                        source="xml",
                    )
                )
                _log_seg_detail(
                    f"📘 Parsed XML segment: {start} → {end} | label='{label}'"
                )
        if result:
            n0 = len(result)
            result = dedupe_overlapping_same_label_segments(result)
            if len(result) != n0:
                log(
                    "✅ Deduped chapter XML segments: %d → %d"
                    % (n0, len(result))
                )
            log(f"✅ Total segments parsed from XML: {len(result)}")
            return result
        _log_seg_detail(
            f"⚠ Chapter XML parsed but no valid segments in {path} — trying next path"
        )

    log("⚠ No chapter XML file produced valid segments")
    return None


def parse_edl(video_path, update_monitor=True, segment_monitor=None):
    paths_to_try = _edl_paths_to_try(video_path)

    if segment_monitor is not None:
        from service_sidecar_probe_cache import resolve_sidecar_paths

        probe = resolve_sidecar_paths(video_path, segment_monitor)
        if probe.probed and not probe.edl_path:
            if update_monitor:
                segment_monitor.segment_file_found = False
                log("🚫 No EDL file found — segment_file_found set to False")
            return []

    _log_seg_detail(f"🔍 Attempting EDL paths: {paths_to_try}")
    edl_data = safe_file_read(*paths_to_try)
    if not edl_data:
        if update_monitor:
            if segment_monitor is None:
                raise TypeError(
                    "parse_edl(..., update_monitor=True) requires segment_monitor="
                )
            segment_monitor.segment_file_found = False
            log("🚫 No EDL file found — segment_file_found set to False")
        return []

    if update_monitor:
        if segment_monitor is None:
            raise TypeError(
                "parse_edl(..., update_monitor=True) requires segment_monitor="
            )
        segment_monitor.segment_file_found = True
        _log_seg_detail("✅ EDL file found — segment_file_found set to True")
    _log_seg_detail(f"🧾 Raw EDL content:\n{edl_data}")

    segments = []
    mapping = get_edl_type_map()
    _ig = get_addon()
    ignore_internal = (
        addon_get_bool(_ig, "ignore_internal_edl_actions", False) if _ig else False
    )
    log(f"🔧 ignore_internal_edl_actions setting: {ignore_internal}")

    try:
        for line in edl_data.splitlines():
            parts = line.strip().split()
            if len(parts) == 3:
                s, e, action = float(parts[0]), float(parts[1]), int(parts[2])
                label = mapping.get(action)

                if ignore_internal and label is None:
                    _log_seg_detail(
                        f"⚠ Unrecognized EDL action type: {action} — not in mapping"
                    )
                    _log_seg_detail(
                        f"🚫 Ignoring unmapped EDL action {action} due to setting"
                    )
                    continue

                label = label or "segment"
                segments.append(SegmentItem(s, e, label, source="edl"))
                _log_seg_detail(
                    f"📗 Parsed EDL line: {s} → {e} | action={action} | label='{label}'"
                )
    except Exception as e:
        log(f"❌ EDL parse failed: {e}")

    log(f"✅ Total segments parsed from EDL: {len(segments)}")
    return segments


def parse_embedded_chapters(segment_player=None):
    """
    Parse chapters embedded in the video file via Kodi's JSON-RPC Player.GetItem chapters property.
    Only returns segments whose label matches custom_segment_keywords.
    """
    pl = segment_player if segment_player is not None else xbmc.Player()
    addon = get_addon()
    if not addon:
        return []

    keywords_raw = addon_get_setting_text(addon, "custom_segment_keywords", "")
    keywords = set(normalize_label(k) for k in keywords_raw.split(",") if k.strip())
    if not keywords:
        _log_seg_detail("📖 Embedded chapters: no custom_segment_keywords configured")
        return []

    try:
        query = {
            "jsonrpc": "2.0",
            "id": "EmbeddedChapters",
            "method": "Player.GetActivePlayers",
        }
        resp = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
        players = resp.get("result", [])
        video_player = next((p for p in players if p.get("type") == "video"), None)
        if not video_player:
            _log_seg_detail("📖 Embedded chapters: no active video player")
            return []
        player_id = video_player.get("playerid")

        query_item = {
            "jsonrpc": "2.0",
            "id": "EmbeddedChaptersItem",
            "method": "Player.GetItem",
            "params": {"playerid": player_id, "properties": ["file"]},
        }
        resp_item = json.loads(xbmc.executeJSONRPC(json.dumps(query_item)))
        _log_seg_detail(
            f"📖 Embedded chapters: Player.GetItem response = {resp_item}"
        )

        query_props = {
            "jsonrpc": "2.0",
            "id": "EmbeddedChaptersProps",
            "method": "Player.GetProperties",
            "params": {"playerid": player_id, "properties": ["chapters"]},
        }
        resp_props = json.loads(xbmc.executeJSONRPC(json.dumps(query_props)))
        _log_seg_detail(
            f"📖 Embedded chapters: Player.GetProperties response = {resp_props}"
        )

        chapters = resp_props.get("result", {}).get("chapters", [])
        if not chapters:
            _log_seg_detail("📖 Embedded chapters: no chapters array in response")
            return []

        log(f"📖 Embedded chapters: found {len(chapters)} chapter(s) in video")
        segments = []
        for i, ch in enumerate(chapters):
            name = ch.get("name", "") or ch.get("label", "") or ""
            start_sec = ch.get("time", 0)
            label = normalize_label(name)

            if label not in keywords:
                _log_seg_detail(
                    f"📖 Embedded chapter '{name}' (label='{label}') not in keywords — skipping"
                )
                continue

            if i + 1 < len(chapters):
                end_sec = chapters[i + 1].get("time", start_sec)
            else:
                try:
                    end_sec = pl.getTotalTime()
                except RuntimeError:
                    end_sec = start_sec + 300

            if end_sec > start_sec:
                segments.append(
                    SegmentItem(start_sec, end_sec, label, source="embedded")
                )
                log(f"📖 Embedded chapter matched: '{name}' [{start_sec}-{end_sec}]")

        if segments:
            log(f"✅ Total embedded chapters matched keywords: {len(segments)}")
        else:
            _log_seg_detail(
                "📖 Embedded chapters: none matched custom_segment_keywords"
            )
        return segments

    except Exception as e:
        log(f"❌ Embedded chapters parse failed: {e}")
        return []


def _parse_source_segments_uncached(
    path,
    playback_type,
    segment_monitor,
    segment_player,
    on_remote_segments_saved,
    on_local_to_online_sync_check=None,
):
    """Read/select segment sources. Per-time filtering/linking remains in parse_and_process_segments.

    Returns (segments, segment_origin) where segment_origin is one of:
    ``remote``, ``local``, ``embedded``, ``none`` — which family of sources won
    priority for the returned list (used by the segment editor when online data
    is active before sidecar save).
    """
    addon = get_addon()
    if not addon:
        return [], "none"

    parsed = []
    segment_origin = "none"

    if playback_type == "episode":
        tv_local = addon_get_bool(addon, "tv_use_local_chapter_edl", True)
        tv_online = addon_get_bool(addon, "tv_use_online_segment_lookup", False)
        priority_raw = addon_get_setting_text(
            addon, "tv_segment_source_priority", "LocalFirst"
        ) or "LocalFirst"
        priority = _normalize_segment_source_priority(priority_raw)

        if not tv_local and not tv_online:
            log("📺 TV episode: local and online segment sources disabled — no segments")
            segment_monitor.segment_file_found = False
            return [], "none"

        local_list = []
        if tv_local:
            pxml = parse_chapters(path, update_monitor=False, segment_monitor=segment_monitor)
            if pxml:
                local_list = pxml
            else:
                local_list = parse_edl(path, update_monitor=False, segment_monitor=segment_monitor)
        local_file_found = (
            local_chapter_or_edl_file_exists(path, segment_monitor)
            if tv_local
            else False
        )

        remote_list = []
        defer_remote = priority == "LocalFirst" and tv_online
        if defer_remote and not local_list:
            remote_list = pop_deferred_remote_for_playback(
                segment_monitor, path, playback_type
            ) or []
        if tv_online and not defer_remote:
            try:
                total_time = segment_player.getTotalTime()
            except RuntimeError:
                total_time = 0
            remote_list = fetch_remote_tv_segments(
                total_time, segment_monitor.remote_segment_cache
            )
            if remote_list:
                on_remote_segments_saved(path, remote_list)
        elif tv_online and defer_remote and not remote_list:
            log(
                "📺 LocalFirst — deferring online segment lookup to background"
            )
            schedule_deferred_remote_probe(
                segment_monitor,
                path,
                playback_type,
                local_list,
                local_file_found,
                segment_player,
            )
        elif tv_online and defer_remote and local_list:
            log(
                "📺 LocalFirst with local sidecar — deferring online segment lookup (dialog path)"
            )
            schedule_deferred_remote_probe(
                segment_monitor,
                path,
                playback_type,
                local_list,
                local_file_found,
                segment_player,
            )

        if priority == "OnlineFirst":
            parsed = remote_list if remote_list else local_list
        else:
            parsed = local_list if local_list else remote_list

        embedded_list = []
        if not parsed and addon_get_bool(addon, "use_embedded_chapters_fallback", True):
            embedded_list = parse_embedded_chapters(segment_player)
            if embedded_list:
                parsed = embedded_list

        segment_monitor.segment_file_found = (
            local_file_found or bool(remote_list) or bool(embedded_list)
        )
        if priority == "OnlineFirst":
            segment_origin = (
                "remote"
                if remote_list
                else "local"
                if local_list
                else ("embedded" if embedded_list else "none")
            )
        else:
            segment_origin = (
                "local"
                if local_list
                else "remote"
                if remote_list
                else ("embedded" if embedded_list else "none")
            )
        _src_tags = sorted({getattr(s, "source", "?") for s in (parsed or [])})
        log(
            "📺 Episode segment summary: local=%d remote=%d embedded=%d priority=%s → using %s (%d segs, sources %s)"
            % (
                len(local_list),
                len(remote_list),
                len(embedded_list),
                priority,
                segment_origin,
                len(parsed or []),
                _src_tags,
            )
        )
        if not defer_remote:
            _invoke_local_to_online_sync(
                path,
                playback_type,
                local_list,
                local_file_found,
                tv_online,
                remote_list,
                segment_monitor,
                segment_player,
                on_local_to_online_sync_check,
                addon,
            )

    elif playback_type == "movie":
        movie_local = addon_get_bool(addon, "movie_use_local_chapter_edl", True)
        movie_online = addon_get_bool(addon, "movie_use_online_segment_lookup", False)
        priority_raw = addon_get_setting_text(
            addon, "movie_segment_source_priority", "LocalFirst"
        ) or "LocalFirst"
        priority = _normalize_segment_source_priority(priority_raw)
        log(
            f"🎬 Movie source settings: local={movie_local}, online={movie_online}, priority={priority}"
        )

        if not movie_local and not movie_online:
            log("🎬 Movie: local and online segment sources disabled — no segments")
            segment_monitor.segment_file_found = False
            return [], "none"

        local_list = []
        if movie_local:
            log(f"🎬 Movie: attempting local chapter/EDL parsing for {path}")
            pxml = parse_chapters(path, update_monitor=False, segment_monitor=segment_monitor)
            if pxml:
                local_list = pxml
                log(f"🎬 Movie: found {len(pxml)} segments from chapters.xml")
            else:
                local_list = parse_edl(path, update_monitor=False, segment_monitor=segment_monitor)
                log(f"🎬 Movie: found {len(local_list)} segments from EDL")
        local_file_found = (
            local_chapter_or_edl_file_exists(path, segment_monitor)
            if movie_local
            else False
        )

        remote_list = []
        movie_defer_remote = priority == "LocalFirst" and movie_online
        if movie_defer_remote and not local_list:
            remote_list = pop_deferred_remote_for_playback(
                segment_monitor, path, playback_type
            ) or []
        if movie_online and not movie_defer_remote:
            try:
                total_time = segment_player.getTotalTime()
            except RuntimeError:
                total_time = 0
            remote_list = fetch_remote_movie_segments(
                total_time, segment_monitor.remote_segment_cache
            )
            if remote_list:
                on_remote_segments_saved(path, remote_list)
        elif movie_online and movie_defer_remote and not remote_list:
            log(
                "🎬 LocalFirst — deferring online segment lookup to background"
            )
            schedule_deferred_remote_probe(
                segment_monitor,
                path,
                playback_type,
                local_list,
                local_file_found,
                segment_player,
            )
        elif movie_online and movie_defer_remote and local_list:
            log(
                "🎬 LocalFirst with local sidecar — deferring online segment lookup (dialog path)"
            )
            schedule_deferred_remote_probe(
                segment_monitor,
                path,
                playback_type,
                local_list,
                local_file_found,
                segment_player,
            )

        if priority == "OnlineFirst":
            parsed = remote_list if remote_list else local_list
        else:
            parsed = local_list if local_list else remote_list

        embedded_list_m = []
        if not parsed and addon_get_bool(addon, "use_embedded_chapters_fallback", True):
            embedded_list_m = parse_embedded_chapters(segment_player)
            if embedded_list_m:
                parsed = embedded_list_m

        segment_monitor.segment_file_found = (
            local_file_found or bool(remote_list) or bool(embedded_list_m)
        )
        if priority == "OnlineFirst":
            segment_origin = (
                "remote"
                if remote_list
                else "local"
                if local_list
                else ("embedded" if embedded_list_m else "none")
            )
        else:
            segment_origin = (
                "local"
                if local_list
                else "remote"
                if remote_list
                else ("embedded" if embedded_list_m else "none")
            )
        _src_tags_m = sorted({getattr(s, "source", "?") for s in (parsed or [])})
        log(
            "🎬 Movie segment summary: local=%d remote=%d embedded=%d priority=%s → using %s (%d segs, sources %s)"
            % (
                len(local_list),
                len(remote_list),
                len(embedded_list_m),
                priority,
                segment_origin,
                len(parsed or []),
                _src_tags_m,
            )
        )
        if not movie_defer_remote:
            _invoke_local_to_online_sync(
                path,
                playback_type,
                local_list,
                local_file_found,
                movie_online,
                remote_list,
                segment_monitor,
                segment_player,
                on_local_to_online_sync_check,
                addon,
            )
    else:
        pxml = parse_chapters(path, segment_monitor=segment_monitor)
        if pxml:
            parsed = pxml
            segment_origin = "local"
        else:
            pedl = parse_edl(path, segment_monitor=segment_monitor)
            if pedl:
                parsed = pedl
                segment_origin = "local"
        if not parsed and addon_get_bool(addon, "use_embedded_chapters_fallback", True):
            parsed = parse_embedded_chapters(segment_player)
            if parsed:
                segment_origin = "embedded"

    return parsed or [], segment_origin


def get_cached_source_segments(
    path,
    playback_type,
    *,
    segment_monitor,
    segment_player,
    on_remote_segments_saved,
    on_local_to_online_sync_check=None,
    sidecar_mtime_check_interval,
):
    addon = get_addon()
    if not addon:
        return []

    now = time.time()
    settings_sig = _source_settings_signature(addon, playback_type)
    cache = segment_monitor.segment_parse_cache

    if (
        cache
        and cache.get("path") == path
        and cache.get("playback_type") == playback_type
        and cache.get("settings_signature") == settings_sig
    ):
        last_check = cache.get("last_sidecar_check", 0)
        if now - last_check < sidecar_mtime_check_interval:
            segment_monitor.segment_file_found = cache.get("segment_file_found", False)
            _log_seg_detail(
                "♻ Using cached source segments (sidecar check interval not reached)"
            )
            return _clone_segments(cache.get("segments", []))

        sidecar_sig = _sidecar_signature(path, segment_monitor)
        cache["last_sidecar_check"] = now
        if sidecar_sig == cache.get("sidecar_signature"):
            segment_monitor.segment_file_found = cache.get("segment_file_found", False)
            _log_seg_detail("♻ Using cached source segments (sidecars unchanged)")
            return _clone_segments(cache.get("segments", []))

        log("🔄 Sidecar file change detected — reparsing segments")

    sidecar_sig_before = _sidecar_signature(path, segment_monitor)
    parsed, segment_origin = _parse_source_segments_uncached(
        path,
        playback_type,
        segment_monitor,
        segment_player,
        on_remote_segments_saved,
        on_local_to_online_sync_check,
    )
    sidecar_sig_after = _sidecar_signature(path, segment_monitor)
    segment_monitor.segment_parse_cache = {
        "path": path,
        "playback_type": playback_type,
        "settings_signature": settings_sig,
        "sidecar_signature": sidecar_sig_after or sidecar_sig_before,
        "last_sidecar_check": now,
        "segment_file_found": segment_monitor.segment_file_found,
        "segments": _clone_segments(parsed),
        "segment_origin": segment_origin,
    }
    publish_parse_cache(segment_monitor.segment_parse_cache)
    try:
        schedule_tv_successor_prefetch(segment_monitor, path, playback_type)
    except Exception as exc:
        log("⚠ TV successor prefetch schedule failed: %s" % exc)
    return _clone_segments(parsed)
