# Changelog

All notable changes to Skippy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.9] - 2026-04-19

### Changed
- **Log detail level → All detail**: High-frequency **SettingsUtils** lines moved off **Normal** — missing-file toast **JSON-RPC** dump, **`get_video_file`** path/toast toggles, **`infer_playback_type`** showtitle line, chapter/EDL **path lists**, **fallback base path**, **safe_file_read** attempt/success, per-atom **XML** / **EDL** parse lines, and related diagnostics. **Normal** keeps segment flow, summaries (e.g. total XML segments), **`🚫` no chapter file**, and **`⚠`/`❌`** read/parse failures. New helper: **`log_service_detail`**.

## [1.1.8] - 2026-04-19

### Fixed
- **Invalid setting type** (remaining): **`_addon_read_setting_raw`** no longer falls through to **`getSettingString`** when **`getSetting`** returns an **empty string** (some builds use that for **false** bools). That fallthrough could still make Kodi log **Invalid setting type** at the C++ layer. **`getSettingString`** is now used only when **`getSetting`** raises.
- **TheMovieDB Helper** API key read: same idea — **`getSetting` first**; if it succeeds (even with an empty value), do not call **`getSettingString`** for that id.

## [1.1.7] - 2026-04-19

### Fixed
- **`remote_segments`**: Restored **`addon_get_bool`** import (removed by mistake when switching remote logging to **`log_remote`**), which caused **`NameError`** during TV online context / lookup.

## [1.1.6] - 2026-04-19

### Added
- **Playback settings snapshot**: On each **new video** (path change while playing), Skippy logs four **`📋 Playback settings snapshot`** lines (setting ids and values, keyword/EDL lists truncated). Shown when verbose logging is **Normal** or **All detail** (not **Errors only** or off). **TMDB API key** is not printed; only **`tv_tmdb_api_key_set=true|false`**.

## [1.1.5] - 2026-04-19

### Added
- **Debug logging → Log detail level** (visible when **Enable verbose logging** is on): **Errors only** (no routine Skippy INFO), **Normal** (service + `[service.skippy - remote]` + SkipDialog + non-spam SegmentItem), **All detail** (restores per-tick **`SegmentItem.is_active` / `get_duration`** and debounce/no-eligible dialog traces).

### Fixed
- **Invalid setting type** noise: **`_addon_read_setting_raw`** now calls **`getSetting` first**, then **`getSettingString`**, so Kodi is less likely to log a C++ exception on every bool read. Remaining **`getSetting`** call sites in **service**, **skipdialog**, and **settings_utils** (`get_user_skip_mode`, **EDL** map) use the safe reader.

## [1.1.4] - 2026-04-19

### Fixed
- **Settings reads on CoreELEC / some Kodi builds**: When `getSettingString` raises **Invalid setting type**, Skippy no longer falls back to **wrong Python defaults** (e.g. TV **use local chapter** forced on and **online lookup** forced off). It now retries via **`getSetting`**. Segment source **priority** strings use the same path. **`rewind_threshold_seconds`** uses safe int parsing instead of **`getSettingInt`** (which could throw the same C++ exception).

## [1.1.3] - 2026-04-19

### Added
- **Episode / movie segment summary** (verbose): one line per parse showing local vs online counts, priority, which list won, and `SegmentItem.source` tags (e.g. `xml` vs `theintrodb`).

### Changed
- **Verbose logging**: Removed per-call logs from **`SegmentItem.is_active`** and **`get_duration`** (they fired every main-loop tick and drowned out useful lines).

## [1.1.2] - 2026-04-05

### Changed
- **Remote API backoff**: Cooldown after errors is now **exponential** per host (`base × 2^n` capped at **3600 s**) until a successful JSON response. **HTTP 429** responses honor integer **`Retry-After`** when present (still capped); other behavior unchanged (**404** does not backoff; **0** disables).

## [1.1.1] - 2026-04-05

### Added
- **Remote API failure cooldown **: **Segment sources → Online APIs (TMDB)** includes **Seconds to pause remote API calls after errors** (default **120**, max **3600**, **0** = off). After a timeout, network error, non-404 HTTP error, or invalid JSON, Skippy skips further requests to that host (TheIntroDB, IntroDB.app, or TMDB) until the window ends; a successful response clears the pause for that host.

## [1.1.0] - 2026-04-05

### Added
- **Save online segments → chapters.xml **: When a sidecar already exists, **Segment Settings** now offers **If chapter XML already exists**: **Skip** (default), **Overwrite (no prompt)**, **Overwrite (ask first)**, or **Merge with existing** (adds non-overlapping online windows; existing atoms win on overlap). **Back up chapter XML before overwrite or merge** copies the file to `*.bck` first (on by default).

## [1.0.38] - 2026-04-05

