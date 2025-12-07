<img width="1200" height="1200" alt="icon" src="https://github.com/user-attachments/assets/822f7386-ce10-48e7-bb6f-ee90bfdb0a02" />

# 📼 Skippy — The XML-EDL Segment Skipper

Skippy is a Kodi service that detects and can skip predefined video segments such as intros, recaps, ads, or credits using companion `.xml` or `.edl` files. 

Supports chaptered Matroska XMLs, enhanced EDLs with labeled action types.
 
It provides both automatic and user-prompted skipping, and integrates seamlessly into playback with customizable notifications and dialogs.

Discreet, cross-platform, and customizable.

Supported Video Formats: Works for MKV and AVI containers.

Known Limitations: Video files in MP4 containers are currently not working, seems to be a Kodi issue and not addon issue.

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
│           │   ├── SkipDialog.xml              # Default fallback skip dialog located bottom right
│           │   ├── SkipDialog_TopRight.xml     # Skip dialog located top right corner
│           │   ├── SkipDialog_TopLeft.xml      # Skip dialog located top left corner
│           │   ├── SkipDialog_BottomRight.xml  # Skip dialog located bottom right corner
│           │   └── SkipDialog_BottomLeft.xml   # Skip dialog located bottom left corner
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
Tested on **Kodi Omega 21.2** across:

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
- 🖼️ Skip Dialog Placement: Choose dialog layout position (Bottom Right, Top Right, Top Left, Bottom Left)
- ⏪ Rewind detection logic: Resets skip prompts only on significant rewinds — with a user-defined threshold.
- 📺 Toast segment file not-found notification filtering: Notifies when no segments were found for the current video. Toggle on/off for movies or TV episodes. Supports per-playback cooldown (default: 6 seconds)
- 🧹 Debug logging: Verbose logs for each segment processed and decision made. Toggle on/off.

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
| skip_overlapping_segments   | Configurable overlap detection to help avoid redundant or conflicting skips   |

|Category:                    | Customize Skip Dialog Look and Behavior                                       | 
|-----------------------------|-------------------------------------------------------------------------------|
| show_progress_bar			      | Enables visual progress bar during skip dialog                                |    
| skip_dialog_position	    	| Chooses layout position for the skip confirmation dialog                      |
| button_focus_style          | Choose visual style for focused buttons in skip dialog (Default, Aqua, Aqua Bevel, Aqua Dark, Aqua Vignette, Aqua Rounded, Blue) |
| rewind_threshold_seconds	  | Threshold for detecting rewind and clearing dialog suppression states         |
| show_skip_dialog_movies	    | Show skip dialog for movies when behavior is set to ask	                      |
| show_skip_dialog_episodes	  | Show skip dialog for TV episodes when behavior is set to ask                  |

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
|Behavior	        | Dialogs Enabled (show_dialogs = True)	       | Dialogs Disabled (show_dialogs = False) |
|-----------------|----------------------------------------------|-----------------------------------------|
|never	           | ❌ Skip silently	                           | ❌ Skip silently                        |
|ask	             | ✅ Show dialog	                              | ❌ Suppress dialog                      |
|auto	            | ✅ Skip automatically	                      | ✅ Skip automatically                   |

If show_skip_dialog_movies = False, then dialogs will be suppressed for movie segments even if their behavior is "ask".

If show_skip_dialog_episodes = False, then dialogs will be suppressed for episode segments with "ask" behavior.

This suppression is independent of the segment file presence or toast settings.

✅ Example
If a segment in a movie has behavior "ask" and show_skip_dialog_movies = False, the dialog will not appear. Instead, the segment will be silently skipped or ignored depending on other settings.

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

🔁 Skip Overlapping Segments
Skippy now supports configurable overlap detection to help avoid redundant or conflicting skips. This feature ensures that segments which overlap in time are handled according to your preference.

⚙️ Setting: Skip overlapping segments
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

Toggle Skip overlapping segments on/off.

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
Verbose logging reveals:

- Parsed segments and labels
- Playback state and detection
- Toast decision logic and suppression
- Skip dialog flow and user choice
- Overlapping/nested segments
- Enable via enable_verbose_logging for full insight.

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
- EDL action types 0 and 3 (Kodi-native) are ignored
- Only -chapters.xml and _chapters.xml and .edl files are scanned

---

🧑‍💻 Contributors
jonnyp — Architect, debugger


