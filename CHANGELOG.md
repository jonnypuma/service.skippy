# Changelog

## [3.3.3] - 2026-05-22

### Changed
- **Backup settings** (`settings_backup.py`): Folder picker uses **`files`** (all Kodi file sources) instead of **`local`**, matching **Restore**. Destination paths use vfs-safe joining; JSON read/write tries the raw Kodi path first then **`translatePath`**, so backups to **`smb://`**, **`nfs://`**, etc. are more reliable.

## [3.3.2] - 2026-05-22

### Changed
- **TheIntroDB API v2 → v3** (sunset deadline **2027-01-18**): **GET** `https://api.theintrodb.org/v3/media` with optional **`duration_ms`** from Kodi playback duration; **POST** `…/v3/submit` with optional **`video_duration_ms`** when library or current playback yields a duration ≥300 s (per API constraints). Parses **`submissions`** array on success; still accepts legacy v2 **`submission`** object when present. **Credits/preview** entries with **`end_ms: null`** map to **end-of-media** using known runtime (`remote_segments.py`, `online_segment_upload.py`). See **`openapi_theintrodb_v3.yaml`** in-repo for the OpenAPI spec.

### Fixed
- **Addon settings GUI** (`resources/settings.xml`, `tools/gen_settings_v1.py`): Regenerated definitions use **`short_empty_elements=False`** so empty-string defaults serialize as ``<default></default>`` rather than self-closing tags (better compatibility with some Kodi XML parsers). If the addon settings pane is still blank or glitched after updating, quit Kodi and delete **`userdata/addon_data/service.skippy/settings.xml`**, then reopen settings.

### Notes
- V2 **`/v2/media`** and **`/v2/submit`** are unchanged in older releases only; upgrading **Skippy ≥3.3.2** is required before removal of v2 endpoints.

## [3.3.1] - 2026-05-22

### Changed
- **`.chapters/` sidecar fallback** (`service_sidecar_paths.py`): After basename-matched files **beside** the video, discovery tries **`video_dir/.chapters/<basename>`** with the same Matroska-style chapter suffixes and **`.edl`** matches the Jellyfin Kodi chapters/edl exporter layout. Used by playback parse cache, online sidecar logic, **Segment Editor** (load/save/backup/delete), and **Segment Marker** target paths (`segment_editor_parser.py`, `segment_marker.py`).

### Notes
- **Skin vs skip/editor colours**: **Estuary** honours Skippy’s **`Window.Property(skip_dialog_text_color)`** / bundled **`colors/defaults.xml`** for bundled WindowXML. Some **third-party skins** (reports: **Arctic Fuse 3**) apply global label styling that can still tint dialog text — that is a skin limitation, not a Kodi **Piers–only** behaviour.

## [3.3.0] - 2026-05-13