### Added
- **Per-type online API overlap priority**: **Segment sources** now has **TV episodes** and **Movies** settings for which remote source wins when **TheIntroDB** and **IntroDB.app** both define the same time window (the other source may still add non-overlapping segments). Default remains **TheIntroDB first** (previous behavior).

## [1.0.37] - 2026-04-05

### Added
- **Optional dependency**: `plugin.video.themoviedb.helper` (`optional="true"`) so installs can surface the integration in the addon manager.
- **TheIntroDB / IntroDB**: Parse additional payload keys when present (`credits`, `preview`, `outro`, `commercial`). IntroDB.app accepts list-shaped segment arrays like TheIntroDB.

### Fixed
- **Settings reads**: Centralized safe bool/text helpers in `settings_utils` (`addon_get_bool`, `addon_get_setting_text`); replaced remaining `getSettingBool` / `getSettings().getBool` usage in `service`, `skipdialog`, `segment_item`, and `settings_utils` to reduce CoreELEC **Invalid setting type** log noise.
- **Full skip dialog focus**: Removed `<defaultcontrol>3012</defaultcontrol>` from Full dialog skins (3012 is hidden when the close button is hidden) and aligned Python focus fallback with `_full_skip_focus_id`.

### Changed
- **Save online segments → chapters.xml**: Skips writing a sidecar for `plugin://` URLs, `.strm` paths, and common stream URL schemes (`http(s)`, RTMP, etc.) where a sibling file is not appropriate.

## [1.0.36] - 2026-04-18

### Fixed
- **CoreELEC / `Invalid setting type`**: Additional avoidance of **`getSettingBool`** in **`parse_and_process_segments`** (TV local/online, **skip overlapping**). **`_addon_get_bool`** now prefers **`getSettingString`** when present; **`_get_tmdb_api_key`** and **TheMovieDB Helper** reads use **`getSettingString`** / **`_addon_get_setting_text`** to reduce Kodi’s C++ **EXCEPTION** lines during remote TV context / TMDB paths.

## [1.0.35] - 2026-04-18

### Changed
- **Settings UI**: **TV episodes** and **Movies** segment options are merged into one **Segment sources** category. **Online APIs (TMDB)** — resolve missing ids, API key, TheMovieDB Helper — is **global** at the top (single key for both). **TV episodes** and **Movies** subsections follow with local/online/priority only. Removed duplicate **movie** TMDB setting ids; **`tv_tmdb_*`** ids remain the shared storage keys.

## [1.0.34] - 2026-04-18

### Changed
- **Movies — segment sources** now mirrors **TV episodes** in the settings UI: added **TMDB API** subsection (**resolve missing ids**, **API key**, **use TheMovieDB Helper’s key**) with the same labels as TV. Movie-specific values are used first; empty movie fields fall back to the TV episode TMDB settings (see tooltips).

## [1.0.33] - 2026-04-18

### Fixed
- **Movie TMDB API enrichment**: When Kodi has **IMDb** but no **movie** TMDB id in `uniqueid`, Skippy now resolves **`tmdb_id`** via TMDB v3 **`/find/{imdb_id}?external_source=imdb_id`** before falling back to title search (TheIntroDB prefers `tmdb_id` when both are available).

## [1.0.32] - 2026-04-18

### Added
- **Save online segments to chapters.xml** (Segment Settings): when online lookup returns intro/recap data, optionally write **`filename-chapters.xml`** next to the video if **no** chapter XML exists yet (never overwrites).
- **Movies — segment sources**: separate category with **local chapter/EDL**, **online lookup (TheIntroDB only)**, and **local vs online priority** — mirrors TV behavior but does **not** use IntroDB.app (movies use **`GetMovieDetails`** + optional TMDB API resolution via the same TV TMDB API settings).

## [1.0.31] - 2026-04-18

### Fixed
- **Remote / CoreELEC**: `EXCEPTION: Invalid setting type` could still appear in `kodi.log` during TV online lookup because Kodi logs at the C++ layer when **`getSettingBool`** is used. **`_addon_get_bool`** and **`_rlog`** now read bools **only** via **`getSetting`** string parsing (no `getSettingBool`).

## [1.0.30] - 2026-04-18

### Changed
- **Online TV lookup**: Resolve **TMDB** and **IMDb** the same way as **service.nextonlibrary** before calling **api.themoviedb.org**: **`VideoLibrary.GetTVShowDetails`** → show **`uniqueid.tmdb`** (when the episode row only has TVDB/Sonarr), **`GetEpisodeDetails`** with a **minimal** `uniqueid` query, then **infolabel** fallbacks (`ListItem`/`VideoPlayer` TMDB, `TVShowIMDBNumber` labels). TMDB HTTP enrichment remains only when ids are still missing.

## [1.0.29] - 2026-04-18

