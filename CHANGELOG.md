# Changelog

## [7.13.0] - 2026-11-12

### Added

- **Skin integration properties.** While a video plays, Skippy sets Home window properties a skin can read: `Skippy.HasSegments`; the segment the playhead is in (`Skippy.Segment.Type`, `.TypeId`, `.Mode` with what Skippy will do after per-title choices and binge mode, `.Start`, `.End`, `.Remaining`, `.RemainingSeconds`, `.Progress`); the next segment (`Skippy.Segment.Next.Type`, `.Next.Start`); and the next episode (`Skippy.NextEpisode.Label`, `.Thumb`, `.Due`). Values are written only when they change and cleared when playback stops; skins that do not read them are unaffected. The README has a table and skin XML examples.
- **`RunScript(service.skippy,skip_current)`** skips the segment the playhead is in, like an auto-skip (jump offset, statistics, toast), within a second. For a skin's own skip button, or a key in a keymap.
- **A skin can draw its own skip button.** When the skin sets `Skippy.SkinSkipButton` to `true` on the Home window, Skippy opens no dialog for **Ask** segments; **Always** segments are still skipped. Clearing the property brings the dialog back.
- 12 tests: the properties inside, between and without segments, nested segments, the next episode, writing only changes, the skin button replacing the dialog, skip_current (fresh, outside a segment, too old), the cached modes, and the RunScript command.

## [7.12.0] - 2026-11-12

### Added

