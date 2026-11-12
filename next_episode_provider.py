# -*- coding: utf-8 -*-
"""The Up Next integration: what a video add-on says about the episode that follows.

Video add-ons (Netflix, Jellyfin, Emby, ...) that support the Up Next add-on announce the
next episode with ``JSONRPC.NotifyAll``: sender ``<add-on id>.SIGNAL``, message ``upnext_data``,
data a one item list that holds the payload as JSON, base64 (or hex) encoded. Skippy listens to
the same signal, so those add-ons work with it too, also for videos that are not in the library.

The payload carries ``current_episode`` and ``next_episode`` (Kodi style episode details with an
``art`` dict) and how to start the next one: ``play_url`` (opened directly) or ``play_info`` (sent
back to the add-on as ``upnextprovider.SIGNAL`` / ``<add-on id>_play_action``). Optional
``notification_time`` (seconds before the end) or ``notification_offset`` (seconds into the
episode) say when the add-on wants the prompt.

Nothing here talks to Kodi.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, replace
from typing import Any, Optional

from next_episode_lookup import SOURCE_PROVIDER, pick_thumb
from remote_http import parse_int

SIGNAL_SUFFIX = ".SIGNAL"
# Where the add-on is told to start the next episode when it gave ``play_info`` and no ``play_url``.
REPLY_SENDER = "upnextprovider"
REPLY_SUFFIX = "_play_action"
# A payload bigger than this is not an episode announcement.
MAX_ENCODED_CHARS = 262144


@dataclass(frozen=True)
class ProviderData:
    """What the add-on said about the video that was playing when it said it."""

    provider: str
    next_item: dict
    # Seconds before the end / seconds into the episode where the add-on wants the prompt.
    notification_time: Optional[float] = None
    notification_offset: Optional[float] = None
    # The playing file when the signal arrived, and when (``time.monotonic``).
    video: str = ""
    received_mono: float = 0.0

    def stamped(self, video, received_mono) -> "ProviderData":
        return replace(self, video=str(video or ""), received_mono=float(received_mono))

    def prompt_start(self, total_time) -> Optional[float]:
        """Seconds into the episode where the add-on wants the prompt, or None."""
        if self.notification_offset is not None:
            return self.notification_offset
        try:
            total = float(total_time)
        except (TypeError, ValueError):
            return None
        if self.notification_time is not None and total > 0:
            return total - self.notification_time
        return None


def provider_id(sender) -> str:
    """The add-on id behind a ``<id>.SIGNAL`` sender, or an empty string."""
    text = str(sender or "").strip()
    if not text.endswith(SIGNAL_SUFFIX):
        return ""
    return text[: -len(SIGNAL_SUFFIX)].strip()


def decode_notification(data) -> Optional[dict]:
    """The payload dict inside a notification's ``data`` string, or None when it is not one."""
    try:
        outer = json.loads(data) if isinstance(data, (str, bytes, bytearray)) else data
    except ValueError:
        return None
    encoded = outer[0] if isinstance(outer, list) and outer else outer
    if isinstance(encoded, dict):
        return encoded or None
    if not isinstance(encoded, str) or not encoded or len(encoded) > MAX_ENCODED_CHARS:
        return None
    # Up Next accepts hex and base64; a text that reads as both is whichever one holds JSON.
    for decode in (binascii.unhexlify, base64.b64decode):
        try:
            payload = json.loads(decode(encoded))
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _seconds(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def parse_payload(provider, payload) -> Optional[ProviderData]:
    """Turn a decoded payload into what the prompt needs, or None when it has no usable next episode."""
    if not provider or not isinstance(payload, dict):
        return None
    nxt = payload.get("next_episode")
    if not isinstance(nxt, dict):
        return None
    play_url = _text(payload.get("play_url"))
    play_info = payload.get("play_info")
    if not play_url and not play_info:
        return None
    item = {
        "source": SOURCE_PROVIDER,
        "provider": provider,
        "play_url": play_url,
        "play_info": play_info,
        "title": _text(nxt.get("title")),
        "showtitle": _text(nxt.get("showtitle")),
        "season": parse_int(nxt.get("season")),
        "episode": parse_int(nxt.get("episode")),
        "file": "",
        "thumb": pick_thumb(nxt.get("art")),
    }
    return ProviderData(
        provider=provider,
        next_item=item,
        notification_time=_seconds(payload.get("notification_time")),
        notification_offset=_seconds(payload.get("notification_offset")),
    )


def encode_reply(play_info: Any) -> str:
    """``play_info`` the way Up Next sends it back: JSON, base64 encoded (``{}`` when empty)."""
    return base64.b64encode(json.dumps(play_info or {}).encode("utf-8")).decode("ascii")


def reply_message(provider) -> str:
    return "%s%s" % (provider, REPLY_SUFFIX)