### Changed
- **Skip dialog font colour (bundled WindowXML)**: Full and minimal skip layouts bind button and auxiliary line text to **`$INFO[Window.Property(skip_dialog_text_color)]`**, set from **Skip dialogue font colour** (`skipdialog.py`). Python only updates label **text** (`setLabel` without colour slots) so it does not fight Kodi’s focus/skin rendering. **`SkipDialog.__init__`** seeds the property **`FFFFFFFF`** until **`onInit`** resolves the setting. **`resources/skins/default/colors/defaults.xml`** defines stable named colours (**`lightgrey`**, **`white`**, etc.) for **Segment Editor** and other skins.
- **Segment Editor + online playback snapshot**: Loading the editor from the published parse cache (merged online-first timeline) now treats the service snapshot path and `Player.getPlayingFile()` / `Player.GetItem.file` as the **same video** when `paths_refer_to_same_video` matches, instead of requiring identical strings (fixes NFS / Kodi path forms where overlap auto-open still fell back to chapter XML). Logs a clear reason when the snapshot is skipped (`segment_editor_session.py`). **RunScript** (auto-open overlap) runs in a **separate** Python invoker, so the in-memory `playback_segment_cache` snapshot is **not** visible there — the service now **mirrors** the same parse payload to `Window(10000)` so `get_parse_cache_snapshot()` works from `segment_marker.py` (`playback_segment_cache.py`).
- **Editor yes/no and OK + scroll modals** (`skippy_editor_modal_skin.py`): **Up** / **Down** and **Page Up** / **Page Down** move the message while **Yes**, **Cancel**, or **OK** is focused (`ControlTextBox.scroll`), because the text area often cannot receive focus in a Python `WindowDialog`. **▲** / **▼** buttons left of **Yes** / **OK** use the same page step for remote-friendly scrolling and show normal button focus.
- **Chapter XML sidecars** (`segment_editor_parser.normalize_matroska_chapter_xml_text`, `service_segment_sources.parse_chapters`, `service_sidecar_paths._find_existing_sidecar_chapter_xml_path`): Tolerate BOM, leading whitespace before `<?xml`, and a duplicate XML declaration. The service **tries each chapter sidecar path** until one parses (no longer stops at the first file that merely exists). Existing sidecar discovery prefers the **first path that is valid XML** so a corrupt `-chapters.xml` does not block updates or force the editor onto a different file than the save logic.
### Added
- **Behind the scenes / featurette** (local sidecars only): Default **Segment keywords to watch for** includes `behind the scenes`, `behind-the-scenes`, `bts`, and `featurette`. Those four default to **ask to skip** (with intros, recaps, previews, etc.). **EDL action mapping** includes `18:Behind the scenes` and `19:Featurette`. Segment Marker and Segment Editor type pickers read the keyword list. New installs get these defaults; existing profiles keep saved values until edited.
- **TV prefetch next episode** (Advanced): Under **Segment Settings → Online segments sidecar**, **Prefetch next episode** (default on, requires **Use online segment lookup** for TV). When **Segment source priority** is **Online first**, Skippy finds the **library** successor (in-season `E+1`, else next season’s smallest episode index), fetches **merged online-only** segments into a separate **`prefetch_segment_cache`** (not mixed with `remote_segment_cache` until handoff), and applies them on playback **only** when the started file matches that successor (path + `build_tv_cache_key`). Cleared when the service starts; discarded on priority/local-only paths and when scheduling fails. **Verbose → All detail** logs lines tagged **`[service.skippy - prefetch]`** (schedule, store, reject) plus normal **`[service.skippy - remote]`** handoff messages. Implementation: **`prefetch_segment_cache.py`**, **`service_segment_prefetch.py`**, **`remote_segments`** (`resolve_tv_library_successor_episode_item`, `fetch_remote_tv_segments_core`, handoff in `fetch_remote_tv_segments`), **`service_segment_sources`**, **`service` / `service_main_loop`** (`prefetch_tv_scheduled_path`). Strings **31013–31014**.
- **Segment Editor** when opened from **online-first** playback snapshot: each row keeps its API **Source** (**theintrodb** / **introdb**) instead of a single **online** label (`segment_editor_session.py`).
- **Neighbor snap** (Expert): applies to **Update** and **Update All** only. **Snap neighbor end** trims a neighbor that overlaps the **start** of the anchor (e.g. prologue **end** → intro **start**). **Snap neighbor start** trims a neighbor overlapping past the anchor **end** (e.g. main **start** → intro **end**; epilogue **start** → credits **end**). Separate rows each get at most one trim; **no** chapter/EDL row is duplicated into two. If a **single** local row fully **wraps** the anchor (one segment covering the whole intro/credits window), only **one** trim runs on that row: **intro/recap** anchors use **snap start** (resume after anchor); **credits/preview** anchors use **snap end** (truncate before anchor). Prefer prologue / main / epilogue as distinct rows for full control with both toggles on.
- **Update / Update All confirmation**: **Neighbor snap** On/Off is shown when either snap is enabled. Previews reflect retime + snap + (for Update All) inserted segments.

## [3.2.1] - 2026-05-13

### Removed
- **TV next-episode prefetch** (`tv_prefetch_next_episode`, playlist-based online warm-up): Little benefit for small payloads; removed setting **32075–32076**, `prefetch_next_episode_segments` / `_get_playlist_next_episode` from `remote_segments.py`, and the call from `service_segment_sources.py`.

## [3.2.0] - 2026-05-13

### Added
- **Jump offset** (Advanced): Under **Playback and Skip Dialog → Global options**, a **−5…+5 s** slider (default 0) adds to the computed skip seek target for **Auto** and **Ask** (after confirm) paths. Negative lands earlier (e.g. still watch the tail of an intro); positive lands later; seek is clamped **≥ 0**. Setting id `skip_jump_offset_seconds`; strings **32091–32092**.

