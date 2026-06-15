<img width="1200" height="1200" alt="icon" src="https://github.com/user-attachments/assets/822f7386-ce10-48e7-bb6f-ee90bfdb0a02" />
# Skippy — Segment skip, mark, and edit

Skippy is an all-in-one Kodi add-on for timed **video segments** (intros, recaps, credits, ads, and anything you define). 

During playback it can **skip or ask** using sidecar **`.edl`** and **Matroska-style `chapters.xml`** data, **mark** new ranges with **Segment Marker**, and **edit** existing sidecars with the built-in **Segment Editor** — all driven by the same **segment keywords** and **EDL action mapping**.
<img width="858" height="313" alt="image" src="https://github.com/user-attachments/assets/019bc5ee-4b83-4a56-9098-2618db5c8d41" />
<img width="374" height="147" alt="2026-06-15 22_29_21-Kodi" src="https://github.com/user-attachments/assets/471f4207-a66a-466c-9ac1-109aff0e622d" />

**Local workflows** stay on disk: Skippy reads and writes those sidecars next to your video files, so you can work entirely offline. 

**Online** adds optional **lookup** from **TheIntroDB.org** and **IntroDB.app** (together on **TV** episodes; **movies** use TheIntroDB only today — see **Online segment lookup** below). 

When you choose, Skippy can **materialize** fetched windows into local **chapters XML** and/or **EDL**. Separately, **Expert** settings can enable **upload** from the **Segment Editor**, so you can **push** your segment times to one or both services (**API keys** required; submissions are de-duplicated on this device).

You can tune skip dialogs and toasts and use **separate hotkeys** and **remote button mapping** for Segment Marker (`userdata/keymaps/skippy_marker.xml`, default **CTRL+E**) and the editor (`skippy_editor.xml`, default **CTRL+SHIFT+E**).

**Permissions** Skippy uses explicit **Default / 644 / 666** modes for saved sidecars (same as Segment Marker).

Supported containers include **MKV**, **MP4**, **AVI**, and other common formats Kodi plays.

When **Save online segments** is enabled, fetched lookup ranges can be written next to the video as **`-chapters.xml` / `_chapters.xml` / `.chapters.xml`**, **`.edl`**, or **both** (see **Save format** under *Online segments sidecar* in Segment Settings). Skippy does not write sidecars next to **`plugin://` playback**, **`.strm`** files, or common **stream URLs** (only a real on-disk video path). If a matching sidecar already exists, you can **skip**, **overwrite** (with optional confirmation), **merge** (add non-overlapping online windows), **update** (adjust start/end only on segments matched to online intro/recap/credits/preview; IntroDB *outro* maps to credits), and optionally **back up** the previous file as `*.bck`.

**Update policy caveat:** Matched rows get new times from online lookup; **other** local rows (e.g. prologue, main, epilogue, ads) are **not** moved. If online shifts or lengthens an intro/recap/credits block, those updated windows can **overlap** unchanged neighbors in your sidecar. Use **Merge**, full **Overwrite**, or the **Segment Editor** if you need a clean, non-overlapping timeline.

---

```
## Folder Structure

service.skippy/
├── addon.xml
├── README.md
├── service.py
├── segment_marker.py                          # Segment Marker (RunScript entry + marker UX)
├── skipdialog.py
├── segment_item.py
├── settings_utils.py
├── icon.png
├── fanart.jpg
├── screenshot01.png
├── screenshot02.png
├── screenshot03.png
├── service.skippy - Copy.code-workspace
├── resources/
│   ├── settings.xml
│   ├── language/
│   │   └── English/
│   │       └── strings.po                      # Localization strings for addon settings
│   └── skins/
│       └── default/
│           ├── colors/
│           │   └── defaults.xml                # Named colours for bundled skins (Segment Editor buttons, …)
│           ├── 720p/
│           │   ├── SkipDialog.xml              # Default fallback skip dialog (Full mode)
│           │   ├── SkipDialog_TopRight.xml     # Full skip dialog — top right
│           │   ├── SkipDialog_TopLeft.xml      # Full skip dialog — top left
│           │   ├── SkipDialog_BottomRight.xml  # Full skip dialog — bottom right
│           │   ├── SkipDialog_BottomLeft.xml   # Full skip dialog — bottom left
│           │   ├── Minimal_Skip_Dialog_TopRight.xml    # Minimal chip — top right
│           │   ├── Minimal_Skip_Dialog_TopLeft.xml     # Minimal chip — top left
│           │   ├── Minimal_Skip_Dialog_BottomRight.xml # Minimal chip — bottom right
│           │   └── Minimal_Skip_Dialog_BottomLeft.xml  # Minimal chip — bottom left
│           └── media/
│               ├── icon_skip.png               # Skip button icon
│               ├── icon_close.png              # Close button icon
│               ├── progress_left.png           # Progress bar left segment
│               ├── progress_right.png          # Progress bar right segment
│               ├── progress_background.png     # Progress bar background texture
│               ├── progress_mid.png            # Default progress fill (full-width if using reveal)
│               ├── progress_mid_blue_purple.png # Optional progress fill variants (`progress_bar_style`)
│               ├── button_nofocus.png          # Skip dialog button background texture when not highlighted
│               ├── button_focus.png            # Skip dialog button background texture when highlighted (default)
│               ├── button_focus_aqua.png       # Aqua style button focus texture
│               ├── button_focus_aqua_bevel.png # Aqua bevel style button focus texture
│               ├── button_focus_aqua_dark.png  # Aqua dark style button focus texture
│               ├── button_focus_aqua_vignette.png # Aqua vignette style button focus texture
│               ├── button_focus_aqua_rounded.png # Aqua rounded style button focus texture
│               ├── button_focus_blue.png       # Blue style button focus texture
│               └── white.png                   # Dialog background (credit: im85288, Up Next)
└── tools/
    ├── edl-updater.bat                         # (Optional) EDL action type batch normalizer
    └── ed-updater_all_but_4.bat               # (Optional) EDL updater for all action types except 4
```

## Supported Kodi versions and platforms
Tested on **Kodi Omega 21.2** and **Kodi v22 Piers Alpha 2** across:

