# Skippy (service.skippy) — project notes for Claude

Kodi add-on (Python 3, `xbmc.python 3.0.0`) for timed video segments: intros, recaps, credits, ads and user-defined types. Read `README.md` for the feature list. There is no compiled build and no database server; see the sections below for what stands in for each.

## Rules that always apply

- **Bump the version whenever anything is changed, added or fixed.** The version lives only in `addon.xml` (`<addon ... version="X.Y.Z">`) and `CHANGELOG.md` (newest section on top, `## [X.Y.Z] - YYYY-MM-DD`). Every bump needs a changelog entry. Each number goes 0–9 (7.1.9 → 7.2.0). **Never mention version numbers in `README.md`.**
- Toast text is never truncated and never gets a second overlay: Kodi's toast scrolls long text itself.
- A native toast must never be force-closed without `unstick_toast()` (`_dismiss_toast` does it) and every post goes through `ready_toast_window()`: Kodi shows the next queued toast only once the message fade label has scrolled through, and a closed window does not scroll, so a toast closed early blocks all later toasts until Kodi restarts (the invisible OK catcher still answers).
- Non-English strings are written by hand (no translation service); keep placeholders (`%s`, `%d`, `\n`, `\"`) identical to English.
- Do not reproduce or paste secrets (Kodi web password, API keys) into files or chat.

## Build

There is nothing to compile. The "build" is regenerating derived files, then packaging the add-on folder as a zip (the GitHub zip must **include** the screenshots; they are shown in the Kodi add-on info page — keep `.gitattributes` so they are not export-ignored).

Run generators from the add-on root:

| Command | What it does |
|---|---|
| `python3 tools/gen_settings_v1.py` | Regenerates `resources/settings.xml` (Kodi settings v1). Edit the generator, not the XML. Setting levels (0 Basic … 3 Expert) are defined there. |
| `python3 tools/gen_skin_1080i.py` | **720p is the source of truth.** Reports drift between `skins/default/720p` and `1080i` (1080i = ×1.5, rounded half up). `--write` only creates missing 1080i files; `--overwrite` regenerates every non-`MANUAL` file (changes hand-tuned values by up to 1 px — review the diff). Exit code 1 when drift is found. Files ending `-Jon.xml` are personal variants; leave them alone. |
| `python3 tools/gen_preset_textures.py` | Flat / glass / outline / underline button focus textures. |
| `python3 tools/gen_button_focus_nine_slice.py` | Rebuilds the 9-slice focus textures. |
| `python3 tools/gen_minimal_plate_variants.py` | Pre-renders Minimal plates per width into `media/plates/`. |
| `python3 tools/gen_progress_tiled_textures.py` | Pre-renders the segmented progress bar per bar height (`progress_tiled_*_h<N>.png`). |

Layout changes: edit `720p`, then run `gen_skin_1080i.py` (add `--overwrite` only when you mean it). The user runs 1080i.

Strings: add the new id to `resources/language/resource.language.en_gb/strings.po`, then to every other folder under `resources/language/` (10 languages). Folder names must be Kodi's language add-on ids (`resource.language.de_de`, `resource.language.pt_br`, ...), never English names such as `German`: Kodi 23 nightlies no longer find those, and then every settings label is blank (`tests/test_language_pack_sync.py` guards this). Ids used so far reach 48046 (47000-47154 is the Next episode block; 48000-48046 statistics per title, Current video and binge mode). `addon.xml` also carries translated `<summary>` / `<description>` per language.

Do not add files named `_*.png`, `tools/_*.py` or `*-Jon.*` to commits — they are scratch/personal files.

## "Database" and migrations

Skippy has no SQL database. Persistent data is:

- Kodi add-on settings (`resources/settings.xml` ↔ `addon_data/service.skippy/settings.xml`).
- JSON files in `addon_data/service.skippy/` handled by `skippy_profile_store.py`: segment-type catalog, per-title auto-skip rules, statistics, upload fingerprints, saved skip-dialog presets.
- Sidecar files next to videos: `.edl` and Matroska-style `*_chapters.xml`.

Migration rules when changing any of that:

- Settings keys: never rename or reuse an id without reading the old value on first run. `segment_types.migrate_from_legacy_settings` shows the pattern (first 7.0 run converts old settings into the catalog).
- Profile JSON: keep reads tolerant (missing keys → defaults); never drop unknown keys on write.
- Backups: `settings_backup.py` and `skippy_profile_backup.py` import older backups (the profile backup also reads the old upload-history-only files). Keep older formats importable and cover changes with tests.
- Saved presets are matched **by values** (`detect_preset`), so two built-in presets with identical values break apply → detect.

