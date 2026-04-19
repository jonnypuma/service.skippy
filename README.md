<img width="1200" height="1200" alt="icon" src="https://github.com/user-attachments/assets/822f7386-ce10-48e7-bb6f-ee90bfdb0a02" />
# 📼 Skippy — The XML-EDL Segment Skipper

Skippy is a Kodi service that detects and can skip predefined video segments such as intros, recaps, ads, or credits using companion `.xml` or `.edl` files. 

Supports chaptered Matroska XMLs, enhanced EDLs with labeled action types.
 
It provides both automatic and user-prompted skipping, and integrates seamlessly into playback with customizable notifications and dialogs.

Discreet, cross-platform, and customizable.

Supported Video Formats: Works for MKV and AVI containers.

Known Limitations: Video files in MP4 containers are currently not working, seems to be a Kodi issue and not addon issue.

When **Save online segments to chapters.xml** is enabled, Skippy does not write a sidecar next to **`plugin://` playback**, **`.strm`** files, or common **stream URLs** (only a real on-disk video path gets a `-chapters.xml`). If a sidecar already exists, you can **skip**, **overwrite** (with optional confirmation), **merge** (add non-overlapping online windows), and optionally **back up** the previous file as `*.bck` (see Segment Settings).

---

```xml
## 📁 Folder Structure

service.skippy/
├── addon.xml
├── README.md
├── service.py
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
│               ├── progress_mid.png            # Progress bar middle segment
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

✅ Supported Kodi Versions and Platforms
Tested on **Kodi Omega 21.2** and **Kodi v22 Piers Alpha 2** across:

| Platform       			      | Status     |
|---------------------------|------------|
| Android (Nvidia Shield) 	| ✅ Tested |
| Linux (CoreELEC)  		    | ✅ Tested |
| Windows 11       			    | ✅ Tested |

---

## 🚀 Key Features

- ⏭️ User-configurable skip behavior: Auto-skip, prompt, or ignore segments based on per-label rules.
- 📁 File format support: Supports Matroska-style `.xml` chapters and enhanced `.edl` format
- 🧠 Smart playback type detection: Infers playback type and detects whether you're watching a movie or TV episode using metadata and filename heuristics.
- 🔍 Playback-aware toast notifications: Notifies when no skip metadata is found — only if enabled in settings.
- 🧠 Label logic allows fine-grained control: `"intro"`, `"recap"`, `"ads"`, etc.
- 🛡️ Platform-agnostic compatibility: Works seamlessly across Android, Windows, CoreELEC, and Linux.
- 📊 Progress Bar Display toggle: Progress bar which fills up until end of segment. On/off toggle available under settings.
- 🖼️ Skip Dialog Placement: Choose dialog layout position (Bottom Right, Top Right, Top Left, Bottom Left) — separate positions for **Full** and **Minimal** mode.
- 🪟 **Full** vs **Minimal** skip UI: Full = classic panel (icons, optional Close, progress bar). Minimal = small plate + Skip only; font color and plate style are configurable.
- 🎨 **Skip dialog font color**: Global preset colors (including black) applied reliably on Full and Minimal dialogs via the Python API.
- ⏪ Rewind detection logic: Resets skip prompts only on significant rewinds — with a user-defined threshold.
- 📺 Toast segment file not-found notification filtering: Notifies when no segments were found for the current video. Toggle on/off for movies or TV episodes. Supports per-playback cooldown (default: 6 seconds)
- 🧹 Debug logging: Verbose logs for each segment processed and decision made. Toggle on/off.
- 🌐 **Online segment lookup** (optional): TV episodes can pull intro/recap windows from **TheIntroDB** and **IntroDB.app**; movies use **TheIntroDB** only. See the **Online segment lookup** section below for TMDB/API requirements.

---

## Online segment lookup (TheIntroDB / IntroDB.app)

Remote services match your library using **TMDB** and/or **IMDb** IDs—not Kodi’s internal database IDs. Skippy reads those from Kodi’s **`uniqueid`** (and can lift **show-level** TMDB when the episode row only has TVDB/Sonarr-style IDs). If metadata is incomplete, Skippy can call **api.themoviedb.org** to resolve missing IDs, **but only when a TMDB v3 API key is available**.

**For reliable online lookup**, plan on one of these (you do **not** need both):

1. **TMDB API key in Skippy** — In **Add-on settings → Segment sources → Online APIs (TMDB)**, paste a key from [themoviedb.org API settings](https://www.themoviedb.org/settings/api) (free tier is enough), **or**
2. **[TheMovieDB Helper](https://kodi.wiki/view/Add-on:The_Movie_Database_Helper)** (`plugin.video.themoviedb.helper`) — Install and configure that add-on’s TMDB key, then enable **Use TheMovieDB Helper addon API key when empty** in Skippy’s same **Online APIs (TMDB)** section.

If neither a Skippy key nor the helper path is available, online lookup only works when Kodi’s library already exposes the IDs TheIntroDB/IntroDB need—**which is often not true** for partial or non-TMDB scrapes.

Turn on **Resolve missing TMDB / IMDb via TMDB API** when you use online lookup and expect enrichment. Filter `kodi.log` for `service.skippy - remote` when **verbose logging** is enabled.

Under **Segment sources**, **TV episodes** and **Movies** each have **online API overlap priority** (TheIntroDB first vs IntroDB.app first). That controls which service wins when both return a segment in the same time range; the other can still add segments that do not overlap. For movies, IntroDB.app currently returns no data, so this usually matches TheIntroDB-only behavior.

**Seconds to pause remote API calls after errors** (same category) sets the **base** backoff per host (TheIntroDB, IntroDB.app, TMDB). After errors, wait time **doubles** on repeated failures (capped at one hour) until a call succeeds. **HTTP 429** responses may carry a **`Retry-After`** header; when the server sends it (as seconds), Skippy honors that wait (still capped). **HTTP 404** does not trigger backoff.

---

## Release notes

### v1.0.17 (April 2026)

**Minimal skip dialog**

- **Minimal mode** is a small corner chip only: background plate (**Minimal plate style**) plus one **Skip** button—no progress bar, Close control, or skip/close icons. Dismiss with **Back** / **ESC**; the dialog still closes when the segment ends.
- Layout follows the **720p** skin grid so the chip stays on-screen. Chip size **120×46** (skin coordinates); bottom/top right variants are offset inward so the chip is not clipped at the screen edge.
- Skin templates: `Minimal_Skip_Dialog_BottomRight.xml`, `Minimal_Skip_Dialog_BottomLeft.xml`, `Minimal_Skip_Dialog_TopRight.xml`, `Minimal_Skip_Dialog_TopLeft.xml` in `resources/skins/default/720p/`. The service patches plate and skip-button focus textures from settings (same pattern as Full mode button focus textures).

**Skip dialog font color**

- **Skip dialog font color** (Playback behavior) offers named presets—white, light/dark grey, black, blue, red, green, aquamarine, pink, purple, peach, orange, yellow—with values stored as **ARGB hex** (`optionvalues`) for consistent reads across Kodi builds.
- Colors are applied in **`skipdialog.py`** via **`Control.setLabel`** with explicit text and shadow colors, because `$INFO[Window.Property(…)]` inside `textcolor` / `textcolorfocus` is unreliable for **WindowXML** script dialogs on many builds. Skin XML keeps static fallbacks. Full mode: **next-jump** line control id **3011**; **countdown** line id **2** is refreshed as playback time updates.

**Playback and segment file detection**

- **`get_video_file()`** treats **`Player.HasVideo`** like active playback when resolving **`getPlayingFile()`**, not only **`isPlayingVideo()`**, so **chapters.xml** / **.edl** resolve during startup when Kodi reports video before playback is fully started.
- **JSON-RPC `Player.GetItem`** no longer discards the item when **title** is temporarily missing; **file**-based inference still runs. If JSON-RPC fails, **playback type** falls back from the **resolved video path** so segment parsing is not skipped.

---

🎬 Play the Video
Start playback of MyMovie.mkv in Kodi. Skippy will:

1. Search for XML or EDL metadata file alongside the video.

2. Try to read .xml first, then .edl as fallback. Parses segment list and stores in memory

3. Match segment labels

4. Skip, prompt or never ask based on your preferences

5- Show a toast if no segments are found (if enabled)

Each second:
- Checks current time against segment list
- If within an active segment: Applies skip behavior
- Flags as prompted to avoid repeats
- Checks current playback time
- If a matching segment is active and unskipped:
    ⏩ Skips automatically 
    ❓ Prompts the user
    🚫 Does nothing — based on label behavior
- Remembers if a segment is dismissed to avoid repeat prompts (unless user seeks back), i.e. at stop, end, or rewind: clears segment cache and skip history

---

🧪 Forced Cache Clearing
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

⚙️ Settings

Found under:  
`Settings → Add-ons → My Add-ons → Services → Skippy - Video Segment Skipper`

⚙ Default Settings Overview
Default settings file loaded at first start located in: .../addons/service.skippy/resources/settings.xml

| Setting | Description |
|---------|-------------|

|Category:                    | Segment Settings                                                              |
|-----------------------------|-------------------------------------------------------------------------------|
| custom_segment_keywords     | Comma-separated list of labels (case-insensitive) the skipper should monitor  |
| segment_always_skip         |	Comma-separated list of segment labels to skip automatically                  |
| segment_ask_skip            | Comma-separated list of labels to prompt for skipping                         |
| segment_never_skip          |	Comma-separated list of labels to never skip                                  |
| ignore_internal_edl_actions | Ignore internal EDL action types not in mapping (default: true)              |
| edl_action_mapping          |	Map .edl action codes to skip labels (e.g. 4:intro,5:credits)                 |
| skip_overlapping_segments   | Ignore overlapping segments to help avoid redundant or conflicting skips   |

|Category:                    | Customize Skip Dialog Look and Behavior                                       | 
|-----------------------------|-------------------------------------------------------------------------------|
| show_progress_bar			      | Enables visual progress bar during skip dialog                                |    
| skip_dialog_position	    	| Chooses layout position for the skip confirmation dialog                      |
| button_focus_style          | Choose visual style for focused buttons in skip dialog (Default, Aqua, Aqua Bevel, Aqua Dark, Aqua Vignette, Aqua Rounded, Blue) |
| skip_button_format          | Choose how the skip button label is displayed: "Skip", "Skip + Type", or "Skip + Type + Duration" (default: Skip + Type + Duration) |
| hide_close_button           | Hide the Close button and its icon, leaving only the Skip button visible (default: false) |
| hide_skip_icon              | Hide both the skip icon and close icon, leaving only the Skip and Close buttons visible (default: false) |
| hide_ending_text            | Hide the 'Segment ending in:' countdown text line (default: false) |
| enable_skip_movies          | Enable skipping for movies. When disabled, no segments will be skipped (auto-skip or dialog) for movies (default: true) |
| enable_skip_episodes        | Enable skipping for TV episodes. When disabled, no segments will be skipped (auto-skip or dialog) for episodes (default: true) |
| rewind_threshold_seconds	  | Threshold for detecting rewind and clearing dialog suppression states         |
| show_skip_dialog_movies	    | Show skip dialog for movies when behavior is set to ask. Requires 'Enable Skip for Movies' to be enabled (default: true) |
| show_skip_dialog_episodes	  | Show skip dialog for TV episodes when behavior is set to ask. Requires 'Enable Skip for Episodes' to be enabled (default: true) |

|Category:                                    | Segment Toast Notifications                                    |
|---------------------------------------------|----------------------------------------------------------------|
| show_not_found_toast_for_movies             | Enable Missing Segment File Toast for Movies                   |
| show_not_found_toast_for_tv_episodes        | Enable Missing Segment File Toast for TV Episodes              |
| show_toast_for_overlapping_nested_segments  | Enable overlapping segment toast if found in segment file      |
| show_toast_for_skipped_segment              | Enable toast notification for skipped segment                  |

|Category:                    | Debug Logging                                                  |
|-----------------------------|----------------------------------------------------------------|
| enable_verbose_logging      | Enables extra log entries for debugging                        |

---

🧠 Skip Modes examples
Segment behavior is matched via normalized labels and defined in:

- segment_always_skip
- segment_ask_skip
- segment_never_skip

Examples:

segment_always_skip = commercial, ad
segment_ask_skip = intro, recap, credits, pre-roll
segment_never_skip = logo, preview, prologue, epilogue, main

---

🎨 Button Focus Texture Customization

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
1. Go to `Settings → Add-ons → My Add-ons → Services → Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Select your preferred "Button Focus Style"
4. The change takes effect immediately for new skip dialogs