| Platform | Status |
| --------------------------- | ------------ |
| Android (Nvidia Shield) | Tested |
| Linux (CoreELEC) | Tested |
| Windows 11 | Tested |

Third-party skins—and sometimes **individual colour schemes** within those skins—vary in how they tint **add-on** dialogs. Skippy’s skip dialog and Segment Editor use bundled WindowXML tied to your **Skip dialogue font colour** setting and `resources/skins/default/colors/defaults.xml`. **Estuary** generally matches expectations. Heavily customised skins can still restyle label and button text globally. For example, **Arctic Fuse 3**: the **Bright White** colour scheme has been reported to alter skip dialog text tinting, while **Miami Vaporware** looked normal in testing. If colours look muted or wrong, try another **colour scheme** in the skin, switch to **Estuary** to confirm Skippy’s own styling, or stick with a scheme that leaves add-on dialogs readable.

---

## Key Features

- User-configurable skip behavior: Auto-skip, prompt, or ignore segments based on per-label rules.
- File format support: Supports Matroska-style `.xml` chapters and enhanced `.edl` format
- Smart playback type detection: Infers playback type and detects whether you're watching a movie or TV episode using metadata and filename heuristics.
- Playback-aware toast notifications: Notifies when no skip metadata is found — only if enabled in settings.
- Label logic allows fine-grained control: `"intro"`, `"recap"`, `"ads"`, etc.
- Platform-agnostic compatibility: Works seamlessly across Android, Windows, CoreELEC, and Linux.
- Progress Bar Display toggle: Progress bar which fills up until end of segment. On/off toggle available under settings.
- Skip dialog modes: **Full** (panel with optional Close, progress bar, icons) or **Minimal** (small corner chip + Skip only). Separate corner placement per mode. See **Skip dialog modes** below.
- **Skip dialogue font colour**: Named presets stored as **ARGB hex**; applied via **`Window.Property(skip_dialog_text_color)`** in bundled WindowXML (see **Skip dialog modes**).
- Rewind detection logic: Resets skip prompts only on significant rewinds — with a user-defined threshold.
- **Jump offset** (Advanced, **Global options**): slider **−5…+5 seconds** (default 0) applied whenever Skippy seeks past a segment (**Auto** skips and **Ask** after you confirm). Negative values seek earlier than the default target (e.g. catch the last few seconds before the marked end); positive values seek later. The target is clamped to **≥ 0**.
- Toast segment file not-found notification filtering: Notifies when no segments were found for the current video. Toggle on/off for movies or TV episodes. Supports per-playback cooldown (default: 6 seconds)
- Debug logging: Verbose logs for each segment processed and decision made. Toggle on/off.
- **Online segment lookup** (optional): TV episodes can pull intro/recap windows from **TheIntroDB** and **IntroDB.app**; movies use **TheIntroDB** only. See the **Online segment lookup** section below for TMDB/API requirements.

---

## Online segment lookup (TheIntroDB / IntroDB.app)

Remote services match your library using **TMDB** and/or **IMDb** IDs—not Kodi’s internal database IDs. Skippy reads those from Kodi’s **`uniqueid`** (and can lift **show-level** TMDB when the episode row only has TVDB/Sonarr-style IDs). If metadata is incomplete, Skippy can call **api.themoviedb.org** to resolve missing IDs, **but only when a TMDB v3 API key is available**.

TheIntroDB’s **GET** `https://api.theintrodb.org/v3/media` returns each segment type (**intro**, **recap**, **credits**, **preview**, …) as a **JSON array** of windows (`start_ms` / `end_ms`; some segments may omit an end timestamp meaning “through end of the file”). Skippy passes **`duration_ms`** from playback/runtime when known to better match theatrical vs extended cuts. Multiple segments per type are supported, and empty types are **left out** of the response.

**For reliable online lookup**, plan on one of these (you do **not** need both):

