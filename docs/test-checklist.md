# Manual test checklist - Video Segment Editor 1.0

Run this by hand on a real Windows PC with the real program (`VideoSegmentEditor.bat`), real VLC and real FFmpeg.
The automated tests (`python -m unittest discover -s tests`) cover the logic; this list covers what a
script cannot see. Fill in **Result** (PASS / FAIL / N/A + a short note) and **Date** for each line.
Not shipped in the release zip.

Test material: one short MP4 with sound (about 1-5 min), one video without sound, one MKV and one AVI,
one file with a name like `Tom's [clip] & friends - שלום.mp4`, a text file renamed to `fake.mp4`.

## A. Items earlier build tasks could NOT verify (do these first)

| # | Check | Result | Date |
|---|---|---|---|
| A1 | Visual look matches the mockup (`mock screen.png`; the mockup is kept locally and is not published, so only the owner can compare): dark theme, logo, layout, readable contrast, nothing clipped at 900x760, 1100x840 and maximised on 1920x1080 | | |
| A2 | Real VLC picture is drawn INSIDE the video frame (not in a separate window), also after resizing the window | | |
| A3 | Click inside the video picture, then press Delete / Enter: nothing breaks, keys still reach the program (the table keys work after clicking the table) | | |
| A4 | Real file-open dialog: shows MP4/MOV/AVI/MKV filter and "All files"; Cancel in the dialog changes nothing | | |
| A5 | Real message boxes (errors, confirm questions) appear in front, with readable text and the right buttons, in English and in Russian | | |
| A6 | Windows display scaling 125% and 150%: no clipped text or buttons, logo sharp, video area usable | | |
| A7 | Taskbar and title bar show the panda logo (not the Python feather), also after the window has been open a second | | |
| A8 | Start under `pythonw` (the .bat): no console window; a forced error writes to `%LOCALAPPDATA%\VideoSegmentEditor\app.log` | | |
| A9 | Tab order through the controls is sensible; focus is visible | | |
| A10 | Audio: volume slider changes loudness; sound plays in sync | | |
| A11 | Russian wording read by a native speaker: nothing wrong, cut off or too long for its button | | |
| A12 | Launcher paths never run: Python missing, winget install of Python / FFmpeg / VLC, answering N, requirements change, broken venv rebuild, VLC missing prompt, a truly read-only program folder, a UNC path start | | |
| A13 | Real read-only output folder and a nearly full output drive give the plain messages; source untouched | | |
| A14 | Close the window while FFmpeg is still running: stops within about 5 s; a `.part` file may remain (delete it), source untouched | | |
| A15 | Close the window while the final check ("Checking the result") runs | | |
| A16 | A source file larger than 1 GB: load, seek, create | | |

## B. Loading

| # | Check | Result | Date |
|---|---|---|---|
| B1 | Load an MP4: the info line shows `name - duration - WxH` and the controls become active | | |
| B2 | Load a MOV, an MKV and an AVI | | |
| B3 | Load `fake.mp4` (not a video): message "This file could not be read as a video.", nothing else changes | | |
| B4 | Load a video whose name has an apostrophe, brackets, `&` and Hebrew/Unicode characters | | |
| B5 | Load a second video while segments exist: asks first; "No" keeps everything | | |
| B6 | Start with FFmpeg removed from PATH (rename or use a PC without it): the FFmpeg help message appears, the program does not crash | | |

## C. Playback and seeking

| # | Check | Result | Date |
|---|---|---|---|
| C1 | Play, Pause, Stop (Stop returns to 0:00:00.000) | | |
| C2 | Drag the seek slider while playing and while paused; time label follows | | |
| C3 | Seek accuracy: seek to a known moment (for example 00:01:05.000) and compare with VLC / another player: same picture within a frame or two | | |
| C4 | Seek to the very end and the very start | | |
| C5 | Volume slider: 0 is silent, 100 is loud | | |
| C6 | Resize the window during playback: picture follows, no crash | | |

## D. Marking

| # | Check | Result | Date |
|---|---|---|---|
| D1 | Mark Start: the button shows the marked time; Mark Start again replaces it | | |
| D2 | Mark End after Mark Start: a row appears at once, counter increases (`1 / 10`) | | |
| D3 | Mark End without Mark Start: message "Press Mark Start first, then Mark End." | | |
| D4 | End before or equal to start: refused with a message | | |
| D5 | Mark the 10th segment, then try an 11th: message "You can have at most 10 segments." | | |
| D6 | Overlapping segments and the same footage twice are accepted | | |