### Changed
- **Segment upload results** modal (`online_segment_upload.py`): Lists **Successful submissions**, **Skipped**, and **Errors** with bullet lines per segment—**API** (TheIntroDB.org / IntroDB.app), **label**, **online bucket**, **time range**, and for skips/errors the **reason** or message. New strings **39048–39049** (truncation / empty placeholder), **39054–39055** (API short names).

## [3.1.7] - 2026-05-13

### Changed
- **Editor-styled modals** (`skippy_editor_modal_skin.py`): Shared **white.png** stripes (**E0000000**, same as the Segment Editor seek/action row overlay) on **heading** and **button/footer** rows for tall Yes/Cancel, **OK + scroll**, and **vertical list pick** dialogs.
- **Online sidecar overwrite/update prompt**: Uses the shared **EditorTallYesNoDialog** (striped header/footer); implementation moved from `service_online_sidecar_save.py` into `skippy_editor_modal_skin.py`.
- **Segment Editor → Upload**: “Upload chapter XML and EDL…” **target** picker uses **show_editor_list_pick** instead of Kodi `Dialog().select`; errors and **upload results** summary use **show_editor_ok** (`online_segment_upload.py`, `segment_editor_dialog.py`).
- **Segment label / type picker** (`SegmentMarkerTypePicker.xml`): **Heading** and **footer** stripes for parity with the editor.

### Notes
- Other Segment Editor flows still use Kodi’s stock **ok**, **yesno**, **input**, and **select** (e.g. edit times, delete confirm, jump-to-segment list, embedded chapter import). Those can be migrated later to the same helpers if desired.

## [3.1.6] - 2026-05-13

### Changed
- **Online sidecar — Update / Overwrite confirmation**: The tall “update chapter XML and EDL…” prompt uses a **custom `WindowDialog`** instead of Kodi’s stock yesno, aligned with the **Segment Editor** look (top-left panel, `font16` heading, `font13` scrollable body, **Yes** / **Cancel** as list-style `font10` buttons with the same textures and colors as editor actions). Labels use add-on strings **35018** / **35019** (not core `$LOCALIZE` ids).

### Fixed
- **That dialog**: Remote **OK** on **Yes** / **Cancel** and focus on the scrollable body no longer leaves the modal inert — focus defaults to **Yes**, Left/Right track the intended button, and **Select** applies the current choice when focus is not on a button.

## [3.1.5] - 2026-05-13

### Added
- **Segment Editor**: **Snap start** and **Snap end** beside **Edit** / **Delete** align the selected segment to the chronologically sorted timeline: first segment start snaps to `00:00:00.000`; other starts snap to the previous segment’s end; ends snap to the next segment’s start; the last segment’s end snaps to the current video duration (requires playback). Invalid snaps (would break `start < end`) show an error instead of applying.

## [3.1.2] - 2026-05-17

### Changed
- **TheIntroDB GET `/v2/media`**: Parse each segment type (**intro**, **recap**, **credits**, **preview**, etc.) as an **array** of `{start_ms,end_ms}` objects (v2). Missing types are omitted in v2 (treated as empty). Single-object v1-shaped responses are still accepted client-side. (`remote_segments.py`: `_theintrodb_normalize_segment_field`, `_theintrodb_segment_entries`.)

## [3.1.1] - 2026-05-17

### Added
- **Online segments sidecar — Update policy**: **Update (no prompt)** and **Update (ask first)** (settings: *If matching sidecar already exists*). Adjusts **start/end only** for local segments matched to online intro/recap/credits/preview (IntroDB.app `outro` maps to the same bucket as credits for matching); local labels and structural rows you did not match (e.g. prologue, main, epilogue) stay put and are never removed. **Overwrite (ask)** / **Update (ask)** confirmations append a detail block: online data by **TheIntroDB.org** vs **IntroDB.app**, planned time changes (update), or local vs online comparison (overwrite). Strings **35012–35017**; **`service_online_sidecar_save.py`**, **`service_online_policy.py`**, **`online_segment_upload.py`** (`local_label_to_online_bucket`, `remote_payload_label_to_online_bucket`); **`tools/gen_settings_v1.py`** + **`resources/settings.xml`**; English help updates for **32047**, **32070–32072**.

### Changed
- **README**: Documents **update** alongside other sidecar policies and adds an **Update policy caveat** (updated online windows can overlap unchanged neighbors — use merge, overwrite, or the editor for a clean timeline).