## Tests

Offline unit tests with Kodi stubbed (`tests/kodi_stubs.py`); no Kodi needed. From the add-on root:

```
python3 -m unittest discover -s tests -t .
```

Run one module: `python3 -m unittest tests.test_skin_resolution_sync`. Always run the full suite before finishing (about 1,700 tests, under half a minute).

`tests/test_lint_undefined_names.py` fails on any name a module uses but never defines or imports (a standard-library check that always runs, plus pyflakes when it is installed). Tests that touch sidecar or keymap files use `tests/fake_vfs.py`, a stand-in for `xbmcvfs` that reads and writes a temp folder (it can also fail writes and skip truncation, like a network share). `tests/test_setting_defaults_match.py` fails when a default written in the code (`addon_get_bool(addon, key, default)` and friends) differs from `resources/settings.xml`; change both together.

`tests/test_strings_used_exist.py` fails when the code asks for a string id (`get_localized`, `getLocalizedString`, `_T`, `_t`) that is missing from a language, or whose placeholders differ from English. Dialogs built in Python (`skippy_editor_modal_skin.py`, `segment_editor_dialog.py`) are tested through `tests/fake_gui.py`, a stand-in for `xbmcgui` that keeps labels, focus, scrolling and positions; `fake_gui.load(module, test)` imports a fresh copy of a module against it.

Notable guards: `test_language_pack_sync.py` (every language has the same ids and English `msgid`s), `test_skin_resolution_sync.py` (1080i matches 720p, label offsets), `test_skip_dialog_presets.py` (apply → detect round trip), `test_progress_tiled_bar.py`.

### Lint and coverage

Run these before finishing a change that touches Python (install once with `pip install --user pyflakes vulture coverage`):

| Command | Expect |
|---|---|
| `python3 tools/lint.py` | Exit 0, nothing printed. It runs pyflakes over every `.py` file except `-Jon` and `tools/_*` scratch files, and skips re-exports marked `# noqa: F401` (the `remote_segments.py` facade and friends). An undefined name is a crash waiting for its code path (`tests/test_lint_undefined_names.py` also catches those); unused imports and variables get removed. |
| `python3 -m vulture . --exclude '*-Jon*' --min-confidence 80` | Nothing. Below 80 it lists Kodi callbacks (`onInit`, `onClick`, `onAction`, `onNotification`), which Kodi calls by name. |
| `python3 -m coverage run --source=. --omit='tests/*,tools/*' -m unittest discover -s tests -t .` then `python3 -m coverage report` | Total does not drop (64% after 7.11.6). New code that writes files or talks to a server gets a test that runs it. |

## Verifying in Kodi

Python and skin XML are cached by Kodi: after changing Python or a skip-dialog XML, restart Kodi, or disable then enable the add-on from its info page. The Full skip dialog must open from the add-on path: the textures it gets from window properties and from Python (`setImage`) are bare file names that Kodi looks up in the `media` folder next to the XML it loaded. Opening it from a copy elsewhere loses them (tried in 7.11.6, reverted). The Customize modal reloads its own XML each time it opens. A running service does not pick up `.py` edits.

Skip-dialog notes learned the hard way:

- Skip/Close buttons are repositioned from Python (`skip_dialog_appearance.py`) when the dialog opens, so skin `<left>/<top>` values are only defaults.
- The Customize skip dialog and Customize next episode popup screens share one look: navy panel, tinted rows with a rounded teal highlight, the name of a row at the left and its value at the right (`setLabel(label=…, label2=…)`), the same footer buttons. A change to the look of one goes into the other; `tests/test_skip_customize_style.py` compares their skin files. The small list / message windows (Statistics, Manage saved auto-skips, Manage autoplay by show and the choices and confirmations inside them) use the same look through `SkippyPanel.xml` + `skippy_panel_ui.py`; `tests/test_skippy_panel.py` compares it with the next episode screen. Those fall back to the grey editor dialogs (`skippy_editor_modal_skin.py`) and then Kodi's own if the panel cannot open. Do not run `gen_skin_1080i.py --overwrite` to add a file: it rewrites the hand-tuned 1080i skip dialog files (use `--write`).
- Kodi ignores `<textoffsety>` on buttons with `<aligny>center</aligny>`; the Customize preview uses label controls and is nudged in Python (`preview_label_nudge`).
- Python writes to add-on settings do not refresh an open settings page.
- The seek bar (`Player.HasPerformedSeek`) cannot be suppressed from an add-on; the optional `Skippy.Skipping` Home property needs a per-skin edit (see README).
