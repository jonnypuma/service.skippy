# Changelog

All notable changes to Skippy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