**Technical Details:**
- Button dimensions: 240x25 pixels
- Textures are located in `resources/skins/default/media/`
- The system dynamically updates all skip dialog XML files when you change the setting
- No restart required - changes apply immediately

---

📊 Progress Bar Display

Skippy includes a visual progress bar that shows the elapsed time of the current skip segment:

**Features:**
- **Visual Progress**: Fills up as the segment progresses toward its end
- **Real-time Updates**: Updates every 0.25 seconds during segment playback
- **Toggle Control**: Can be enabled/disabled in addon settings
- **Dynamic Setting**: Changes to the setting take effect immediately without restart

**How to Control:**
1. Go to `Settings → Add-ons → My Add-ons → Services → Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Toggle "Show Progress Bar in Skip Dialog" on/off
4. Changes apply immediately for new skip dialogs

**Technical Details:**
- Progress bar dimensions: 370x5 pixels
- Located at the bottom of the skip dialog
- Uses custom textures: `progress_left.png`, `progress_mid.png`, `progress_right.png`, `progress_background.png`
- Setting is read dynamically - no caching issues

---

🎯 Skip Button Format Customization

Skippy allows you to customize how the skip button label is displayed in the skip dialog:

**Available Formats:**
- **Skip**: Shows only "Skip" (no segment type or duration)
- **Skip + Type**: Shows segment type, e.g., "Skip Intro" or "Skip Recap"
- **Skip + Type + Duration**: Shows segment type and duration, e.g., "Skip Intro (29s)" or "Skip Recap (1m15s)" (default)

**How to Change:**
1. Go to `Settings → Add-ons → My Add-ons → Services → Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Select your preferred "Skip Button Format"
4. Changes apply immediately for new skip dialogs