## E. Editing the list

| # | Check | Result | Date |
|---|---|---|---|
| E1 | Edit (button, Enter, double-click): dialog with Start and End; `1:05` and `65` are accepted and shown as `00:01:05.000` | | |
| E2 | Edit with a bad time (`abc`, `99:99`, end past the video length): plain message, list unchanged | | |
| E3 | Enter = OK and Esc = Cancel in the edit dialog | | |
| E4 | Delete (button and Delete key), Clear All (asks first) | | |
| E5 | Move Up / Move Down change the order; the selection follows the row; buttons disabled at the ends | | |
| E6 | "Total selected" equals the sum of the rows after every change | | |

## F. Creating the video

| # | Check | Result | Date |
|---|---|---|---|
| F1 | 3 segments in a non-original order: confirm dialog shows count, total, file name, folder; output plays in the table order | | |
| F2 | Output name is `<name> (segmented).mp4`; creating again gives `(segmented 2).mp4`; nothing overwritten | | |
| F3 | Output duration equals the total (within a fraction of a second); no black frame or gap at the joins; sound in sync | | |
| F4 | Source file unchanged (same size, same date) | | |
| F5 | Source without sound: output builds, no sound, no error | | |
| F6 | A segment that ends exactly at the end of the video | | |
| F7 | A segment that starts at a non-keyframe moment: first frame is the chosen frame | | |
| F8 | While creating: the window does not freeze, progress and operation text update, other controls are locked, the language button still works | | |
| F9 | Temp folder `%LOCALAPPDATA%\VideoSegmentEditor\work\job_...` is gone after success | | |
| F10 | The result path box can be selected and copied | | |

## G. Error cases (each must show a plain message and never a false "Done")

| # | Check | Result | Date |
|---|---|---|---|
| G1 | Corrupted / truncated source | | |
| G2 | Unsupported codec | | |
| G3 | Low disk space (use a small RAM disk or USB stick): message with MB needed and free | | |
| G4 | Read-only source folder: "Cannot save in this folder..." | | |
| G5 | FFmpeg removed while the program runs (rename ffmpeg.exe): plain error, temp folder kept and its path shown | | |
| G6 | Empty list: the big Create button is greyed out and cannot be pressed (no message can appear); it becomes active with the first segment | | |

## H. No VLC

| # | Check | Result | Date |
|---|---|---|---|
| H1 | Without VLC (or `set VSE_FORCE_NO_VLC=1` before starting): message with the VLC link, playback controls off | | |
| H2 | The VLC link opens the VLC download page | | |
| H3 | Manual entry (type start and end, "Add segment") works and the video can be created | | |
| H4 | 64-bit Python with 32-bit VLC only: the message is understandable | | |

## I. Close during processing

| # | Check | Result | Date |
|---|---|---|---|
| I1 | Close the window while creating: question "Stop and close?" with Yes/No in the program language; "No" continues | | |
| I2 | "Yes": the status shows "Stopping... please wait.", the window keeps responding and closes within about 5 seconds, no FFmpeg process left (Task Manager) | | |
| I3 | After closing: temp folder kept; no `.part` file beside the source (if one remains, it can be deleted) | | |
| I4 | Source file untouched after a cancelled run | | |

## J. Language button (RU / EN)

| # | Check | Result | Date |
|---|---|---|---|
| J1 | Starts in English; button shows `RU` | | |
| J2 | Click: every visible text turns Russian (labels, buttons, table headers, status), button shows `EN`; times stay HH:MM:SS.mmm | | |
| J3 | Loaded video, segments, marked start and playback position survive the switch | | |
| J4 | Dialogs and error messages appear in the chosen language | | |
| J5 | Close and reopen: the language is remembered (`settings.json`) | | |
| J6 | Switch language while creating a video: progress text changes, creation continues | | |

## K. Release package (after `build_release.ps1`)

| # | Check | Result | Date |
|---|---|---|---|
| K1 | Unzip `VideoSegmentEditor.zip` into a new empty folder on a clean user account / PC and double-click the .bat: the whole first-run path works | | |
| K2 | README.txt opens in Notepad, Russian section readable, no garbled characters | | |
| K3 | The zip holds only the files listed in README.txt "Files in this package" | | |

## L. Items nobody has verified yet (fix round 1; leave Result/Date empty until run)

