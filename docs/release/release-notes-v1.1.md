# Release notes

## 1.1 - type the start and end times by hand, with or without VLC

Video Segment Editor cuts the parts you want out of a video and joins them into one new MP4.

### What is new in 1.1
A tester could not type a time: with the video preview working there were only the Mark Start and Mark End buttons. Now you can also **type** the times:
- Two boxes, **Start** and **End**, and the button **Add segment** are in the header row of the segment list, next to "Selected Segments". They are always there, with or without VLC (before 1.1 they appeared only when VLC was missing).
- Write the times in any of these forms: `00:01:05.250` (hours:minutes:seconds), `1:05` (1 minute 5 seconds) or `65` (65 seconds). Press **Add segment** or the Enter key.
- The same rules and messages as for the Mark buttons: the end must be after the start and not past the end of the video; the limit of 10 segments counts both ways. If a time is not understood, nothing is added and what you typed stays in the box.
- You can mix both ways in one list: mark one segment with the buttons and type the next one.
- A tooltip on each box names the accepted time forms (English and Russian). The hint line under the Mark buttons now says: "Move to where the segment should begin and press Mark Start, or type the times above the table (for example 1:05)."
- The window is not taller than before: the boxes share the header row of the list. The two screenshots in the README show the new window.
- Nothing else changed: the cutting, the re-encoding, the checks before "Done", the Setup program and the launcher work as in 1.0.

### What it does
- Load a video (MP4, MOV, AVI, MKV), play it with the built-in VLC preview, and mark up to 10 start/end segments with the Mark buttons or by typing times.
- Edit, reorder and remove segments, then create ONE new MP4 with a single button ("Create Video").
- Exact cuts: every segment is re-encoded (H.264, CRF 18, AAC with a bitrate by channel count: mono 96k, stereo 192k, 5.1 384k, 7.1 512k, faststart), then the segments are joined.
- The original file is read-only: never changed, moved, renamed or deleted. The result is saved next to it as `<name> (segmented).mp4` (then `(segmented 2)`, ...), never overwriting.
- The finished file is checked (exists, not empty, picture and sound present, length matches the segments) before "Done".
- Disk-space check before starting; plain-language messages; Cancel works; temporary files are kept and named after a failure (folders older than 7 days are removed at the next start).
- English and Russian interface, switchable in the window. The program starts in English; the language you choose is remembered.
- Without VLC the preview is off, the Mark buttons are hidden and the Start / End boxes are the way to add a segment.

### How to install
There are two ways. Both files are unsigned, so Windows may show the blue "Windows protected your PC" window: click "More info", then "Run anyway" (only for a file you got from a source you trust).

**Way A: Setup program, no Python needed (easiest)**
1. Download `VideoSegmentEditor-Setup.exe` from the Assets list below and double-click it.
2. Setup installs the program for the current Windows user only (no administrator rights) into `%LOCALAPPDATA%\Programs\Video Segment Editor`. The folder is fixed: there is nothing to choose. It shows the licence and an optional desktop-icon tick box.
3. If FFmpeg or VLC are missing, one page lists them, and Setup installs them with winget after copying the program, with no further question. This needs internet and can take several minutes, and the Setup window may look frozen. Windows may show one permission window for VLC: click Yes.
4. Start "Video Segment Editor" from the Start menu.
Silent install: `VideoSegmentEditor-Setup.exe /VERYSILENT` (add `/NOINSTALLMISSING` to skip FFmpeg and VLC).

**Way B: zip and launcher**
1. Download `VideoSegmentEditor.zip` and unzip it into a folder of your own.
2. Double-click `VideoSegmentEditor.bat`. It checks Python, FFmpeg and VLC, lists what is missing on one screen, asks ONE question (Y/N) and installs everything with winget. This needs internet and can take a few minutes; click Yes in VLC's permission window.

Updating from 1.0: run the new Setup (it installs over the old program and keeps your settings), or unzip the new zip into the same folder.

The full guide is `README.txt` inside the zip (install steps, every message, troubleshooting).

### Known limits
- Windows 10/11 only. The first start needs internet if Python, FFmpeg or VLC are missing.
- A segment cutter, not a video editor: no transitions, text, filters, audio-only output.
- Output is always MP4 (H.264 + AAC) at the size of the original; HDR is converted to SDR; subtitles and chapters are dropped. A 4K video takes longer than its own length to cut (a tester reported roughly 10 to 15 minutes for about 5 minutes of what was probably 4K video); there is no switch for a smaller picture yet.
- Maximum 10 segments; the segment list is not saved between sessions. Overlapping or identical segments are accepted without a warning; closing the window with marked segments does not ask first (only while a video is being created).
- The program does not warn about an incomplete video file (for example an interrupted download).
- Join accuracy: about 13 ms of sound drift per junction (about 120 ms after 10 segments), measured on generated test videos on one laptop and not repeated after the last fixes. Short sound gaps at junctions were not tested with real speech or music.
- Speed was measured on one laptop only: 1080p about 3.4x faster than real time, 4K slower than real time.
- Tested for 1.1: 455 automated tests (11 new ones for the typed times and the window layout), the installed 1.1 program was started and its window looked at by the author (Russian and English layouts), and the Setup 1.1 was installed and removed silently on the author's PC. NOT tested: the 1.1 Setup and the typed times on another PC or by another person, a real 125 / 150 % display, a clean PC without Python, FFmpeg and VLC, SmartScreen. A friend ran the 1.0 Setup on a second PC and it installed VLC as intended; the other steps there were not recorded.
- See `docs/test-checklist.md` (section O for 1.1) for what was and was not checked by eye.

### Ideas from testers that are NOT in 1.1
Skip buttons (10 / 30 seconds), playback speed, choosing the output resolution, a warning for a duplicate segment, a warning when closing with marked segments, more than 10 segments, a shorter time display. They are noted for a later version; nothing is promised.

### Quality
- 455 automated tests (offline; 1 skipped), all passing in the last run before publishing.
- Built with Claude Code; rules and decisions by the author.

### Downloads
- `VideoSegmentEditor-Setup.exe` (Setup program, no Python needed), 12,323,745 bytes, SHA-256 `C4730E526A3973ACFB4FCDFBAE94B36C2EBE67F90767F35A2A17DEBF0D7D306A`
- `VideoSegmentEditor.zip` (unzip, then run `VideoSegmentEditor.bat`), 134,715 bytes, SHA-256 `D1180E1033A6333CCC0BA026764FE04EED201D55127A00A3541636C21CD8229B`

### Licence
MIT.
