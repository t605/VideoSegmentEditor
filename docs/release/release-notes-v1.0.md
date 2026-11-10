# Release notes

## 1.0 - first public release

Video Segment Editor cuts the parts you want out of a video and joins them into one new MP4.

### What it does
- Load a video (MP4, MOV, AVI, MKV), play it with the built-in VLC preview, and mark up to 10 start/end segments with the Mark buttons or by typing times (hours:minutes:seconds, for example `00:01:05.250`; short forms `1:05` and `65` also work).
- Edit, reorder and remove segments, then create ONE new MP4 with a single button ("Create Video").
- Exact cuts: every segment is re-encoded (H.264, CRF 18, AAC with a bitrate by channel count: mono 96k, stereo 192k, 5.1 384k, 7.1 512k, faststart), then the segments are joined.
- The original file is read-only: never changed, moved, renamed or deleted. The result is saved next to it as `<name> (segmented).mp4` (then `(segmented 2)`, ...), never overwriting.
- The finished file is checked (exists, not empty, picture and sound present, length matches the segments) before "Done".
- Disk-space check before starting; plain-language messages; Cancel works; temporary files are kept and named after a failure (folders older than 7 days are removed at the next start).
- English and Russian interface, switchable in the window.
- Without VLC the preview is off but typed times still work.

### How to install
1. Download `VideoSegmentEditor.zip` from the Assets list below.
2. Unzip it into a folder of your own and double-click `VideoSegmentEditor.bat`.
3. The launcher checks Python, FFmpeg and VLC, lists what is missing on one screen, asks ONE question (Y/N) and installs everything with winget. This needs internet and can take a few minutes; Windows may show one permission window for VLC: click Yes.
4. The files are unsigned, so Windows may show the blue "Windows protected your PC" window: click "More info", then "Run anyway" (only for a file you got from a source you trust).

A Setup program (`.exe`) is not part of this release. It was tested only on the author's PC, so it will be added to a later release after a test on a clean PC.

The full guide is `README.txt` inside the zip (install steps, every message, troubleshooting).

### Known limits
- Windows 10/11 only. The first start needs internet if Python, FFmpeg or VLC are missing.
- A segment cutter, not a video editor: no transitions, text, filters, audio-only output.
- Output is always MP4 (H.264 + AAC); HDR is converted to SDR; subtitles and chapters are dropped.
- Maximum 10 segments; the segment list is not saved between sessions.
- Join accuracy: about 13 ms of sound drift per junction (about 120 ms after 10 segments), measured on generated test videos on one laptop and not repeated after the last fixes. Short sound gaps at junctions were not tested with real speech or music.
- Speed was measured on one laptop only: 1080p about 3.4x faster than real time, 4K slower than real time.
- The launcher's install steps were exercised by automated dry-run tests and by hand on the author's PC, which already has Python, FFmpeg and VLC. A clean PC without them was not tested by anyone else.
- Real VLC rendering, display scaling and the launcher paths were checked by hand only on the author's own PC (see `docs/test-checklist.md` for what was and was not run).

### Quality
- 444 automated tests (offline; 1 skipped), all passing in the last run before publishing.
- Built with Claude Code; rules and decisions by the author.

### Downloads
- `VideoSegmentEditor.zip` (unzip, then run `VideoSegmentEditor.bat`)

### Licence
MIT.