| # | Check | Result | Date |
|---|---|---|---|
| L1 | Real VLC, play the video to the very end, then press Mark End: the segment ends at the video length (not refused, not 0) | | |
| L2 | Click inside the VLC picture, then press Delete / Enter / Space: the keys still reach the program (table, buttons) | | |
| L3 | The owner's 5-minute example through the real window: 00:00:15-00:00:30, 00:01:10-00:01:35, 00:03:00-00:03:20 give a 60 s video (about 60.07 s), sound in sync, no gap at the joins; write down how long it took | | |
| L4 | Real display at 125% and at 150% (not emulated): nothing clipped at the minimum size, logo sharp, table readable, Create/Cancel/Open folder visible in every state | | |
| L5 | Real HDR footage (a phone HDR10 / HLG clip): the Create dialog says "HDR to SDR"; the result looks natural on a normal screen (not grey, highlights not burnt out); note the peak brightness of the source | | |
| L6 | Play the output in Windows Media Player and in Movies & TV (not only VLC): picture and sound, seeking, no green frame | | |
| L7 | Russian wording of every new text (Cancel, Open folder, status messages, conversion notes, tooltips, the Create dialog) read by a native speaker | | |
| L8 | Speech or music cut at 3 and at 10 junctions: listen for ticks and for sound drift at the end (README.txt section 9 says about 13 ms per junction; this was measured only with a sine tone and before the last fixes) | | |
| L9 | A 4K source and a computer with 8 GB of memory: the job finishes (4K needs about 4.4 GB for FFmpeg) | | |
| L10 | Launcher on a clean PC (superseded by section N for the one-screen flow): Python 3.12 missing and answer N: the launcher stops with by-hand steps; FFmpeg only in Program Files: found, not listed as missing | | |

## M. New features of fix round 1

| # | Check | Result | Date |
|---|---|---|---|
| M1 | While creating, a "Cancel" button shows right of the progress bar; it is not visible when idle | | |
| M2 | Cancel > question "Stop creating the video? Temporary files are kept." > No: the work continues, the button works again | | |
| M3 | Cancel > Yes: "Stopping... please wait.", then "Cancelled." (warning level), the box names the kept folder, Create is active again, no `.part` file beside the source | | |
| M4 | After a failure or cancel the "Open folder" button opens the kept `job_...` folder in Explorer; it disappears after loading another video | | |
| M5 | Status levels: dot = info, green check = success, orange triangle = warning, red cross = error; the colours are readable | | |
| M6 | Marking warnings (for example Mark End without Mark Start) vanish by themselves after about 8 s or at the next action | | |
| M7 | The 10th segment: the line above the Mark buttons says "Limit of 10 segments reached."; an 11th attempt shows the message box "You can have at most 10 segments." | | |
| M8 | Success: status "Done." with a check, box "Saved to: <path>" (selectable) | | |
| M9 | The Create question window has "Create video" and "Cancel" buttons (Russian: "Создать видео" / "Отмена"); other questions have Yes/No in the program language | | |
| M10 | Tooltips: hold the mouse over Play, Pause, Stop for half a second (EN and RU) | | |
| M11 | Mark Start turns green when set and returns to normal when cleared; the focus ring is visible on buttons, sliders, the table and entries | | |
| M12 | Dark title bar on the main window and on dialogs | | |
| M13 | Window minimum and default size scale with the display scaling; the window opens centred and never larger than the screen | | |
| M14 | HDR / 10-bit / interlaced / odd-size / multi-audio sources: the Create dialog lists "What will be converted"; the output is 8-bit 4:2:0, progressive, has all audio tracks (check with `ffprobe`); subtitles and chapters are announced as not kept | | |
| M15 | A source with 2 or more audio tracks: all tracks are in the output with their language tags (VLC: Audio > Track) | | |
| M16 | A phone video stored rotated: the info line shows the size as seen; the output is the right way up | | |
| M17 | A file name longer than about 220 characters: the output name is shortened and the file is created | | |
| M18 | A source that another program has open (exclusive lock): message "The video file is in use by another program..." | | |
| M19 | `app.log` has a time stamp on every line and a "session start" line; renamed to `app.log.1` above 1 MB | | |
| M20 | A `work\job_...` folder older than 7 days is removed at the next start; a newer one stays | | |
| M21 | Break the program on purpose (rename `gui.py`) and start it with the launcher: one message box points to `app.log` | | |
| M22 | Launcher: when the black window printed a note (answered N), it says "press any key" and waits; `.\VideoSegmentEditor.bat /check` works in PowerShell | | |