### Fixed
- **service.py**: Missing import for **`sync_marker_pending_indicator`** (`marker_indicator`).

## [3.1.0] - 2026-05-13

### Added
- **Expert → Upload to online sources**: default target (Both / TheIntroDB.org / IntroDB.app), and hidden fields for **TheIntroDB.org** and **IntroDB.app** API keys. Category is placed above **Backup & Restore**.
- **Enable upload to online sources** master toggle: when off, the Segment Editor **Upload** control is hidden. (Default **off** until you opt in.)
- **Segment Editor**: **Upload** button (row with Delete All / Save) opens a dialog to submit segments to one or both databases. Labels are normalized to each API’s segment types (e.g. Opening→intro, Credits→TheIntroDB `credits` / IntroDB `outro`). Submissions are fingerprinted in **`addon_data` → `online_upload_submissions.json`** to avoid repeat POSTs for the same range from this device. Upload errors (missing keys, HTTP 401/403, rate limits, network) use localized explanations where possible.
- **`online_segment_upload.py`**, **`remote_segments.py`** helpers **`get_enriched_item_for_path`** / **`build_upload_context`** (with forced TMDB enrichment for uploads when an API key is available).

### Changed
- **TheIntroDB TV**: submit and remote lookup use the **TV series** TMDB id (Kodi episode `uniqueid.tmdb` is often an **episode** id; Skippy prefers the show’s library row or TMDB `/find` from the episode IMDb id when a TMDB API key is configured).
- **IntroDB.app** requests use **HTTPS** (avoids **HTTP 308** redirect issues on POST).
- **Upload** button label comes from add-on strings via Python (`$LOCALIZE[...]` in add-on XML resolves to **core** Kodi strings, which led to labels like “Optional”).
- **Online upload**: failures are logged as **`[service.skippy - online upload]`** at ERROR (and a short INFO summary when the run finishes), not only in the modal.

## [3.0.1] - 2026-05-13