- **Binge mode** (**Segment Settings → Binge mode**, off by default). Episodes of one show played one after the other make a run: the first episode plays its intro, and from the second on the intro is skipped without asking. **Also skip the recap** (on by default) skips the recap from the second episode too; the first keeps it. It does not matter how the next episode starts (Play now, the autoplay countdown, a playlist, Kodi's own play next video or by hand). A run ends when another show or a film plays, or after **End the run after a pause of** minutes with nothing of the show on screen (Advanced, default 10). Shows are told apart by Kodi's library id, else the show title, else the folder above the episode (`Season 01` folders skipped).
- **Time saved per show or film** in the Statistics window, most time saved first (the 25 biggest, the rest summed in one line). Kept in `statistics.json`, included in the profile backup and merged on restore. Skips recorded before this version count in the totals only.
- **Current video** (**Debug Logging**, also `RunScript(service.skippy,show_diagnostics)`): where the playing video's segments came from (sidecar, online, embedded chapters, none) and which files or services, each segment with what it will do (Skip automatically, Ask, Never skip) and why when something other than its segment type decided (binge mode, a per-title choice, skipping turned off), the binge run, and the last error the playback loop hit, with its time.
- 34 new strings in all 11 languages, and 35 tests (binge runs and decisions, the skip loop with binge mode, show and film identity, per-title statistics, the Current video window and what the service mirrors for it).

## [7.11.6] - 2026-11-12

### Fixed

- **Saving online segments with Merge or Update no longer stops the video's segments from loading.** With **Existing sidecar** set to **Merge with existing**, **Update** or **Update all** (no prompt or ask first), and a sidecar beside the video that differed from the online data, the save failed with an internal error. That error ended Skippy's check for the video, so its segments were never loaded and no skip dialog appeared for it, every time it played. A helper was left out when the save code was split into modules in 7.0.0. The default policy, **Skip if exists**, was not affected.
- **"Still watching?" now counts the episodes Kodi starts by itself.** An episode that played to its end and was followed by the next one from a playlist or Kodi's own **Play next video** reset the count to zero, so the question only came after episodes Skippy's automatic play had started. The video that ended is now looked at before the count is updated. Starting the same video over still starts the count over.
- **A new video starts with no segments of the one before.** For the first second of a new video, Skippy still held the previous video's segments. With **Start at the credits** on, a new episode resumed near its end could get its next episode prompt at the previous episode's credits time.
- **The Segment Editor no longer drops the rows after a bad EDL row.** A row whose end came before its start stopped the editor reading the rest of the file, so saving from the editor wrote the file back without those rows. The row is now skipped and the rest is read, as the playback side already did.
- **The Segment Marker can add to every chapters.xml Skippy can read.** A file with a blank line before its XML declaration or a second declaration (both seen in the wild) was read fine during playback but made the marker fail to save into it.
- **Episodes numbered 100 and up are recognised from the file name.** For files outside the library, `Show.S01E105.mkv` was read as episode 10, so online segments were looked up for the wrong episode. Seasons and episodes of up to four digits are read now.
- **A failed save to an NFS share no longer lands in the share's root folder.** When writing a sidecar beside a video on an `nfs://` path failed, Skippy tried other spellings of the path, and the last one was the share's root, so the .edl or chapters.xml could end up in the wrong folder, away from the video. Only the path itself and the same path without the export name (for servers that publish the share under a shorter name) are tried now.
- **An unknown `RunScript(service.skippy, …)` command no longer marks a segment.** Any argument Skippy did not recognise (a typo in a keymap or skin, a command from an older or newer Skippy, or another add-on calling it) fell through to the Segment Marker and marked a segment at the playhead. It is now written to the log and ignored. `RunScript(service.skippy)` with no argument, as the marker key sends it, still marks.
- **Online lookups find the right title when several share a name.** The TMDB title search took its first result, so a remake (*Dune*, 1984 or 2021), a reboot (*Doctor Who*, 1963 or 2005) or a same-named show from another country (*The Office*, UK or US) could get another title's segments. Skippy now passes the year from the library or the file name, prefers an exact title from that year (one year either side for release-date differences), and searches again without the year when that finds nothing.
- **The defaults in the code now match the settings.** When Skippy cannot read a setting (for a moment during an add-on update, or when a value is empty), it uses the default written in the code. For 14 settings that default differed from the one in the settings screen: **Enable Skip for Movies / Episodes**, **Show Skip Dialog for Movies / Episodes**, **Enable toast notification for skipped segment**, **Enable missing segment file toast for TV Episodes**, **Ignore unmapped EDL actions**, **Skip dialog text in ALL CAPS**, **Hide Close Button**, **Combined skip and progress**, **Show Progress Bar in Skip Dialog**, **Skip dialog mode** (Compact Full), **Skip Button Format** (Skip + Type) and **Button Focus Style** (flat teal).

### Changed

- **The choices in the settings are translated.** Positions (**Bottom Right**…), save formats and existing-file policies, skip button and duration formats, dialog modes and styles, source priorities, file permissions, press types, log levels and the like showed in English in every language. These 56 choices now use strings in all 11 languages. Names of looks, colours and textures (**Aqua Bevel**, **Neon Pink**…) stay as they are, as do the service names TheIntroDB.org and IntroDB.app.
- **The online save preview and the keymap messages are translated.** The window that shows what an online save would change in a sidecar (counts per source, overwrite and update comparisons, the local → online lines) and the messages after installing or removing the marker and editor keymaps were English in every language. They now use 21 new strings in all 11 languages.
- **The playing file is checked once, not every second.** Skippy confirmed that the playing file exists on every tick of playback; on NFS or SMB each check is a network request. It now checks once per playback and again only when another file starts. A path it cannot reach is written to the log once instead of every second.
- **Hide OSD display during skip is on by default and shown at the Standard settings level.** Skins that read `Skippy.Skipping` (Glass Aeon, for one) hide the seek bar during Skippy's skips without a trip to the Advanced settings; skins that do not read it are unaffected. A value you set yourself is kept.
- **Seven settings help texts are translated.** **Ignore unmapped EDL actions**, **Ignore overlapping segments**, the rewind threshold, the three missing or overlapping sidecar toasts and **Enable toast notification for skipped segment** showed their help in English in every language. They now have strings in all 11 languages.
- **The add-on page in Kodi describes the next episode prompt** in all 11 languages, and lists the licence (MIT), the source repository and recent changes (shown in Kodi's update dialog).
- **Only Skippy's own notification opens the Segment Editor.** Any add-on notification whose data contained the words `open_segment_editor` used to open it; now only a notification whose method ends in `open_segment_editor` does.
- **The skip dialog logs less.** Two lines written at every skip dialog (dialog opened, text colour) now appear only with detailed logging on.
- Removed 17 strings nothing used any more (old preset names and messages), from all 11 languages.
- **Stale code removed.** Two modules nothing used (`upload_history_backup.py`, replaced by the profile backup, which still reads old upload-history files; `segment_editor_window_ui.py`), 15 functions and constants with no caller, a unit test block inside `segment_item.py`, about 175 unused imports, leftover variables and five one-off scripts in `tools/` that had already been applied. Tests that only checked the removed row texts now check the panel rows that replaced them.
- **Personal and scratch files are out of the repository.** The `-Jon` variants (settings, strings, skip dialog skins, `service-Jon.py`, `skipdialog-Jon.py` and others), the `_*.png` previews and 65 `.pyc` files were tracked although `CLAUDE.md` says to keep them out of commits, so the `-Jon` files shipped in the add-on zip. They stay on disk, are no longer tracked, and `.gitignore` and `.gitattributes` keep them out. The empty `online_upload_submissions.json` at the root (the real file lives in the profile folder) is no longer tracked.
- Internal: one `normalize_label` and one sidecar detail logger instead of copies in several modules; no bare `except:` left in the skip dialog; the TheIntroDB API description is left out of the add-on zip again (the rule named an older file).

### Added

- **More tests, about 130 of them, on what was least tested.** Reading and writing .edl and chapters.xml on a real folder (including failed writes, network shares that do not truncate, backups and deleting), every Segment Marker policy on both file types, the online save preview text, the sync-to-online question, TMDB and library id lookups, online requests (back-off after errors, Retry-After, the API key kept out of the log), the keymap files, every settings button reaching its handler, and the per-title auto-skip choice during playback. Line coverage went from 52% to 60%. The undefined-name check now runs without pyflakes too, so it can no longer be skipped by a missing package.
- **Tests for the Segment Editor window and the editor's own dialogs**, about 120 of them, through a new stand-in for Kodi's dialog controls (`tests/fake_gui.py`): the segment list and its overlap marks, every list-row action (merge, split, fix overlap, snap, set to current time, edit, delete, undo), marking start and end, jumping and seeking, the buttons and keys, unsaved changes on exit, saving in each format and the online upload choice; and the Yes/No, OK and list-pick dialogs (every button, scroll limits, Back, focus, preselect). Coverage of `segment_editor_dialog.py` went from 7% to 73% and of `skippy_editor_modal_skin.py` from 9% to 83%; the whole add-on is at 64%. Also new: tests for the NFS paths, unknown commands, the TMDB year match, the once-per-playback file check, and that every string id the code asks for exists in all 11 languages with the same placeholders.
- **`tools/lint.py` and lint and coverage steps in `CLAUDE.md`.** `tools/lint.py` runs pyflakes over the add-on, skipping the deliberate re-exports, and fails on anything it reports; the leftover unused imports and variables in the tests and tools are gone, so it starts clean. `CLAUDE.md` lists it with vulture and coverage, and what each should show.
- Tests that write sidecars through every existing-file policy, a test that fails when a module uses a name it never defines (needs pyflakes), a test that fails when a default in the code differs from `settings.xml`, a test that only the method name opens the Segment Editor, and a test that every settings choice made of words uses a string that all 11 languages define.

## [7.11.5] - 2026-11-07

### Fixed

- **The native toast of the next episode prompt no longer stops every later toast.** After the **Play next episode?** toast had been used once, it did not appear on the next video any more, and neither did the native skip toasts for the recap or intro at the start of that video. Pressing OK still worked (the invisible key catcher was still there), so it moved on to the next episode with nothing on screen. The prompt was not hiding the skip dialogs: Kodi's own toast window was stuck.
  - The cause is in Kodi. It shows the next queued toast only when the message of the previous one has scrolled all the way through, and a window that is closed does not scroll. The prompt toast has a long message (**S01E02 · title · Press OK to play**) that scrolls, so closing it a few seconds after it appeared (OK, Back, or the end of the stretch) left the old message "not finished", and Kodi showed no toast at all until it was restarted.
  - Skippy now resets the message of the toast window every time it closes a toast, and again before it posts one while no toast is on screen. That also frees a toast window that was stuck before. The native skip toast uses the same code and is covered too.
  - The skip dialogs are held back only while the prompt of the episode that is playing is due (from the start of its window until that episode ends, as before), never at the start of the next one. Tests now cover Play now, a dismissed prompt and automatic play followed by the first minutes of the next episode: none of them is held.

## [7.11.4] - 2026-11-07

### Changed

- **Statistics, Manage saved auto-skips and Manage autoplay by show look like the Customize screens.** They were small grey dialogs with a column of plain buttons. They are now the same navy panel as **Customize skip dialog** and **Customize next episode popup**: tinted rows with a rounded teal highlight, white text with a shadow and the same footer buttons.
  - **Statistics** shows each figure as a row with its name at the left and its value at the right (**Time saved**, **Segments skipped**, each segment type under **Skips by segment type**, **Online segments downloaded** and **uploaded**), and **Counting since …** in small text under the rows. The rows scroll when there are many segment types. **Reset statistics** asks its question in the same panel.
  - **Manage saved auto-skips** lists each title with the types saved for it at the right (**Friends** · **Intro, Recap**). Choosing a title asks **Delete** or **Cancel** in the same panel; with nothing saved, it says so in the panel.
  - **Manage autoplay by show** (the same kind of list, so it is changed with them) shows each show with its choice at the right, and the choices inside it (**Play automatically**, **Ask first**, **Never offer**, **Forget this show**) and **Choose a show** (before the stock Kodi list) are in the same panel. Only the question that appears while a show plays (**Always play the next episode?**) is unchanged.
  - The panel is as high as what it shows, centred on the screen, with a scrollbar when the list is longer than the screen. Up and down move through the rows and on to the buttons; the headings between groups of rows are skipped. Both skin resolutions are done (the 1080i file is generated from the 720p one).
  - If the panel cannot open for any reason, the old grey dialogs open instead, so these screens never stay empty.
- **The two settings that choose the skip dialog are named like the ones for the next episode popup.** **Toggle mode** (Custom or Native) is now **Skip dialog style**, like **Popup style**, and **Skip dialog presets…** is now **Skip dialog look**, like **Popup look**. Only the names changed (translated in all 11 language packs); inside **Customize skip dialog** the row is still called **Preset**.

## [7.11.3] - 2026-11-07

### Fixed

- **The skip dialog preview now follows the segment type again.** In **Customize skip dialog**, changing **Preview type** (Intro, Commercial, Prologue…) changed the label but not the length of the button and card: they were all the same width. The lines under the button (**Commercial ending in: 01:07** and **Skip to Recap at 00:30**) had a fixed minimum width (190 and 280 px), and with **Skip + Type** that minimum was wider than any label, so it decided the width every time.
  - The minimum now comes from the text of those lines. A short type such as Intro gets a narrower card than Commercial, and a long one gets a wider card.
  - The same fixed minimum was too narrow for long types: **Commercial ending in: 0…** was cut off in the preview, and in the real dialog with **Skip** or **Skip + Type** as the button format. The ending line is now always shown in full (also in ALL CAPS and with long type names).
  - The same sizing applies to the real skip dialog, not only to the preview.
  - When the **Skip to … at …** line is shown (**Ignore overlapping segments** set to **No**), that line itself needs about 240 px, so the card is that wide for any short type; it only gets wider for a longer label.

## [7.11.2] - 2026-11-07

### Changed

- **The Customize skip dialog screen now looks like Customize next episode popup.** Same dark blue panel and dimming behind it, the same small blue heading, the same rows (a faint tint with a gap between them, white text with a shadow, a rounded teal highlight on the row you are on) and the same two-column rows: the name of the setting at the left and its value at the right, instead of one line like `Card opacity (%): 95`. **Save** and **Cancel** are the same kind of button as the ones in the other screen, side by side under the rows with the width of the rows. Nothing about what the screen does has changed: the same rows, the same order, the same keys.
  - The panel now ends right below **Save** and **Cancel**, as in the other screen, so a short list (Minimal mode) no longer leaves an empty grey slab under it. With many rows (Full mode with every option) the rows sit a little closer together, as before, and the panel still fits the screen.
  - The section headings (**Full mode**, **Minimal mode**) keep their blue and their place; the live preview on the right is unchanged.
  - Both skin resolutions are done (the 1080i file is generated from the 720p one as before). The row names are the same translated strings as before; they are just no longer joined to the value.

## [7.11.1] - 2026-11-07

### Changed

- **"Still watching?" no longer depends on automatic play.** **Ask if you are still watching** and **Episodes in a row before asking** used to show only while **Play the next episode automatically** (or autoplay per show) was on, and the question was only asked when Skippy was about to start the next episode by itself. Both settings now show whenever **Enable play next episode** is on, and the question works on its own.
  - Skippy counts the episodes that played one after another without a button press, whoever starts the next one: its own automatic play, Kodi's own **Play next video automatically**, or a playlist. After the chosen number, the prompt of the next hand-off is **Still watching?** (with **Continue** and **Stop**) in place of the usual prompt or the automatic start. With automatic play off and a limit of **1**, it replaces the usual prompt after every episode you pressed nothing during.
  - An episode counts as started by Kodi or a playlist when it begins within a minute of the previous one playing on to its last seconds without you answering its prompt. This is a best guess: **Play now**, **Close**, **Continue**, **Stop** and starting an episode yourself all start the count over, as does any button press during an episode.
  - **Stop**, or no answer, now stops playback a few seconds before the end for any source (before only a playlist), so Kodi's own play next video cannot carry on by itself. **Continue** stands that down.
  - **Continue** is only an answer to "still watching?", not a choice about the show, so it never leads to the "Always play the next episode?" question of **Remember autoplay per show**, with or without automatic play.
  - The help text of **Ask if you are still watching** says it works whether Skippy, Kodi or a playlist starts the next episode (translated in all 11 language packs).

## [7.11.0] - 2026-11-07

### Added

- **Popup size: Normal or Large.** The new setting **Popup size** (Standard level, shown while **Popup style** is **Custom**, right after **Popup position**) makes the next episode popup a quarter bigger, text included, for a TV you watch from far away. **Large** applies to the prompt, to the **Still watching?** question and to **Preview**. The popup grows from the corner it sits in, so its distance to the edges of the screen does not change and it still fits in all four corners. **Customize next episode popup…** has the same choice as a row after **Popup position**, and its mockup shows the size as you change it.
  - What the popup shows and where it sits are the same in both sizes; only the drawing is bigger. It is done by the skin (a zoom of the whole popup), so the text is the same font made bigger, a little softer than a real larger font would be.
  - The Customize screen now has 14 rows (one more), so the rows sit a little closer together.
  - The new setting, its help and the two values are translated in all 11 language packs. The 1080i skin is generated from the 720p one as before (the generator now also scales the centre of a zoom effect).

## [7.10.0] - 2026-11-07

### Added

- **The next movie of a collection.** When a movie that belongs to a Kodi collection (a movie set, for example a trilogy) is about to end, Skippy now offers the next movie of that collection, as it already did for the next episode of a show. Until now the feature only worked for TV episodes. The new setting **Offer the next movie in a collection** (Standard level, default **on**, next to **Mark the episode as watched when moving on**, shown while **Enable play next episode** is on) turns it off again.
  - The movies of the collection are taken in the order Kodi lists them: by year, then by sort title; movies without a year come last. A movie that is not in a collection, the last movie of its collection and a movie that is not in your video library get no prompt. The playlist still comes first: if the current playlist has an item after the movie, that is what is offered.
  - The popup and the toast ask **Play next movie?** and show the title with its year; the countdown reads **Movie ends in 00:42** or **Next movie starts in 00:20** (**Closing in 00:20** as before). The picture is the movie's landscape or fanart image, never its poster, because the picture box is wide.
  - The movie is started with **Resume a partly watched next episode** respected, the one you leave is marked as watched when Kodi did not (**Mark the episode as watched when moving on**), and **Skip episodes already watched** offers the next unwatched movie. **Seconds before the end**, **Start at the credits**, **Show the prompt for (seconds)**, **When the countdown ends**, **Play the next episode automatically**, **Ask if you are still watching**, **Hide skip dialogs during the prompt** and the popup style and look all apply to movies too. The choices per show do not apply to movies.
  - The new setting, its help, the two countdown lines and the heading are translated in all 11 language packs; the help of **Skip episodes already watched** now mentions movies.

## [7.9.0] - 2026-11-07

### Added

- **Never offer, per show.** **Manage autoplay by show** (shown while **Remember autoplay per show** is on) now has a third choice next to **Play automatically** and **Ask first**: **Never offer**. A show set to it gets no next episode prompt and no automatic start, even while **Play the next episode automatically** is on, and the skip dialogs keep working as they do without the feature (they are not held back for a prompt that never comes). Pick it when you choose a show in the list or when you add one with **Add a show...**; change or forget the choice there to get the prompt back, also while an episode is playing. The choice is saved with the other per-show choices and is part of **Back up profile data**. The new word and the extended help texts are translated in all 11 language packs.

## [7.8.1] - 2026-11-07

### Changed

- **Show the prompt for (seconds) can no longer be longer than Seconds before the end.** The prompt appears that many seconds before the end of the episode, so it cannot stay up longer. When you set the prompt time higher, or lower **Seconds before the end** below it, Skippy lowers the prompt time to the lead time and tells you in a short message. While **Start at the credits** is on nothing is limited, because the credits can start long before the usual time; a prompt time that is longer than what is left when the prompt appears simply runs to the end of the episode (this was always safe and still is). The help text of the setting says so too. The new message and the extended help are translated in all 11 language packs.

## [7.8.0] - 2026-11-07

### Added

- **A Looks… button in Customize next episode popup.** Between **Preview** and **Save** the screen now has a **Looks…** button that opens a menu:
  - **Reset to defaults** puts everything on the screen (style, look and the six parts changed on top of it, corner, picture, time left, progress bar, first-focused button) back to its default. Nothing is stored until you press **Save**, so **Cancel** still keeps what you had.
  - **Save this look…** stores the look on screen under a name you type. A saved look is the **Popup look** plus the six parts changed on top of it (text colour, heading colour, all caps, button highlight, progress bar style, card opacity); the corner, the rows shown and the first-focused button are not part of it. A look that is just one of the built-in looks, or that is already saved under another name, is not saved again (you are told which); the name of a built-in look is refused; saving over one of your own names asks first. Up to 50 looks can be saved.
  - Every look you saved is listed in the menu (the one on screen is ticked): pick one to load it onto the screen. Loading changes only the look and its six parts, so your corner, rows and first-focused button stay as they are. Like any change on the screen, nothing is stored until **Save**.
  - **Delete a saved look…** removes one after asking.
- Saved looks are kept in `next_episode_looks.json` in the add-on's profile folder and are included in **Back up profile data**; restoring adds the looks you do not have yet.
- The footer of the screen now has four buttons of the same size in a row. The new strings are translated in all 11 language packs.

## [7.7.0] - 2026-11-07

### Added

- **Video add-ons can tell Skippy what comes next (the Up Next signal).** Add-ons that support the Up Next add-on (Netflix, Jellyfin, Emby and others) announce the next episode with the `upnext_data` signal. Skippy now listens to it, so those add-ons work with the next episode prompt too, including videos that are not in your library. The announcement carries the next episode's title, numbering and picture and how to start it: a `play_url` Skippy opens, or `play_info` Skippy sends back to the add-on the way Up Next does.
- **The prompt now also works for playback Skippy otherwise ignores.** Add-on and stream URLs (`plugin://`, `http://`, `https://`) have no segments or library entry, so the skip dialogs still leave them alone. When the add-on announced a next episode for what is playing, the next episode prompt (or autoplay, the **Still watching?** guard, **Show the prompt for (seconds)** and **When the countdown ends**) runs for it as usual. Without an announcement nothing changes.
- **Start at the credits** also follows the add-on: when an announcement asks for a time (`notification_offset` or `notification_time`) and the episode has no Credits segment of Skippy's own, that time starts the prompt.
- **Use next episode info from other add-ons** (Advanced level, default **on**, shown with **Enable play next episode**) switches all of this off. The announcement wins over Skippy's own playlist and library lookup while it is on. It does nothing while the Up Next add-on is turned on, as before. An episode started this way is not marked as watched by Skippy: the add-on does that.

## [7.6.0] - 2026-11-07

### Added

- **Show the prompt for a fixed time.** A new **Show the prompt for (seconds)** setting (Standard level, 0 to 120 in steps of 5, default **0**) keeps the next episode prompt on screen only that long once it appears. The countdown and the progress bar then run over that time instead of down to the end of the episode. **0** keeps the old behaviour: the prompt stays up until the episode ends. A prompt that appears late, because you seeked into the window, still gets its full time. The **Still watching?** question is not affected: it always stays up until the episode ends, so a timeout can never stand in for an answer to it.
- **Choose what happens when the countdown ends.** A new **When the countdown ends** setting (Standard level) says what happens if nobody has answered by then: **Close the prompt** (default, as before; the end of the episode is left to Kodi, which only moves on by itself if its own **Play next video automatically** setting is on), or **Play the next episode**. It works with a fixed time and with the countdown to the end of the episode, and an episode started this way counts as unattended for the **Still watching?** guard. After the prompt closes by itself it stays away for the rest of the episode.
- The countdown line says which it is: **Episode ends in 00:42** as before, **Next episode starts in 00:20** when the next episode will start, **Closing in 00:20** when the prompt will only close. Both the custom popup, **Preview** and the mockup in **Customize next episode popup…** follow the two settings; the native toast stays up for the shortened time too.
- The new strings are translated in all 11 language packs.

## [7.5.1] - 2026-11-07

### Added

- **A live mockup in Customize next episode popup.** The screen now shows the popup itself on a stage at the right of the rows, and redraws it as soon as you change a row, the way **Customize Skip Dialog** does: the look, text and heading colour, all caps, button highlight, progress bar style, card opacity, corner, picture, time left, progress bar and the button that starts highlighted all show at once, without opening **Preview**. With **Popup style** set to **Native toast** the stage shows a toast instead. The popup and the mockup are drawn from the same code, so what the stage shows is what you get. **Preview** is still there and opens the real popup with a countdown that runs.

### Changed

- The rows of **Customize next episode popup** moved to the left edge of the screen to make room for the stage.

## [7.5.0] - 2026-11-06

### Added

- **Change the popup's colours, button highlight and bar one by one.** **Customize next episode popup…** now has the same kind of rows as **Customize Skip Dialog**, so you can start from a **Popup look** and change single parts of it: **Text colour**, **Heading colour** (the "Play next episode?" line), **All caps**, **Button highlight**, **Progress bar style** and **Card opacity**. The colour, focus and bar lists are the skip dialog's own, so every colour, highlight texture and bar style you can pick there can be picked here. Each row starts at **Same as look**, which leaves that part to the chosen look; any other choice replaces it. Left and Right (or OK) step through the choices and the screen redraws, **Preview** shows the result, **Save** stores only what you changed and **Cancel** discards it. Picking another **Popup look** in the screen clears the individual choices again, the way applying a preset does in the skip dialog. **Progress bar style** is only listed while **Show progress bar** is on. The six choices are also ordinary settings under the **Popup look** setting (Standard level for text colour, all caps, button focus style; Advanced for heading colour, progress bar style and card opacity), shown while the style is **Custom**, so the settings and the screen always agree. With the default choices the popup looks exactly as before.

## [7.4.0] - 2026-11-06

### Added

- **Popup look.** A new **Popup look** setting, also a row in **Customize next episode popup…**, changes how the next episode popup looks without moving anything: the card behind it, the text colours, upper case, the highlight behind the focused button and the progress bar. **Default** is the look the popup has always had and stays the default. **Same as skip dialog** follows the skip dialog's own settings as you change them (progress bar style, button focus style, card opacity, font colour and all caps). The other 34 choices are the skip dialog's Full and Compact Full presets, from **Classic** to **Underline**, so a preset you like there looks the same here. **Preview** shows the look you picked. A progress bar drawn as squares keeps their size and loses whole squares as the time runs down; the other bar styles shrink from the right.
- **Autoplay per show.** A new **Remember autoplay per show** setting (off by default) lets each show have its own answer to "start the next episode by itself?". With it on, pressing **Play now** on the prompt for a show Skippy has no choice for makes Skippy ask, a few seconds into the next episode, **Always play the next episode?** **Yes** starts that show's next episodes automatically from then on, even while **Play the next episode automatically** is off; **Keep asking** keeps the prompt for that show, even while automatic play is on. Either answer is remembered and asked only once per show. A show is recognised by its TMDB id (IMDb id as fallback), the same way the per-title auto-skip rules do it, so every copy of its episodes counts; shows Skippy cannot identify just follow the global setting. **Manage autoplay by show** lists the shows with a choice, lets you switch a show between **Play automatically** and **Ask first** or forget it, and has **Add a show...** to pick any show from your library in advance. **Clear saved autoplay choices** forgets them all. The "Still watching?" question applies to automatic play from a show's own choice as well, so its rows now show while either kind of automatic play is on. The choices are included in **Back up profile data** and restored by merging.

## [7.3.4] - 2026-11-06

### Fixed

- **The progress bar in the next episode popup is no longer squeezed.** As the episode ran down, the whole bar was shrunk, so its segments got narrower and narrower. The bar now loses whole segments from the right instead: they disappear one by one and keep their size, like the segmented progress bar in the skip dialog.

## [7.3.3] - 2026-11-06

### Added

- **"Still watching?" guard.** With **Play the next episode automatically** on, Skippy now counts the episodes that played one after another without anyone pressing a button. After **Episodes in a row before asking** (default 3, 1 to 10; the episode playing counts as one) it asks **Still watching?** with **Continue** and **Stop** instead of starting the next episode. **Continue** starts it and the count begins again. **Stop**, or no answer, leaves the next episode unstarted, so the episode finishes and playback ends. A button press during an episode, or starting an episode yourself, starts the count over. The question uses the popup, or the toast when **Popup style** is **Native toast**, and **Continue** is always the button under the cursor. It is on by default and only matters with automatic play; **Ask if you are still watching** turns it off. Kodi carries on through a playlist by itself, so when nobody answers there Skippy stops playback a few seconds before the end.
- **Start at the credits.** A new **Start at the credits** setting (off by default) makes the prompt, or the automatic start, begin when the episode's **Credits** segment starts instead of **Seconds before the end**. The segment has to begin in the second half of the episode and at least 10 seconds before its end; otherwise, and when the episode has no Credits segment, the usual time applies. The countdown and the progress bar in the popup run from that moment to the end of the episode.

## [7.3.2] - 2026-11-06

### Added

- **A real popup for the next episode.** The "Play next episode?" prompt is now a small popup in a screen corner instead of a Kodi toast. It shows the next episode's picture, its number and title, **Episode ends in 00:42** with a progress bar that runs down to the end of the episode, and two buttons, **Play now** and **Close**. **Back** also dismisses it, and it goes away by itself when the episode ends or playback stops. It works on 720p and 1080i skins. If the popup cannot be shown, Skippy falls back to the toast so the prompt is never lost.
- **Popup style.** A new **Popup style** setting (Basic) chooses between **Custom** (the popup) and **Native toast** (the plain Kodi toast used before).
- **Customize next episode popup.** A new button in the Next episode settings opens a screen with **Popup style**, **Popup position** (any corner), **Show episode picture**, **Show time left**, **Show progress bar** and **Default button**. **Preview** shows the result with an example episode and a countdown that starts over, **Save** stores only what you changed, **Cancel** discards everything. The same options are also available as ordinary settings (position, picture, time left and progress bar at Standard level while the style is Custom, default button at Advanced).
- **Episode pictures.** Skippy now asks Kodi for the next episode's artwork, from the library or from the playlist item, and uses its thumbnail (or fanart) in the popup.

### Changed

- **The setting that turns the feature on is now called "Enable play next episode"** (it was "Offer the next episode"), in all 11 languages.

## [7.3.1] - 2026-11-06

### Fixed

- **Settings showed no text on recent Kodi builds.** On a current Kodi master build (23.0 nightly) every Skippy setting and category name was blank, and the toggles and values had no labels. Those builds no longer look in language folders named after the English language name (`English`, `German`, `Portuguese (Brazil)`, ...), so none of Skippy's texts were loaded. The language folders are now named the way Kodi names its language add-ons (`resource.language.en_gb`, `resource.language.de_de`, `resource.language.pt_br`, ...), which every Kodi version from 19 on understands. The texts themselves are unchanged. This was not caused by the Next episode category; the problem was already there on that build.
- **A guard against it coming back.** The tests now fail if a language folder is not named after a Kodi language add-on, and if a settings label or help id has no English text.

## [7.3.0] - 2026-11-06

### Added

- **Next episode.** A new **Next episode** settings category lets Skippy offer the next episode near the end of a TV episode, like the Up Next add-on. It is off by default. **Offer the next episode** turns it on; **Seconds before the end** (default 45) says when. At that moment a Kodi toast asks "Play next episode?" with the episode's number and title: **OK** plays it now, **Back** dismisses it for the rest of the episode. **Play the next episode automatically** skips the question and starts the next episode at that moment instead.
- **Where the next episode comes from.** If the current playlist has an item after this one, that is the next episode. Otherwise it is the next episode of the same show in the video library, in season and episode order (numbering gaps are fine, specials are not offered after a regular episode, and a file that holds several episodes is not played twice). **Skip episodes already watched** (Advanced) offers the next unwatched one instead. **Resume a partly watched next episode** (Advanced, on) continues from the saved position.
- **Hide skip dialogs during the prompt** (Standard, on). From the moment the prompt is due until the episode ends, Skippy does not offer to skip segments, so a credits skip dialog does not compete with it. This only applies when a next episode was found; turn it off to keep skip dialogs working at the end.
- **Mark the episode as watched when moving on** (Standard, on). Moving on 45 seconds before the end can fall short of Kodi's watched threshold, which would leave the episode unwatched. A few seconds after the switch Skippy marks it as watched if Kodi did not.
- **Up Next add-on.** If `service.upnext` is turned on, Skippy's prompt stays off so you do not get two popups, and Skippy says so once per Kodi session.
- **Playback details.** Skippy now also asks Kodi for the show id and season of the playing item.

## [7.2.7] - 2026-11-05

### Fixed

- **A segment with two or more nested segments now stops at each of them.** Take a Recap with a Prologue and an Ad inside it. "Skip Recap" went to the Prologue, but once the Prologue was over, the Recap's skip jumped straight to the end of the Recap, past the Ad. Starting or resuming playback in between worked the skip out differently again and went to the Ad. Both now follow one rule: the skip stops at the next nested segment that is still ahead of the playhead, and goes to the end only when none is left. Each stop says where it lands (for example "Skip to Ad at 00:50"), and every nested segment now reliably says "Skip to remaining Recap"; a later one could miss that when playback started before the first. A single nested segment and overlapping segments behave as before.

## [7.2.6] - 2026-11-05

### Fixed

- **Embedded chapters: no more guessed end for the last chapter.** When a file's chapters carry no end times and Kodi does not report the total running time, the last chapter used to be given an end of 300 seconds after its start. Its real end is unknown, and a guessed end could skip real content, so that chapter is now left out. Every other chapter still ends where the next one starts, and the last chapter still ends at the total time whenever Kodi reports it.

## [7.2.5] - 2026-11-02

### Fixed

- **A damaged Segment types list no longer silently resets to the defaults.** If `segment_types.json` ended up empty or unreadable (for example after a power cut), Skippy started over with the built-in types and overwrote the file, so your custom types and aliases were gone. The file is now kept as `segment_types.json.corrupt`, and your types are restored from `segment_types.json.bak`, a copy of the last good file that is refreshed on every save (and never replaced by a damaged one). The same safety net covers your saved skip dialog presets and the remembered local/online choices.

## [7.2.4] - 2026-11-02

### Fixed

- **A failed sidecar save no longer counts as success when it left an empty file.** Opening a file for writing creates it, so when the write itself failed (read-only share, full disk) an empty file stayed behind and the save was still reported as done, with the original already deleted. The result is now judged by the file's size, not by what the write call returned: an empty file is a failed save, it is cleared, and the original file is put back.

## [7.2.3] - 2026-11-02

### Fixed

- **One malformed chapter could stop Skippy until Kodi restarted.** A chapter in a `*_chapters.xml` whose end time was before its start (or whose time could not be read) raised an error that nothing caught, which ended the service. Such a chapter is now skipped on its own and the others still load. The monitor loop also has a safety net now: if a tick ever fails, the error is logged once with its traceback and Skippy carries on.
- **One bad EDL row dropped the rest of the file.** A row with the end before the start (or `nan`, `inf` or a negative time) made every following row disappear. Only the bad row is skipped.
- **Changes made in the settings windows now reach the running service.** The service kept its own copy of the per-title auto-skip rules and of the statistics, so "Manage titles", "Clear all" and "Reset statistics" (and restoring a backup) did not take effect until Kodi restarted, and a reset could be undone by the next skip. Both caches now notice when the file was changed by another script.
- **Skip dialog left open when playback stopped.** If the video stopped or ended while the dialog was showing, the dialog stayed on screen and blocked skipping until a button was pressed. It now closes by itself (without counting as a skip or a dismissal) once playback has been gone for about three quarters of a second, and also closes if its update thread fails.
- **Pausing no longer dismisses the skip dialog.** The dialog's safety timeout counted wall-clock time, so a long pause declined the skip and marked the segment as dismissed. Paused time no longer counts.
- **Saving a segment could lose or misreport the sidecar.** The Segment Marker said "saved" even when the write failed (read-only share, full disk) and did not use the safe writer. It now uses the shared writer and reports failure. The writer also puts the original file back when every write attempt fails; before, it had already deleted it.
- **Dismissing a nested skip dialog could reopen it at once** when two segments had (nearly) the same start and end. The nested-segment bookkeeping no longer treats such a segment as its own parent.
- **Profile data files are flushed to disk** (`fsync`) before they replace the old file, so a power cut right after a save cannot leave an empty statistics, catalog or overrides file. Data that cannot be written as JSON now leaves the old file untouched instead of raising.

## [7.2.2] - 2026-11-02

### Fixed

- **Embedded MKV chapters: several editions.** Files with more than one chapter edition (for example a commentary or alternative cut) had all editions merged, giving duplicate and overlapping segments. Skippy now uses the default edition, otherwise the first visible one, and ignores hidden editions.
- **Disabled chapters** (ChapterFlagEnabled = 0) are no longer turned into segments; a disabled chapter also hides its sub-chapters.
- **SeekHead handling.** A later SeekHead without a Chapters entry no longer erases the position found in an earlier one, SeekHeads that only point at another SeekHead are followed, and the chapters block is read in full when it is larger than the first read.
- **Faster, lighter chapter read.** Chapters are looked up in the first 256 KiB; the larger read of the file header only happens when the file has no SeekHead pointers. File names with a query string or `|` headers (stream URLs) are now recognised as MKV by extension.

### Added

- **More default segment names** matched exactly: Intro: opening credits, opening titles, title sequence, op. Credits: ending credits, end credits, closing credits, end titles, ending titles, ending theme, ed. Preview: next episode preview, episode preview, next episode. They are added once to an existing Segment types list (never over a name another type already uses, and never again after you remove one). "Post-Credits" is left unmapped on purpose.

## [7.2.1] - 2026-11-02

### Fixed

- **Embedded MKV chapters not found on large files** (GitHub issue #3): the Matroska parser rejected the whole top-level Segment when its declared size was larger than the part of the file that is read (8 MiB), which is the case for almost any real MKV. The Segment is now parsed from the bytes that are available, so chapters in the header are found, and the SeekHead retry that reads Chapters from further into the file works as well. Thanks to bitcreepy for the report and the working fix.

## [7.2.0] - 2026-10-24

### Added

- **Translated add-on summary and description** in `addon.xml` (Danish, Dutch, French, German, Greek, Italian, Norwegian Bokmål, Spanish, Swedish, Brazilian Portuguese), so the Kodi add-on info page follows the interface language. English remains the default (`en_GB`).

## [7.1.9] - 2026-10-24

### Added

- **Brazilian Portuguese (Portuguese (Brazil))** language pack with all 506 strings, matching the English catalog.

## [7.1.8] - 2026-10-23

### Fixed

- **Skip and Close icons were hidden even when enabled**: the icons were drawn underneath the button's focus texture, so with the wide button (Hide Close Button on) they were covered and the option only made the button wider. The icons are now drawn above the buttons in every skin layout and in the Customize preview, and the Skip icon now sits in its own slot beside the button instead of on top of the focus texture, whether or not the Close button is shown.

### Changed

- **Built-in presets hide the Skip and Close icons by default**; turn off *Hide Skip and Close Icons* to show them.

## [7.1.7] - 2026-10-23

### Fixed

- **Skip button label too low in the Customize preview**: the preview draws its labels as separate label controls, which the earlier text-offset nudge never reached. They now sit about 1.5 px higher (1 px at 720p, 2 px at 1080i), so text no longer crowds the bottom border or underline textures. The add-on repositions those labels from Python, so the nudge is applied there. Underline focus styles (Clean, and the other underline presets) raise the label an extra 2 px at 720p (3 px at 1080i) so the text clears the line.

## [7.1.6] - 2026-10-23

### Fixed

- **Skip button label still sat low**: measured in the live Customize preview across presets, the label was still about 2 px below centre. The nudge is now 3 px at 720p and 4 px at 1080i.

## [7.1.5] - 2026-10-23

### Fixed

- **Skip button label sat too low**: the label in Full / Compact Full buttons is nudged up (1 px at 720p, 2 px at 1080i) so there is no extra space above the text and descenders (p, g, y) no longer touch the bottom border.
- **Noir preset unreadable**: it used a bright white focus texture with near-white text. It is now a black card with a white ring and white text.

## [7.1.4] - 2026-10-23

### Added

- **12 new presets**: Arcade, Terminal, Blueprint, Lava, Deep Sea, Candy, Noir, Aurora (Full / Compact Full) and Minimal Sunset, Minimal Midnight, Minimal Cyberpunk, Minimal Coffee.

## [7.1.3] - 2026-10-23

### Added

- **Source picker**: new setting *Offer to review sources that disagree* (Segment Sources, off by default). When TheIntroDB and IntroDB.app agree on a segment (within 1.5 s) but the local sidecar differs by more, Skippy asks whether to review. The modal lists each source with *Start* / *End* buttons that jump playback there (playback is paused while it is open), then *Use local* or *Use online*. The choice is remembered per file.
- **Label width probe** (diagnostic): `RunScript(service.skippy,label_width_probe)` measures whether auto-width skin labels report their real text width, and shows the result next to Skippy's glyph estimate.
- **Export / import of saved presets**: the preset menu (Preset row in Customize skip dialog) has *Export saved presets…* (writes `skippy-presets-<date>.json` to a folder you pick) and *Import presets…* (adds presets from such a file; existing names are kept).

### Fixed

- **Segmented progress bar no longer squishes** (smooth bar): the *Segmented White / Teal / Green* styles keep the same segment size while the bar fills or empties, so segments appear or disappear one whole segment at a time instead of being compressed or growing pixel by pixel. Uses pixel-exact `progress_tiled_segmented_<color>_h<height>.png` textures (one per bar height, drawn 1:1 so spacing never varies by a pixel; generated by `tools/gen_progress_tiled_textures.py`).

## [7.1.2] - 2026-10-22

### Added

- **Native toast: "Press OK to skip" is optional** (Native mode, toast on): new setting *Show "Press OK to skip" in the toast* (default on). Off gives a shorter toast with just the skip label and the next-jump line.

### Fixed

- **Jellyfin `.chapters` folder not detected on CoreELEC** (GitHub issue #1): Kodi's `listdir` can omit hidden folders, so `.chapters/<name>_chapters.xml` was skipped. Skippy now falls back to an `exists` check on the folder when it is missing from the listing.

## [7.1.1] - 2026-10-22

### Removed

- **Current preset settings row**: it could show a stale value until Kodi was restarted. The preset name is still shown in the Customize skip dialog.

## [7.1.0] - 2026-10-22

- **TheIntroDB API v4**: submit (`POST /v4/submit`) and lookup (`GET /v4/media`) moved off v3, which no longer accepts submissions. Exactly one media id is sent per request, **TVDB first** (the API's identity and the fastest path), then TMDB, then IMDb, since v4 resolves `tvdb_id` → `tmdb_id` → `imdb_id`. Lookups and uploads now also work when Kodi only has a TVDB id. For TV, when Kodi has both the **series** TVDB id (from the TV show) and the **episode** TVDB id, Skippy sends `tvdb_id` plus `tvdb_episode_id`, which pins the exact episode regardless of numbering order. (Previously the episode row's TVDB id was stored as `tvdb_id`; it is now correctly the series id.)
- **IntroDB.app movies and specials**: movie uploads now send `is_movie: true` (required by the current API) and no longer send `tmdb_id`/`tvdb_id`, which the API documents as *series* ids. TV uploads send the series TVDB id (see above). Movie **lookups** now use `GET /segments?imdb_id=…&is_movie=true` (previously skipped), and season 0 / episode 0 are no longer looked up or uploaded because the API requires 1 or higher. `post_credits` is not mapped to a Skippy segment, so it is ignored.

- **Preview type** picker in the Customize skip dialog header: choose which segment type the preview shows (default Commercial) to see how the width changes. It only affects the preview.

### Changed

- **Full and Compact Full panels are about 13% narrower**: the label width estimate is scaled down and the ladders retuned.
- **Minimal plates are no longer stretched.** Every Minimal plate style is pre-rendered per width (`media/plates/<name>_w<width>.png`, generated by `tools/gen_minimal_plate_variants.py`), so the rounded ends keep their shape and only the flat middle stretches. The plate width snaps to the nearest pre-rendered step (120, 150, 190, 240, 270, 320, 380 or 420). The Minimal skin XML is no longer rewritten at runtime; a custom plate image without variants falls back to the stretched original.
- **Minimal plate width follows the label** like Full and Compact Full: never narrower than the classic plate, and right corners keep their right edge, so "Skip Commercial" no longer truncates.
- **Ask dialog debounce is now a legacy option.** It stays at **0** (no wait). If you do set a delay, Skippy re-checks after it that playback is still running and the playhead is still inside the segment, and drops the prompt otherwise, so a stale prompt can no longer open. Duplicate prompts are handled by the single-flight, just-skipped and same-segment guards. The setting will be removed in a later release if no double-opening dialogs are reported.
- **New installs default to the Sleek look** (Compact Full, combined skip and progress, ALL CAPS, Flat Teal, Skip + Type, no Close button). Existing settings are untouched.
- **Customize preview shows "Commercial"** as the example type, the longest common name, so width problems show up straight away. Presets *Paper* and *Pastel* are now *Minimal Paper* and *Minimal Pastel*.
- **Skip dialog width follows the label.** The Full and Compact Full panel is no longer fixed at 430 px. Each label format has its own ladder of fixed widths (`Skip`, `Skip + Type`, `Skip + Type + Duration`), and the longest label the segment can show (type name, duration format, ALL CAPS) picks the first rung that fits. A plain `Skip` is now a small panel. The button, focus frame, progress bar, card, Close icon and corner anchoring all follow the chosen width. Rows that need room (next-jump line, ending text) keep a minimum width.

### Added
- **Native skip dialog** (Playback & Dialog → **Toggle mode**: Custom / Native). Native uses the skin's own look: a notification toast with an invisible listener so **OK / Enter** skips and **Back** dismisses (default, kept on screen for the whole segment), or Kodi's built-in Yes/No dialog. Options: skip button text, segment duration suffix and format, default focus, close at segment end, next-jump line. Custom-only options are hidden in Native mode. New file `skip_dialog_native.py`.
- **Skip dialog presets** for Custom mode: Classic, Modern, Stylish, Colorful, Vibrant, Glass, Outline, Subtle, Sleek, Clean, Mono, Slate, Gold, Neon, Neon Pink, Frosted, Steel, Retro, Segments, Stripes, Sunset, Big & Bold, Ghost, Accessible, Pill, Underline, Minimalist, Minimal Dark, Minimal Glass, Minimal Color, Minimal Steel, Minimal Gold, Minimal Neon, Minimal Frosted, Minimal Paper, Minimal Pastel (36 in total). Pick from **Preset** in Customize Skip Dialog (left/right previews live) or the new **Skip dialog presets…** settings action. Save the current look as your own preset and delete it later; saved presets are part of profile-data backup. New files `skip_dialog_presets.py`, `skip_dialog_presets_ui.py`.
- **Card background** (**Show card background**, **Card opacity (%)**) for the Full-mode panel.
- **35 new flat, matte, glass, outline and underline textures** (15 button focus styles, 11 progress fills, 11 minimal plates), generated by `tools/gen_preset_textures.py`.
- **26 more textures** (`tools/gen_preset_textures.py`): button focus styles *Frosted White*, *Brushed Steel*, *Neon Cyan/Magenta*, *Gold Leaf*, *Pastel Mint/Peach/Lavender* and *Bracket White/Cyan/Green* (corner brackets); progress styles *Segmented White/Teal/Green*, *Glow Cyan/Magenta*, *Striped Blue/Orange* and *Gradient Gold*; Minimal plates *Pastel Mint/Peach/Lavender*, *Brushed Steel*, *Frosted*, *Gold Leaf* and *Neon Cyan*.
- **Presets in Customize**: choosing a preset from the **Skip dialog presets…** settings action now opens it in **Customize Skip Dialog** as a live preview (nothing is stored until **Save**). The Preset row reads **Custom** once a look matches no preset, and **Save** on a Custom look asks for a name and stores it as your own preset (cancelling the name box still saves the settings).

### Fixed
- **Customize: switching to Full from a combined Compact look** (Sleek, Pill) left almost the same rows, because Combined skip and progress hides the separate progress rows. Switching to Full now turns Combined off so all Full options show.
- **Presets**: every Full and Compact Full preset now hides the Close button. The Neon button and plate textures no longer draw their ring inset from the edge, and the Outline White / Cyan rings are thinner, so the label no longer touches the border.
- **Full mode and Minimal mode options missing from the settings page**: Kodi builds the list of option groups once when the page opens and leaves out any group whose settings are all hidden at that moment, so the separate Native, Full mode and Minimal mode groups could never appear after you changed **Toggle mode** or **Skip dialog mode**. All Skip dialog options now live in one group, where they show and hide live. The group headers are gone.
- **Settings page showed every mode's options at once**: in Custom Toggle mode, the Playback & Dialog page now shows only what applies to **Skip dialog mode**: Full shows everything, Compact Full a reduced set (no card, ending text, bar height or icon options), Minimal only the plate, format, position, font and duration options.
- **Pill focus textures looked stretched at the ends**: the flat, glass and outline button textures were twice the button height, so Kodi squashed the rounded caps into ovals. They are regenerated at 64×25 with a `12,12,12,12` 9-slice border, so the caps stay true half-circles at any button height.
- **Option labels that start with a digit** (`1m30s`, `01:30`, `3D Blue`, …) were read by Kodi as string ids and shown as "Pictures" / "Videos". Duration format options are now **Short (1m30s)** / **Clock (01:30)**; minimal plates are **Blue 3D**, **Glossy Blue 3D**, **Red Glossy 3D**. Stored values are unchanged.

## [7.0.2] - 2026-09-25

### Fixed
- **Live TV / IPTV**: Skippy stays idle on a live channel. A PVR or live-TV playback no longer enters the segment loop, Segment Editor, or Segment Marker. Remote playback URLs (`http`, `https`, `pvr`, `rtp`, `rtsp`, `rtmp`, `udp`, `mmsh`, `mms`, `plugin`) are not passed to `xbmcvfs.exists()`, which was a HEAD (then a GET after HTTP 405) about once a second against proxies such as Dispatcharr.

## [7.0.1] - 2026-09-22

### Fixed
- **Settings backup** includes the segment-types catalog. Restore merges that catalog into the live one. A settings file from before 7.0 applies its old skip lists, keywords, and EDL map to the catalog instead of dropping those removed keys.
- **Profile-data restore** keeps a built-in type's local skip mode, aliases, and EDL number when that type is missing from the backup. Statistics and per-title rules stored under an old alias fold into the canonical type on merge.

### Changed
- Profile-data backup help text and the restore summary include segment types.

## [7.0.0] - 2026-09-21

### Changed
- **Segment types catalog**: skip mode, aliases, and EDL numbers live in one JSON catalog (`addon_data/service.skippy/segment_types.json`) edited from a single **Segment types and skip behavior** dialog. Comma-separated keyword / always-ask-never / EDL mapping fields are removed from settings.
- **Unknown labels Never skip** (breaking): a chapter that matches no type is still a segment, but skip mode is Never instead of Ask.
- **Credits / Outro** and **Commercial / Ad / Sponsor** are one type each. **Cold open** is an alias of **Prologue**, not Intro.
- **EDL write** always uses the type’s primary number (legacy 6/16 → 7, 13 → 8, 17 → 10). Old numbers still parse.
- The first 7.0 run imports leftover comma lists from the profile `settings.xml`. Kodi’s `getSetting` no longer returns those removed ids. Profile-data backup includes `segment_types`.
- Online upload matches a catalog alias exactly. A longer name such as "cold open extended" is not uploaded.

### Fixed
- Skip dialog, skip toast, editor list, and statistics show the type’s display name (`Behind the scenes`, not `behind_the_scenes`). Older statistic rows for the same type are combined.

### Added
- WindowXML **Segment types** editor (720p and 1080i): Always / Ask / Never per type, EDL number, aliases, add/delete custom types.

## [6.9.0] - 2026-09-21

### Fixed
- **IntroDB.app outro**: downloaded outro windows are treated as **credits** (skip dialog, matching, and sidecar save). Chapter XML writes **Credits**, not `outro`.

### Added
- **Add missing online types to existing sidecar**: when **Save online segments** is on and a local `.edl` / chapters.xml already exists, an optional toggle still appends intro/recap/credits/preview windows that the file does not already have (by type). Existing local times are not changed. Works with **Skip if exists**. Overwrite still replaces the file; **Update All** already inserts missing types.

## [6.8.0] - 2026-09-20

### Changed
- **Sidecar parse**: EDL reads skip the extra `exists()` when the directory listing already named the file (same as chapter XML). `update_monitor=True` no longer re-stats a probe-confirmed XML before the read. Parse-cache hits and mtime watch paths slash-normalize like probe invalidation, so `nfs://…\file` vs `nfs://…/file` reuse the cache instead of reparsing; signature stats use the probe’s real sidecar paths.

### Fixed
- **Skip click log**: the dialog logs the same destination the service seeks to (nested start or end+1, plus Jump offset).
- **Nested skip bookkeeping**: matching the landing segment allows a 50ms start-time difference so a float mismatch cannot drop parent/nested rewind tracking.
- **Skip dialog layout**: Full without Combined fill no longer `setVisible(False)` on the four combined-fill images the skin already hides.

### Removed
- Unused `PROBE_MAX_AGE_S` alias (hit/miss TTLs remain `PROBE_HIT_MAX_AGE_S` / `PROBE_MISS_MAX_AGE_S`).
- Unused `_sidecar_chapter_xml_exists` (discovery is `_find_existing_sidecar_chapter_xml_path`).
- Unused `SkipDialog.xml` (720p and 1080i). Playback already opens `SkipDialog_{Corner}.xml`; the unnamed file was a leftover default and was still texture-patched on settings change.

## [6.7.0] - 2026-09-13

### Changed
- **Faster skip dialog on network shares**: the uncached segment parse dropped from ~1.3s to ~0.6s on NFS by removing redundant round trips. The sidecar probe lists each directory once for both chapter XML and EDL candidates instead of twice; `_sidecar_signature` and `parse_chapters` skip the `exists()` call on paths a directory listing already confirmed; and the post-parse signature is only recomputed when a sidecar write invalidated the probe cache during the parse.
- **Skip dialog layout**: Full layout places and repaints only the button variants the skin can actually show, instead of every variant. Each GUI control call waits for a rendered frame, so this cut dialog `onInit` roughly in half on Amlogic devices.

## [6.6.4] - 2026-09-12

### Fixed
- **Embedded chapters on Piers**: an empty `Player.GetChapters` list no longer skips VFS/`mkvextract`. Kodi 22 can report no chapters at start of playback; Skippy now reads the Matroska header (then local `mkvextract`) in that case. A non-empty GetChapters result is still used as-is.
- **Skip dialog off vs auto-skip**: turning skip dialogs off no longer blocks Always-skip. Ask is still suppressed; Never is unchanged.
- **Sidecar probe invalidation**: editor/marker writes match the playing file after slash-normalizing VFS paths (`nfs://…\file` vs `nfs://…/file`). Sidecar candidates on Windows join with `/` so NFS/SMB URIs are not mixed with backslashes.

## [6.6.3] - 2026-09-03

### Fixed
- **Segment Editor 720p canvas**: `720p/SegmentEditorDialog.xml` now uses a **1280×720** coordinate space (and matching fullscreen overlay) instead of 1920×1080 with 720p panel coords.
- **WindowXML init fallback**: if Kodi rejects the 4-argument constructor, Python still records the heuristic skin folder (`1080i` on near-HD) instead of always claiming `720p`. Skip dialog open logs `asked` / `locked` plus GUI screen size.

## [6.6.2] - 2026-09-03

### Fixed
- **Skip dialog log spam**: Full layout no longer `getControl`s Customize-only 9-slice overlays (3040–3043) during playback. Those IDs exist only in `SkipDialogCustomize.xml`; looking them up on the live dialog logged `Non-Existent Control` every time the skip UI opened.
- **720p skip XML canvas**: Full and Minimal skip dialogs in the `720p` skin folder now declare a **1280×720** `<coordinates>` block (matching their `posx` values) instead of 1920×1080.

## [6.6.1] - 2026-09-03

### Fixed
- **Skip dialog corner placement**: Full layout no longer overwrites the card group's left position in Python (that is what pulled Bottom Right toward centre when 720p scale met 1080i XML). Height still follows ending text / progress / jump rows. Skin-folder re-lock now measures image widths that exist in that XML — Full/Customize backdrop **3081**, Minimal plate **3021**, editor list **5000** — instead of missing group IDs that logged `Non-Existent Control` on every open.

## [6.6.0] - 2026-08-30

### Fixed
- **Save online sidecars**: merge / update / overwrite against an existing file no longer `NameError`s after the save-module split (`_merge_sidecar_segments`, `_finalize_sidecar_after_update_policy`, `_VFS_IO_EXC` in write/preview).
- **Online lookup cache**: failed fetches and host cooldown (`fetch_remote_json` returning `None`) are not stored as a permanent empty result for the title. HTTP **404** still caches as no match.
- **Sidecar probe miss**: Segment Editor and Segment Marker writes notify the playback service to drop the 60s miss cache (and parse snapshot) via a Home window property, so a sidecar created mid-playback is picked up on the next tick.
- **Per-title auto-skip**: the yes/no prompt runs after skip-chain, not between seek and the next nested/abutting skip.
- **Title change while paused**: Skippy no longer advances `last_video` without resetting dismiss/prompt state. The session resets when the new file actually plays.
- **Next jump line**: Full / Compact Full jump times include **Jump offset**, matching the seek target.
- **Statistics**: time saved uses the playhead after `seekTime` when Kodi reports it, not only the planned destination.

## [6.5.2] - 2026-08-22

### Fixed
- **Embedded chapters fallback**: `Player.GetProperties` has no `chapters` property on Kodi Omega (invalid params, `embedded=0`). Playback now uses `Player.GetChapters` when the JSON-RPC method exists (Kodi 22 / Piers), then a bounded Matroska header read through VFS (works on NFS), then `mkvextract` for local files. Keyword matching is unchanged.
- **Customize / settings**: Black Beveled minimal plate is `minimal_black_beveled.png` (the old `.jpg` name is no longer referenced).

### Added
- Remaining user-facing translations that were still English copies (Ask-dialog debounce help, ALL CAPS skip-dialog text, Greek neighbor-snap labels, and a few editor/marker strings). Texture names and Segment Editor / Segment Marker stay as product labels. English msgid text is unchanged.

### Changed
- **Sidecar probe**: after a confirmed miss (no chapter XML or EDL), Skippy waits **60s** before listing the folder again. Hits still refresh every **5s** so an edited sidecar is picked up. Writes still clear the probe cache immediately.

## [6.5.1] - 2026-08-22

### Added
- **Minimal skip plates**: 3D Blue, 3D Glossy Blue, 3D Red Glossy, and Black Beveled in settings and the Customize skip-dialog preview.

## [6.5.0] - 2026-08-17

### Fixed
- **Skip dialog lower-centre on windowed near-HD (Windows)**: When Kodi’s GUI was slightly under 1920×1080 (e.g. windowed `1902×973`), Skippy requested the `720p` skin and scaled the Full panel to X=`840`, while Kodi still loaded `1080i` XML (right edge X=`1260`) — so Bottom Right looked centred. Near-HD GUIs now request `1080i`, and WindowXML dialogs re-lock scale in `onInit` from loaded control widths if the folders still disagree.

## [6.4.2] - 2026-08-16

### Added
- **Customize skip dialog** translations (title, help, Save/Cancel/Yes/No, Compact Full, Combined skip and progress, duration format/content) in Danish, Dutch, French, German, Greek, Italian, Norwegian, Spanish, and Swedish. English msgid text is unchanged.

## [6.4.1] - 2026-08-16

### Added
- Three more add-on screenshots (`screenshot04.png`–`screenshot06.png`) listed in `addon.xml` for the Kodi add-on browser.

## [6.4.0] - 2026-08-16

### Added
- **Sleek 3D button focus** styles: Cyan, Silver, Orange, Violet, Graphite, and Ice (glossy pills, 9-sliced like Green/Pink 3D).
- **Matching 3D progress fills** for the same six colours (vertical gloss so Combined/short fills do not stretch a side-to-side gradient).

## [6.3.5] - 2026-08-16

### Fixed
- **Segment ending text** (and its countdown) stays white. Skip/Close still follow the skip-dialog font colour setting.

## [6.3.4] - 2026-08-15

### Fixed
- **Aqua Vignette**: 9-slice copied the darkest ends and flattened the bright center, so the caps looked much darker than the body. The original full-width gradient is back, height-matched to the 25px Skip/Close button.

## [6.3.3] - 2026-08-15

### Fixed
- **Aqua Bevel, Aqua Vignette, Aqua Rounded** button focus textures are 9-sliced like the 3D styles, so Skip/Close endcaps stay round (or beveled) instead of stretching.
- **Right-corner skip dialog**: after the panel grew to 430px (5px right inset), lower-right and upper-right still used the old X (`895` / `1342`), so the dialog hung off the right edge. It now keeps the same 10px inset as the left corners.

## [6.3.2] - 2026-08-15

### Fixed
- **Customize skip dialog**: Skip + Type + Duration (format and content rows) no longer overlap Save and Cancel. Setting rows shrink to stay above the pinned footer.

## [6.3.1] - 2026-08-15

### Fixed
- **Customize skip dialog**: Combined skip and progress stays with Ignore overlapping segments. Enabling it no longer inserts the Full/Compact header above Combined or drops the row under the Full-mode options.

## [6.3.0] - 2026-08-15

### Added
- **Combined skip and progress** is available in **Full** mode as well as Compact Full (Skip-only fill, no Close, no separate bar). Full still keeps the card, ending text, and icons unless those Full options hide them.

## [6.2.2] - 2026-08-15

### Fixed
- **Ask dialog debounce** and **Jump offset** (and the other integer range settings) use a spinner instead of a slider so left/right actually changes the value. Kodi addon sliders often ignore those keys, and they cannot represent Jump offset’s negative range (it stayed at 0).

## [6.2.1] - 2026-08-15

### Fixed
- **Combined** dimmed track uses the same 9-slice endcaps as the fill / 3D button focus textures (Green 3D and the other sliced styles no longer stretch the background).

## [6.2.0] - 2026-08-15

### Added
- **Compact Full Combined**: optional Skip-only pill where the button focus texture is the progress fill (no Close, no separate bar).
- **Skip duration format**: `1m30s` or numeric `01:30` (hours as `H:MM:SS`).
- **Skip duration content**: total segment time, elapsed counting up, remaining counting down, or `elapsed / total`. Live Skip labels refresh when the content is elapsed-based.

### Fixed
- Progress bar no-outline track: dropped missing `progress_left.png` / `progress_right.png` endcaps (they rendered as white ticks) and replaced `progress_background.png` with a flat dark fill.

## [6.1.0] - 2026-08-15

### Added
- **Compact Full** skip dialog mode: a pill Skip/Close cluster without the Full black card, ending text, or skip/close icons. Recap/next-jump and a 4px progress bar still use Full focus textures, skip format, and corner position.

## [6.0.3] - 2026-08-15

### Fixed
- **3D button focus textures** (Blue Rounded, Gold Rectangular, Green, Pink, Light Pink): rebuilt as 9-slice templates so Skip and Close keep their endcaps at every button width instead of stretching.

## [6.0.2] - 2026-08-15

### Added
- **Skip dialog text in ALL CAPS**: global Full + Minimal option in settings and Customize. Button and info labels go uppercase; duration units stay `m`/`s` (`SKIP INTRO (1m30s)`).

### Fixed
- **Skip dialog font color**: focused Skip/Close buttons and Customize mock labels follow the selected colour instead of staying white.
- **Full skip panel**: progress bar and buttons use the same 5 px right inset as the left (bar width 420 / 630).
- **Customize Minimal mode**: Hide ending text and Ignore overlapping segments are hidden (Full-only).

## [6.0.1] - 2026-08-15

### Fixed
- **Customize skip dialog**: Progress bar style and Hide Skip and Close Icons rows; button focus textures on the mockup; up/down no longer skips a row.
- **Skip to Recap** nested jump line uses accent cyan (`FFB0D4E8`) and `font11` in both the live skip dialog and the Customize mockup.

## [6.0.0] - 2026-08-15

### Added
- **Button focus styles**: Green 3D, Pink 3D, and Light Pink 3D (`button_focus_3d_green.png`, `button_focus_3d_pink.png`, `button_focus_3d_light_pink.png`).
- **Customize skip dialog**: Playback & Skip Dialog has a **Customize skip dialog** action that opens a two-pane preview (draft settings on the left, frozen Intro/Recap mockup on fanart on the right). Save writes settings; Cancel discards. The modal is loaded only from RunScript, not by the playback service.

## [5.6.0] - 2026-08-13

### Changed
- **Logging**: Normal verbose no longer heartbeats `Playback time` every second or logs playhead-during-parse for fast parses. Those lines are All-detail only (playhead-moved also requires parse ≥ 200 ms). Unchanged `showtitle` / episode is deduped. Shared `log()` / `log_always` / `log_error` tags default to `service` instead of `SettingsUtils`.
- **NFS sidecar discovery**: Probe via directory listing (and `.chapters/` only when that folder is listed). Missing candidates are not `File()`-opened. Negative probes re-list every 5s so a sidecar added mid-playback is still found.
- **Idle parse**: When source/processed caches are valid and the playhead is more than 3s from any segment or nested-link boundary, the monitor tick skips `parse_and_process_segments`. Loop interval stays 1s.
- **Segment Editor**: Uses the playback parse snapshot for local as well as remote origin. Disk fallback opens only listed/existing sidecar paths.
- **Profile data backup** module renamed to `skippy_profile_backup.py`. Settings actions call `backup_profile_data` / `restore_profile_data`; legacy `backup_upload_history` / `restore_upload_history` RunScript names still work.

### Fixed
- Service `safe_file_read` no longer opens paths `exists()` already said were missing (Kodi `CNFSFile::Open` ERROR spam on NFS).

### Changed (hygiene)
- `PlaybackSessionState` helpers in `service_playback_state.py` own monitor field init/reset.
- `remote_segments.py` is a facade over `remote_http.py`, `remote_tmdb.py`, `remote_library.py`, `remote_lookup.py`.
- `service_online_sidecar_save.py` is a facade over merge / preview / write modules.
- Removed leftover `tools/_tmp_string_ranges.py`, `tools/_repair_marker_try_block.py`, and `tools/apply_segment_editor_phase1.py`.

## [5.5.2] - 2026-08-02

### Changed
- **Profile data backup / restore**: The former upload-history backup now also exports and merges **per-title auto-skip rules** and **statistics**, writing `skippy-profile-data-backup-*.json` (`skippy_profile_data_backup_v1`). Legacy `skippy_upload_history_backup_v1` files still restore (history only). Upload fingerprints union as before; title overrides merge per key; statistics keep the larger counter values (and recompute total from per-type counts).

## [5.5.1] - 2026-08-02

### Added
- **Title autoskip** settings category: hosts the per-title auto-skip toggle, **Manage saved auto-skips** (list titles with auto-skip rules and delete one entry at a time), and **Clear saved per-title auto-skip choices**.
- **`per_show_overrides_ui.py`**: Manage modal with delete confirmation; loops until Close or the list is empty.

### Fixed
- **Marker remote discovery / picker chrome**: The five on-screen discovery labels and Segment Marker picker title/subtitle/footer strings (`#44040`–`#44050`) are localized in all ten language packs.

## [5.5.0] - 2026-08-01

### Added
- **Per-title auto-skip (Ask to auto-skip per show or movie, default off)**: After you confirm an Ask skip, Skippy offers to auto-skip that segment type for that show or movie from now on. The choice — including a decline, so you are not asked twice — is stored in `addon_data/service.skippy/show_overrides/<kind>_tmdb_<id>.json` (IMDb id as fallback), so it follows the title across re-encodes, renames, and other versions of the same movie or episode. **Clear saved per-title auto-skip choices** forgets every decision.
- **Statistics** (new settings category): Total time saved, segments skipped in total and per segment type, and how many segments were downloaded from or uploaded to the online databases. Counters live in `addon_data/service.skippy/statistics.json`; **Reset statistics** zeroes them after a confirmation prompt.
- **`tests/test_stats_and_overrides.py`**: Counter accumulation, corrupt-file fallback, modal text and reset confirmation, override key derivation, per-title storage, and path-traversal refusal.
- **`tests/test_main_loop_dedup.py`**: Confirms segment skips are evaluated once per steady tick and re-evaluated when the playhead moves or the segment list changes during parsing.

### Fixed
- **`sync_local_to_online`**: The Expert setting was documented and read by the code but missing from `settings.xml`, which left local→online upload permanently off. Added, along with **`toast_online_segments_applied`**, which was hardcoded on with no way to disable it.
- **Marker remote discovery**: The three button-discovery toasts (CEC button set, remote button set, no button code captured) were hardcoded English and now use `strings.po` (`#44011`–`#44013`) in all ten language packs.
- **Swedish catalog**: Five `msgid` lines used straight quotes where the English source uses typographic quotes.

### Changed
- **Hot path**: The add-on handle and log-detail level are cached for one second, skip-mode keyword lists are parsed once per settings value, and per-tick segment work no longer runs twice when the playhead has not moved and the segment list is unchanged.
- **Shared helpers**: Time formatting (`time_format.py`), segment nesting/overlap and jump-hint text (`segment_relations.py`), and EDL line parsing (`edl_format.py`) now have one implementation each instead of near-duplicates in the service, editor, marker, and sidecar modules.
- **Dead code**: Dropped the unused `maybe_save_online_segments_to_chapters_xml` wrapper and `skipdialog`'s duplicate `get_addon`, and renamed `segment_editor_parser.parse_embedded_chapters` to `parse_embedded_chapters_via_mkvextract` to end the name collision with the service-side parser.

## [5.3.8] - 2026-08-01

### Fixed
- **Nested jump-label coverage**: Added an end-to-end test for the `0 60 5` / `20 40 9` EDL flow, including the **Skip to remaining Intro at 00:40** result.
- **Jump-label casing**: Intentional capitalization such as `TV OVA` and `Behind-the-Scenes` is preserved while normalized labels remain human-readable.
- **Long jump times**: Next-jump text now uses `HH:MM:SS` for targets at or beyond one hour; shorter targets retain `MM:SS`.

## [5.3.7] - 2026-07-26

### Fixed
- **Ask next-jump subtext**: Skipping a nested segment (e.g. Recap inside Intro) now shows **Skip to remaining Intro at …** instead of generic “next segment”. Same for Recap, Preview, and other parent labels.

### Changed
- **README**: Nested-segment examples and Full-mode next-jump docs match the new subtext; Ask anti-dupe section clarifies debounce default **0** vs the separate 300 ms same-seg cooldown.

## [5.3.6] - 2026-07-26

### Changed
- **Ask anti-dupe**: After a Skippy skip (Ask or Auto), the same segment id is ignored while the playhead is still inside that segment. Cleared when outside, on new video, or major rewind. Nested / overlapping / consecutive abutting segments (different ids) still process.
- **Same-seg Ask cooldown**: Refuse re-opening Ask for the same `seg_id` within **300 ms**.
- **`ask_dialog_debounce_ms`**: Default **0** (optional settle delay only; devices that still need it can raise it).

### Added
- **`tests/test_ask_guards.py`**: Just-skipped, cooldown, debounce-0, consecutive abutting, nested, and overlapping coverage.

## [5.3.5] - 2026-07-24

### Changed
- **Full skip dialog**: When Close is hidden, the Skip button (3015 / 3016) is the same width as the progress bar (370 / 555). Layout with Close visible is unchanged.

## [5.3.4] - 2026-07-20

### Changed
- **IntroDB.app upload**: Round `start_sec` / `end_sec` to 1 decimal place (matches docs examples; still float, not integers).

## [5.3.3] - 2026-07-20

### Changed
- **TheIntroDB.org upload**: POST `/v3/submit` now includes optional `tvdb_id` when Kodi library metadata has it (same context already used for IntroDB.app). Matches TheIntroDB OpenAPI optional field.

## [5.3.2] - 2026-07-20

### Changed
- **IntroDB.app upload**: POST `/submit` now sends float `start_sec` / `end_sec` (3 decimal places) instead of rounded integers, and includes optional `tmdb_id` / `tvdb_id` when Kodi library metadata has them (TV show uniqueid, or episode uniqueid). Matches IntroDB.app API docs for improved aggregate accuracy.

## [5.3.1] - 2026-07-20

### Added
- **Greek localization**: Full settings + runtime UI catalog (`resources/language/Greek/strings.po`, `Language: el`).

## [5.3.0] - 2026-07-20

### Added
- **Runtime UI localization**: Skip dialog labels (Skip / Close / formats / ending / next-jump), playback toasts (skipped, missing segments, online loaded, overlapping), Segment Editor dialogs/notifications/list chrome (Pause/Resume, etc.), and the marker “close editor first” toast now use ``strings.po`` via ``settings_utils.get_localized`` (IDs ``#40000+``, ``#41000+``, ``#42000``, ``#43000+``). English plus the eight European language packs from 5.3.0’s predecessors include the new strings.
- **``tests/test_get_localized.py``**: Fallback and ``%``-format coverage for the shared helper.

## [5.2.14] - 2026-07-20

### Fixed
- **Segment Editor Pause/Resume label**: Opening the editor while playback was running sometimes labelled the button **Resume** because initial pause was inferred from two close ``getTime()`` samples (playhead often stalls briefly during WindowXML open). Now uses Kodi’s ``Player.Paused`` condition (same as the service loop) and resyncs after the player listener registers.

## [5.2.13] - 2026-07-18

### Added
- **European settings localizations**: German, Dutch, French, Spanish, Norwegian (Bokmål), Swedish, Danish, and Italian (`resources/language/*/strings.po`), matching the English catalog (262 strings).

### Changed
- **Install packaging**: `.gitattributes` `export-ignore` now also omits `tools/`, `__pycache__/`, `*.code-workspace`, `openapi_theintrodb_v3.yaml`, and the gitignore/gitattributes files from GitHub Download ZIP / `git archive` (in addition to `tests/`).
- **README folder tree**: Updated for the modular `service_*.py` layout, 720p/1080i skins, multi-language folders, and note that `tests/` / `tools/` stay out of install ZIPs.

## [5.2.12] - 2026-07-17

### Fixed
- **Skip dialog focus / OK after atomic open**: Focus was applied while the panel group was still hidden (`skippy_dialog_ready=false`), so Kodi rejected `setFocusId` (“Control … can't”) — no focus texture and Enter/OK did nothing. Reveal first, then focus.

## [5.2.11] - 2026-07-17

### Changed
- **Skip dialog atomic open**: Full and Minimal panels stay hidden (`skippy_dialog_ready=false`) until labels, layout, and progress seed finish in ``onInit``, then reveal with the slide/fade **Visible** animation. Avoids the piecemeal paint while ``WindowOpen`` used to run over an unfinished panel. Window-level open animation removed; close animation unchanged. Top placements slide in from above; bottom from below.

## [5.2.10] - 2026-07-17

### Fixed
- **Skip dialog flash after confirmed skip**: After `seekTime`, Skippy set `last_time` to the seek target while Kodi’s `getTime()` still lagged inside the old segment. The next rewind check treated that lag as a major rewind, cleared `prompted`, and briefly reopened the ask dialog (then auto-declined). Post-seek grace now suppresses that false rewind; grace is stamped on every Skippy seek even when **Hide OSD during skip** is off; the main loop also syncs its playhead clock to the seek target after an early skip in the same tick.

### Added
- **`tests/test_post_seek_rewind_grace.py`**: Regression for rewind suppression while Skippy seek grace is active.

## [5.2.9] - 2026-07-16

### Changed
- **Dead WindowDialog skip UI removed**: ``skip_dialog_window_ui.py`` no longer contains the unused programmatic skip-dialog builder (skip UI is WindowXML only). The module now exports only **``_argb_to_kodi``** for colour conversion shared by ``skipdialog.py``.

### Added
- **README — Recommended starting presets**: Three quick-start tables (local only, Local first + online fill-in, Online first) so new users need not dig through Expert settings first.
- **Tests**: ``test_online_sidecar_policy.py`` (policy normalize, merge, update / update-all), ``test_marker_save_helpers.py`` (marker policy, overlap, EDL trim), ``test_editor_save_helpers.py`` (editor save format, dedupe, chronological order).

## [5.2.8] - 2026-07-16

### Fixed
- **Intro dialog after recap skip**: After a confirmed ask/auto seek, Skippy immediately chains skip processing at the landing time (no wait for the next 1s monitor tick), skips ask debounce on the chained prompt, and allows the ask dialog while `Skippy.Skipping` is held even if Kodi briefly reports Paused.
- **Post-new-video GetItem delay**: New-video/replay reset no longer clears the playback-context cache that was just populated by `refresh_playback_context` (that forced a redundant `Player.GetItem` on the next tick and delayed the following skip dialog).

### Changed
- **Log spam during `main` (never)**: Never-skip segments are marked prompted so skip mode is not re-resolved every tick; skip-mode match lines are detail-only; warm cache-hit / path fallback / per-tick playback-time lines are quieter.

## [5.2.7] - 2026-07-16

### Fixed
- **Hide OSD during skip**: Hold `Skippy.Skipping` for **~5s** and until `Player.HasPerformedSeek(3)` / caching settle (was ~2s / seek(2)), so the seek bar does not flash right after the skip toast.
- **Intro dialog after recap skip**: Run skip processing **before** deferred online probe/sync when segments are already loaded, and do not treat brief post-seek **Paused** as a full processing stop while `Skippy.Skipping` is active (Kodi often reports paused for several seconds after seek).

## [5.2.6] - 2026-07-16

### Added
- **Hide OSD display during skip** setting (`signal_skipping_for_skins`, default **off**) under **Playback and Skip Dialog → Global options**. When on, Skippy sets Home property `Skippy.Skipping` around auto-skip / confirmed ask-skip **seeks** (not while the ask dialog is open). Help text notes this **requires a per-skin `DialogSeekBar.xml` edit** (or a patching add-on); turn off to keep the normal seek OSD after skips.

## [5.2.5] - 2026-07-16

### Added
- **`Skippy.Skipping` Home window property**: Set immediately before auto-skip / confirmed ask-skip `seekTime`, cleared after seek+caching settle (min ~2s) or on stop/new video. Stock skins ignore it; cooperative skins (or DialogSeekBar patches) can hide seek OSD while the property is set. See README **Skin: hide seek OSD during Skippy skips**.

## [5.2.4] - 2026-07-14

### Removed
- **Suppress seek OSD after skip (experimental)**: Removed — `Dialog.Close(seekbar)` only flashed against skin-driven seek OSD; not useful in practice.

## [5.2.3] - 2026-07-14

### Changed
- **Suppress seek OSD after skip (experimental)**: Now keeps calling `Dialog.Close(seekbar|fullscreeninfo,true)` for **~5 seconds** (every 0.3s) instead of a single flash close. Extends the window if another skip happens while suppression is active.

## [5.2.2] - 2026-07-14

### Added
- **Suppress seek OSD after skip (experimental)**: New setting under **Playback and Skip Dialog → Global options** (`suppress_seek_osd_after_skip`, default off). After auto-skip or confirmed ask-skip seeks, Skippy calls `Dialog.Close(seekbar,true)` (and `fullscreeninfo`) — skin-dependent; remove if it proves unreliable.

## [5.2.1] - 2026-07-13

### Changed
- **Chapter XML default write name**: New sidecars are written as **`_chapters.xml`** (Segment Marker, Segment Editor, online save). Existing **`-chapters.xml`**, **`_chapters.xml`**, and **`.chapters.xml`** files are still discovered and updated when present.

## [5.2.0] - 2026-07-13

### Added
- **Upload history backup / restore (merge)**: Backup & Restore settings category has separate actions for `online_upload_submissions.json` (TheIntroDB / IntroDB.app upload dedupe fingerprints). Restore **merges** fingerprints into the local profile file; duplicates are skipped. Implemented in **`upload_history_backup.py`** via `RunScript(service.skippy,backup_upload_history|restore_upload_history)`.
- **Pause during online lookup**: New setting pauses playback while Skippy runs a **blocking** online segment fetch (**Online first**, or **Local first** when no local sidecar exists). With the setting off, Local first without a sidecar still uses the background deferred probe. Does not pause when a local sidecar is present (background probe for save/sync only).

## [5.1.5] - 2026-07-12

### Fixed
- **Skip dialog / segment editor layout on Windows 1080p**: WindowXML dialogs now **lock** the skin folder chosen at `__init__` for all Python coordinate scaling (`scale_skin_coord`), instead of re-querying `getScreenHeight()` during `onInit` (can drop below 1080 during fullscreen playback and mis-layout 1080i XML). Resolution detection also treats **width ≥ 1920** as 1080i when height is under-reported. Skip dialog progress bar height is scaled to match 1080i skin XML.
- **False “no segments” toast with Local first**: Missing-segments toast is suppressed while a **deferred online segment probe** is still running for the current file.

## [5.1.4] - 2026-07-05

### Fixed
- **Skip dialog white font colour (Windows / WindowXML)**: Bundled skip layouts no longer bind button and label **`textcolor`** to **`$INFO[Window.Property(...)]`** (unreliable in addon WindowXML; often left colours unset on focus). Skin XML now uses literal **`FFFFFFFF`** like the segment editor; **`skipdialog.py`** applies the user's **Skip dialogue font colour** via keyword **`setLabel`** (**`textColor`**, **`focusedColor`**, etc.), re-applies after **`setFocusId`**, and logs the resolved colour at dialog open.

## [5.1.3] - 2026-07-05

### Fixed
- **Skip dialog white font colour**: **`setLabel(text)`** without colour arguments reset button and countdown labels to the skin default, overriding **Skip dialogue font colour** (including White). **`skipdialog.py`** now applies text colours via **`setLabel`** with the correct Kodi argument order (matching **`skip_dialog_window_ui.py`**) on init, countdown refresh, and progress ticks.

### Added
- **`tests/test_skip_dialog_font_color.py`**: White preset resolution and coloured **`setLabel`** regression test.

## [5.1.2] - 2026-07-05

### Added
- Integration/regression tests: **`test_parse_and_process.py`**, **`test_deferred_remote_probe.py`**, **`test_service_loop_skip.py`**, **`test_service_loop_nested.py`**, **`test_skipdialog_result.py`**.

## [5.1.1] - 2026-07-05

### Added
- **Toast when online segments apply**: New setting **`toast_online_segments_applied`** (Toasts category). One-shot notification when deferred online lookup updates the playback timeline (Local first, no local sidecar).
- **`tests/test_online_segments_toast.py`**.

## [5.1.0] - 2026-07-05

### Changed
- **Cached home window**: **`get_home_window(monitor)`** in **`segment_editor_utils.py`** reuses `Window(10000)` on the monitor instead of constructing it every service tick.

### Added
- **`tests/test_home_window_cache.py`**.

## [5.0.9] - 2026-07-05

### Changed
- **Hot-path logging**: Removed per-call detail logs from **`SegmentItem.is_active`** / **`get_duration`**. Dismissed-segment messages in **`service_loop_skip.py`** use **`log_if_changed`**.

### Added
- **`tests/test_hot_path_logging.py`**.

## [5.0.8] - 2026-07-05

### Changed
- **Faster post-skip monitor**: Removed blocking **`xbmc.sleep(500)`** after auto-skip and confirmed ask-skip seeks; playhead verification happens on subsequent ticks.

### Added
- **`tests/test_service_loop_skip_sleep.py`**.

## [5.0.7] - 2026-07-05

### Changed
- **Unified player snapshot**: New **`service_player_snapshot.py`** stores `player_id` and minimal `Player.GetItem` data from the playback context. Remote lookup, deferred online probe, and embedded-chapter fallback reuse the snapshot to skip duplicate `GetActivePlayers` / `GetItem` JSON-RPC when the playing file is unchanged.

### Added
- **`tests/test_player_snapshot.py`**: Snapshot path matching and enriched-item reuse.

## [5.0.6] - 2026-07-05

### Changed
- **Nested parent map**: Pass 2 builds `nested_parent_map` (child → parent segment ids) once per title; **`service_loop_nested.py`** uses O(1) map lookups instead of scanning all segment pairs every monitor tick.

### Added
- **`tests/test_nested_parent_map.py`**: Verifies nested parent map construction.

## [5.0.5] - 2026-07-05

### Changed
- **TV prefetch non-blocking**: **`schedule_tv_successor_prefetch`** now runs library lookup and online API fetch in a daemon thread (same pattern as deferred remote probe), so Online-first TV playback no longer blocks the main monitor loop during successor prefetch.

### Added
- **`tests/test_tv_prefetch_threading.py`**: Verifies prefetch schedules a background thread and dedupes in-flight work.

## [5.0.4] - 2026-07-05

### Changed
- **Processed segment cache**: Pass 1 (overlap filter) and Pass 2 (nested linking) results are cached per title with link-phase invalidation when the playhead crosses nested segment boundaries. Subsequent monitor ticks reuse the cache instead of re-linking every second. New **`service_segment_processed_cache.py`**; invalidated on video change, sidecar/settings change, deferred remote apply, and major rewind.

### Added
- **`tests/test_segment_processed_cache.py`**: Offline tests for link phase, cache hit/miss, and invalidation.

## [5.0.3] - 2026-07-04

### Fixed
- **Ask skip still did not seek after OK (5.0.2)**: After the dialog returned a valid jump time, logging `"… %s" % seg_id` raised `TypeError` because `seg_id` is a `(start, end)` tuple — Python treats that as two format arguments. The exception was caught before `seekTime`, so playback never jumped. Fixed in **`service_loop_skip.py`** and **`service_loop_nested.py`** by wrapping tuple ids as `(seg_id,)` for single-placeholder logs.

## [5.0.2] - 2026-07-04

### Fixed
- **Ask skip did not seek after OK**: The skip dialog could close with `response` still unset (lost when the Kodi window is destroyed after `close()`), so the service treated it as a dismiss and never called `seekTime`. **`skipdialog.py`** now stashes `_skippy_dialog_result` before close; **`service_loop_skip.py`** reads that stash, logs the outcome, and only marks a segment dismissed when the user explicitly declined.
- **Skip button control id**: Normalize `onClick` control ids to `int` (matches other Skippy dialogs) so OK/Skip is recognized on all Kodi builds.
- **Playhead tracking after skip**: The main loop refreshes `last_time` from the player after skip processing instead of overwriting a successful seek with the pre-dialog playhead.

## [5.0.1] - 2026-07-03

### Fixed
- **Service startup crash on Windows/Kodi**: **`service_loop_nested.py`** had an invalid `except` / `elif` pair in the rewind handler (`SyntaxError` at import), preventing the monitor service from starting.

### Added
- **`tests/test_service_imports.py`**: Offline import tests for refactored loop modules and **`service.py`** (with Kodi stubs) to catch startup `SyntaxError`s before deploy.

## [5.0.0] - 2026-07-02

### Changed
- **Monitor loop performance**: Playback metadata (path, type, toast settings) is cached in **`service_playback_context.py`**; JSON-RPC runs on cache miss or video change only. While paused, the loop uses a fast path with no JSON-RPC and minimal logging.
- **Smarter pause handling**: Pause is checked immediately after a lightweight context refresh, **before** segment parse, toast logic, or JSON-RPC. After a skip seek Kodi often reports `is_playing=True` and `is_paused=True` for several seconds; the service no longer repeats `get_video_file`, `Player.GetItem`, and settings logs every tick during that window.
- **Sidecar probing**: **`service_sidecar_probe_cache.py`** negative-caches NFS `exists()` probes per video so titles without sidecars are not re-scanned every loop tick.
- **Service refactor**: **`service_main_loop.py`** is a thin orchestrator; replay/video change, toast, nested-segment, and skip logic live in **`service_loop_playback.py`**, **`service_loop_toast.py`**, **`service_loop_nested.py`**, and **`service_loop_skip.py`**.

### Removed
- Unused **`PlayerMonitor.item_metadata_ready`** and **`last_playback_item`** fields.

### Added
- Offline unit tests under **`tests/`** (`python -m unittest discover -s tests`).

## [4.0.1] - 2026-06-29

### Fixed
- **Skip dialog late after blocking parse (3.7.7 regression)**: **`service_main_loop.py`** again re-reads **`player.getTime()`** after segment parse before active-segment / dialog processing, so a multi-second NFS or API parse does not leave a stale playhead from loop start.
- **Local first without local sidecar**: With **Local first** and online lookup enabled, online APIs always run in a **background thread** (not only when a local sidecar exists). Completed remote segments are stashed and applied on the next parse so the skip dialog can appear as soon as data arrives while playback is still inside the segment.

## [4.0.0] - 2026-06-22

### Changed
- **Service architecture**: Playback monitor loop lives in **`service_main_loop.py`** only; **`service.py`** is the Kodi entry (monitor, helpers, bindings). Segment parse/link logic uses **`service_segment_processing.py`** (no duplicate implementations in the entry module).
- **Ask dialog debounce**: New setting **`ask_dialog_debounce_ms`** (**0–500**, default **300**) under **Playback → Global options** replaces the hard-coded 300 ms delay before Ask dialogs open.

### Added
- **README**: Documents **Sync local → online**, **Prefetch next episode**, **embedded chapters fallback**, **Open Segment Editor when overlaps are detected**, and the debounce setting.

## [3.7.9] - 2026-06-21

### Fixed
- **Kodi v21 startup crash on Windows**: `service_online_sidecar_save.py` used PEP 604 type hints (`str | None`) without deferred annotation evaluation; Kodi’s embedded Python 3.8/3.9 evaluates those at import time and raised `TypeError`. Added `from __future__ import annotations` to match other service modules.

## [3.7.8] - 2026-05-29

### Added
- **Local first — background online probe**: When **Local first** and a local sidecar are in use, online segment lookup still runs in a **background thread** after parse so **Save online segments** and **Sync local → online** work without blocking the first skip dialog. Results apply on the main service thread when no skip/editor/marker modal is open.

### Fixed
- **Sync local → online**: When online lookup is enabled but the dialog path had no remote data yet, sync now **probes online APIs** instead of comparing against an empty remote list (which could over-prompt for upload).

## [3.7.7] - 2026-05-29

### Fixed
- **Skip dialog late or missing at playback start**: Segment parsing blocked the main loop for several seconds while still using a stale playhead from before the parse — on resume-from-bookmark this picked the wrong active segment (e.g. ``main`` instead of ``recap``). Playhead is refreshed after parse before dialog processing. With **LocalFirst** and a local sidecar present, online API lookup is deferred on the dialog path so local segments are ready in ~300–400ms instead of waiting on TheIntroDB/IntroDB (~9s).

## [3.7.6] - 2026-05-29

### Removed
- **Orphan ``resources/textures/white.png``**: Leftover from the removed Segment Marker pending on-screen chip. All UI uses ``resources/skins/default/media/white.png`` via skin XML and ``addon_skin_media()``.

## [3.7.5] - 2026-05-29

### Fixed
- **Segment editor 1080i button height**: Repack script was double-scaling toolbar and list-row button height (``45 × 1.5 → 68px``) while Python still centered floats for **45px**, so list-row actions sat low and focus clipped the row below; row 3 toolbar focus clipped the panel bottom. All editor buttons are **45px** at 1080i again (**30px** at 720p).
- **Segment editor panel bottom margin**: Main panel and bottom button-row dark overlay extended **+15px** (``570→585`` at 720p, ``855→878`` at 1080i) so toolbar focus textures clear the panel edge.

## [3.7.4] - 2026-05-29

### Fixed
- **Segment editor toolbar rows 1–3**: All three rows use the same packer — minimum width per label, then **equal extra pixels on every button** to fill the 1170px panel, with any leftover slack split as **equal side margins** so rows stay centered and focus textures do not clip the panel edges. Replaces 3.7.3 left-aligned rows 2–3 and uneven per-button stretching from earlier releases.

## [3.7.3] - 2026-05-29

### Fixed
- **Segment editor toolbar buttons**: Reverted toolbar and list-row button height to **30px** at 720p (**45px** at 1080i) — the 38px height was never requested and caused the blue focus texture to clip into the row below. Row 1 seek buttons are **centered** in the panel instead of left-aligned. Row 2 **Start at End of Segment** / **End at Start of Segment** and row 3 **Add Current + User Set Time** / **Manual Start + End Times** use **tight fixed widths** (label + small padding only) instead of stretching across spare panel space — the focus texture matches the control box, so narrower widths sit closer to the label text.

## [3.7.2] - 2026-05-29

### Fixed
- **Segment editor list-row action buttons**: Each button **+5px** wider with **2px** gaps repacked from the list row (``Start@Curr`` … ``Del``). **``textoffsetx=0``** already applied; Python ``_update_edit_delete_positions`` left coords synced to match skin XML.

## [3.7.1] - 2026-05-29

### Fixed
- **Segment editor toolbar layout**: Removed **``<aspect>0.85</aspect>``** and **auto width** from toolbar buttons (they shrank unfocused labels and left large empty gaps when width stayed at ``min``). Rows 1–3 are repacked edge-to-edge with **2px** gaps and fixed widths sized to each label. Seek row widened for **-10m**, **+10s**, **+30s**, **+10m**; row 3 action buttons widened (**Jump**, **Delete**, **Upload**, **Save**, **Exit**). **``<textoffsetx>0</textoffsetx>``** so label text uses the full button width inside the focus texture.

### Changed
- **Segment editor labels**: **Add at Current Time + User Set Time** → **Add Current + User Set Time**; **Add Manual Start and End Points** → **Manual Start + End Times**.

## [3.7.0] - 2026-05-29

### Changed
- **Segment editor — skin-independent toolbar (Phase 1)**: Toolbar and list-row action buttons are taller (**38px** at 720p / **57px** at 1080i). Long row-2/row-3 labels use **``<width min="…" max="…">auto</width>``** so Kodi can size to the active skin font without exceeding the previous fixed layout. Segment list **focused** lines use **``<scroll>true</scroll>``** when text overflows.
- **Segment editor button labels**: **Set Start to Start of File** → **Set to Start of File**; **Set End to End of File** → **Set to End of File**.

## [3.6.14] - 2026-05-29

### Fixed
- **Skip dialog progress bar flash on open**: Progress controls stay hidden until seeded from one ``player.getTime()`` sample. Classic bar no longer becomes visible at Kodi's default (~100% fill) before ``setPercent`` runs. Countdown mode seeds at the correct remaining width/percent (full at segment start); elapsed mode seeds empty. Smooth fill width uses the same seed instead of always starting at 0.

## [3.6.13] - 2026-06-12

### Added
- **Sync local to online**: New Expert → Upload setting **Sync local to online** (**Off** / **Ask**). During playback, when a local sidecar has segment types missing from online databases (e.g. local recap/credits but online intro only), Skippy prompts to upload the missing types using your default upload target and API keys. Probes online APIs even when online lookup is disabled for playback.

## [3.6.12] - 2026-06-12

### Fixed
- **Segment editor button fonts**: Dropped Estuary-only **font_flag**; buttons use skin-standard **font10** via ``setLabel`` with **``<aspect>0.85</aspect>``** in ``720p`` / ``1080i`` XML to fit long labels without skin-specific font names.

## [3.6.11] - 2026-06-12

### Fixed
- **Segment editor toolbar layout (1080p)**: Rows 2–3 repacked edge-to-edge (2px gaps) with wider buttons so long labels are not clipped; **5024** and **Del** moved left (Python list-row positions synced to skin XML — **Del** was drifting 27px right on 1080i).
- **Segment editor button fonts**: Switched from **font10** to **font_flag** via ``setLabel`` / ``setFont`` (Estuary **font10** matched the skin default; **font_flag** is visibly smaller).

## [3.6.10] - 2026-06-12

### Fixed
- **Segment editor toolbar buttons**: All editor buttons use **font10** via ``setLabel`` (was font12). Narrower **5029**, **5030**, **5005**, **5002** in ``720p`` and ``1080i`` skins. **5024** (End at Start of Segment) moved right — **1080i** had a 100px overlap with **5023**.

## [3.6.9] - 2026-06-12

### Fixed
- **Segment editor button text at 1080p**: All editor buttons now get **`font12`** via ``setLabel`` in ``onInit`` (WindowXML ignores skin ``<font>`` tags; row 3 buttons were using the skin default and clipped). **1080i** list-row and long row-3 controls are slightly wider with positions updated to match ``segment_editor_dialog.py``.
- **Skip dialog open latency**: ``onInit`` sets **final panel height** and progress **track** first (no ``player.getTime()`` on open — fill starts at 0 and the monitor thread updates immediately). Removed duplicate early focus pass and verbose layout logging from the open path.

## [3.6.8] - 2026-05-31

### Fixed
- **Skip dialog focus texture delay**: Focus frame appeared 1–2 s after the dialog because (1) every segment re-wrote all Full/Minimal skip skin XML files on disk before ``doModal()``, forcing Kodi to reload textures, and (2) Full layouts had no ``defaultcontrol`` so focus waited until ``onInit`` finished heavy layout work. Textures are now warmed once at service start (cached; refreshed on settings change), ``defaultcontrol`` **3012** is restored for the common case, and focus is set immediately when ``onInit`` starts (again after label refresh).

## [3.6.7] - 2026-05-31

### Changed
- **Dialog layout docs**: ``addon_skin_resolution.py`` now documents the **WindowXML vs WindowDialog** split at the top of the module (which surfaces use ``1080i``, why Python modals must stay 1280×720, and what happens if you mix them). Removed unused ``_MODAL_METRICS_1080I`` table that invited the same mistake again.

## [3.6.6] - 2026-05-31

### Fixed
- **Online upload / editor modals spilling off-screen on 1080**: ``xbmcgui.WindowDialog`` uses a **1280×720** coordinate canvas on all GUI resolutions (Kodi upscales it to the display). The upload target picker and other modals were using **1080i** panel coords (width **1755**), which extends past **x=1280** and clipped off the right. Modals now always use the **720p** panel box (`50/60/1170×570`) and 720p control metrics — same footprint as ``720p/SegmentEditorDialog.xml``, visually matched on HD after Kodi scaling. ``WindowXML`` skins still use ``1080i`` where appropriate.

## [3.6.5] - 2026-05-31

### Fixed
- **Addon startup crash**: ``ModalMetrics`` declared ``__slots__`` but had no ``__init__``, so importing ``addon_skin_resolution.py`` failed with ``ModalMetrics() takes no arguments``.

## [3.6.4] - 2026-05-29

### Fixed
- **Editor modals on 1080**: Removed runtime ``unit_scale`` / “inner spacing ×1.5” — modal control sizes are now **explicit pixel tables** (`ModalMetrics` in ``addon_skin_resolution.py``): one set for 1280×720, one for 1920×1080. Canvas stays **1920×1080** with the **1080i** segment-editor panel box (`75/90/1755×855`); no 720 canvas on HD displays.

## [3.6.3] - 2026-05-29

### Fixed
- **Editor modals on 1080**: ``WindowDialog`` now uses a fixed **1920×1080** canvas with the **1080i** segment-editor panel (`75/90/1755×855` — same as ``1080i/SegmentEditorDialog.xml``). Inner control spacing uses a single ×1.5 pass from the original 720p-authored constants. Short dialogs (upload picker, results) stay shorter than the full panel height. **1280×720 canvas is only used when GUI height is below 1080.**

## [3.6.2] - 2026-05-29

### Fixed
- **Editor modals**: Use the segment editor's exact main panel on a **1280×720** ``WindowDialog`` canvas (`left=50`, `top=60`, `1170×570` — same as ``720p/SegmentEditorDialog.xml``). Previous attempts used full screen width or 1080i pixel coords, which ``WindowDialog`` does not share with WindowXML and made modals spill off-screen.

## [3.6.1] - 2026-05-29

### Fixed
- **Editor modals on 1080 displays** (upload target picker, upload results, Yes/No, list pick): Panel now uses the same footprint as the segment editor main group (`left=75`, `width=1755` on 1920×1080, scaled to actual screen size) instead of a fixed 1280×720 canvas that overflowed when Kodi mapped coordinates to the full screen.

## [3.6.0] - 2026-05-29

### Fixed
- **TheIntroDB v3 upload**: Accept HTTP 200 when the response contains a ``submissions`` array (v3 OpenAPI), not only legacy ``ok: true``. Send ``end_ms: null`` for credits/preview through end-of-media; ``start_ms: null`` for intro/recap from the beginning. Relaxed local validation for null-end credits/preview (no 30-minute cap when end is omitted).
- **TheIntroDB v3 GET**: Optional ``Authorization: Bearer`` using the user's upload API key so pending submissions can appear in lookup. ``start_ms: null`` on GET now maps to start at 0 s (was 1 s).
- **Editor modals on 1080 displays** (upload target picker, upload results, Yes/No, list pick): ``WindowDialog`` layouts stay **1280×720** — they were incorrectly scaled ×1.5 with the 1080i skin folder (panels overflowed off-screen). Remote button discovery dialog reverted to the same fixed size.

## [3.5.9] - 2026-05-29

### Fixed
- **1080i segment list**: ``itemlayout`` / ``focusedlayout`` ``width`` and ``height`` attributes were not scaled (only inner controls were), so row height stayed 50px while content and the focus overlay were 75px — misaligned highlight bar and row 2 overlapping the next entry. Regenerated all ``1080i`` dialog XML with layout attributes included.

## [3.5.8] - 2026-05-29

### Fixed
- **1080i segment editor / skip dialogs**: Layouts in the ``720p`` folder are 1280-reference coordinates on a 1920 canvas; Kodi upscales them on 1080 displays. The ``1080i`` copies were not scaled, so the editor panel looked too small. ``1080i`` XML for the editor and skip dialogs is now ×1.5; Python list-row and skip progress layout constants scale the same way.

## [3.5.7] - 2026-05-29

### Added
- **1080i skin folder**: Addon dialogs now load from ``resources/skins/default/1080i`` when the GUI height is 1080 or higher (``720p`` otherwise). Includes full-size variants of **Segment Marker type picker** and **button discovery** (scaled from 1280×720), plus copies of segment editor and skip dialog layouts (1920×1080 coordinates).
- **`addon_skin_resolution.py`**: Shared resolution selection and coordinate scaling for WindowXML and programmatic modals.

### Changed
- **Editor modals** (Yes/No, OK, list pick) and **remote button discovery** use fixed 1280×720 ``WindowDialog`` coordinates on all GUI resolutions (1080i scaling applies to WindowXML skins only).
- **Skip dialog skin texture patches** apply to both ``720p`` and ``1080i`` XML.

## [3.5.6] - 2026-05-29

### Fixed
- **Segment list row 2**: One left-aligned line built in Python (`Duration: … | Source: … | Nested/Overlapping`). Kodi list item layouts cannot place a second label after variable-width text, so the split-label / right-align attempts truncated or misaligned the source field.

## [3.5.5] - 2026-05-29

### Fixed
- **Segment list row 2**: **Nested** / **Overlapping** suffix uses a right-aligned prefix field plus fixed suffix column (Kodi list items do not honour dynamic `$INFO` left positions).

### Changed
- **List-row buttons**: **Merge** 70px, **Fix Ovl** 80px; rail shifted 37px left so **Del** stays at 1150px.

## [3.5.4] - 2026-05-29

### Fixed
- **Segment list row 2**: **Nested** / **Overlapping** suffix position follows the end of `Duration: … | Source: …` (computed `line2_suffix_left`), not a fixed screen-centre offset.

### Changed
- **List-row buttons**: Restored original widths for **Start@Curr** … **Del** (pre-3.5.2); **Merge** / **Split** / **Fix Ovl** widened; full rail shifted left so **Del** stays inside the list overlay (ends at 1150px).

## [3.5.3] - 2026-05-29

### Changed
- **Segment Editor**: Seek/mark/action button rows and bottom dark overlay shifted down to align with the panel bottom edge (570px). **Add at Current Time + User Set Time** and **Add Manual Start and End Points** widened; row-3 controls spread toward **Exit** using available width.

## [3.5.2] - 2026-05-29

### Changed
- **Segment Editor list row**: Nine floating actions — **Merge** (picker: previous/next), **Split**, **Fix Ovl**, plus existing six — reachable via **Right** from the list without losing the highlighted segment. Row-3 **Tools** button removed (**Undo** remains). Buttons shifted 15px left; labels use **font10** via `setLabel`.
- **Segment list row 2**: **Nested** / **Overlapping** suffixes moved from row 1 to row 2 after source (coloured labels); row 1 is always the plain segment title line.

## [3.5.1] - 2026-05-29

### Changed
- **Segment Editor**: **Snap End** list-row button widened (78→92px); **Edit** / **Del** shifted right to match.

## [3.5.0] - 2026-05-29

### Added
- **Segment Editor — Tools picker** (row 3): **Merge with previous segment**, **Merge with next segment**, **Split at playhead**, and **Fix overlap**. Adjacent merge uses the shared label when both segments match; otherwise the standard segment type picker is shown.
- **Segment Editor — Undo** (row 3): Restores the previous segment list state (up to 20 steps). Cleared after a successful save.

## [3.4.9] - 2026-05-29

### Changed
- **Segment Editor**: Action row (row 3) buttons match seek/mark row height (30px); row 3 moved up and bottom overlay shortened. **Start@Curr**, **End@Curr**, and **Snap End** list-row buttons widened.

## [3.4.8] - 2026-05-29

### Fixed
- **Segment Editor banner**: Top-left placement at ~40px height with ``aspectratio keep`` (no full-width stretch). Layout below the title restored to pre-banner offsets.

## [3.4.7] - 2026-05-29

### Changed
- **Segment Editor**: Text title replaced with bundled banner image ``segment_editor_banner.png``.

## [3.4.6] - 2026-05-29

### Fixed
- **IntroDB.app upload**: **Preview** segments are no longer sent as **outro** (IntroDB.app does not accept preview). Only **credits** (and local **outro** labels) map to **outro**; preview still uploads to TheIntroDB.org when selected.

## [3.4.5] - 2026-05-29

### Changed
- **Segment Editor**: Wider **Start@Curr** / **End@Curr** / **Snap Start** / **Snap End** list-row buttons (Edit/Del unchanged); seek jump row shifted 5px left.

## [3.4.4] - 2026-05-29

### Fixed
- **Segment Editor list fonts**: Custom ``skippyListLine*`` names are not loaded for script WindowXML (Kodi uses the **active skin** fonts); unknown names all became **font13**, so line 1 and line 2 matched. List row 1 uses **font12**, row 2 **font10**.
- **List-row action buttons**: Skin XML ``<font>`` is ignored on buttons; ``onInit`` now calls ``setLabel(..., font_flag)`` so Start@Curr … Del render smaller than list text (Estuary **font_flag** ≈18px vs **font12** ≈25px).

## [3.4.3] - 2026-05-29

### Fixed
- **Segment Editor fonts actually apply**: Added bundled ``resources/skins/default/Font.xml``. Unknown names like ``font8`` were falling back to the active skin's **font13** (larger than **font12**), so list row 2 and list-row buttons never looked smaller. List lines now use **skippyListLine1** / **skippyListLine2**; the six row actions use **skippyListBtn**.

## [3.4.2] - 2026-05-29

### Fixed
- **Segment list focus highlight** spans the full row again (list width restored so the overlay covers list-row action buttons).
- **Duration / Source** sub-line uses `font8` (below row-one `font12`); Kodi often has no `font9`, which made line two render too large.

### Changed
- **List-row action buttons**: `font8` labels; non-Edit buttons widened; Edit width unchanged.
- **Mark row** (row 2): shifted 7px right.

## [3.4.1] - 2026-05-29

### Added
- **Segment Editor list row**: **Start@Curr** / **End@Curr** set the selected segment's start or end to the current playhead (six-button rail: Start@Curr | End@Curr | Snap Start | Snap End | Edit | Del).

### Changed
- **Segment list**: Narrower text column (`font12` / `font9`); action buttons use `font9` with tighter widths.
- **Mark row**: **Set Start to Start of File** / **Set End to End of File** (was SOF/EOF); **Start at End of Segment** / **End at Start of Segment** buttons narrowed.

## [3.4.0] - 2026-05-29

### Changed
- **Segment Editor layout**: Three button rows — seek jumps (including ±1/5/10 minute steps with Resume centered), mark/create (with **Set to SOF** / **Set to EOF**), then actions. Dark overlay height adjusted for the extra row; snap button labels **Start at End of Segment** / **End at Start of Segment**.

### Added
- **Set to SOF** / **Set to EOF**: Set pending start to `0.0` or pending end to video duration without seeking.

## [3.3.28] - 2026-05-23

### Removed
- **Legacy marker overlay machinery**: Deleted ``marker_indicator.py``, ``MarkerPendingChip.xml``, service-loop ``sync_marker_pending_indicator`` polling, ``NotifyAll`` **skippy_detach_marker_chip** handling, and RunScript **force-detach** IPC. Segment marker cleanup is ``clear_marker_pending_state()`` → ``set_pending_start(None)`` only.

## [3.3.27] - 2026-05-22

### Removed
- **Cursor/session NDJSON debugger**: Deleted ``agent_debug_ndjson.py`` and all **`H*`** / **`NM1`** / **`H_BOOT`** hooks; marker service periodic **H3** snapshots removed. **kodi.log** unchanged.

## [3.3.26] - 2026-05-22

### Added
- **Segment Marker cancelled toast**: When the second-press flow aborts (**invalid end time**, **Back** from overlap-policy picker, segment **type** picker, or **save confirmation**), Skippy shows **#36036** *Segment marker cancelled.* — gated by **`show_toast_for_segment_marker`** like start/end notifications. Help text **#33005** updated.

## [3.3.25] - 2026-05-22

### Added
- **Toast Notifications**: **Enable toast notifications for segment marker** (``show_toast_for_segment_marker``, default on, visible when Segment Marker is enabled). When off, no Kodi notification for marker **start** / **end** presses; type/save dialogs unchanged.

### Changed
- **Toast Notifications** labels **#33000** / **#33001**: sentence-style wording (*missing segment file toast for TV Episodes / movies*).

## [3.3.24] - 2026-05-22

### Removed
- **Settings**: **Show pending marker indicator** (``segment_marker_show_indicator``) — marker feedback is **toasts only**; the home-window ``skippy_marker_indicator`` property is no longer written. Stale values are cleared when marker state resets or marker is disabled.

### Changed
- **``segment_editor_utils.marker_flow_blocks_editor_launch``**: Dropped the ``skippy_marker_indicator`` check (other marker props already cover active flows).

## [3.3.23] - 2026-05-22

### Fixed
- **Segment Marker** start/end toasts during **fullscreen playback**: ``notify_marker_pending_like_editor`` mistakenly used ``Dialog().notification`` only, which often does not appear on top of fullscreen video. It now calls ``notify_skippy(..., prefer_builtin=True)`` — same **Kodi ``Notification`` builtin** path as the pre-3.3.22 marker toasts (multiline body is flattened to a single line by the builtin formatter).

## [3.3.22] - 2026-05-22

### Changed
- **Segment Marker** pending feedback uses Kodi **notifications** (about **2 seconds**) on start and end, with **HH:MM:SS.mmm** via **`segment_editor_parser.seconds_to_hms`**. **Removed** fullscreen **`addControl` / `removeControl`** chip on **`Window(12005/10800)`**. The Skippy **service only tears down legacy** controls left from older installs. (The old home-window ``skippy_marker_indicator`` toggle was removed in **3.3.24**.)

### Debug
- **NDJSON**: Service snapshots use **`chip_overlay: notifications_editor_parity`**; **`marker_indicator.detach_fs_marker_chip`** logs **`impl: editor_parity_no_attach`**. **`NM1`** on marker notifications (`segment_marker.py:notify_marker_pending_like_editor`).

## [3.3.21] - 2026-05-24

### Fixed
- **Marker pending chip / Omega GUI meltdown (NDJSON)**: ``WindowXML`` ``show()`` left the chip **alive** while ``getCurrentWindowId()`` flapped through **13001** (HDR/DV info) and **10502** (playback UI). That stacked state correlated with **black video**, **OSD blocked**, and **wrong window** (e.g. music library file mode). Reverted the chip to **native ``ControlImage`` + ``ControlLabel``** on ``Window(12005/10800)`` with **module-level refs** and **strict detach** whenever we are **not** in fullscreen video/live fullscreen. Shipped **``resources/textures/white.png``** (1×1) for the semi-transparent pill.

### Debug
- **NDJSON**: ``H6`` ``marker_fs_chip_show``, ``H7`` ``chip_detached`` (``impl: fs_controls``); ``H12`` targets ``_ensure_fs_chip``; snapshots use ``chip_overlay: fs_native_controls``.

## [3.3.20] - 2026-05-22

### Changed
- **Pending marker badge uses ``WindowXML``** (**`MarkerPendingChip.xml`**) in the addon service interpreter — **same Kodi skin/control stack as Segment Editor / marker pickers** — instead of injecting ``ControlLabel`` onto ``VideoFullScreen`` (**12005**). **``close()``** removes the Kodi window graph so **cancel/back no longer fights ``removeControl``** (NDJSON **`H11` + EXCEPTION**).

### Removed
- **Fullscreen ``addControl`` / ``physical_remove`** branch for marker chip teardown.

### Debug
- **NDJSON**: `H6` `marker_xml_window_show`, `H7` `xml_overlay_closed`; **H3** snapshot uses **`xml_overlay_visible`** (replaces fullscreen **`has_bg_control`**).

## [3.3.19] - 2026-05-22

### Notes
- **Superseded by 3.3.20**: fullscreen chip **physical ``removeControl``** path — removed in favour of **`WindowXML`** overlay.

## [3.3.18] - 2026-05-22

### Fixed
- **Marker chip invisible during picker (NDJSON)**: Snapshots showed `indicator_len` 25 while `marker_modal_prop` was **`true`** and **`has_bg_control`** stayed **`false`** — **`_marker_ui_suppressed`** was still treating **`skippy_marker_modal_open`** like the editor-modal case and forced **`_detach`** for the entire Segment Marker dialog chain. **`skippy_marker_modal_open` is no longer a chip suppressor**, so the fullscreen chip can stay attached while marker pickers and yes/no confirm run. **Segment Editor** suppression is unchanged (**`skippy_editor_modal_open`** / **`skippy_editor_session_modal`**).

### Changed
- **Segment Marker**: Restored the **first-press start time** **`Notification`** (**`show_toast`**) while keeping later save-flow prompts toast-free.

## [3.3.17] - 2026-05-22

### Changed
- **Segment Marker UX**: First press shows the **service overlay** (when enabled); second press sets the end time, updates the overlay to **start → end**, runs policy / type / confirm dialogs, then **clears the overlay in `finally` or on any cancel path** — no reliance on **toast** feedback (notifications are dropped for this flow on CoreELEC/fullscreen). **`pick_marker_option`** no longer wipes props mid-chain; **`skippy_marker_second_press_flow` no longer hides the chip** (only active **modal** flags still suppress attaching while a dialog is open).

## [3.3.16] - 2026-05-24

### Fixed
- **`EXCEPTION: Control does not exist`** on second marker press: NDJSON proved **`detach_lock`** always ran on one thread (`ident` unchanged) while **`removeControl`** still raised **`RuntimeError`** (**`remove_control_failed`**). On Omega the binding logs **EXCEPTION** before Python sees the exception, so **`removeControl` is never called on detach** — only module refs are cleared (orphans clear when Kodi rebuilds fullscreen or playback stops).

### Debug
- **NDJSON**: **`H10`** `detach_refs_only_no_removecontrol` (replaces **`H9`** `remove_control_failed` from the old path).

## [3.3.15] - 2026-05-24

### Fixed
- **Concurrent marker chip detach (Kodi Omega `EXCEPTION: Control does not exist`)**: `PlayerMonitor.onNotification` can detach the chip while the service loop is also handling `NotifyAll` / `sync_marker_pending_indicator`. Those paths now share a **`threading.RLock`**, and `_detach()` clears module globals **before** `removeControl` so a second thread cannot re-snapshot stale wrappers mid-teardown.
- **Stop/teardown `player.getTime()` errors**: The main monitor loop (and replay-detection `getTime()` sample) now swallow **all** `Exception` types, matching Omega’s **`Kodi is not playing any media file`** throw when playback ends between `HasVideo`/poll and `getTime()`.

### Debug
- **NDJSON**: `H9` logs **`detach_lock_acquired`**, failed **`removeControl` / `addControl`** (**`exc`** type); **`H7`** unchanged.

## [3.3.14] - 2026-05-24

### Fixed
- **Marker chip detach / Kodi `EXCEPTION: Control does not exist`**: **`_detach()`** no longer calls **`setVisible` / `setColorDiffuse` / `setLabel`** on chip wrappers before **`removeControl`**. Kodi can invalidate fullscreen child controls slightly ahead of the Python wrapper during **second-press / picker prep**; poking accessors then logs Omega **`EXCEPTION`** even though removal was imminent.
- **Editor launch guard vs Segment Marker**: **`marker_flow_blocks_editor_launch`** now treats **`skippy_marker_second_press_flow`** and **`skippy_marker_modal_open`** with the same **_truthy** parsing as **`marker_indicator`** suppression (consistent `1/true/yes/on`).

### Debug
- **NDJSON**: **`marker_indicator.py:_detach`** logs **`detach_enter` / `detach_exit`** (**hypothesisId `H7`**) until this regression is verified on-device.

## [3.3.13] - 2026-05-24

### Fixed
- **Marker chip / `Control does not exist` / ghost text**: Overlay is **fullscreen `Window(12005/10800)`** again so **marker hotkey** is not stolen by `WindowDialog`. **`sync_marker_pending_indicator` no longer calls `setLabel` every tick** — it only **re-attaches** controls when **text or fullscreen window id** changes, avoiding stale Python wrappers after Kodi rebuilds `VideoFullScreen` during picker/modals.

- **Segment Editor vs Segment Marker**: Added **`skippy_editor_session_modal`** (set for the whole `open_segment_editor` try/finally) and **`segment_editor_modal_is_open()`** now accepts **truthy** property spellings. The **second Segment Editor key** relies on **`segment_editor_modal_is_open`**, so **close** still works if **`skippy_editor_modal_open`** flickers. **`marker_indicator`** suppresses the chip when **either** editor flag is active.

## [3.3.12] - 2026-05-24

### Changed
- **(Superseded by 3.3.13)** Option B used **`xbmcgui.WindowDialog`** for the chip; it regressed **marker focus/toasts** versus fullscreen parenting. **3.3.13** restores **fullscreen** parenting and stops **per-tick `setLabel`.**

### Notes (historical — 3.3.12 WindowDialog)
- **Second marker press vs focus**: **`WindowDialog.show()` can still divert input on some setups** despite no focus widgets; string **#36035** prompts **press marker again for end**. If Back is needed before end-mark, note your Kodi skin/device so we can try a tighter mitigations pass.

### Fixed (continued from fullscreen chip path)
- **Toasts under fullscreen overlays**: Kodi **`Notification`** via **`prefer_builtin`** remains visible alongside this chip (unlike stacking our own fullscreen-injected overlays).

## [3.3.11] - 2026-05-24

### Fixed
- **Segment Marker second press / double-Back**: **3.3.10** used a **`WindowDialog`** chip; **`show()` grabbed focus**, so the marker hotkey did not reach the player until **Back** returned focus. The chip is **again parented to fullscreen `Window(12005/10800)`** (same as pre-3.3.10) so **start → end** works with **no extra Back**.
- **Detach / ghost mitigation**: Before **`removeControl`**, Skippy now **hides** the chip, **clears** the label, and **zeroes** the image **`ColorDiffuse`** so a failed removal is less likely to leave readable “Start…” text on Omega/CoreELEC.
- **Toasts (e.g. open Segment Editor while marker pending)**: With **`WindowDialog`** gone, Kodi’s **`Notification`** built-in used by **`notify_skippy(..., prefer_builtin=True)`** is no longer covered by Skippy’s own overlay dialog.

### Added
- String **#36035** and first-mark toast line: reminds you to **press the segment marker key again** for the **end** time (no reliance on Back).

## [3.3.10] - 2026-05-24

### Fixed
- **(Superseded by 3.3.11 — `WindowDialog` stole marker focus.)** **Ghost “Start: …” chip after end mark / picker** (Kodi Omega, CoreELEC): Runtime logs showed **`removeControl`** on fullscreen could diverge from what was painted. **3.3.11** restores fullscreen parenting and mitigates with pre-removal hiding (see above).
- **`SegmentMarkerTypePicker.xml`**: **`defaultcontrol`** must be focusable (**tiny off-screen `button` id 9098**). **`9101`** is the **title label** — using it caused **“Control 9101 … can’t focus”** (the 3.3.9 defaultcontrol change was incorrect).
- **Segment Editor modal flag**: **`SegmentEditorDialog.close()`** clears **`skippy_editor_modal_open`** in a **`finally`** after **`super().close()`**. **`segment_editor_session`** no longer calls **`set_editor_modal_open(False)`** when rejecting an editor launch only because marker flow is active (spurious clears).

## [3.3.9] - 2026-05-24

### Fixed
- **Persistent “Start: …” fullscreen chip** (attempt): service-side fullscreen **`setLabel`/`removeControl`** hardening + second-press ordering + picker defaultfocus experiment. **Superseded by 3.3.10** (WindowDialog chip + picker **9098** defaultcontrol).

## [3.3.8] - 2026-05-24

### Fixed
- **`segment_marker.py` syntax**: Repaired the second-press save block so **`try:`** wraps the whole policy/type/save sequence and **`finally`** always clears **`skippy_marker_second_press_flow`** plus **`clear_marker_chip_and_sync()`** (`SyntaxError: expected except or finally` near **`existing_policy`** when the body was accidentally dedented).
- **RunScript robustness**: The **`xbmc.python.script`** entry is now **`skippy_runscript_entry.py`**, which handles **`open_segment_editor`**, **`discover_editor_button`**, and **`install_editor_keymap`** **without importing** **`segment_marker`**, so a broken marker script no longer blocks the Segment Editor launcher (Kodi still parses **`segment_marker.py`** when other commands import it).
- **Segment Marker toasts**: All marker **`show_toast(...)` paths use `notify_skippy(..., prefer_builtin=True)`** so notifications still show **under fullscreen WindowXML** (same path as mutual-exclusion messages). **`SegmentEditorDialog`** re-sets **`skippy_editor_modal_open`** from **`onInit`** so **`RunScript(segment_marker)`** reliably sees an open editor before blocking the marker hotkey.
- **Stale “Start: …” chip**: **`marker_indicator.sync_marker_pending_indicator`** now **drops the fullscreen chip** whenever **`skippy_marker_modal_open`**, **`skippy_marker_second_press_flow`**, or **`skippy_editor_modal_open`** is active, and **`pick_marker_option`'s `finally`** calls **`clear_marker_chip_and_sync()`** after **`doModal`** so picker **close/cancel** cannot leave orphaned controls until the next loop tick (**`marker_indicator.py`**, **`segment_marker.py`**).

## [3.3.7] - 2026-05-24

### Fixed
- **Pending marker chip (“Start: …”) not disappearing**: The fullscreen chip is **`ControlImage` / `ControlLabel`** added by the **addon service** to `Window(12005/10800)`; those widgets live inside the **service** Python interpreter. **`segment_marker.py` runs via `RunScript` in a different interpreter**, so importing `marker_indicator` there cannot call `removeControl` on the real controls (`marker_indicator.sync_marker_pending_indicator` only had empty refs). RunScript now sets **`Window(10000)`** property **`skippy_marker_chip_force_detach`**, emits **`NotifyAll(..., skippy_detach_marker_chip)`**, and **`service.py`** / each **`sync_marker_pending_indicator`** pass **`force_detach_marker_pending_overlay()`** immediately with **retried `removeControl`** (`marker_indicator.py`, `segment_marker.py`, `service.py`).
- **Repo**: `tools/_repair_marker_try_block.py` restores the valid `try`/`finally` second-press save block when `segment_marker.py` ends up dedented (`SyntaxError: expected except or finally` around `existing_policy`).

## [3.3.6] - 2026-05-24

### Changed
- **Segment Marker chip**: Once **end time** is set, the pending **top-left chip is cleared immediately** (before policy/type/confirm dialogs) so playback no longer carries a phantom “marker” badge through the picker. A short-lived window property (**`skippy_marker_second_press_flow`**) fills the timing gap until the picker sets **`skippy_marker_modal_open`**, so Segment Editor stays blocked consistently (`segment_marker.py`, `segment_editor_utils.py`).

### Fixed
- **Toasts blocked by Kodi modals**: **`settings_utils.notify_skippy(..., prefer_builtin=True)`** sends the Kodi **`Notification(...)` built-in** (with **`skippy_notification_icon`**) when the fullscreen segment editor or picker would hide **`xbmcgui.Dialog().notification`** — used for mutual-exclusion prompts in both directions.
- **Duplicate `marker_flow_blocks_editor_launch`** / broken **`MARKER_SECOND_PRESS_FLOW`** helpers in **`segment_editor_utils.py`** (repair).

### Notes
- **Saving a marker when a sidecar already exists**: behavior is solely the **Existing segment overlap policy** (**Settings → Segment Marker**). **`Merge non-overlapping`** (default) writes **nothing** when the new range overlaps an existing chapter/EDL row and shows “not changed”; **`Append always`** keeps existing rows **and adds** the marked range regardless of overlaps/nesting; **`Overwrite`** / **`Keep both`** / **`Replace file`** do what their labels say in `save_to_edl` / `save_to_chapters_xml`.

## [3.3.5] - 2026-05-24

### Fixed
- **Segment Marker → chapters.xml**: `save_to_chapters_xml` now accepts the same **`addon`** positional argument as **`save_to_edl`**, fixing **`TypeError: … got multiple values for argument 'policy'`** when saving **Both** EDL + XML after an EDL merge skip.
- **Marker chip after cancel / errors**: `SegmentTypePickerDialog` defaults to **cancelled** until an explicit OK/list pick; leaving the skin dialog without a mapped back action no longer behaves like confirming the first keyword. Clearing the overlay calls **`marker_indicator.sync_marker_pending_indicator`** so the top-left chip hides immediately after abort or **`finally`**.
- **Mutual exclusion**: **Segment Editor** does not launch while a marker **pending start**, **picker modal**, or **chip** property is active; the **marker hotkey** is ignored while the editor modal flag is set (`segment_editor_utils.py`, `segment_editor_session.py`, `segment_marker.py`).

## [3.3.4] - 2026-05-22

### Changed
- **Segment Editor hotkey**: A second press while an editor window is active **requests close** (`Window.Property` IPC) instead of stacking multiple `RunScript` instances; overlapping launches within ~**1.2** s are **debounced**. (`segment_editor_session.py`, `segment_editor_utils.py`, `segment_editor_dialog.py`)
- **Segment Marker**: After marking **start**/**end**, the pending chip is always cleared via **`finally`**, cancelling the type/policy/save dialogs no longer strands the overlay. **`SegmentTypePickerDialog`** treats **cancelled** as abort, resets **selected_index** on back, clears **cancelled** on OK, and uses **extended back action ids** (`xbmcgui` aliases alongside 10 / 92 / 216).

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