## N. One-screen launcher and the Setup program (decision 2026-11-09; Result/Date empty until run)

Launcher (`VideoSegmentEditor.bat`). Developer switches for rehearsals: `VSE_DRYRUN=1` (winget commands only printed, stops before the environment step) and `VSE_FAKE_MISSING=python,ffmpeg,vlc`.

| # | Check | Result | Date |
|---|---|---|---|
| N1 | Clean PC (no Python, FFmpeg, VLC) with winget: ONE screen lists all three with sizes, ONE Y/N question, answer Y: the three winget installs run one after the other with no further question (one Windows permission window for VLC is expected) | | |
| N2 | N1 continued: after the Python install the launcher checks again by itself in the same window (no "close and start again"), finds Python, creates the environment and starts the program | | |
| N3 | Only FFmpeg missing, only VLC missing, only Python missing: the list shows only the missing items; counter says "1 of 1" | | |
| N4 | Answer N: Python missing = stops with by-hand steps and "press any key"; only FFmpeg/VLC missing = by-hand steps, the program starts, the window waits for a key | | |
| N5 | PC without winget (PATH without WindowsApps): plain message about "App Installer", by-hand steps, nothing is run | | |
| N6 | winget present but an install fails or is cancelled (cancel the VLC permission window): second check lists what is still missing with by-hand steps, no second Y/N, the program still starts (unless Python is missing) | | |
| N7 | `VideoSegmentEditor.bat /check` on the clean PC: lists the missing items and "a normal start would list this", installs nothing, creates no folder under `%LOCALAPPDATA%\VideoSegmentEditor` | | |
| N8 | `build_release.ps1 -Dest <scratch folder>`: the byte check of the .bat still passes (ASCII, CRLF) | | |

Setup program (`VideoSegmentEditor-Setup.exe`, built by `build_installer.ps1`). Rehearsed on the development PC only: silent install into a scratch folder, program started (window title shown, `app.log` line written), silent uninstall.

| # | Check | Result | Date |
|---|---|---|---|
| N9 | Double-click Setup on a clean PC (no admin account needed): wizard shows licence, folder, tasks; installs to `%LOCALAPPDATA%\Programs\Video Segment Editor`; Start menu entry has the logo | | |
| N10 | FFmpeg and VLC missing, winget present: ONE page "Programs the editor needs" with sizes and the sentence that Setup installs them (no tick box, no question); Install: status text "Installing FFmpeg..." / "Installing VLC player...", no further question, then both are found by the program | | |
| N11 | `Setup /NOINSTALLMISSING` (wizard, missing programs, winget present): the page says Setup will NOT install them; the program is installed, nothing downloaded; at start the program says what is missing | | |
| N12 | winget missing: the page explains "App Installer" and by-hand steps, nothing is run, the program is installed | | |
| N13 | FFmpeg and VLC already installed: the page does not appear | | |
| N14 | `Setup /VERYSILENT`: program AND missing FFmpeg and VLC are installed (by default); `/VERYSILENT /NOINSTALLMISSING`: program only, no winget run (rehearsed on the development PC); `/INSTALLMISSING=1` is accepted and changes nothing | | |
| N15 | "Start Video Segment Editor now" on the last page opens the window with the logo in title bar and taskbar; the taskbar icon matches the Start menu shortcut (no second icon) | | |
| N16 | Installed exe: load a video, preview plays (real VLC), create a video, result verified ("Done."): same behaviour as from source | | |
| N17 | Uninstall (Settings > Apps): program folder and shortcuts removed; `%LOCALAPPDATA%\VideoSegmentEditor` (settings, log) stays | | |
| N18 | Antivirus / SmartScreen on the unsigned Setup and exe: note what Windows says; try a second PC | | |
| N19 | Upgrade: install a newer Setup over an installed one: replaces files, keeps settings | | |
| N20 | Setup creates the Start-menu entries "Video Segment Editor" and "Video Segment Editor - Read me" (opens README.txt); the desktop-icon task is unticked by default and creates the icon when ticked | | |
| N21 | VLC permission window (Setup and launcher): click No = VLC is not installed, the program starts without preview and says so; click Yes = VLC is found. The README text about the "Windows protected your PC" window and the VLC window matches what is really shown | | |
| N22 | Launcher pause rule: all installed fine = black window closes by itself; answer N, no winget, or one install cancelled = window waits for a key; Python missing and not installed = waits and stops | | |