### Added
- **Optional dependency** **`script.module.jurialmunkey`** in **`addon.xml`**: TheMovieDB Helper requires this module; declaring it as **`optional="true"`** on Skippy helps Kodi resolve installs when optional add-ons are enabled and the repository provides the module. Skippy does not import it directly. If installs still fail, add [jurialmunkey’s repo](https://github.com/jurialmunkey/script.module.jurialmunkey) or install **[releases](https://github.com/jurialmunkey/script.module.jurialmunkey/releases)** as ZIP before the helper.

## [3.0.0] - 2026-05-13

### Changed
- **Service architecture**: Playback monitor loop, segment parsing/linking, and related logic are split into **`service_main_loop.py`** and **`service_*.py`** helpers (e.g. segment sources, sidecar paths, segment processing); **`service.py`** remains the Kodi service entry. Major version reflects this structural refactor.

## [2.2.7] - 2026-05-13

### Added
- **Open Segment Editor when overlaps are detected** (`open_segment_editor_on_overlap`, Advanced): Shown only when **Ignore overlapping segments** is **off**. Uses the same pass-2 overlap/nested detection as the toast. Runs **once per playback file** (flag cleared on new video or genuine replay). Launches **`RunScript(service.skippy,open_segment_editor)`** so the service loop is not blocked. Requires **Segment Editor** enabled. (`service.py`, `gen_settings_v1.py`, strings **31011–31012**.)

## [2.2.6] - 2026-05-13

### Added
- **Backup & Restore** (Advanced settings category): **Back up settings to JSON** picks a writable folder and writes `skippy-settings-backup-<timestamp>.json` with every persisted add-on setting (same keys as `resources/settings.xml`, excluding action buttons). **Restore settings from JSON** picks a backup file, confirms, then applies overlapping keys; unknown keys are ignored; keys not in the file stay unchanged. Implemented in **`settings_backup.py`**, triggered via **`RunScript(service.skippy,backup_settings|restore_settings)`** from settings actions (`segment_marker.py` dispatch). English strings **30007**, **38000–38008**.

## [2.2.5] - 2026-05-13

### Changed
- **README**: Clarified the **playback loop** (auto / ask / never), **decline vs session** behavior for ask dialogs (what clears **recently dismissed**: new file, major rewind, genuine replay—not pause/resume). New **Ask dialog debounce** section: fixed **300 ms** delay, why it exists, tradeoffs of lowering/raising it (requires source edit today). Cross-linked from **Ask to skip** usage.

## [2.2.4] - 2026-05-13

### Changed
- **Settings help (English)**: Separate help strings for **Enable skip** and **Show skip dialog** (movies/episodes): explains master vs child toggles and when Kodi hides the dialog row. **Progress bar updates per second** help now focuses on **smooth mode** and **high-refresh** tuning (default 4 for most TVs). New string IDs **32087–32090**; **`tools/gen_settings_v1.py`** + **`resources/settings.xml`** updated.

## [2.2.3] - 2026-05-13

### Changed
- **Skip UI suppression**: Marker modal, editor modal, and pending first-press marker handling live in **`skippy_skip_ui_suppression_state()`** (`SkipUiSuppression`); the service loop only opens the home window and checks **`skip_ui.suppress`**. Behavior unchanged; easier to reuse and review. (`service.py`.)

## [2.2.2] - 2026-05-16

### Changed
- **Service loop — marker/editor pending guard**: Replaced silent **`except Exception`** with **`RuntimeError`** ignored (typical when the home window or properties are unavailable) and **`log_service_detail`** + traceback for anything else (**All** / verbose detail level only). Inner **`clearProperty`** and path-compare fallbacks use the same split. (`service.py`.)

## [2.2.1] - 2026-05-16

### Changed
- **`is_skip_enabled` / `is_skip_dialog_enabled`**: Movie/episode skip and skip-dialog settings are logged only when the value **changes**, not on every service poll. Unknown playback types warn **once per distinct** type per session. Removed the redundant “skipping disabled — dialog will not be shown” line (the skip toggle log already covers that). (`settings_utils.py`.)

## [2.2.0] - 2026-05-16

### Changed
- **Full skip dialog — classic progress logs**: Progress-bar telemetry in **`_monitor_segment_end`** is throttled to at most once per **~1.5 s** (same cadence as smooth mode), reducing log spam while the bar still updates every poll tick. (`skipdialog.py`.)

## [2.1.9] - 2026-05-16

### Changed
- **Segment marker pending start**: Skip dialog is only suppressed for a pending first-press mark when **Segment Marker** is **enabled** in settings. If the feature is off, orphaned `Window` properties are cleared. New **`skippy_marker_pending_ts`** tracks when the mark was set; pending state older than **24 hours** is cleared automatically. (`segment_marker.py` + `service.py`.)

## [2.1.8] - 2026-05-15

### Changed
- **Smooth progress — updates per second**: Slider range widened from **2–60** to **2–120** (runtime clamp and `settings.xml`) for high-refresh displays (e.g. 120 Hz).
- **Segment activation near boundaries**: Playback uses **0.25 s** tolerance when strict `[start, end]` misses due to polling / float time (`segments_active_for_playback`). If no strict match, at most **one** lenient segment is chosen (nearest interval, then latest start) so adjacent chapters do not both prompt. `SegmentItem.is_active` remains strict for nested-exit semantics; dialog loop and overlap-suppression use the new resolver.

### Fixed
- **Skip dialog countdown / progress**: The poll loop no longer uses a second **`xbmc.Monitor.waitForAbort`** (the add-on already has a service **`Monitor`**; an extra instance / worker-thread **`waitForAbort`** could stop the loop immediately or prevent timed wakeups). Restored **`time.sleep(delay)`** between ticks while keeping fractional percent, easing, and redundant-update skips.

## [2.1.7] - 2026-05-15

### Fixed
- **Full skip dialog — progress poll thread**: Replaced **`time.sleep`** with **`xbmc.Monitor.waitForAbort`** (monitor created in **`onInit`**). Progress uses **fractional elapsed → percent** (finer steps than integer 1% buckets), **exponential smoothing** for smooth mode (`tau=0.35`, works at default 4 updates/s), and **skips redundant `setProperty` / `setPercent`** when values are unchanged. Should reduce playback stutter and jerky bar updates.

## [2.1.6] - 2026-05-15

### Added
- **Full skip dialog — smooth progress bar** (`smooth_progress_bar`, Advanced, default off): faster refresh with simple easing on the existing `type="progress"` control. **Progress bar updates per second** (`progress_bar_updates_per_second`, slider **2–60**, default **4**) appears when smooth mode is on so weaker hardware can lower the rate if playback stutters.

## [2.1.5] - 2026-05-15

### Added
- **Full skip dialog**: **Show skip button focus frame** (`show_skip_button_focus_texture`, default on). When **Hide Close Button** is enabled, turn this off to omit the focus texture on the Skip control (sets skin `texturefocus` to `-`, same as no-focus). Standard level; only enabled in settings when Close is hidden.

## [2.1.4] - 2026-05-14

### Changed
- **Add-on settings (Kodi format v1)**: `resources/settings.xml` now uses **`settings version="1"`** with **`<level>`** per setting so **Basic / Standard / Advanced / Expert** actually hide/show options (legacy flat `settings.xml` ignored `level`). **Enable/visible** chains use **`<dependencies>`** (e.g. progress bar and segment marker sub-options). Regenerate via `tools/gen_settings_v1.py` when adding settings.
- **Saved file permissions** (Segment Marker and Segment Editor): the first option’s label is now **Leave unchanged (no chmod)**; stored value is still **`Default`**—Skippy does not call **`chmod`** for that choice (inherits OS/process default). **`644`** / **`666`** still force modes after save.

## [2.1.3] - 2026-05-13

### Added
- **Full skip dialog — progress bar countdown**: New setting **Progress bar shows remaining (countdown)** (`progress_bar_countdown`). When enabled, the bar starts at **100%** and shrinks toward **0%** as the segment plays; when disabled, behavior is unchanged (fills with elapsed time).
- **Full skip dialog — progress bar style** (`progress_bar_style`): labelenum of **`progress_mid*.png`** filenames (same storage pattern as **Button Focus Style**), applied to the Full mode progress control before each dialog open.
- **Full skip dialog — progress bar height** (`progress_bar_height`): slider **5–32** pixels (**step 1**, default **16**); applied at runtime via **`setHeight`** when the dialog lays out.

### Changed
- **Full skip dialog — progress bar**: Kodi progress control now uses **`reveal` true** so a full-width **`midtexture`** (same size as **`texturebg`**) is clipped to the current percent instead of stretched; works for both default fill and countdown shrink.

## [2.1.2] - 2026-05-09

### Fixed
- **Missing-segments toast** wording follows **TV/Movie source toggles**: online-only failures report **no online data**; if **local is off** but a **chapter XML / `.edl`** exists, the toast notes **local data is available**; local-only and **both** on use **no local** / **neither locally nor online** text. When **both local and online** are off for that type, the toast is **not** shown.
- **Sidecar chapter XML**: Overlapping **same-label** chapter windows (duplicate intro/credits atoms from bad merges) are **deduped** on parse and when saving/writing Matroska-style XML, so lists and files stay coherent.
- **Ask skip dialog**: A **single-flight** guard avoids opening a second skip dialog while one is already modal (reduces rare stacked dialogs).

## [2.1.1] - 2026-05-04

### Fixed
- **Segment Editor hotkey / remote**: Opening the editor from **RunScript** (CTRL+SHIFT+E, editor remote, etc.) hung because the session imported **`service`**, which runs the service’s blocking main loop on load. The playback segment cache is now published via **`playback_segment_cache.py`** and the editor reads that snapshot — **no `import service` from script paths**. Remote/keyboard editor entry works again; online-segment bootstrap for the editor is unchanged in behavior.

## [2.1.0] - 2026-05-04

### Added
- **Segment Editor + online segments**: When playback is using **online** lookup (priority gives remote segments and the service has them cached for the current file **before** sidecars exist or match), opening the Segment Editor loads that cached list. Each row shows **Source: online** (normalized from TheIntroDB / IntroDB segment data). If the service has not parsed online segments for this path, behavior is unchanged (chapters XML / `.edl` on disk). Saving from the editor still writes sidecars per **Segment Editor** save settings.

### Changed
- **Service segment cache** now records **`segment_origin`** (`remote` / `local` / `embedded` / `none`) alongside segments so the editor and future features can tell which family of sources won priority for the active parse.

## [2.0.3] - 2026-05-04

### Fixed
- **Segment Editor — Select Segment Label**: The label chooser when adding or editing a segment now uses the same skinned list as Segment Marker (`SegmentMarkerTypePicker.xml`) instead of `Dialog().select()`. All entries from **Segment keywords to watch for** (`custom_segment_keywords`), including **Main**, are listed reliably; the previous dialog could omit items on some Kodi builds.

## [2.0.2] - 2026-05-03

### Fixed
- **Toast notification icon**: Skippy artwork now loads reliably for **Discover remote** (Segment Marker and Segment Editor), **marker/editor keymap** success and error toasts, and playback toasts that use the shared icon path (e.g. segment skip, no segments found, overlapping segments). Paths prefer Kodi’s **`getAddonInfo("icon")`** value, fall back to **`icon.png`** in the add-on folder, and normalize slashes so builds that ignored Windows-style paths no longer fall back to Kodi’s generic info icon.

## [2.0.1] - 2026-05-02

### Changed
Overwrite dialog titles: Heading strings were too generic. They’re now explicitly show that local sidecars are being replaced with online lookup data

### Fixed
Stale segments after overwrite (without stopping playback): Fixed issue where old segments persisted even after online lookup and saving of new files. 

## [2.0.0] - 2026-05-01

### Added
- **Segment Editor** (integrated from the former `service.segmenteditor` add-on): edit `.edl` and `-chapters.xml` sidecars during playback — add, adjust, or remove segments from a list UI. New settings category **Segment Editor** under **Segment Marker**, with **Enable** gating all sub-options.
- **Separate editor keymap** (`userdata/keymaps/skippy_editor.xml`): configurable keyboard shortcut (default **CTRL+SHIFT+E**), optional remote button, discover-remote and **Update editor keymap** actions — independent of the Segment Marker keymap (`skippy_marker.xml`).
- Editor uses the same **Segment Settings** list (**custom segment keywords** / labels and **edl action mapping**) as the rest of Skippy. Save format (Both / EDL / XML), file permissions (Default / 644 / 666), and **back up before save** align with Segment Marker behavior.
- **JSON-RPC**: `NotifyAll` / announcements containing **`open_segment_editor`** still open the editor from the service (compatible with prior `service.segmenteditor` triggers).
- **Debug Logging** settings category moved to the bottom of the add-on settings UI.
- **Online segments sidecar**: **Save format (online segments)** — write online lookups to **`.edl`**, **chapters XML**, or **both** (independent of Segment Marker save format).

### Changed
- **Version 2.0.0**: Skippy is documented as an all-in-one add-on for **creating** (Segment Marker), **editing** (Segment Editor), and **skipping** segments during playback.
- **Segment Marker pending chip**: The on-screen “mark in progress” indicator is drawn on the fullscreen video window (`12005` / live TV `10800`) instead of a `WindowDialog`, so remote and keyboard marker shortcuts still apply for the second press without expanding keymaps to `global`.
- **Segment Marker indicator text**: After the end time is set, the chip shows **Start → End** until save completes or you cancel a save dialog; clearing uses the same paths as aborting (e.g. end before start clears the pending mark and hides the chip). Disabling Segment Marker also clears a stuck pending mark and indicator.

### Fixed
- **TV online lookup**: Restored missing `fetch_remote_tv_segments()` call in the episode parse path (online was enabled but `remote_list` stayed empty). **Online overwrite (ask first)**: With **Save format** set to **Both**, a single confirmation is shown when both chapter XML and `.edl` already exist (instead of two identical prompts). Per-type prompts use clearer messages. **Online segment sidecar save**: Chapter XML writes use **delete-then-write** via `safe_file_write` so shorter overwrites do not leave stale bytes after `</Chapters>` (fixes corrupted XML tails). **Overwrite (ask first)** is recognized when Kodi stores the human-readable label instead of `OverwriteAsk`. New **Save format (online segments)** setting: **Both** / **EDL only** / **Chapters XML only** (default **Both**), with relabeled **Save online segments**, **If matching sidecar already exists**, **Back up sidecar files…**, and generic replace confirmation strings. **No-op save**: If the sidecar already matches what would be written (**overwrite**: identical segment list; **merge**: nothing new to add), Skippy skips write, backup, and overwrite prompts. For **`.edl` overwrite**, “unchanged” compares **start/end/action** triples (what the file actually stores) instead of text labels, so replaying after an online save does not re-prompt when the API label text differs from the mapped label. **EDL merge** on an empty file now mirrors chapter XML (empty = no segments; non-empty but unparseable still forces a normal save path). **Segment Editor** `save_edl` label lookup matches the service (normalized labels, numeric `action_type` coerced for EDL lines). **`edl_action_mapping`** merges **stock defaults** from the add-on (including **13:Outro**) with the value stored in Kodi so older profiles still resolve labels like **outro** to the right action in `.edl`; your settings override the default for the same label or action number.

## [1.3.6] - 2026-04-30

### Changed
- Default **`edl_action_mapping`** now includes **`17:Cold_open`** (cold open) so the stock mapping matches the Segment Editor / shared numbering scheme for types 4–17.

## [1.3.5] - 2026-04-29

### Changed
- **Segment parsing cache**: Skippy now parses/selects segment sources once per playback and reuses the parsed source segments while still evaluating active segments against the live playback time every loop. This reduces repeated `.edl` / `chapters.xml` reads and repeated online/source selection during playback.
- **Sidecar refresh detection**: While using the parsed segment cache, Skippy checks local sidecar file mtime/size every 5 seconds and reparses if a `.edl` or chapter XML file changes during playback.
- **EDL diagnostics**: Raw `.edl` file contents are now logged only at **All detail** log level. Normal logging keeps the higher-level EDL found / parsed segment count messages without dumping the full file.
- **Segment Marker keymap**: The Segment Marker settings now let users type a free-form keyboard shortcut (default normal **CTRL+E**), choose normal vs long press for keyboard and remote bindings, enter or discover a remote button code, and regenerate `userdata/keymaps/skippy_marker.xml`. The generated keymap now includes `global`, `FullscreenVideo`, `VideoOSD`, and `VideoMenu` so the marker also works while Kodi's video OSD is open.
- **Segment Marker save safety**: Manual marker saves now have an overlap policy (**Merge non-overlapping**, **Overwrite overlapping**, **Append always**, **Replace file**, **Ask each time**) and optional `.bck` backups before changing existing `.edl` / chapter XML files. Merge mode is the default and leaves overlapping existing entries unchanged. Ask mode shows the save-method picker before segment type selection only when a selected sidecar already exists, and warns when the marked range overlaps existing entries. Backups follow the marker **Save format** setting, so **Both** backs up both existing sidecars.
- **Segment Marker picker layout**: The segment type picker now uses the 720p skin coordinate grid so it is centered instead of drifting toward the bottom-right.

## [1.3.0] - 2026-04-20

### Added
- **Segment Marker**: New manual segment creation feature. Long-press **CTRL+E** during playback to mark start time, long-press again to mark end time, then pick a segment type from your custom keywords. New settings category **Segment Marker** with:
  - **Enable Segment Marker** (default: off)
  - **Auto-save marked segments**: skip confirmation prompt (default: off)
  - **Show pending marker indicator**: on-screen display while waiting for end time (default: on)
  - **Save format**: Both / EDL only / Chapters XML only (default: Both)
  - **Saved file permissions**: Default / 644 / 666 for network share compatibility
- EDL action types are now correctly mapped from `edl_action_mapping` setting when saving (e.g., Intro → 5, Recap → 9).
- Keymap file at `resources/keymaps/keyboard.xml` — users can copy to `userdata/keymaps/` and customize for remote buttons.
- Script entry point `segment_marker.py` callable via `RunScript(service.skippy)` for custom keymaps.

## [1.2.0] - 2026-04-20

### Added
- **MP4 sidecar diagnostic logging** (All detail): When verbose logging is **All detail**, Skippy logs: **container extension** (`🎬`), **`xbmcvfs.exists()`** result for each candidate path, and for **MP4/M4V** files a **parent directory listing** (`📁`) to help diagnose sidecar detection issues. Also warns if a file **exists but read returns empty**.
- **Embedded chapters fallback**: When no sidecar (`chapters.xml` / `.edl`) or online segments are found, Skippy can parse chapters embedded in the video file (MKV, MP4) via **`Player.GetProperties → chapters`**. Only chapters whose label matches **Custom segment keywords** are used. New setting **Use embedded chapters as fallback** (default: **on**) under **Segment Settings**. Segment summary now includes `embedded=N`.
- **Playlist / Up-Next prefetch**: When TV online segment lookup is enabled and the video playlist contains additional episodes, Skippy pre-fetches segment data for the next episode in the background so it is ready when playback transitions. New setting **Pre-fetch segments for next episode** (default: **on**) under **TV Episode Settings**.

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