**Examples:**
- Format: "Skip" → Button shows: `Skip`
- Format: "Skip + Type" → Button shows: `Skip Intro`
- Format: "Skip + Type + Duration" → Button shows: `Skip Intro (29s)`

---

📝 Dynamic Segment Type Display

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

🚫 Hide Close Button Option

You can now hide the Close button and its icon to create a minimal skip dialog with only the Skip button:

**Features:**
- **Minimal Interface**: Removes both the Close button and close icon
- **Full-Width Skip Button**: When enabled, the Skip button expands to 350px width with centered text
- **Smart Positioning**: Button starts at left=30px when skip icon is visible, or left=5px when skip icon is hidden
- **Cleaner Look**: Only the Skip button remains visible
- **Still Closable**: Dialog can still be closed using ESC/Back actions

**How to Enable:**
1. Go to `Settings → Add-ons → My Add-ons → Services → Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Toggle "Hide Close Button" on
4. Changes apply immediately for new skip dialogs

**Note:** When the Close button is hidden, you can still dismiss the dialog using:
- ESC key
- Back button on remote/keyboard
- The dialog will auto-close when the segment ends

---

🎨 Hide Skip and Close Icons Option

You can hide both the skip icon and close icon while keeping the buttons visible:

**Features:**
- **Icon-Free Interface**: Removes both icons, leaving only the text buttons
- **Balanced Layout**: When skip icon is hidden, the close icon is automatically hidden too for visual balance
- **Button Visibility**: Both Skip and Close buttons remain fully functional

**How to Enable:**
1. Go to `Settings → Add-ons → My Add-ons → Services → Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Toggle "Hide Skip and Close Icons" on
4. Changes apply immediately for new skip dialogs