### Fixed
- **TMDB enrichment**: Some Kodi/CoreELEC builds throw **Invalid setting type** on `getSettingBool` for newly added settings, which skipped the whole TMDB API block so **`tmdb_id` was never filled** (TheIntroDB stayed unused). Skippy now reads those bools via **`_addon_get_bool`** with a `getSetting` string fallback.

## [1.0.28] - 2026-04-18

### Added
- **Online TV lookup — TMDB API**: TheIntroDB and IntroDB require TMDB/IMDb-style ids ([TheIntroDB docs](https://theintrodb.org/docs), [IntroDB API](https://introdb.app/docs/api)). When Kodi’s `uniqueid` does not have them, Skippy can call **api.themoviedb.org/3** (search TV → `external_ids` → episode `external_ids`). New settings under **TV episodes — segment sources**: optional **TMDB API key**, **use TheMovieDB Helper’s key** when the field is empty (`plugin.video.themoviedb.helper`), and **Resolve missing TMDB/IMDb via TMDB API** (default on when online lookup is enabled). Request URLs log with the key redacted.

## [1.0.27] - 2026-04-18

### Added
- **Online TV lookup**: If `VideoLibrary.GetEpisodeDetails` still fails after the minimal property retry, **Skippy** now tries **`VideoLibrary.GetEpisodes`** with a **`path` contains** filter on the **playback filename** (and the stem), then picks the row whose **`episodeid`** matches the library id from **`Files.GetFileDetails`**. This is **Kodi JSON-RPC path matching** only — it does **not** call TMDB’s web API (unlike **plugin.video.themoviedb.helper**, which searches TMDB by title). TheIntroDB / IntroDB.app still require **TMDB/IMDb ids from Kodi’s `uniqueid`** after the episode row is found.

## [1.0.26] - 2026-04-18

### Fixed
- **Online TV lookup**: On some Kodi/CoreELEC builds, **`tvshowtitle`** is not a valid `VideoLibrary.GetEpisodeDetails` property (`Invalid params` / `array element at index 6`). The request list now uses **`showtitle`** (Kodi’s Episode field for the show name). If the full field list is still rejected, a **second call** uses a minimal set (`season`, `episode`, `uniqueid`, `tvshowid`, `title`, `file`). **Library episodes** with incomplete metadata may **fill only missing** season/episode from **SxxExx in the path** (e.g. `S02E01` in the filename) when Kodi did not return season.

## [1.0.25] - 2026-04-18

### Fixed
- **Online TV lookup**: `VideoLibrary.GetEpisodeDetails` **must not** include **`imdbnumber`** in the `properties` array — it is not a valid Episode field in Kodi’s JSON-RPC enum (`Invalid params` / `array element at index 3`). IMDb/TMDB come from **`uniqueid`**. **`Player.GetItem`** now uses the **same four properties** as the working toast path (`file`, `title`, `showtitle`, `episode`); when the item lacks `type`/`id`/`uniqueid`, the playing path is merged once via **`Files.GetFileDetails` → `GetEpisodeDetails`**.

## [1.0.24] - 2026-04-18

### Fixed
- **Online TV lookup**: `VideoLibrary.GetEpisodeDetails` must use Kodi’s episode field **`tvshowtitle`**, not **`showtitle`**. Requesting `showtitle` can return **empty** `episodedetails`, so the file-path fallback never enriched the item. **`Player.GetItem`** now uses the same **minimal property list** as other working code paths (no `uniqueid` / `imdbnumber` / `tvshowid` on the initial call), which avoids an empty item on some CoreELEC/Kodi builds; episode IDs are still merged via `GetEpisodeDetails`.

## [1.0.23] - 2026-04-18

### Changed
- **Docs / logging**: Clarified that online APIs use **TMDB/IMDb from Kodi’s `uniqueid`** (via `GetEpisodeDetails` / `GetTVShowDetails`); Kodi’s internal episode id is only for library lookup. Verbose log lists `uniqueid` keys; if only **TVDB** is present, the log explains that TheIntroDB/IntroDB need TMDB/IMDb from the scraper.

## [1.0.22] - 2026-04-18

### Fixed
- **Online TV lookup**: `Player.GetItem` often returns an **empty item** for ~0.5–1s right after playback starts; remote lookup now uses **`Files.GetFileDetails` on the playing path** (then `VideoLibrary.GetEpisodeDetails`) when `GetItem` is empty, and **retries `GetItem`** with short delays. This matches Kodi behavior where toast/metadata paths succeed slightly later than the first segment parse.

## [1.0.21] - 2026-04-05

### Added
- **Online lookup debug**: With **verbose logging** enabled, TV remote lookup logs under the tag **`service.skippy - remote`** (playing item, resolved TV context, HTTP/API outcomes, empty responses, merged segment counts). Debug setting tooltip notes how to filter `kodi.log`.

## [1.0.20] - 2026-04-05

### Changed
- **Settings UI**: TV episode segment options (local files, online lookup, priority) are in their own category **“TV episodes — segment sources”** in the add-on settings sidebar, so they are not buried under the playback/dialog section.

## [1.0.19] - 2026-04-05

### Added
- **TV-only segment sources** (Playback behavior): use local `chapters.xml` / `.edl`, optional **online** intro/recap lookup via **TheIntroDB** and **IntroDB.app**, and **prefer local vs online** when both are enabled. Movies continue to use **local files only**.
- Online lookup uses **season/episode from Kodi** (and IDs from the library) for scanned episodes; **SxxExx in the filename/path is only used** when playback is **not** a library episode (e.g. file not in the video library).
- `remote_segment_cache` cleared on new video; episode cache key matches season/episode and IDs.

## [1.0.18] - 2026-04-05

### Fixed
- Skip dialog font colors: `Control.setLabel` arguments now follow Kodi’s order (`textColor`, `disabledColor`, `shadowColor`, `focusedColor`). The previous order put the user’s text color into the **shadow** slot, so the outline tracked the caption color.
- Shadow uses a simple contrast rule: dark halo for light text, soft light halo for dark text.

## [1.0.17] - 2026-04-05

### Added
- **Skip dialog mode**: **Minimal** — small corner chip (plate + single Skip control). Separate corner positions from Full mode. No progress bar, Close button, or icons in Minimal; dismiss with Back/ESC.
- **Skip dialog font color** setting (Playback behavior): named presets with ARGB `optionvalues`; colors applied in Python via `setLabel` because `$INFO` in skin `textcolor` is unreliable for WindowXML dialogs. Full mode: next-jump label control id `3011`; countdown refreshed with playback time.
- `README.md`: **Release notes** section for v1.0.17; folder tree lists `Minimal_Skip_Dialog_*.xml` skins.

### Fixed
- **Playback / segment files**: `get_video_file()` resolves the path when `Player.HasVideo` is true, not only `isPlayingVideo()`, avoiding missed `chapters.xml` / `.edl` during startup/buffering.
- **JSON-RPC `Player.GetItem`**: no longer requires `title` before using the item; file-based inference when metadata is late. Fallback playback type from resolved file path if JSON-RPC fails.
- Minimal skip dialog layout aligned to the 720p skin grid (on-screen placement; narrow chip width and right-corner inset).

### Changed
- Minimal skin templates reduced to plate + button; service patches plate image `3021` and skip button `3012` focus texture only.

## [1.0.3] - 2024-12-31

### Fixed
- Updated fanart file reference from fanart.jpg to fanart.png in addon.xml

## [1.0.2] - 2024-12-31

### Fixed
- Fixed "Unknown addon id 'service.skippy'" error during addon updates in Kodi
- Graceful handling of addon shutdown during repository updates - no more error messages in logs when updating the addon

## [1.0.0] - 2024-12-XX

### Added
- Initial release of Skippy - Video Segment Skipper for Kodi
- Support for Matroska-style `.xml` chapter files and MPlayer-style `.edl` files
- Three skip behaviors per segment type: auto-skip, prompt user, or ignore segments
- Intelligent playback type detection (movies vs. TV episodes) using metadata and filename heuristics
- Customizable skip dialogs with four positioning options (Top Left, Top Right, Bottom Left, Bottom Right)
- Progress bar display showing segment completion progress (toggleable in settings)
- Multiple button focus texture styles (Default, Aqua variants, Blue, Gold, etc.)
- Skip button label formatting options (Skip only, Skip + Type, Skip + Type + Duration)
- Support for nested and overlapping segments with intelligent parent-child relationship handling
- Rewind detection with user-configurable threshold to reset skip prompts on significant rewinds
- Toast notifications when no segment files are found (separate toggles for movies and TV episodes)
- Respects user dismissals - dismissed segments stay dismissed until video replay or major rewind
- Dialog dismissal handling preserves state correctly on pause/resume
- Nested segment dialog management - parent segments can reappear after nested segments end
- Debug logging toggle for detailed segment processing information
- Cross-platform compatibility tested on Android (Nvidia Shield), Linux (CoreELEC), and Windows 11
- Works with MKV and AVI video containers

### Fixed
- Skip dialogs now properly set button focus on initialization, ensuring select/ok/enter works correctly
- Missing segments toast no longer spams when video is paused
- Nested segment dialogs no longer spam after dismissal
- Dismissed segments no longer reappear on playback resume
- Parent segment dialogs correctly reappear after nested segments are handled
- Overlapping segments toast shows only once per video playback session

### Known Issues
- Video files in MP4 containers are currently not supported (Kodi limitation, not addon issue)

