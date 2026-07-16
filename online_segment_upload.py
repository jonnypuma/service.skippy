# -*- coding: utf-8 -*-
"""Submit segment timestamps to TheIntroDB.org and IntroDB.app from the Segment Editor."""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from contextlib import closing
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import xbmc
import xbmcaddon
import xbmcvfs

from remote_segments import (
    ADDON_ID,
    build_upload_context,
    get_enriched_item_for_path,
    normalize_imdb_id,
    playback_duration_seconds_for_upload,
)
from segment_editor_parser import seconds_to_hms
from skippy_editor_modal_skin import show_editor_ok

THEINTRODB_SUBMIT_URL = "https://api.theintrodb.org/v3/submit"
INTRODB_SUBMIT_URL = "https://api.introdb.app/submit"

TARGET_BOTH = "Both"
TARGET_THEINTRODB = "TheIntroDB"
TARGET_INTRODB_APP = "IntroDBApp"

_HISTORY_VERSION = 1
_MAX_HISTORY_ENTRIES_PER_API = 4000
_POST_TIMEOUT = 20
_MEDIA_END_TOLERANCE_SEC = 3.0
_INTRO_RECAP_START_AT_BEGINNING_SEC = 0.5


def _up_log_err(msg: str) -> None:
    try:
        safe = (
            unicodedata.normalize("NFKD", str(msg))
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    except Exception:
        safe = str(msg)
    xbmc.log("[service.skippy - online upload] %s" % safe, xbmc.LOGERROR)


def _up_log_info(msg: str) -> None:
    try:
        safe = (
            unicodedata.normalize("NFKD", str(msg))
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    except Exception:
        safe = str(msg)
    xbmc.log("[service.skippy - online upload] %s" % safe, xbmc.LOGINFO)


# Longer phrases first (substring safety). Value is TheIntroDB segment name.
_PHRASE_MAP = (
    ("previously on", "recap"),
    ("last time on", "recap"),
    ("next time on", "preview"),
    ("sneak peek", "preview"),
    ("cold open", "intro"),
    ("last on", "recap"),
    ("next on", "preview"),
)

_TOKEN_TIDB = {
    "intro": "intro",
    "opening": "intro",
    "title": "intro",
    "titles": "intro",
    "beginning": "intro",
    "teaser": "preview",
    "recap": "recap",
    "previously": "recap",
    "credits": "credits",
    "outro": "credits",
    "closing": "credits",
    "ending": "credits",
    "preview": "preview",
}

_TOKEN_SKIP = frozenset(
    {
        "commercial",
        "commercials",
        "ad",
        "ads",
        "sponsor",
        "sponsors",
        "segment",
        "unknown",
        "interruption",
        # Library-style labels that must not be mapped to intro/credits/outro online:
        "prologue",
        "epilogue",
        "main",
    }
)


def _addon_version():
    try:
        return xbmcaddon.Addon(ADDON_ID).getAddonInfo("version") or "0"
    except Exception:
        return "0"


def _http_post_json(url: str, headers: dict, payload: dict) -> tuple[int, dict | None, str | None]:
    """POST JSON; returns (http_code, parsed_json_or_none, error_text)."""
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "%s/%s" % (ADDON_ID, _addon_version()))
    req.add_header("Accept", "application/json")
    for k, v in headers.items():
        if v is not None and str(v).strip():
            req.add_header(k, str(v).strip())
    try:
        with closing(urlopen(req, timeout=_POST_TIMEOUT)) as response:
            body = response.read().decode("utf-8", errors="replace")
            code = getattr(response, "status", None) or getattr(response, "code", 200)
            try:
                parsed = json.loads(body) if body.strip() else None
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = None
            return int(code), parsed, None if parsed is not None else (body[:500] or None)
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        parsed = None
        if body.strip():
            try:
                parsed = json.loads(body)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return exc.code, parsed, body[:800] if body else str(exc)
    except URLError as exc:
        return 0, None, str(exc.reason)
    except Exception as exc:
        return 0, None, str(exc)


def classify_segment_label_normalized(norm: str) -> tuple[str | None, str | None] | None:
    """
    Map a normalized label to (TheIntroDB segment, IntroDB segment).
    TheIntroDB allows intro / recap / credits / preview; IntroDB.app only
    intro / recap / outro (credits → outro; preview is not accepted).
    Returns None if this segment should not be uploaded (ads, unknown, etc.).
    """
    if not norm:
        return None
    n = norm.strip()
    for phrase, tidb in _PHRASE_MAP:
        if phrase in n:
            return tidb, _introdb_for_tidb(tidb)
    toks = [t.strip().lower() for t in re.split(r"[^\w]+", n) if t.strip()]
    if any(t in _TOKEN_SKIP for t in toks):
        return None
    for tok in toks:
        if tok in _TOKEN_TIDB:
            tidb = _TOKEN_TIDB[tok]
            return tidb, _introdb_for_tidb(tidb)
    return None


def _introdb_for_tidb(tidb: str) -> str | None:
    """Map TheIntroDB segment name to IntroDB.app ``segment_type``, or None to skip."""
    if tidb == "intro":
        return "intro"
    if tidb == "recap":
        return "recap"
    if tidb == "credits":
        return "outro"
    if tidb == "preview":
        return None
    return None


def remote_payload_label_to_online_bucket(label: str) -> str | None:
    """
    Map an API payload key / remote ``SegmentItem`` label to the same canonical
    four-bucket model as :func:`classify_segment_label_normalized` (intro / recap
    / credits / preview). IntroDB.app uses ``outro`` for end-of-show windows;
    that maps to **credits** for matching local ``credits`` / ``outro`` / etc.
    """
    lab = (label or "").strip().lower()
    if lab in ("intro", "recap", "credits", "preview"):
        return lab
    if lab == "outro":
        return "credits"
    return None


def local_label_to_online_bucket(norm: str) -> str | None:
    """Normalized local label -> canonical bucket, or None (e.g. main, ads)."""
    m = classify_segment_label_normalized(norm or "")
    return m[0] if m else None


def _media_key(ctx: dict) -> str:
    if ctx.get("type") == "movie":
        return "m|tmdb=%s|imdb=%s" % (ctx.get("tmdb_id"), ctx.get("imdb_id") or "")
    return "tv|tmdb=%s|showimdb=%s|s=%s|e=%s" % (
        ctx.get("tmdb_id"),
        ctx.get("show_imdb_id") or "",
        ctx.get("season"),
        ctx.get("episode"),
    )


def _fingerprint(api: str, media_key: str, tidb_seg: str, start: float, end: float) -> str:
    s = "%s|%s|%s|%.3f|%.3f" % (api, media_key, tidb_seg, start, end)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _fp_short(fp: str) -> str:
    """First 12 hex chars of fingerprint for logs (full fp stays in history file)."""
    return (fp or "")[:12]


def _history_path():
    try:
        prof = xbmcaddon.Addon(ADDON_ID).getAddonInfo("profile")
        return os.path.join(xbmcvfs.translatePath(prof), "online_upload_submissions.json")
    except Exception:
        return None


def _load_history() -> dict:
    path = _history_path()
    if not path or not os.path.isfile(path):
        return {"v": _HISTORY_VERSION, "theintrodb": [], "introdb": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"v": _HISTORY_VERSION, "theintrodb": [], "introdb": []}
        data.setdefault("v", _HISTORY_VERSION)
        data.setdefault("theintrodb", [])
        data.setdefault("introdb", [])
        if not isinstance(data["theintrodb"], list):
            data["theintrodb"] = []
        if not isinstance(data["introdb"], list):
            data["introdb"] = []
        return data
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {"v": _HISTORY_VERSION, "theintrodb": [], "introdb": []}


def _save_history(data: dict) -> None:
    path = _history_path()
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        pass
    for key in ("theintrodb", "introdb"):
        lst = data.get(key) or []
        if len(lst) > _MAX_HISTORY_ENTRIES_PER_API:
            data[key] = lst[-_MAX_HISTORY_ENTRIES_PER_API :]
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as exc:
        _up_log_err("online upload: could not save history: %s" % exc)


def load_upload_submission_history() -> dict:
    """Return upload dedupe history from the addon profile (empty buckets if missing)."""
    return _load_history()


def merge_upload_submission_history(incoming: dict) -> tuple[int, int]:
    """Union fingerprint lists into profile history. Returns (added, already_present)."""
    data = _load_history()
    added = 0
    already = 0
    for bucket in ("theintrodb", "introdb"):
        inc = (incoming or {}).get(bucket) or []
        if not isinstance(inc, list):
            continue
        lst = data.setdefault(bucket, [])
        if not isinstance(lst, list):
            lst = []
            data[bucket] = lst
        seen = set(lst)
        for fp in inc:
            if not isinstance(fp, str):
                continue
            fp = fp.strip()
            if not fp:
                continue
            if fp in seen:
                already += 1
                continue
            lst.append(fp)
            seen.add(fp)
            added += 1
    _save_history(data)
    return added, already


def _history_contains(api_bucket: str, fp: str) -> bool:
    data = _load_history()
    lst = data.get(api_bucket) or []
    return fp in lst


def _history_record(api_bucket: str, fp: str) -> None:
    data = _load_history()
    lst = data.setdefault(api_bucket, [])
    if fp in lst:
        return
    lst.append(fp)
    _save_history(data)


def _validate_theintrodb_times(
    segment: str,
    start: float,
    end: float,
    *,
    end_at_media_end: bool = False,
) -> str | None:
    if start < 0 or start > 21600:
        return "start must be within 0-21600 s"
    if not end_at_media_end:
        if end < 0 or end > 21600:
            return "end must be within 0-21600 s"
    dur = end - start if not end_at_media_end else None
    if segment in ("intro", "recap"):
        if dur is None:
            return "%s end time is required" % segment
        if not (5 <= dur <= (200 if segment == "intro" else 1200)):
            return "%s duration must be within API limits (see TheIntroDB docs)" % segment
    elif segment in ("credits", "preview"):
        if end_at_media_end:
            if start > 0 and start < 5:
                return segment + " start must be >= 5 s (or 0 for no segment)"
            return None
        if dur is None or not (5 <= dur <= 1800):
            return segment + " duration must be 5-1800 s when an end time is set"
    return None


def _near_media_end(end_sec: float, duration_sec) -> bool:
    if duration_sec is None:
        return False
    try:
        return float(end_sec) >= float(duration_sec) - _MEDIA_END_TOLERANCE_SEC
    except (TypeError, ValueError):
        return False


def _build_theintrodb_submit_times(
    segment: str,
    start_sec: float,
    end_sec: float,
    duration_sec,
) -> tuple[object, object, bool]:
    """
    Return (start_ms, end_ms, end_at_media_end) for v3 POST.

    ``None`` values are encoded as JSON null (intro/recap start at beginning;
    credits/preview through end of media).
    """
    start = float(start_sec)
    end = float(end_sec)
    end_at_media = segment in ("credits", "preview") and _near_media_end(
        end, duration_sec
    )

    if segment in ("intro", "recap") and start <= _INTRO_RECAP_START_AT_BEGINNING_SEC:
        start_ms = None
    else:
        start_ms = int(round(start * 1000.0))

    if end_at_media:
        end_ms = None
    else:
        end_ms = int(round(end * 1000.0))

    return start_ms, end_ms, end_at_media


def _theintrodb_submit_accepted(parsed: dict | None) -> bool:
    if not isinstance(parsed, dict):
        return False
    subs = parsed.get("submissions")
    if isinstance(subs, list) and subs:
        return True
    legacy = parsed.get("submission")
    if isinstance(legacy, dict):
        return True
    return parsed.get("ok") is True and bool(subs or legacy)


def _submit_theintrodb(
    ctx: dict,
    tidb_segment: str,
    start_sec: float,
    end_sec: float,
    api_key: str,
) -> tuple[bool, str]:
    """
    POST /v3/submit (flat JSON: ``tmdb_id``, ``type``, ``segment``, times — **not** the nested
    ``intro``/``recap``/… arrays from GET /media). Sends ``start_ms``/``end_ms`` as integers or
    JSON ``null`` (intro/recap from beginning; credits/preview through end-of-media). Optional
    ``video_duration_ms`` aligns submissions with release cuts when playback/library duration is known.
    """
    key = (api_key or "").strip()
    if not key:
        _up_log_err("TheIntroDB submit: API key not set")
        return False, _translate(39028)

    if tidb_segment not in ("intro", "recap", "credits", "preview"):
        _up_log_err("TheIntroDB submit: bad segment %r" % tidb_segment)
        return False, _translate(39047)

    tmdb_id = ctx.get("tmdb_id")
    try:
        tmdb_int = int(tmdb_id) if tmdb_id is not None else None
    except (TypeError, ValueError):
        tmdb_int = None
    if tmdb_int is None or not (1 <= tmdb_int <= 10_000_000):
        _up_log_err(
            "TheIntroDB submit: invalid tmdb_id %r (ctx type=%s)"
            % (tmdb_id, ctx.get("type"))
        )
        return False, _translate(39044)

    api_type = "movie" if ctx.get("type") == "movie" else "tv"
    duration_sec = ctx.get("playback_duration_seconds")
    start_ms, end_ms, end_at_media = _build_theintrodb_submit_times(
        tidb_segment, float(start_sec), float(end_sec), duration_sec
    )
    body: dict = {
        "tmdb_id": tmdb_int,
        "type": api_type,
        "segment": tidb_segment,
        "start_ms": start_ms,
        "end_ms": end_ms,
    }
    if api_type == "tv":
        try:
            body["season"] = int(ctx.get("season"))
            body["episode"] = int(ctx.get("episode"))
        except (TypeError, ValueError):
            _up_log_err(
                "TheIntroDB submit: bad TV season/episode %r/%r"
                % (ctx.get("season"), ctx.get("episode"))
            )
            return False, _translate(39043) + "\n\n" + "invalid season or episode"

    vd_sec = ctx.get("playback_duration_seconds")
    if vd_sec is not None:
        try:
            vd_ms = int(round(float(vd_sec) * 1000.0))
            if 300_000 <= vd_ms <= 21_600_000:
                body["video_duration_ms"] = vd_ms
        except (TypeError, ValueError):
            pass

    imdb_opt = None
    if ctx.get("type") == "movie":
        imdb_opt = ctx.get("imdb_id")
    else:
        imdb_opt = ctx.get("imdb_id") or ctx.get("show_imdb_id")
    imdb_opt = normalize_imdb_id(imdb_opt)
    if imdb_opt:
        body["imdb_id"] = imdb_opt

    err = _validate_theintrodb_times(
        tidb_segment,
        float(start_sec),
        float(end_sec),
        end_at_media_end=end_at_media,
    )
    if err:
        _up_log_err(
            "TheIntroDB submit: local validation failed segment=%s %s-%s: %s"
            % (tidb_segment, start_sec, end_sec, err)
        )
        return False, _translate(39043) + "\n\n" + err

    vd_log = (
        body.get("video_duration_ms")
        if body.get("video_duration_ms") is not None
        else "omit"
    )
    tv_log = ""
    if api_type == "tv":
        tv_log = " S=%s E=%s" % (body.get("season"), body.get("episode"))
    _up_log_info(
        "TheIntroDB v3 submit: POST segment=%s tmdb=%s type=%s%s start_ms=%s end_ms=%s video_duration_ms=%s imdb=%s"
        % (
            tidb_segment,
            tmdb_int,
            api_type,
            tv_log,
            body["start_ms"],
            body["end_ms"],
            vd_log,
            "yes" if body.get("imdb_id") else "no",
        )
    )

    code, parsed, raw_err = _http_post_json(
        THEINTRODB_SUBMIT_URL,
        {"Authorization": "Bearer %s" % key},
        body,
    )
    if code == 200 and _theintrodb_submit_accepted(parsed):
        subs = (parsed or {}).get("submissions")
        legacy = (parsed or {}).get("submission")
        if isinstance(subs, list) and subs:
            n = len(subs)
            sid = subs[0].get("id") if isinstance(subs[0], dict) else None
            if sid:
                _up_log_info(
                    "TheIntroDB v3 submit OK: submissions=%s first_id=%s"
                    % (n, sid)
                )
            else:
                _up_log_info(
                    "TheIntroDB v3 submit OK: submissions=%s (no id in first row)"
                    % n
                )
            return True, "ok"
        if isinstance(legacy, dict):
            sid = legacy.get("id")
            _up_log_info(
                "TheIntroDB submit OK (legacy v2-shape response): submission id=%s"
                % (sid or "?")
            )
            return True, "ok"
        _up_log_info("TheIntroDB v3 submit OK (HTTP 200, ok=true)")
        return True, "ok"
    if code == 200:
        detail = _detail_from_parsed(parsed, raw_err)
        base = _translate(39041)
        msg = base + ("\n\n" + detail if detail else "")
        _up_log_err(
            "TheIntroDB submit: HTTP 200 but no submissions in response (segment=%s tmdb=%s): %s"
            % (tidb_segment, tmdb_int, detail or raw_err or "")
        )
        return False, msg
    msg = _submit_http_user_message("theintrodb", code, parsed, raw_err)
    _up_log_err(
        "TheIntroDB submit failed HTTP %s segment=%s tmdb=%s: %s"
        % (code, tidb_segment, tmdb_int, msg.replace("\n", " | "))
    )
    return False, msg


def _submit_introdb_app(
    ctx: dict,
    idb_segment: str,
    start_sec: float,
    end_sec: float,
    api_key: str,
) -> tuple[bool, str]:
    """
    IntroDB.app POST /submit with X-API-Key: numeric ``start_sec`` / ``end_sec`` (integers).
    ``segment_type`` is only intro, recap, or outro (credits → outro; preview is not sent).
    """
    key = (api_key or "").strip()
    if not key:
        _up_log_err("IntroDB.app submit: API key not set")
        return False, _translate(39029)

    if idb_segment not in ("intro", "recap", "outro"):
        _up_log_err("IntroDB.app submit: bad segment %r" % idb_segment)
        return False, _translate(39046)

    imdb = None
    if ctx.get("type") == "movie":
        imdb = normalize_imdb_id(ctx.get("imdb_id"))
    else:
        imdb = normalize_imdb_id(ctx.get("show_imdb_id") or ctx.get("imdb_id"))
    if not imdb:
        _up_log_err(
            "IntroDB.app submit: no imdb in ctx (type=%s)" % ctx.get("type")
        )
        return False, _translate(39045)

    body: dict = {
        "imdb_id": imdb,
        "segment_type": idb_segment,
        "start_sec": int(round(float(start_sec))),
        "end_sec": int(round(float(end_sec))),
    }
    if ctx.get("type") == "tv":
        body["season"] = int(ctx.get("season"))
        body["episode"] = int(ctx.get("episode"))

    code, parsed, raw_err = _http_post_json(
        INTRODB_SUBMIT_URL,
        {"X-API-Key": key},
        body,
    )
    if 200 <= code < 300:
        return True, "ok"
    msg = _submit_http_user_message("introdb", code, parsed, raw_err)
    _up_log_err(
        "IntroDB.app submit failed HTTP %s imdb=%s segment=%s: %s"
        % (code, imdb, idb_segment, msg.replace("\n", " | "))
    )
    return False, msg


def _translate(id_: int) -> str:
    try:
        return xbmcaddon.Addon(ADDON_ID).getLocalizedString(id_)
    except Exception:
        return ""


def _detail_from_parsed(parsed: dict | None, raw_err: str | None) -> str:
    if isinstance(parsed, dict):
        for k in ("error", "message", "detail", "errors"):
            v = parsed.get(k)
            if v is None:
                continue
            if isinstance(v, (list, dict)):
                try:
                    v = json.dumps(v, ensure_ascii=False)
                except (TypeError, ValueError):
                    v = str(v)
            s = str(v).strip()
            if s:
                return s[:400]
    if raw_err and str(raw_err).strip():
        return str(raw_err).strip()[:400]
    return ""


def _upload_time_range(start: float, end: float) -> str:
    return "%s – %s" % (seconds_to_hms(float(start)), seconds_to_hms(float(end)))


def _upload_result_sections(
    title_ok: str,
    title_skip: str,
    title_err: str,
    lines_ok: list,
    lines_skip: list,
    lines_err: list,
    more_ellipsis: str,
    none_placeholder: str,
    *,
    max_lines: int = 22,
) -> str:
    """Build scrollable summary for the Segment Editor upload results modal."""

    def _one_section(title: str, n: int, lines: list) -> str:
        out = ["%s (%d)" % (title, n)]
        if not lines:
            out.append("• %s" % none_placeholder)
        else:
            head = lines[:max_lines]
            out.extend("• %s" % x for x in head)
            if len(lines) > max_lines:
                try:
                    tail = more_ellipsis % (len(lines) - max_lines,)
                except (TypeError, ValueError):
                    tail = "+%d more" % (len(lines) - max_lines)
                out.append("• %s" % tail)
        return "\n".join(out)

    return "\n\n".join(
        (
            _one_section(title_ok, len(lines_ok), lines_ok),
            _one_section(title_skip, len(lines_skip), lines_skip),
            _one_section(title_err, len(lines_err), lines_err),
        )
    )


def _submit_http_user_message(
    api: str, code: int, parsed: dict | None, raw_err: str | None
) -> str:
    """User-facing explanation for a failed HTTP response."""
    detail = _detail_from_parsed(parsed, raw_err)
    if code in (401, 403):
        head = _translate(39030) if api == "theintrodb" else _translate(39031)
    elif code == 429:
        head = _translate(39032)
    elif code == 0:
        head = _translate(39033)
    elif code in (301, 302, 303, 307, 308):
        head = _translate(39033)
    elif 400 <= code < 500:
        head = _translate(39041) if api == "theintrodb" else _translate(39042)
    else:
        head = _translate(39034) % (code if code else "?")
    if detail and detail.lower() not in head.lower():
        return head + "\n\n" + detail
    return head


def segment_has_pending_upload(
    seg,
    target: str,
    media_key: str,
    t_db_key: str,
    idb_key: str,
) -> bool:
    """True if ``seg`` would be POSTed to at least one API (not history-skipped)."""
    label_norm = getattr(seg, "segment_type_label", "") or ""
    mapped = classify_segment_label_normalized(label_norm)
    if mapped is None:
        return False
    tidb_seg, idb_seg = mapped
    start = float(seg.start_seconds)
    end = float(seg.end_seconds)
    do_tidb = target in (TARGET_BOTH, TARGET_THEINTRODB) and (t_db_key or "").strip()
    do_idb = target in (TARGET_BOTH, TARGET_INTRODB_APP) and (idb_key or "").strip()
    if do_tidb:
        fp = _fingerprint("theintrodb", media_key, tidb_seg, start, end)
        if not _history_contains("theintrodb", fp):
            return True
    if do_idb and idb_seg is not None:
        fp_i = _fingerprint("introdb", media_key, idb_seg, start, end)
        if not _history_contains("introdb", fp_i):
            return True
    return False


def upload_segments_subset(
    video_path,
    segments,
    target: str,
    *,
    show_empty_message: bool = True,
    show_result: bool = True,
) -> None:
    """
    Upload ``segments`` (SegmentItem list) for ``video_path``.
    ``target`` is TARGET_* constant matching settings stored values.
    """
    addon = xbmcaddon.Addon(ADDON_ID)
    if not segments:
        if show_empty_message:
            show_editor_ok(
                _translate(39013),
                _translate(39014),
            )
        _up_log_info("Upload dismissed: no segments to upload")
        return

    item = get_enriched_item_for_path(video_path)
    ctx = build_upload_context(item)
    if not ctx:
        if show_result:
            show_editor_ok(
                _translate(39013),
                _translate(39016),
            )
        _up_log_err("Upload aborted: could not build library/TMDB context for path")
        return

    dur_sec = playback_duration_seconds_for_upload(item, video_path)
    if dur_sec is not None and float(dur_sec) >= 300.0:
        ctx["playback_duration_seconds"] = float(dur_sec)

    media_key = _media_key(ctx)
    t_db_key = (addon.getSetting("online_upload_theintrodb_api_key") or "").strip()
    idb_key = (addon.getSetting("online_upload_introdb_api_key") or "").strip()

    do_tidb = target in (TARGET_BOTH, TARGET_THEINTRODB)
    do_idb = target in (TARGET_BOTH, TARGET_INTRODB_APP)
    need_tidb = do_tidb
    need_idb = do_idb
    if do_tidb and not t_db_key:
        do_tidb = False
    if do_idb and not idb_key:
        do_idb = False
    if not do_tidb and not do_idb:
        if show_result:
            body_parts = []
            if need_tidb and not t_db_key:
                body_parts.append(_translate(39028))
            if need_idb and not idb_key:
                body_parts.append(_translate(39029))
            body = "\n\n".join(body_parts) if body_parts else _translate(39015)
            show_editor_ok(
                _translate(39037),
                body,
            )
        _up_log_err("Upload aborted (missing API keys)")
        return

    lines_ok = []
    lines_skip = []
    lines_err = []
    lbl_tidb = _translate(39054)
    lbl_idb = _translate(39055)
    if not (lbl_tidb or "").strip():
        lbl_tidb = "TheIntroDB.org"
    if not (lbl_idb or "").strip():
        lbl_idb = "IntroDB.app"

    for seg in segments:
        label_norm = getattr(seg, "segment_type_label", "") or ""
        mapped = classify_segment_label_normalized(label_norm)
        tr = _upload_time_range(seg.start_seconds, seg.end_seconds)
        if mapped is None:
            raw = getattr(seg, "raw_label", label_norm)
            lines_skip.append(
                "%s — %s — %s"
                % (raw, tr, _translate(39020))
            )
            _up_log_info(
                "skip (not uploaded: label not mapped to online types): raw=%r norm=%r %s"
                % (raw, label_norm, media_key)
            )
            continue
        tidb_seg, idb_seg = mapped
        start = float(seg.start_seconds)
        end = float(seg.end_seconds)
        raw = getattr(seg, "raw_label", label_norm)

        if do_tidb:
            fp = _fingerprint("theintrodb", media_key, tidb_seg, start, end)
            if _history_contains("theintrodb", fp):
                lines_skip.append(
                    "%s — %s (%s) — %s — %s"
                    % (lbl_tidb, raw, tidb_seg, tr, _translate(39021))
                )
                _up_log_info(
                    "skip TheIntroDB (already in local submit history): %r segment=%s %.3f-%.3f fp=%s %s"
                    % (raw, tidb_seg, start, end, _fp_short(fp), media_key)
                )
            else:
                ok, err = _submit_theintrodb(ctx, tidb_seg, start, end, t_db_key)
                if ok:
                    _history_record("theintrodb", fp)
                    lines_ok.append(
                        "%s — %s (%s) — %s"
                        % (lbl_tidb, raw, tidb_seg, tr)
                    )
                    _up_log_info(
                        "ok TheIntroDB: %r segment=%s %.3f-%.3f fp=%s %s"
                        % (raw, tidb_seg, start, end, _fp_short(fp), media_key)
                    )
                else:
                    lines_err.append(
                        "%s — %s (%s) — %s — %s"
                        % (lbl_tidb, raw, tidb_seg, tr, err)
                    )
            xbmc.sleep(200)

        if do_idb:
            if idb_seg is None:
                lines_skip.append(
                    "%s — %s (%s) — %s — %s"
                    % (lbl_idb, raw, tidb_seg, tr, _translate(39056))
                )
                _up_log_info(
                    "skip IntroDB.app (segment type not accepted): %r tidb=%s %s"
                    % (raw, tidb_seg, media_key)
                )
            else:
                fp_i = _fingerprint("introdb", media_key, idb_seg, start, end)
                if _history_contains("introdb", fp_i):
                    lines_skip.append(
                        "%s — %s (%s) — %s — %s"
                        % (lbl_idb, raw, idb_seg, tr, _translate(39021))
                    )
                    _up_log_info(
                        "skip IntroDB.app (already in local submit history): %r segment_type=%s %.3f-%.3f fp=%s %s"
                        % (raw, idb_seg, start, end, _fp_short(fp_i), media_key)
                    )
                else:
                    ok, err = _submit_introdb_app(ctx, idb_seg, start, end, idb_key)
                    if ok:
                        _history_record("introdb", fp_i)
                        lines_ok.append(
                            "%s — %s (%s) — %s"
                            % (lbl_idb, raw, idb_seg, tr)
                        )
                        _up_log_info(
                            "ok IntroDB.app: %r segment_type=%s %.3f-%.3f fp=%s %s"
                            % (raw, idb_seg, start, end, _fp_short(fp_i), media_key)
                        )
                    else:
                        lines_err.append(
                            "%s — %s (%s) — %s — %s"
                            % (lbl_idb, raw, idb_seg, tr, err)
                        )
            xbmc.sleep(200)

    if not show_result:
        _up_log_info(
            "Upload finished (no modal): ok=%d skip=%d err=%d — %s"
            % (len(lines_ok), len(lines_skip), len(lines_err), media_key)
        )
        return

    more_el = _translate(39048)
    if not (more_el or "").strip():
        more_el = "… and %d more (not shown)."
    none_ph = _translate(39049)
    if not (none_ph or "").strip():
        none_ph = "(none)"
    detail = _upload_result_sections(
        _translate(39022),
        _translate(39023),
        _translate(39024),
        lines_ok,
        lines_skip,
        lines_err,
        more_el,
        none_ph,
    )
    show_editor_ok(_translate(39013), detail)
    _up_log_info(
        "Upload finished: ok=%d skip=%d err=%d — %s"
        % (len(lines_ok), len(lines_skip), len(lines_err), media_key)
    )
    if lines_ok:
        _up_log_info("ok lines: %s" % " | ".join(lines_ok[:20]))
        if len(lines_ok) > 20:
            _up_log_info("ok lines: ... +%d more" % (len(lines_ok) - 20))
    if lines_skip:
        _up_log_info("skip lines: %s" % " | ".join(lines_skip[:20]))
        if len(lines_skip) > 20:
            _up_log_info("skip lines: ... +%d more" % (len(lines_skip) - 20))
    if lines_err:
        _up_log_info("err lines: %s" % " | ".join(lines_err[:12]))
        if len(lines_err) > 12:
            _up_log_info("err lines: ... +%d more" % (len(lines_err) - 12))


def upload_all_segments(video_path, segments, target: str) -> None:
    """Upload every uploadable segment from ``segments`` (Segment Editor)."""
    upload_segments_subset(
        video_path,
        segments,
        target,
        show_empty_message=True,
        show_result=True,
    )