**Behavior:**
- When skip icon is hidden, the close icon is automatically hidden as well
- This ensures a balanced appearance when icons are disabled
- All button functionality remains unchanged

---

📐 Button Text Centering

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

🚫 Hide Segment Ending Text Option

You can hide the countdown text line that shows "Segment ending in:" or "Intro ending in:":

**Features:**
- **Cleaner Interface**: Removes the countdown text line
- **Minimal Display**: Only buttons and progress bar remain visible
- **Flexible Control**: Can be combined with other visibility options

**How to Enable:**
1. Go to `Settings → Add-ons → My Add-ons → Services → Skippy`
2. Navigate to "Customize Skip Dialog Look and Behavior"
3. Toggle "Hide segment ending in text" on
4. Changes apply immediately for new skip dialogs

---

⚙️ Enable/Disable Skipping for Content Types

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

📁 File Support
Skippy supports the following segment definition files:

filename.edl

filename-chapters.xml

filename_chapters.xml

These should reside in the same directory as the video file. EDL files follow Kodi’s native format with start, end, and action code lines. XML files use a chapter-based structure. See section below.

---

🧩 File Example
Breaking.Bad.S01E02.mkv
├── Breaking.Bad.S01E02-chapters.xml or Breaking.Bad.S01E02_chapters.xml    # XML chapter file
└── Breaking.Bad.S01E02.edl                                                 # Fallback if no XML found