1. **TMDB API key in Skippy** — In **Add-on settings -> Segment sources -> Online APIs (TMDB)**, paste a key from [themoviedb.org API settings](https://www.themoviedb.org/settings/api) (free tier is enough), **or**
2. **[TheMovieDB Helper](https://kodi.wiki/view/Add-on:The_Movie_Database_Helper)** (`plugin.video.themoviedb.helper`) — Install and configure that add-on’s TMDB key, then enable **Use TheMovieDB Helper addon API key when empty** in Skippy’s same **Online APIs (TMDB)** section. The helper depends on **`script.module.jurialmunkey`**: if your repository does not offer it, install the module from **[GitHub releases](https://github.com/jurialmunkey/script.module.jurialmunkey/releases)** (or add [jurialmunkey’s repo](https://github.com/jurialmunkey/script.module.jurialmunkey)) *before* installing the helper. Skippy lists both as **optional** dependencies in `addon.xml` so Kodi can resolve them when you opt into optional installs—**Skippy itself does not require** TMDB Helper or jurialmunkey.

If neither a Skippy key nor the helper path is available, online lookup only works when Kodi’s library already exposes the IDs TheIntroDB/IntroDB need—**which is often not true** for partial or non-TMDB scrapes.

Turn on **Resolve missing TMDB / IMDb via TMDB API** when you use online lookup and expect enrichment. Filter `kodi.log` for `service.skippy - remote` when **verbose logging** is enabled.

Under **Segment sources**, **TV episodes** and **Movies** each have **online API priority** (TheIntroDB first vs IntroDB.app first). That controls which API wins when both return a segment for the same time window; the other can still add non-overlapping segments. For movies, IntroDB.app currently returns no data, so this usually matches TheIntroDB-only behavior.

**Segment source priority** (label **Prefer when both local and online are enabled**, under TV episodes and Movies): **Local first** (default) or **Online first**. When both local sidecars and online lookup are on, Skippy uses the preferred source when it has data, otherwise the other. **Local first** serves sidecar segments during playback right away (online lookup can run later). **Online first** waits for TheIntroDB / IntroDB network calls before the first skip dialog can show — usually a few seconds, and **up to about 10 seconds** on a cold start or slow network. Use **Local first** if you care about the recap/intro prompt appearing as soon as playback starts.

**Seconds to pause remote API calls after errors** (same category) sets the **base** backoff per host (TheIntroDB, IntroDB.app, TMDB). After errors, wait time **doubles** on repeated failures (capped at one hour) until a call succeeds. **HTTP 429** responses may carry a **`Retry-After`** header; when the server sends it (as seconds), Skippy honors that wait (still capped). **HTTP 404** does not trigger backoff.

---

## Segment Marker hotkey and remote button

Enable **Segment Marker** in Skippy settings to mark segment start/end points during playback. The default keymap is **CTRL+E** normal press, but the **Keyboard marker shortcut** setting is free text, so you can enter shortcuts such as `ctrl+e`, `e`, `f9`, or `ctrl+shift+m`. Use **Keyboard marker press type** to choose normal press or long press.

For remotes, use **Remote marker button** in the same settings category. You can enter a known Kodi remote button name such as `red`, `green`, `blue`, `yellow`, `record`, `select`, or `info`. If you do not know what your remote sends, choose **Discover remote button code**, press the desired remote button, and Skippy stores either the raw value as `key:<code>` or, for CEC-style remotes, the Kodi remote button name automatically. Use **Remote marker press type** to choose normal press or long press for that remote binding.

Skippy writes these choices to Kodi userdata at `userdata/keymaps/skippy_marker.xml` for `global`, `FullscreenVideo`, `VideoOSD`, and `VideoMenu`, then reloads keymaps when settings change. That lets the marker work both during fullscreen playback and while the video OSD is open. You can also run **Update marker keymap now** from the settings screen after manual edits.

Press the marker hotkey once to set **start**, then again for **end**, then choose a segment type and save. While you are between presses, Skippy shows short **Kodi notifications** (about two seconds) with the marked time — not a persistent on-screen chip. Toggle that feedback under **Toast Notifications → Enable toast notifications for segment marker**; the same setting covers cancel toasts when you back out before saving.

When saving marked segments, **How to save marked segments** controls how Skippy combines a new marker range with existing sidecar entries: merge only when non-overlapping, remove overlapping entries first, append anyway, replace the file, or ask each time. In **Ask each time** mode, Skippy shows the save-method picker only when at least one sidecar selected by **Save format** already exists; otherwise it goes straight to segment type selection. When shown, the picker includes an overlap warning when needed. **Back up files before marker save** follows **Save format**: EDL only backs up `.edl`, Chapters XML only backs up chapter XML, and Both backs up both existing files to `*.bck`.

---

## Segment Editor

Enable **Segment Editor** under its own settings category (below **Segment Marker**). While a video is playing, use the configured shortcut (**CTRL+SHIFT+E** by default) or remote to open the editor. Label pick lists come from **Segment keywords to watch for** (`custom_segment_keywords`); EDL types use **`edl_action_mapping`** from **Segment Settings**.

Editor saves use **`userdata/keymaps/skippy_editor.xml`** — independent of the marker keymap. Use **Discover remote button (editor)** and **Update editor keymap now** in the editor category. Optional **Full-screen dark overlay** dims the video behind the editor panel.

<<<<<<< HEAD
Advanced: `RunScript(service.skippy,open_segment_editor)`, `discover_editor_button`, and `install_editor_keymap` are supported the same way as marker script arguments (see `segment_marker.py` dispatch). External automation can also broadcast an IPC message containing **`open_segment_editor`**.
=======
Advanced: `RunScript(service.skippy,open_segment_editor)`, `discover_editor_button`, and `install_editor_keymap` are supported the same way as marker script arguments (see `segment_marker.py` dispatch). External automation can also broadcast an IPC message containing **`open_segment_editor`** (as with the old `service.segmenteditor` add-on).
>>>>>>> 6886271f432f9087a7b4c899c0da7086b7e95424
=======
Advanced: `RunScript(service.skippy,open_segment_editor)`, `discover_editor_button`, and `install_editor_keymap` are supported the same way as marker script arguments (see `segment_marker.py` dispatch). External automation can also broadcast an IPC message containing **`open_segment_editor`**.
>>>>>>> facb69fedd9d0f8ebe086791dc4b22f94d59f40c

---

## Play the Video
Start playback of MyMovie.mkv in Kodi. Skippy will:

1. Search for XML or EDL metadata file alongside the video.

2. Try to read .xml first, then .edl as fallback. Parses segment list and stores in memory

3. Match segment labels

4. Skip, prompt or never ask based on your preferences

5. Show a toast if no segments are found (if enabled)

While a video is playing, the service polls about **once per second** and compares playback time to the loaded segment list:

- **Auto** behavior: seeks past the segment (or nested jump target) without a prompt.
- **Ask** behavior: opens the skip dialog when eligible; see **Ask dialog debounce** below.
- **Never** behavior: plays through with no skip and no dialog.

Segments are marked **prompted** as they are handled so the same interval is not processed repeatedly in the same pass.

**Decline (Close) vs this file:** If you **dismiss** the ask dialog without skipping, that segment is stored in memory as **recently dismissed** for the **current playback of this file**, so the same prompt does not reappear after an ordinary **pause/resume**. That memory is cleared when you start a **different file**, after a **large backward seek** (see **Major Rewind Threshold** / `rewind_threshold_seconds`), or when the service detects a **genuine replay** from near the start (a full rewatch can show asks again). It is **not** cleared on simple pause/resume.

---

## Ask dialog debounce

Before creating the ask dialog, the service sleeps **300 ms** once (`service.py`; not exposed in settings). That **debounce** soaks up rapid re-entries from the ~1 s loop and overlapping edge cases, and gives Kodi a moment to settle **focus and input**, which reduces stacked or duplicate modals on some skins and devices.

- **Lowering** the delay (source change): prompt appears sooner, but duplicate-dialog or focus glitches become more likely.
- **Raising** it: fewer races, but the user waits slightly longer every time an ask fires.

---

## Skip dialog modes

Choose **Skip dialog mode** under **Customize Skip Dialog Look and Behavior** — **Full** or **Minimal**. Each mode has its own **dialog placement** setting (bottom/top × left/right).

### Full mode

Classic panel: optional skip/close icons, **Skip** and **Close** buttons, optional progress bar, optional **Segment ending in:** countdown, and optional **next jump** hint line. **Hide Close Button** and related toggles apply here only (not Minimal).

Focus textures for skip/close buttons and the progress bar **midtexture** are patched from settings when the dialog opens (`service_skip_dialog_skin.py`), same pattern as **Button focus style** and **Progress bar style**.

### Minimal mode

Small corner **chip** only: background plate (**Minimal plate style**) plus one **Skip** button — no progress bar, Close control, or skip/close icons.

- **Dismiss**: **Back** / **ESC** declines the skip (same as Close in Full mode). The dialog also closes automatically when playback reaches the segment end (no skip performed).
- **Layout**: Bundled skins use the **720p** coordinate grid. Chip size is **120×46** (skin coordinates); each corner template insets the group slightly from the screen edge so the chip is not clipped.
- **Skin templates**: `Minimal_Skip_Dialog_BottomRight.xml`, `Minimal_Skip_Dialog_BottomLeft.xml`, `Minimal_Skip_Dialog_TopRight.xml`, `Minimal_Skip_Dialog_TopLeft.xml` under `resources/skins/default/720p/` (1080i variants scale from the same layout). Before opening the dialog, the service patches plate image control **3021** and skip-button focus texture **3012** from **Minimal plate style** (same idea as Full-mode button focus patching).

### Skip dialogue font colour

**Skip dialogue font colour** (Playback behavior) offers named presets — white, light grey, grey, dark grey, black, blue, red, green, aquamarine, pink, purple, peach, orange, yellow — with values stored as **ARGB hex** in settings for consistent reads across Kodi builds.

On dialog open, `skipdialog.py` publishes the resolved colour as **`Window.Property(skip_dialog_text_color)`**. Full and Minimal WindowXML bind **`textcolor`** / **`textcolorfocus`** to **`$INFO[Window.Property(skip_dialog_text_color)]`**. Python only updates label **text** (`setLabel` without colour arguments) so focus and skin rendering stay stable. Full mode: the **next-jump** line is control **3011**; the **Segment ending in:** / countdown line is control **2**, refreshed as playback time updates.

---

## Sidecar resolution at playback start

Skippy must resolve the on-disk video path before it can load `.edl` / `chapters.xml` sidecars. During startup and buffering, Kodi sometimes reports video before playback is fully active:

- **`get_video_file()`** treats **`Player.HasVideo`** like active playback when calling **`getPlayingFile()`**, not only **`isPlayingVideo()`**, so sidecar parsing can start while Kodi is still starting the player.
- **`Player.GetItem`** (JSON-RPC) no longer requires **title** / **label** to be present; if metadata is still loading, **file**-based heuristics still run (**SxxExx**, standalone **Exx** in the path, etc.) to infer movie vs episode for dialog and toast settings.
- If JSON-RPC fails or returns an empty item, **playback type** falls back from the **resolved video path** so segment parsing and skip-dialog enablement are not skipped for the whole session.

Filter `kodi.log` for `service.skippy` with **verbose logging** when diagnosing missing sidecars on first play.

---

## Forced Cache Clearing
Force cache clearing (reparse segments every time), to avoid Kodi cache remembering what you have skipped if you want to restart a playback for instance.

Done by:
```python
monitor.last_video = None
```

Force prompt for testing:
```python
if True:  # triggers skip dialog
```

---

## Settings

Found under:  
`Settings -> Add-ons -> My Add-ons -> Services -> Skippy - Video Segment Skipper`

### Default Settings Overview
Default settings file loaded at first start located in: .../addons/service.skippy/resources/settings.xml

Skippy assigns each option a **visibility level** (Basic through Expert) for Kodi’s add-on settings UI. The definitions live in `resources/settings.xml` using Kodi’s **version 1** settings format (Kodi 19 Matrix and later). Raise the **settings level** in the dialog (gear / mode control, depending on skin) to see **Standard**, **Advanced**, and **Expert** options. To add or edit settings in that file, update and run `tools/gen_settings_v1.py`.

| Setting | Description |
| --------- | ------------- |

| Category: | Segment Settings |
| ----------------------------- | ------------------------------------------------------------------------------- |
| custom_segment_keywords | Comma-separated list of labels (case-insensitive) the skipper should monitor |
| segment_always_skip | Comma-separated list of segment labels to skip automatically |
| segment_ask_skip | Comma-separated list of labels to prompt for skipping |
| segment_never_skip | Comma-separated list of labels to never skip |
| ignore_internal_edl_actions | Ignore internal EDL action types not in mapping (default: true) |
| edl_action_mapping | Map .edl action codes to skip labels (e.g. 4:intro,5:credits) |
| skip_overlapping_segments | Ignore overlapping segments to help avoid redundant or conflicting skips |

| Category: | Customize Skip Dialog Look and Behavior |
| ----------------------------- | ------------------------------------------------------------------------------- |
| show_progress_bar | Enables visual progress bar during skip dialog |
| progress_bar_countdown | Full mode: bar starts full and shrinks (remaining time) instead of filling with elapsed time (default: false) |
| progress_bar_style | Full mode: `progress_mid*.png` fill texture (filename storage; same pattern as button focus). |
| progress_bar_height | Full mode: progress bar height (**slider** **5–32** px, default **16**). |
| smooth_progress_bar | Full mode (Advanced): smoother bar motion via higher refresh + easing; default off — disable if stutter on slow devices |
| progress_bar_updates_per_second | Full mode (Advanced): when smooth progress is on, updates per second (**2–120**, default **4**, same as legacy 0.25 s interval) |
| skip_dialog_mode | **Full** (panel) or **Minimal** (corner chip + Skip only) |
| skip_dialog_position | Corner placement for **Full** mode skip dialog |
| minimal_skip_dialog_position | Corner placement for **Minimal** mode chip |
| minimal_button_style | **Minimal plate style** — background/focus texture for the Minimal chip (patched into skin XML before open) |
| skip_dialog_font_color | **Skip dialogue font colour** — named preset stored as ARGB hex; applied via `Window.Property(skip_dialog_text_color)` in bundled XML |
| button_focus_style | Choose visual style for focused buttons in skip dialog (Default, Aqua, Aqua Bevel, Aqua Dark, Aqua Vignette, Aqua Rounded, Blue) |
| skip_button_format | Choose how the skip button label is displayed: "Skip", "Skip + Type", or "Skip + Type + Duration" (default: Skip + Type + Duration) |
| hide_close_button | Hide the Close button and its icon, leaving only the Skip button visible (default: false) |
| show_skip_button_focus_texture | Full mode: when Close is hidden, show the selected focus texture on Skip (default: true); turn off for no focus frame |
| hide_skip_icon | Hide both the skip icon and close icon, leaving only the Skip and Close buttons visible (default: false) |
| hide_ending_text | Hide the 'Segment ending in:' countdown text line (default: false) |
| enable_skip_movies | Enable skipping for movies. When disabled, no segments will be skipped (auto-skip or dialog) for movies (default: true) |
| enable_skip_episodes | Enable skipping for TV episodes. When disabled, no segments will be skipped (auto-skip or dialog) for episodes (default: true) |
| rewind_threshold_seconds | Threshold for detecting rewind and clearing dialog suppression states |
| show_skip_dialog_movies | Show skip dialog for movies when behavior is set to ask. Requires 'Enable Skip for Movies' to be enabled (default: true) |
| show_skip_dialog_episodes | Show skip dialog for TV episodes when behavior is set to ask. Requires 'Enable Skip for Episodes' to be enabled (default: true) |

| Category: | Toast Notifications |
| --------------------------------------------- | ---------------------------------------------------------------- |
| show_not_found_toast_for_movies | Enable Missing Segment File Toast for Movies |
| show_not_found_toast_for_tv_episodes | Enable Missing Segment File Toast for TV Episodes |
| show_toast_for_overlapping_nested_segments | Enable overlapping segment toast if found in segment file |
| show_toast_for_skipped_segment | Enable toast notification for skipped segment |
| show_toast_for_segment_marker | Enable toast notifications for segment marker (start/end times and cancel) |

| Category: | Debug Logging |
| ----------------------------- | ---------------------------------------------------------------- |
| enable_verbose_logging | Enables extra log entries for debugging |

---

## Skip Modes examples
Segment behavior is matched via normalized labels and defined in:

- segment_always_skip
- segment_ask_skip
- segment_never_skip

Examples:

segment_always_skip = commercial, ad
segment_ask_skip = intro, recap, credits, pre-roll
segment_never_skip = logo, preview, prologue, epilogue, main

---

## Button Focus Texture Customization

Skippy supports multiple visual styles for the focused buttons in the skip dialog. You can choose from several pre-designed button focus textures:

**Available Styles:**
- **Default**: Standard blue focus texture
- **Aqua**: Aqua-colored focus texture
- **Aqua Bevel**: Aqua texture with beveled edges
- **Aqua Dark**: Darker aqua variant
- **Aqua Vignette**: Aqua texture with vignette effect
- **Aqua Rounded**: Aqua texture with rounded corners
- **Blue**: Alternative blue style

**How to Change:**
1. Go to `Settings -> Add-ons -> My Add-ons -> Services -> Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Select your preferred "Button Focus Style"
4. The change takes effect immediately for new skip dialogs

**Technical Details:**
- Button dimensions: 240x25 pixels
- Textures are located in `resources/skins/default/media/`
- The system dynamically updates all skip dialog XML files when you change the setting
- No restart required - changes apply immediately

---

## Progress Bar Display

Skippy includes a visual progress bar that shows the elapsed time of the current skip segment:

**Features:**
- **Visual Progress**: Fills up as the segment progresses toward its end (default), or use **Progress bar shows remaining (countdown)** so the bar starts full and shrinks toward empty
- **Real-time Updates**: Updates every 0.25 seconds during segment playback
- **Toggle Control**: Can be enabled/disabled in addon settings
- **Dynamic Setting**: Changes to the setting take effect immediately without restart

**How to Control:**
1. Go to `Settings -> Add-ons -> My Add-ons -> Services -> Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Toggle "Show Progress Bar in Skip Dialog" on/off; optionally enable **Progress bar shows remaining (countdown)** when the bar is on
4. Changes apply immediately for new skip dialogs

**Technical Details:**
- Progress bar dimensions: width **370**; height **5–32** via settings (default **16**), applied at dialog layout
- Skin uses Kodi **`reveal` true**: **`midtexture`** should match **`texturebg`** dimensions (full-width fill image clips to the current percent instead of stretching horizontally)
- Located at the bottom of the skip dialog
- Uses custom textures: `progress_left.png`, `progress_mid.png`, `progress_right.png`, `progress_background.png`
- Setting is read dynamically - no caching issues

---

## Skip Button Format Customization

Skippy allows you to customize how the skip button label is displayed in the skip dialog:

**Available Formats:**
- **Skip**: Shows only "Skip" (no segment type or duration)
- **Skip + Type**: Shows segment type, e.g., "Skip Intro" or "Skip Recap"
- **Skip + Type + Duration**: Shows segment type and duration, e.g., "Skip Intro (29s)" or "Skip Recap (1m15s)" (default)

**How to Change:**
1. Go to `Settings -> Add-ons -> My Add-ons -> Services -> Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Select your preferred "Skip Button Format"
4. Changes apply immediately for new skip dialogs

**Examples:**
- Format: "Skip" -> Button shows: `Skip`
- Format: "Skip + Type" -> Button shows: `Skip Intro`
- Format: "Skip + Type + Duration" -> Button shows: `Skip Intro (29s)`

---

## Dynamic Segment Type Display

The skip dialog now intelligently displays the segment type in the countdown text:

**Behavior:**
- **With Segment Type**: Shows "Intro ending in: 00:05" or "Recap ending in: 00:10"
- **Without Segment Type**: Falls back to "Segment ending in: 00:05" if no specific type is identified

**How It Works:**
- The dialog automatically detects the segment type from your metadata files
- Uses the segment label (e.g., "Intro", "Recap", "Credits") from your `.xml` or `.edl` files
- If the segment type is generic or unidentified, it defaults to "Segment"

**Example:**
If your segment file contains:
```xml
<ChapterString>Intro</ChapterString>
```
The dialog will show: **"Intro ending in: 00:29"**

If no specific type is found, it shows: **"Segment ending in: 00:29"**

---

## Hide Close Button Option

You can now hide the Close button and its icon to create a minimal skip dialog with only the Skip button:

**Features:**
- **Minimal Interface**: Removes both the Close button and close icon
- **Full-Width Skip Button**: When enabled, the Skip button expands to 350px width with centered text
- **Smart Positioning**: Button starts at left=30px when skip icon is visible, or left=5px when skip icon is hidden
- **Cleaner Look**: Only the Skip button remains visible
- **Still Closable**: Dialog can still be closed using ESC/Back actions

**How to Enable:**
1. Go to `Settings -> Add-ons -> My Add-ons -> Services -> Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Toggle "Hide Close Button" on
4. Changes apply immediately for new skip dialogs

**Note:** When the Close button is hidden, you can still dismiss the dialog using:
- ESC key
- Back button on remote/keyboard
- The dialog will auto-close when the segment ends

---

## Hide Skip and Close Icons Option

You can hide both the skip icon and close icon while keeping the buttons visible:

**Features:**
- **Icon-Free Interface**: Removes both icons, leaving only the text buttons
- **Balanced Layout**: When skip icon is hidden, the close icon is automatically hidden too for visual balance
- **Button Visibility**: Both Skip and Close buttons remain fully functional

**How to Enable:**
1. Go to `Settings -> Add-ons -> My Add-ons -> Services -> Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Toggle "Hide Skip and Close Icons" on
4. Changes apply immediately for new skip dialogs

**Behavior:**
- When skip icon is hidden, the close icon is automatically hidden as well
- This ensures a balanced appearance when icons are disabled
- All button functionality remains unchanged

---

## Button Text Centering

All button texts in the skip dialog are now centered for a consistent, professional appearance:

**Features:**
- **Centered Text**: All buttons (Skip, Close, and full-width variants) display centered text
- **Consistent Layout**: Uniform appearance across all button configurations
- **Professional Look**: Clean, balanced button design

**Applies To:**
- Normal Skip button (when Close button is visible)
- Close button
- Full-width Skip button (when Close button is hidden)

---

## Hide Segment Ending Text Option

You can hide the countdown text line that shows "Segment ending in:" or "Intro ending in:":

**Features:**
- **Cleaner Interface**: Removes the countdown text line
- **Minimal Display**: Only buttons and progress bar remain visible
- **Flexible Control**: Can be combined with other visibility options

**How to Enable:**
1. Go to `Settings -> Add-ons -> My Add-ons -> Services -> Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Toggle "Hide segment ending in text" on
4. Changes apply immediately for new skip dialogs

---

## Enable/Disable Skipping for Content Types

You can now completely disable skipping for movies or TV episodes:

**Features:**
- **Master Control**: When disabled, no segments will be skipped (no auto-skip, no dialogs, no prompts)
- **Per Content Type**: Separate controls for movies and TV episodes
- **Complete Suppression**: Segments are detected but not processed when skipping is disabled

**Settings:**
- **Enable Skip for Movies**: Master switch for skipping in movies (default: true)
- **Enable Skip for Episodes**: Master switch for skipping in TV episodes (default: true)

**How It Works:**
- When "Enable Skip for Movies" is disabled:
  - No segments in movies will be auto-skipped
  - No skip dialogs will appear for movies
  - Segments are detected but playback continues normally
- When "Enable Skip for Episodes" is disabled:
  - Same behavior applies to TV episodes

**Relationship with Dialog Settings:**
- The dialog settings (`Show Skip Dialog for Movies/Episodes`) only apply when skipping is enabled
- If skipping is disabled, dialog settings are ignored
- This allows you to:
  - Disable skipping entirely for a content type
  - Enable skipping but disable dialogs (auto-skip only)
  - Enable both skipping and dialogs (full functionality)

**Example Use Cases:**
- **Movies Only**: Set `enable_skip_episodes = False` to skip only in movies, not TV shows
- **No Auto-Skip**: Set `enable_skip_movies = True` and `show_skip_dialog_movies = False` to show dialogs but disable auto-skip
- **Complete Disable**: Set `enable_skip_movies = False` to completely disable skipping for movies

---

## File Support
Skippy supports the following segment definition files (same **basename** as the video). It looks **beside** the video first, then under a **`.chapters`** subfolder in the same directory (used by the Jellyfin chapters/edl exporter add-on):

- **`basename.edl`**
- **Chapter XML (Matroska-style)** — any of:
  - `basename-chapters.xml`
  - `basename_chapters.xml`
  - `basename.chapters.xml`
  - `basename-chapter.xml`, `basename_chapter.xml`, `basename.chapter.xml` (singular `chapter`, same patterns)
- Optionally a directory-level **`chapters.xml`** next to the video (editor / parser fallback)
- Jellyfin-style nesting: **`videodir/.chapters/basename-chapters.xml`** (and the other suffix variants), **`videodir/.chapters/basename.edl`**, tried after sibling paths

EDL files follow Kodi’s native format with start, end, and action code lines. XML files use a chapter-based structure. If several XML sidecars exist, Skippy tries paths in a fixed order and uses the **first file that contains usable chapter entries**. See section below.

---

## File Example
Breaking.Bad.S01E02.mkv
├── Breaking.Bad.S01E02-chapters.xml — or `_chapters.xml`, `.chapters.xml`, or singular `chapter` variants    # XML chapter file
└── Breaking.Bad.S01E02.edl                                                                                    # Fallback if no XML found

XML takes priority if both exist.

---

## Metadata Formats
Skippy supports two segment metadata formats, placed alongside the .mkv or video file:

1. XML Chapter Files (Preferred)
- Filenames: **`basename-chapters.xml`**, **`basename_chapters.xml`**, **`basename.chapters.xml`**, plus singular **`chapter`** variants (`-`, `_`, `.`); or a sibling **`chapters.xml`**
- Format: Matroska-style (e.g. exported by Jellyfin)
- Label: `<ChapterString>Intro</ChapterString>`
- Configurable behavior per label: auto-skip / ask to skip / never

2. Enhanced EDL Files (Fallback)
- Filename: `filename.edl`
- Format: <start_time> <end_time> <action_type> ;label=Intro (or set preferred label in the settings.xml)
- Configurable behavior per label: auto-skip / ask-to-skip / never (shares the same label settings as the xml route)

## Sample segment files
EDL files define skip segments using three values per line

#### .edl file content example
210 235 4 

-> Will skip or prompt from 3:30 to 3:55 if action type `4` is mapped to `'Intro'` 
Format: <start_time> <end_time> <action_type>. start_time and end_time are in seconds. <action type> is an integer between 4 to 99
Action mapping: action_code maps to a label via edl_action_mapping (e.g. 4:intro, 5:credits)


Kodi may log a warning for unknown EDL action types — this is expected and harmless.

Custom action types (4–99) are supported and configurable via settings:
4 -> Segment (default)
5 -> Intro
6 -> Ad, etc. — 

Optional label support using comments:
42.0 58.3 4 ;label=Intro

If no label is present in edl file or defined in settings, 'Segment' is used as fallback

#### XML chapter format
XML files define segments using chapter metadata:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Chapters>
<EditionEntry>
    <ChapterAtom>
      <ChapterTimeStart>00:00:00.000</ChapterTimeStart>
      <ChapterTimeEnd>00:01:00.000</ChapterTimeEnd>
      <ChapterDisplay>
        <ChapterString>Intro</ChapterString>
      </ChapterDisplay>
    </ChapterAtom>
    <ChapterAtom>
      <ChapterTimeStart>00:20:00.000</ChapterTimeStart>
      <ChapterTimeEnd>00:21:00.000</ChapterTimeEnd>
      <ChapterDisplay>
        <ChapterString>Credits</ChapterString>
      </ChapterDisplay>
    </ChapterAtom>
</EditionEntry>
</Chapters>
ChapterString is the label used for skip mode matching

Times must be in HH:MM:SS.mmm format

Labels are normalized (e.g. Intro, intro, INTRO all match)
```
---

## File Example
Breaking.Bad.S01E02.mkv
├── Breaking.Bad.S01E02-chapters.xml — or `_chapters.xml`, `.chapters.xml`, or singular `chapter` variants    # XML chapter file
└── Breaking.Bad.S01E02.edl                                                                                    # Fallback if no XML found

XML takes priority if both exist.

---

## Segment behavior logic summary

**Skip Enable/Disable Settings:**
- `enable_skip_movies`: Master control for skipping in movies
- `enable_skip_episodes`: Master control for skipping in TV episodes

When skipping is disabled for a content type, no segments will be processed (no auto-skip, no dialogs, no prompts).

**Dialog Enable/Disable Settings:**
- `show_skip_dialog_movies`: Controls dialog display for movies (requires `enable_skip_movies = True`)
- `show_skip_dialog_episodes`: Controls dialog display for episodes (requires `enable_skip_episodes = True`)

| Behavior | Skip Enabled + Dialogs Enabled | Skip Enabled + Dialogs Disabled | Skip Disabled |
| ----------------- | ---------------------------------------------- | ----------------------------------------- | ------------------- |
| never | Skip silently | Skip silently | Skip silently |
| ask | Show dialog | Suppress dialog | Skip silently |
| auto | Skip automatically | Skip automatically | Skip silently |

**Examples:**

1. **Skipping Disabled:**
   - If `enable_skip_movies = False`, no segments in movies will be skipped, regardless of their behavior (auto, ask, or never)
   - Segments are marked as processed but playback continues normally

2. **Skipping Enabled, Dialog Disabled:**
   - If `enable_skip_movies = True` and `show_skip_dialog_movies = False`:
     - Segments with "ask" behavior will be suppressed (no dialog shown)
     - Segments with "auto" behavior will still auto-skip
     - Segments with "never" behavior will play normally

3. **Both Enabled:**
   - If both `enable_skip_movies = True` and `show_skip_dialog_movies = True`:
     - All skip behaviors work as configured (auto-skip, ask dialog, or never skip)

More detailed

**Missing Segment File Toast Behavior:**
| show_skip_dialog setting | Segment File Present | Show Missing Segment Toast Enabled | Show Missing Segment Toast? |
| -------------------------- | ---------------------- | ----------------------------------- | ---------------------------- |
| True | Yes | Yes | No |
| True | No | Yes | Yes |
| False | Yes | Yes | No |
| False | No | Yes | No |
| False | No | No | No |
| True | No | No | No |
| False | Yes | No | No |

**Segment Skip Toast Behavior:**
| Segment File Present | Segment Skipped | Show Segment Skip Toast Enabled | Show Segment Skip Toast? |
| --------------------- | ----------------- | --------------------------------- | -------------------------- |
| Yes | Yes | Yes | Yes |
| Yes | Yes | No | No |
| Yes | No | Yes | No |
| Yes | No | No | No |
| No | No | Yes | No |
| No | No | No | No |

---

## Usage Examples
### Auto-skip
If your chapters.xml contains:

<ChapterString>Intro</ChapterString>

And you've configured "Intro" to auto-skip, the addon will jump past it without prompting.

### Ask to skip
If your .edl file contains:

0.0 90.0 9
And action code 9 maps to "Recap", and "Recap" is mapped to the "Ask to skip" setting, you'll be prompted to skip it.

Just before the dialog opens, Skippy waits **300 ms** (internal debounce; see **Ask dialog debounce** above) so the prompt is not double-fired from rapid loop ticks.

### Never skip example
If your segment label is "Credits" and you've mapped "Credits" to the "Never skip" setting, playback continues uninterrupted with no skip popup.

---

## Toast notification behavior
- Appears when a video has no matching skip segments


Cooldown enforced per playback session (default: 6 seconds)

- Resets on video stop or replay after cooldown

---

### EDL Action Filtering

Skippy supports optional filtering of Kodi-native EDL action types (`0`, `1`, `2`, `3`). This allows users to ignore internal skip markers and rely only on custom-defined segments.

#### Setting
- **Name:** `ignore_internal_edl_actions`
- **Type:** Boolean
- **Default:** `true`

#### Behavior
| Setting Value | Action Types Parsed | Result |
| --------------- | ----------------------------- | ----------------------------------------------------------------- |
| `true` | Only custom actions (`>=4`) | Internal Kodi skip markers are ignored |
| `false` | All action types | Autoskip or prompt for all segments, including Kodi-native ones |

#### Example EDL
```xml
237.5    326.326    5    <-- intro
1323.45  1429.184   8    <-- recap
```
---

## Ignore overlapping segments
Skippy now supports configurable overlap detection to help avoid redundant or conflicting skips. This feature ensures that segments which overlap in time are handled according to your preference.

**Setting:** Ignore overlapping segments
Location: settings.xml -> Segment Settings

Type: Boolean toggle (true / false)

Default: true

### What it does

**When Enabled (true):**
Skippy will skip any segment that overlaps with one already accepted. This is useful when:
- EDL or chapter files contain redundant entries
- Multiple tools or sources generate overlapping metadata
- You want to avoid double prompts or conflicting skips

**When Disabled (false):**
Skippy intelligently handles overlapping and nested segments with smart skip behavior:

### Nested Segments (One segment fully inside another)
Example: Intro (0-50s) with Recap (20-40s) nested inside
- **Intro dialog** appears at 0s: Shows "Skip to Recap at 00:20"
- **Recap dialog** appears at 20s: Shows "Skip to remaining intro at 00:40"
- **Intro dialog** reappears at 40s: Shows normal skip (no nested segments remaining)

### Partially Overlapping Segments
Example: Segment A (45-133s) overlaps with Segment B (50-160s)
- **Segment A dialog** appears at 45s: Shows "Skip to Segment B at 00:50"
- **Segment B dialog** appears at 50s: Shows "Skip to end of Segment B at 02:40"

### Race Condition Prevention
- Only one dialog appears at a time
- Parent segment dialogs are suppressed while nested/overlapping segments are active
- Parent dialogs automatically reappear after nested segments are completed

### Example scenarios

**Scenario 1: Overlapping Segments**
```xml
Segment A: 45.5 -> 133.175
Segment B: 50.0 -> 160.0
```

Behavior:
| Setting Value | Result |
| --------------- | ---------------------------------------------- |
| true | Segment B is skipped entirely |
| false | Smart progressive skipping: A -> B -> end of B |

**Scenario 2: Nested Segments**
```xml
Intro: 0 -> 50s
Recap: 20 -> 40s (nested inside Intro)
```

Behavior:
| Setting Value | Result |
| --------------- | -------- |
| true | Recap is skipped entirely |
| false | Progressive flow: Intro -> Recap -> remaining Intro |

### How to test
Enable verbose logging in settings.

Toggle Ignore overlapping segments on/off.

Observe logs like:

**When enabled:**
```xml
Overlapping segment detected: 50.0–100.0 overlaps with 45.5–133.175
Skipping overlapping segment: 50.0–100.0 | label='segment'
```

**When disabled:**
```
Detected NESTED segment: 'recap' (20.0-40.0) is nested inside 'intro' (0.0-50.0)
Setting jump point for nested 'recap' to 40.0s (remaining intro)
Setting jump point for 'intro' to 20.0s (nested segment 'recap')
```

---

## Logging

Verbose logging provides detailed insight into Skippy's operation. When enabled, it reveals:

**What Gets Logged:**
- Parsed segments and labels
- Playback state and detection
- Toast decision logic and suppression
- Skip dialog flow and user choice
- Overlapping/nested segments
- Dialog and toast creation failures (helps identify Kodi/device limitations)
- State changes and new events

**Smart Logging to Reduce Clutter:**
Skippy uses intelligent state-based logging to keep log files manageable:

- **State Changes Only**: Logs only when values change, not on every check
- **No Repetition**: Same messages aren't logged repeatedly (e.g., "segment not active" won't spam the log)
- **Event-Based**: New events and errors are always logged
- **Cache Management**: Log cache is cleared on video changes, replays, and major rewinds

**Examples:**
- Logs when a new segment becomes active
- Logs when playback type changes
- Logs when state counts change (prompted, dismissed, etc.)
- Doesn't log "segment not active" every second for inactive segments
- Doesn't log "already prompted" repeatedly for the same segment

**Enable via `enable_verbose_logging` for full insight.**

**Troubleshooting Device Limitations:**
When verbose logging is enabled, Skippy will log when dialog or toast creation fails with messages like:
- `Failed to create skip dialog (possible Kodi/device limitation)`
- `Failed to display toast notification (possible Kodi/device limitation)`

This helps identify when Kodi stops creating UI elements due to memory or resource constraints on resource-limited devices (e.g., Amlogic/CoreELEC).

---

## Batch EDL action type normalizer (Windows)
Located in tools/edl-updater.bat:

Updates all .edl files under a folder recursively

Replaces old action types with new ones (e.g. 3 -> 4)

User can specify which action type to look for and which action type to replace with in accordance with user specifications in the settings.xml file.

Ensures full compatibility with Skippy’s behavior mappings

---

## License and credits
Not affiliated with Jellyfin, Kodi, MPlayer or Matroska

white.png background courtesy of im85288 (Up Next add-on)

___________________________________________________________________________________


## Developer notes
- UI driven by WindowXMLDialog
- EDL action types 0 and 3 (Kodi-native) are ignored by Skippy. Use batch tool to convert to other action types.
- Chapter XML sidecars: **`basename-chapters.xml`**, **`basename_chapters.xml`**, **`basename.chapters.xml`**, singular **`chapter`** variants (`-` / `_` / `.`), optional directory **`chapters.xml`**, and **`.edl`** files are considered when resolving sidecars

---

## Contributors
jonnyp — Architect, debugger

