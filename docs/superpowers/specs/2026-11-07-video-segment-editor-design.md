# Video Segment Editor - Design

Date: 2026-11-07. Status: built; updated 2026-11-09 after fix round 1 (see section 11; sections 4, 5, 6 and 8 below were brought up to date). Source requirements: `prompt.txt` (full spec) and `mock screen.png` (look).

## 1. Intent

The owner wants a simple Windows desktop tool: load a video, play and seek, mark up to 10 start/end segments, reorder them, and press one button to get a new video containing only those segments, in list order. It is a segmenting tool, not a general video editor.

Why it matters: accuracy of the cuts and audio/video sync come before speed. The original file is never touched.

## 2. Goals, non-goals, anti-goals

Goals
- Accurate (frame-level) cuts, H.264 + AAC, MP4 output, source resolution and frame rate kept.
- Embedded playback with exact seeking, play / pause / stop, volume.
- Segment list: add by Mark Start / Mark End, edit, delete, clear all, move up/down, total duration, max 10.
- Background processing with progress; GUI never freezes.
- Plain-language errors; never report success until the output file is verified.

Non-goals
- No transitions, filters, text, multi-track editing, or audio-only editing.
- No stream-copy "fast mode" in version 1.
- No macOS/Linux support.

Anti-goals (failure even if it "works")
- Any change to, or overwrite of, the source file.
- Overwriting an existing output file without confirmation.
- Black frames, gaps, A/V drift, or unselected footage in the output.
- A "success" message when the output is missing or has the wrong duration.

## 3. Decisions made by the owner

1. Windows tool following the standard pattern in the shared rules file two folders up (`CLAUDE.md`): `VideoSegmentEditor.bat` launcher, `README.txt` (plain text, CRLF), `build_release.ps1`, zip at `VideoSegmentEditor.zip` in the `Finished tools\VideoSegmentEditor` folder next to `Work In Progress`, runtime data under `%LOCALAPPDATA%\VideoSegmentEditor`.
2. Python 3.11+, Tkinter/ttk, FFmpeg + FFprobe, python-vlc, threading/queue, tempfile/pathlib.
3. The launcher finds or installs Python and python-vlc. It installs FFmpeg and VLC with winget, only after the user agrees (since 2026-11-09 on ONE screen with ONE Y/N question, see section 12). FFmpeg is not bundled in the zip.
4. If VLC is not found, the app shows a message with the VLC download link (videolan.org). Note: python-vlc is only a binding and does not contain VLC. Without VLC the preview is disabled, but the user can type timestamps by hand and still create the video.
5. Look: dark theme and layout of the mockup (`mock screen.png`, which is kept locally and is not published). Content rules come from the prompt: times shown as HH:MM:SS.mmm everywhere, table buttons Move Up, Move Down, Edit, Delete, Clear All. The "3 / 10" counter and "Total selected" line from the mockup are kept.
6. Logo (white panda "MY") as window and taskbar icon and next to the title; `SetCurrentProcessExplicitAppUserModelID`; `iconbitmap` again after about 300 ms (CustomTkinter rule does not apply because we use plain ttk, but the delayed icon call is harmless and kept).
7. English interface by default, plus a language button (added 2026-11-07, forgotten in the original prompt): the owner can switch the whole interface between English and Russian with one button in the header. Builder's calls for it: default English; button shows the other language ("RU" while English is shown, "EN" while Russian is shown); the choice is saved in `%LOCALAPPDATA%\VideoSegmentEditor\settings.json` and restored on start; switching takes effect immediately without restart and without losing loaded video, segments or marks; all visible text is translated (labels, buttons, table headers, dialogs, status and error messages including those raised by `video_processor`); timestamps stay HH:MM:SS.mmm in both languages; the README stays English with one short Russian section describing the button (owner to confirm if a full Russian README is wanted).

## 4. Builder's calls (not yet confirmed by the owner)