XML takes priority if both exist.

---

📁 Metadata Formats
Skippy supports two segment metadata formats, placed alongside the .mkv or video file:

1. ✅ XML Chapter Files (Preferred)
- Filenames: filename-chapters.xml or filename_chapters.xml
- Format: Matroska-style (e.g. exported by Jellyfin)
- Label: `<ChapterString>Intro</ChapterString>`
- Configurable behavior per label: auto-skip / ask to skip / never

2. ✅ Enhanced EDL Files (Fallback)
- Filename: `filename.edl`
- Format: <start_time> <end_time> <action_type> ;label=Intro (or set preferred label in the settings.xml)
- Configurable behavior per label: auto-skip / ask-to-skip / never (shares the same label settings as the xml route)

📄 Sample Segment Files
EDL files define skip segments using three values per line

🧾 .edl File Content Example:
210 235 4 

→ Will skip or prompt from 3:30 to 3:55 if action type `4` is mapped to `'Intro'` 
Format: <start_time> <end_time> <action_type>. start_time and end_time are in seconds. <action type> is an integer between 4 to 99
Action mapping: action_code maps to a label via edl_action_mapping (e.g. 4:intro, 5:credits)


ℹ️ Kodi may log a warning for unknown EDL action types — this is expected and harmless.

Custom action types (4–99) are supported and configurable via settings:
4 → Segment (default)
5 → Intro
6 → Ad, etc. — 

Optional label support using comments:
42.0 58.3 4 ;label=Intro

If no label is present in edl file or defined in settings, 'Segment' is used as fallback

📘 .xml Chapter Format
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

🧩 File Example
Breaking.Bad.S01E02.mkv
├── Breaking.Bad.S01E02-chapters.xml or Breaking.Bad.S01E02_chapters.xml    # XML chapter file
└── Breaking.Bad.S01E02.edl                                                 # Fallback if no XML found

XML takes priority if both exist.

---

✅ Segment Behavior Logic Summary

**Skip Enable/Disable Settings:**
- `enable_skip_movies`: Master control for skipping in movies
- `enable_skip_episodes`: Master control for skipping in TV episodes

When skipping is disabled for a content type, no segments will be processed (no auto-skip, no dialogs, no prompts).

**Dialog Enable/Disable Settings:**
- `show_skip_dialog_movies`: Controls dialog display for movies (requires `enable_skip_movies = True`)
- `show_skip_dialog_episodes`: Controls dialog display for episodes (requires `enable_skip_episodes = True`)

|Behavior	        | Skip Enabled + Dialogs Enabled	       | Skip Enabled + Dialogs Disabled | Skip Disabled |
|-----------------|----------------------------------------------|-----------------------------------------|-------------------|
|never	           | ❌ Skip silently	                           | ❌ Skip silently                        | ❌ Skip silently |
|ask	             | ✅ Show dialog	                              | ❌ Suppress dialog                      | ❌ Skip silently |
|auto	            | ✅ Skip automatically	                      | ✅ Skip automatically                   | ❌ Skip silently |

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
|--------------------------|----------------------|-----------------------------------|----------------------------|
| ✅ True                  | ✅ Yes               | ✅ Yes                            | ❌ No                      |
| ✅ True                  | ❌ No                | ✅ Yes                            | ✅ Yes                     |
| ❌ False                 | ✅ Yes               | ✅ Yes                            | ❌ No                      |
| ❌ False                 | ❌ No                | ✅ Yes                            | ❌ No                      |
| ❌ False                 | ❌ No                | ❌ No                             | ❌ No                      |
| ✅ True                  | ❌ No                | ❌ No                             | ❌ No                      |
| ❌ False                 | ✅ Yes               | ❌ No                             | ❌ No                      |

**Segment Skip Toast Behavior:**
| Segment File Present | Segment Skipped | Show Segment Skip Toast Enabled | Show Segment Skip Toast? |
|---------------------|-----------------|---------------------------------|--------------------------|
| ✅ Yes              | ✅ Yes          | ✅ Yes                         | ✅ Yes                  |
| ✅ Yes              | ✅ Yes          | ❌ No                          | ❌ No                   |
| ✅ Yes              | ❌ No           | ✅ Yes                         | ❌ No                   |
| ✅ Yes              | ❌ No           | ❌ No                          | ❌ No                   |
| ❌ No               | ❌ No           | ✅ Yes                         | ❌ No                   |
| ❌ No               | ❌ No           | ❌ No                          | ❌ No                   |

---

🚀 Usage Examples
✅ Auto-skip
If your chapters.xml contains:

<ChapterString>Intro</ChapterString>

And you've configured "Intro" to auto-skip, the addon will jump past it without prompting.

❓ Ask to skip
If your .edl file contains:

0.0 90.0 9
And action code 9 maps to "Recap", and "Recap" is mapped to the "Ask to skip" setting, you'll be prompted to skip it.


🔕 Never skip example
If your segment label is "Credits" and you've mapped "Credits" to the "Never skip" setting, playback continues uninterrupted with no skip popup.

---

🍿 Toast Notification Behavior
- Appears when a video has no matching skip segments


Cooldown enforced per playback session (default: 6 seconds)

- Resets on video stop or replay after cooldown

---

### 🎛️ EDL Action Filtering

Skippy supports optional filtering of Kodi-native EDL action types (`0`, `1`, `2`, `3`). This allows users to ignore internal skip markers and rely only on custom-defined segments.

#### 🔧 Setting
- **Name:** `ignore_internal_edl_actions`
- **Type:** Boolean
- **Default:** `true`

#### ✅ Behavior
| Setting Value | Action Types Parsed         | Result                                                          |
|---------------|-----------------------------|-----------------------------------------------------------------|
| `true`        | Only custom actions (`>=4`) | Internal Kodi skip markers are ignored                          |
| `false`       | All action types            | Autoskip or prompt for all segments, including Kodi-native ones |

#### 📝 Example EDL
```xml
237.5    326.326    5    <-- intro
1323.45  1429.184   8    <-- recap
```
---

🔁 Ignore Overlapping Segments
Skippy now supports configurable overlap detection to help avoid redundant or conflicting skips. This feature ensures that segments which overlap in time are handled according to your preference.

⚙️ Setting: Ignore overlapping segments
Location: settings.xml → Segment Settings

Type: Boolean toggle (true / false)

Default: true

🧠 What It Does

**When Enabled (true):**
Skippy will skip any segment that overlaps with one already accepted. This is useful when:
- EDL or chapter files contain redundant entries
- Multiple tools or sources generate overlapping metadata
- You want to avoid double prompts or conflicting skips