- Source files live in the project root: seven runtime modules (`main.py`, `gui.py`, `i18n.py`, `create_flow.py`, `segment_manager.py`, `video_player.py`, `video_processor.py`), plus `requirements.txt`, `README.txt`, `LICENSE`, `assets\`. The prompt asks for `README.md`; the standard pattern asks for `README.txt`. Call: ship `README.txt` in the zip (standard pattern wins for a Windows tool).
- Version constant `APP_VER = "1.0"` in `main.py`, repeated in README.txt.
- Re-encode settings: libx264, CRF 18, preset medium, `-pix_fmt yuv420p`, AAC 192 kb/s, `-movflags +faststart`. Frame rate kept via `-fps_mode passthrough`/source rate; resolution kept.
- Video-only sources (no audio track): output has no audio; no error.
- Sources with odd sizes: SUPERSEDED in fix round 1 - they are cropped by 1 pixel to an even size (libx264 rejects odd sizes); the Create dialog says so.
- Tests with `unittest` (standard library only); one integration test generates a 10 s test clip with FFmpeg, cuts 3 segments, and checks the output duration with FFprobe. It is skipped with a clear message when FFmpeg is absent.
- Overwrite protection: unique name first (`(segmented)`, `(segmented 2)`...). Because a unique name is always found, no overwrite prompt is ever needed.
- Closing the window during processing: ask to confirm, then terminate FFmpeg and keep the temp folder.

## 5. Architecture

| File | Responsibility |
|---|---|
| `main.py` | Entry point, `APP_VER`, timestamped rotating log (stdout/stderr to `%LOCALAPPDATA%\VideoSegmentEditor\app.log` under pythonw, rotated at 1 MB), DPI awareness, taskbar ID, start-failure message box, old work-folder sweep, starts the GUI. |
| `i18n.py` | English and Russian texts (`t()`), saved language choice. Every visible text has a key in both dictionaries. |
| `create_flow.py` | Pure helpers for the Create Video flow: work root, progress mapping, conversion notes, sweep of old `job_*` folders. |
| `gui.py` | All Tkinter widgets, dark ttk styling, event handlers, dialogs. No FFmpeg calls, no business rules. Updates from workers only via a queue polled with `after`. |
| `video_player.py` | Wraps python-vlc: load, play, pause, stop, seek (ms), current time, volume, availability check. Reports "VLC missing" without crashing. |
| `segment_manager.py` | Pure logic: `Segment`, list of up to 10, add/validate/edit/delete/clear/move, total duration, time parse and format (HH:MM:SS.mmm). No GUI, fully unit-tested. |
| `video_processor.py` | FFprobe metadata, finding FFmpeg/FFprobe, building commands, extract each segment, concat, verify output, unique output name, cancel, progress callbacks. Runs in a worker thread. No GUI imports. |
| `VideoSegmentEditor.bat` | Bootstrap (ASCII, CRLF): find Python 3.11+, else install via winget (ask first); create venv under `%LOCALAPPDATA%\VideoSegmentEditor`; pip install requirements; check FFmpeg and VLC, offer winget install; start with `pythonw`. |
| `build_release.ps1` | Runs tests, checks README version equals `APP_VER`, copies a whitelist, fails on private/dev files, writes the zip (flat). `-Dest` for trial builds. |
| `tests\` | `unittest` files. Not shipped. |

Data flow: Load Video -> `video_processor.probe()` (duration, size, fps, has audio) -> player loads file -> user marks segments -> `segment_manager` validates -> Completed -> confirm -> worker thread: temp dir, extract N segments, concat, verify, rename into place -> queue messages -> progress bar and status.

## 6. Behaviour details

Loading: file dialog (MP4, MOV, AVI, MKV, plus "All files"). Probe failure shows "This file could not be read as a video." Shows `name - duration - WxH` as in the mockup. Enables controls. Source is opened read-only.

Playback: Play, Pause, Stop (stop returns to 0), seek slider, current/total time, volume slider. Playback controls are independent of marking.

Marking: Mark Start stores the current player time and shows it on the button (as in the mockup). Mark End validates and adds a row at once. Rules: end > start; end <= duration; End without Start refused with a message; zero-length refused; at 10 segments a message appears and further marking is refused. A pending start can be cleared by marking Start again.

Editing: Edit opens a small dialog with Start and End text boxes (HH:MM:SS.mmm; short forms like 1:05 accepted and normalised), same validation. Selected row highlighted. Moving changes the order used for output. Overlapping segments are allowed (the owner may repeat footage), with no warning.

Create video: needs at least one segment; confirm dialog showing count, total duration, and output name; controls disabled while running; temp dir `tempfile.mkdtemp` inside the output drive's temp location is NOT used - it is created under `%LOCALAPPDATA%\VideoSegmentEditor\work\` to avoid cluttering the source folder; segments named `seg_001.mp4` ...; concat with the concat demuxer (all parts have identical encoding, so `-c copy` at the join is safe); verification: file exists, size > 0, FFprobe duration within 0.5 s plus 0.1 s per segment of the sum of segment durations, has a video stream, and an audio stream when the source had one. Success shows the output path. Temp files are removed only after verification passes; on failure the folder is kept and its path is shown.

Disk space: before starting, estimate = source size scaled by selected/total duration times 1.5. The work folder needs 2 x estimate and the output folder 1 x estimate (each at least 200 MB); on the same drive the needs add up. Warn and stop if lower. (Original rule: 2 x scaled size on the output drive; replaced because the measured peak is about 3 x the output.)

Errors handled (each with a plain message): invalid file, FFmpeg/FFprobe missing, unsupported codec, VLC missing, bad timestamps, corrupted source, low disk space, permission denied, failed extraction, failed concat, window closed during processing.

Trade-off to explain in README: stream copy is fast but can only cut at keyframes, so cuts land early or show frozen/black frames; re-encoding is slower but cuts at the exact frame. Version 1 always re-encodes.

Layout (top to bottom, resizable, usable at 1920x1080, minimum 900x760 at 100 % display scaling, scaled by the Windows UI scale and limited to the usable screen): header row (logo, title, Load Video); file info line; video area; transport row and seek bar with times; Mark Start / Mark End buttons with status line; "Selected Segments" table with `n / 10`; buttons Move Up, Move Down, Edit, Delete, Clear All; total selected line; bottom area with the Create Video button (first drafted with a longer label starting with "Completed", shortened after the 2026-11-09 reviews), progress bar, current operation line, status message, final output path (selectable text).

## 7. Testing and what will be reported

Automated: time parsing/formatting, every validation rule, max 10, edit/move/delete/clear, total duration, unique output names, FFmpeg command construction, verification rules, plus the FFmpeg integration test. Manual checklist (delivered in README or a separate checklist file kept in the project, not shipped): load, playback, seek accuracy, marking, edit, reorder, processing, each error case, VLC missing, close during processing. At the end I will state plainly which items were run and which were not (for example, anything needing a real VLC window may only be checked by running the app).

## 8. Packaging

Release zip contents (whitelist, 14 files): the seven runtime `.py` files, `requirements.txt`, `VideoSegmentEditor.bat`, `README.txt`, `LICENSE`, `assets\logo.png`, `assets\logo.ico`, `assets\logo_header.png`. Not in the zip: CLAUDE.md, tests, `build_release.ps1`, docs, caches, venvs. Besides the zip there is a separate Setup program, `VideoSegmentEditor-Setup.exe` (decision of 2026-11-09, section 12; it replaces the earlier decision to build no exe in version 1). README.txt keeps a developer section about it. Neither the installer files (`installer\VideoSegmentEditor.iss`, `build_installer.ps1`) nor the Setup exe are in the zip.

## 9. Left to the builder

Exact colours and spacing within the dark style, widget internals, thread/queue mechanics, wording of messages (plain language), log format.

## 10. Open items for the owner

None blocking. Items in section 4 are my calls; veto any.

## 11. Fix round 1 (2026-11-07 to 2026-11-09): decisions and additions

A nine-specialist test of the first build found 60 defects (register BL-001 to BL-061). The owner decided:

- **D1 - the two-stage encode is kept** (extract each segment re-encoded, join with `concat -c copy`). A single-pass encode (trim/concat filters or one input per segment) was measured: about 8 % less time and no A/V drift, but about 30 % more FFmpeg memory, no kept partial parts, and it conflicts with `prompt.txt` section 4. The owner chose not to change the design. The measured effect of the join is documented as a limit: audio about 13 ms later per junction (about 120 ms after 10 segments), 21-39 ms audio gaps and 21-61 ms picture time-stamp gaps at junctions (README.txt section 9). That measurement predates the other fixes and was not repeated.
- D2 - repo not public until everything is done; `.superpowers/`, `prompt.txt` and `mock screen.png` are not published (owner runs the git steps). D3 - MIT licence. D4 - the logo is public.
- D5 - a Cancel button in v1.0. D6 - odd media is converted properly. D7 - 125-150 % display scaling must work.

Features added in the fix round (all in version 1.0):

- Processing: every part is probed after it is cut; stronger output verification (stream lengths, A/V end time, frame count, picture start, audio track count; relaxed for variable frame rate and sources whose picture starts later than the sound); odd sizes cropped; HDR PQ/HLG tone-mapped to SDR BT.709 (mobius); 10-bit, 4:4:4, full-range and RGB converted to 8-bit 4:2:0; interlaced deinterlaced (bwdif); ALL audio tracks kept with channel-dependent AAC bitrate; keyframe about every 2 s; output name shortened when too long; combined disk check; rotation shown as the display size; source locked/missing messages.
- GUI: Cancel button with confirm and non-blocking close; worker threads always post a terminal event; the player degrades to manual entry after 3 failures; Mark End clamped to the video length; Open folder button after failure or cancel; status levels with glyph; self-clearing warnings; themed dialogs; tooltips for transport buttons; dark title bar; DPI-scaled layout; conversion notice in the Create dialog.
- Runtime hygiene: timestamped rotating `app.log`, start-failure message box, sweep of work folders older than 7 days, BOM-tolerant `settings.json`.
- Launcher: waits for a key when it printed a note; FFmpeg search also covers `Program Files\ffmpeg\bin`.
- Repo: `LICENSE`, `.gitattributes` and `.gitignore` rules, `README.md` install path, `docs/test-checklist.md` extended, `tests/test_gui_smoke.py` and the other new test files (444 tests).

Still open (see `docs/test-checklist.md`, section L): real VLC "play to the end then Mark End", click in the VLC picture then keys, the 5-minute example through the real window, a real 125/150 % display, real HDR footage, playback of the output in Windows Media Player / Movies and TV, Russian wording by a native speaker, a clean-PC launcher run.

## 12. Setup program and one-screen launcher (owner's decision 2026-11-09)

This section replaces the earlier statements that no exe is built in version 1 and "the PyInstaller guide is only a section in README.txt".

- **Two ways to install.** The zip with `VideoSegmentEditor.bat` (as before) and a separate `VideoSegmentEditor-Setup.exe`. The Setup is not inside the zip.
- **What the Setup contains.** A PyInstaller ONE-FOLDER build of `main.py` (windowed, with `assets\`, python-vlc and all modules), wrapped by an Inno Setup installer. It is per-user (no administrator rights), installs to `%LOCALAPPDATA%\Programs\Video Segment Editor`, adds Start-menu entries (the program and a "Read me" entry) and an optional desktop icon, and installs `README.txt` and `LICENSE`. It contains neither FFmpeg nor VLC.
- **Missing programs.** If FFmpeg or VLC are missing, ONE page lists them with approximate sizes and has one tick box; if ticked, Setup runs `winget install` for them after copying the program (several minutes, no further question; Windows may show one permission window for VLC). Silent mode (`/VERYSILENT`) installs the program only, unless `/INSTALLMISSING=1` is given.
- **Launcher.** `VideoSegmentEditor.bat` checks Python, FFmpeg and VLC first, shows ONE screen with everything missing, asks ONE Y/N question, installs with winget without further questions and checks again by itself. `/check` stays read-only. The black window waits for a key only after a note, when Python is missing, or on a problem message.
- **New files (not shipped in the zip):** `installer\VideoSegmentEditor.iss`, `build_installer.ps1` (tests, version check, private build environment, PyInstaller, Inno Setup compile). Built with `powershell -NoProfile -ExecutionPolicy Bypass -File build_installer.ps1`; needs Python and Inno Setup 6.
- **Not verified.** Setup was rehearsed on the development PC only (silent install, start, uninstall). The wizard pages, the winget step, a clean PC and SmartScreen behaviour are listed in `docs/test-checklist.md`, section N, and were not run.