**When Disabled (false):**
Skippy intelligently handles overlapping and nested segments with smart skip behavior:

### 🔗 Nested Segments (One segment fully inside another)
Example: Intro (0-50s) with Recap (20-40s) nested inside
- **Intro dialog** appears at 0s: Shows "Skip to Recap at 00:20"
- **Recap dialog** appears at 20s: Shows "Skip to remaining intro at 00:40"
- **Intro dialog** reappears at 40s: Shows normal skip (no nested segments remaining)

### 🔄 Partially Overlapping Segments
Example: Segment A (45-133s) overlaps with Segment B (50-160s)
- **Segment A dialog** appears at 45s: Shows "Skip to Segment B at 00:50"
- **Segment B dialog** appears at 50s: Shows "Skip to end of Segment B at 02:40"

### 🛡️ Race Condition Prevention
- Only one dialog appears at a time
- Parent segment dialogs are suppressed while nested/overlapping segments are active
- Parent dialogs automatically reappear after nested segments are completed

📊 Example Scenarios

**Scenario 1: Overlapping Segments**
```xml
Segment A: 45.5 → 133.175
Segment B: 50.0 → 160.0
```

Behavior:
| Setting Value | Result                                       |
|---------------|----------------------------------------------|
| true          | Segment B is skipped entirely                |
| false         | Smart progressive skipping: A → B → end of B |

**Scenario 2: Nested Segments**
```xml
Intro: 0 → 50s
Recap: 20 → 40s (nested inside Intro)
```

Behavior:
| Setting Value | Result |
|---------------|--------|
| true | Recap is skipped entirely |
| false | Progressive flow: Intro → Recap → remaining Intro |

🧪 How to Test
Enable verbose logging in settings.

Toggle Ignore overlapping segments on/off.

Observe logs like:

**When enabled:**
```xml
⚠ Overlapping segment detected: 50.0–100.0 overlaps with 45.5–133.175
🚫 Skipping overlapping segment: 50.0–100.0 | label='segment'
```

**When disabled:**
```
🔍 Detected NESTED segment: 'recap' (20.0-40.0) is nested inside 'intro' (0.0-50.0)
🔗 Setting jump point for nested 'recap' to 40.0s (remaining intro)
🔗 Setting jump point for 'intro' to 20.0s (nested segment 'recap')
```

---

🚨 Logging

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
- ✅ Logs when a new segment becomes active
- ✅ Logs when playback type changes
- ✅ Logs when state counts change (prompted, dismissed, etc.)
- ❌ Doesn't log "segment not active" every second for inactive segments
- ❌ Doesn't log "already prompted" repeatedly for the same segment

**Enable via `enable_verbose_logging` for full insight.**

**Troubleshooting Device Limitations:**
When verbose logging is enabled, Skippy will log when dialog or toast creation fails with messages like:
- `❌ Failed to create skip dialog (possible Kodi/device limitation)`
- `❌ Failed to display toast notification (possible Kodi/device limitation)`

This helps identify when Kodi stops creating UI elements due to memory or resource constraints on resource-limited devices (e.g., Amlogic/CoreELEC).

---

🔄 Batch EDL Action Type Normalizer (Windows)
Located in tools/edl-updater.bat:

Updates all .edl files under a folder recursively

Replaces old action types with new ones (e.g. 3 → 4)

User can specify which action type to look for and which action type to replace with in accordance with user specifications in the settings.xml file.

Ensures full compatibility with Skippy’s behavior mappings

---

🧾 License & Credits
Not affiliated with Jellyfin, Kodi, MPlayer or Matroska

white.png background courtesy of im85288 (Up Next add-on)

___________________________________________________________________________________


🧼 Developer Notes
- UI driven by WindowXMLDialog
- EDL action types 0 and 3 (Kodi-native) are ignored by Skippy. Use batch tool to convert to other action types.
- Only -chapters.xml and _chapters.xml and .edl files are scanned

---

🧑‍💻 Contributors
jonnyp — Architect, debugger

