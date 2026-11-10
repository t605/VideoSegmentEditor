# Video Segment Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Windows Tkinter tool that loads a video, lets the user mark up to 10 segments, and writes one accurately cut H.264/AAC MP4 containing only those segments in list order.

**Architecture:** Pure-logic modules (`segment_manager.py`, `video_processor.py`) have no GUI imports and carry the unit tests. `video_player.py` wraps python-vlc and degrades cleanly when VLC is missing. `gui.py` only draws and forwards events; worker threads talk to it through a `queue.Queue` polled with `after`.

**Tech Stack:** Python 3.11+, Tkinter/ttk, python-vlc, FFmpeg/FFprobe (system install), `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-07-video-segment-editor-design.md` (requirements: `prompt.txt`; look: `mock screen.png`).

**Status (2026-11-09):** all tasks below were done; the later fix round is in `2026-11-07-fix-round-1.md` (decision D1: the two-stage encode stays). The file list and whitelist in this plan are the ORIGINAL ones: the real project has seven runtime modules (`i18n.py` from Task 5b and `create_flow.py` were added), a 900x760 minimum window and a 14-file release whitelist.

**Git note (original):** the project folder was not a repository at the start. Steps that say "Checkpoint" mean: stop and let the owner commit with GitHub Desktop. Do not run git unless the owner asks.

## Global Constraints

- Python 3.11+; stdlib only except `python-vlc` (in `requirements.txt`).
- Times displayed and stored as `HH:MM:SS.mmm`; internally integer milliseconds.
- Max segments: 10. Output: libx264 CRF 18 preset medium, `-pix_fmt yuv420p`, AAC 192k, `-movflags +faststart`, MP4. Always re-encode (no stream copy).
- The source file is opened read-only and never modified, moved, overwritten or deleted.
- Output goes in the source's folder, named `<stem> (segmented).mp4`, then `(segmented 2)`, `(segmented 3)`...; never overwrites.
- Temp work dir: `%LOCALAPPDATA%\VideoSegmentEditor\work\<unique>`; deleted only after verified success; kept and its path shown on failure.
- `.bat` / `.ps1`: ASCII only, CRLF, no emoji. `README.txt`: plain text, CRLF, version line `version 1.0`. `APP_VER = "1.0"` defined once in `main.py`.
- GUI thread never blocks; no FFmpeg/FFprobe call on the GUI thread. Under pythonw, stdout/stderr go to `%LOCALAPPDATA%\VideoSegmentEditor\app.log`.
- Interface language: English by default, switchable to Russian with a header button (Task 5b); all user-visible text goes through `i18n.t(key, **params)` from Task 5b on. Plain-language messages. Dark theme; logo from the shared logo files (`logo.png` / `logo.ico` in the `_Shared` folder two folders up) copied to `assets\`.
- Never in the release zip: CLAUDE.md, tests, `build_release.ps1`, docs, venvs, caches.

## Review Focus

1. Source filename with apostrophe, brackets, `&`, or Hebrew/Unicode characters: commands must be passed as argument lists (no shell) and the output name must keep the characters.
2. Source with no audio track: output builds, has no audio, no error.
3. Segment ending exactly at the video duration, or a start in a non-keyframe position: output duration within tolerance, no black frame at the join.
4. Source folder read-only or output drive nearly full: clear message, temp folder kept or removed as specified, source untouched.
5. MKV/AVI where the container reports no duration: duration falls back to the video stream, or the file is rejected with a clear message.

---

## File Structure

| File | Responsibility |
|---|---|
| `segment_manager.py` | `format_ms`, `parse_time`, `Segment`, `SegmentList` (validation, order, totals) |
| `video_processor.py` | tool discovery, probe, naming, command builders, pipeline, verification, cancel |
| `video_player.py` | `VlcPlayer` wrapper, `vlc_available()` |
| `gui.py` | `App` window and dialogs |
| `main.py` | `APP_VER`, logging, DPI, taskbar ID, start |
| `VideoSegmentEditor.bat` | bootstrap |
| `requirements.txt`, `README.txt`, `build_release.ps1`, `assets\`, `tests\` | support |

---

### Task 1: Segment logic and time helpers

**Files:**
- Create: `segment_manager.py`, `tests/__init__.py`, `tests/test_segment_manager.py`

**Interfaces:**
- Produces:
  - `format_ms(ms: int) -> str` -> `"00:01:05.250"`
  - `parse_time(text: str) -> int` accepts `HH:MM:SS.mmm`, `MM:SS`, `MM:SS.m`, `SS`; raises `ValueError` with a plain message
  - `@dataclass Segment(start_ms: int, end_ms: int)` with property `duration_ms`
  - `class SegmentError(ValueError)`
  - `class SegmentList(duration_ms: int, max_segments: int = 10)` with `add(start_ms, end_ms) -> Segment`, `edit(index, start_ms, end_ms)`, `delete(index)`, `clear()`, `move(index, delta) -> int` (returns new index; no-op at ends), `total_ms() -> int`, `is_full() -> bool`, `items` (list), `__len__`

- [ ] **Step 1: Write failing tests** in `tests/test_segment_manager.py`: `test_format_ms` (`format_ms(65250) == "00:01:05.250"`, `format_ms(0) == "00:00:00.000"`, `format_ms(3723004) == "01:02:03.004"`); `test_parse_time_forms` (`parse_time("1:05") == 65000`, `parse_time("00:00:12.500") == 12500`, `parse_time("7") == 7000`); `test_parse_time_rejects` (`"abc"`, `""`, `"1:99"`, `"-5"` raise `ValueError`); `test_add_valid`; `test_end_must_exceed_start` (equal and smaller raise `SegmentError`); `test_cannot_exceed_duration` (end > duration raises); `test_negative_start_rejected`; `test_max_ten` (11th add raises `SegmentError` whose message contains `"10"`); `test_move_up_down_and_edges`; `test_edit_validates_and_keeps_old_on_error`; `test_delete_clear_total`; `test_overlap_allowed` (two identical segments both added).
- [ ] **Step 2: Run** `python -m unittest tests.test_segment_manager -v` -> FAIL (module missing).
- [ ] **Step 3: Implement** the module per the Interfaces block; validation is a single private `_check(start, end)` used by `add` and `edit`.
- [ ] **Step 4: Run** same command -> all PASS.
- [ ] **Step 5: Checkpoint** (owner commits).

---

### Task 2: Processor basics (tools, probe, naming, commands, verification)

**Files:**
- Create: `video_processor.py`, `tests/test_video_processor.py`

**Interfaces:**
- Consumes: `Segment` from Task 1.
- Produces:
  - `class ProcessingError(Exception)` (message is user-ready)
  - `find_tool(name: str) -> str | None` (PATH, then common winget/Program Files locations)
  - `@dataclass VideoInfo(path, duration_ms, width, height, fps, has_audio)`
  - `probe(path: Path, ffprobe: str) -> VideoInfo` (runs `ffprobe -v error -print_format json -show_format -show_streams`; duration from format, else video stream; raises `ProcessingError("This file could not be read as a video.")`)
  - `unique_output_path(source: Path) -> Path`
  - `extract_cmd(ffmpeg, source, seg: Segment, out: Path, info: VideoInfo) -> list[str]` using `-ss <start> -i <src> -t <dur>` (accurate seek with re-encode), the encoding constants from Global Constraints, `-map 0:v:0`, `-map 0:a:0?`, `-avoid_negative_ts make_zero`
  - `concat_cmd(ffmpeg, list_file: Path, out: Path) -> list[str]` (concat demuxer, `-safe 0`, `-c copy`, `-movflags +faststart`)
  - `write_concat_list(parts: list[Path], list_file: Path)` (single quotes escaped as `'\''`)
  - `verify_output(out: Path, expected_ms: int, n_segments: int, had_audio: bool, ffprobe: str) -> None` raises `ProcessingError` unless file exists, size > 0, has a video stream, has audio when `had_audio`, and duration is within `500 + 100 * n_segments` ms of `expected_ms`
  - `check_disk_space(out_dir: Path, source_size: int, selected_ms: int, total_ms: int) -> None` requires free >= `max(200 MB, 2 * source_size * selected_ms / total_ms)`

- [ ] **Step 1: Write failing tests**: `test_unique_output_path` (temp dir: first `Workout (segmented).mp4`; after creating it -> `... (segmented 2).mp4`; after creating that -> `... 3`); `test_unique_keeps_unicode_and_apostrophe` (`it's [a] שלום.mp4` stem preserved); `test_extract_cmd_contents` (list, no shell string; contains `-c:v libx264`, `-crf 18`, `-c:a aac`, start formatted as seconds with 3 decimals, `-map 0:a:0?`); `test_concat_list_escapes_quote`; `test_verify_output_rules` using a stub ffprobe function injected via a module-level `_run_ffprobe_json` that the test monkeypatches (missing file, zero size, no video stream, missing audio when expected, duration out of tolerance, good case); `test_check_disk_space_low` (monkeypatch `shutil.disk_usage`); `test_probe_falls_back_to_stream_duration` (monkeypatched JSON with no format duration).
- [ ] **Step 2: Run** `python -m unittest tests.test_video_processor -v` -> FAIL.
- [ ] **Step 3: Implement** the functions above. All subprocess calls use `subprocess.run([...], creationflags=CREATE_NO_WINDOW, capture_output=True)`; ffprobe JSON goes through the single helper `_run_ffprobe_json(ffprobe, path) -> dict` so tests can patch it.
- [ ] **Step 4: Run** -> PASS.
- [ ] **Step 5: Checkpoint**.

---

### Task 3: Processing pipeline with progress and cancel

**Files:**
- Modify: `video_processor.py`
- Create: `tests/test_pipeline_integration.py`

**Interfaces:**
- Consumes: Task 2 functions.
- Produces:
  - `class Cancelled(Exception)`
  - `class VideoJob(source: Path, info: VideoInfo, segments: list[Segment], ffmpeg: str, ffprobe: str, progress: Callable[[dict], None], work_root: Path)` with `run() -> Path` and `cancel() -> None`. Progress dicts: `{"phase": "extract"|"merge"|"verify"|"done", "segment": int, "total": int, "percent": float, "message": str}`. `percent` is overall 0-100: extraction weighted by segment duration (parsed from FFmpeg `-progress pipe:1` `out_time_ms`), merge and verify the last 5 percent.
  - On failure: raises `ProcessingError` with the temp folder path in the message; folder kept. On `cancel()`: terminates the FFmpeg process, raises `Cancelled`, folder kept. On success: output moved to the unique path chosen at start of `run()`, temp folder removed.

- [ ] **Step 1: Write failing integration test** `test_three_segments_roundtrip`: skip with message `"FFmpeg not found"` if `find_tool("ffmpeg")` is None. Generate a 10 s clip with `testsrc2` + `sine` at 640x360 25 fps into a temp dir; cut segments (1000-3000), (5000-6500), (8000-9000) ms; run `VideoJob`; assert output name `<stem> (segmented).mp4`, `ffprobe` duration within 0.4 s of 4.5 s, 640x360, audio present, source file size and mtime unchanged, work dir removed. Add `test_no_audio_source` (clip without audio -> succeeds, no audio stream), `test_failure_keeps_temp_dir` (segment past end of a truncated/garbage file -> `ProcessingError`, work dir still exists and message contains its path), `test_cancel` (cancel from the progress callback after first extract -> `Cancelled`, no output file).
- [ ] **Step 2: Run** `python -m unittest tests.test_pipeline_integration -v` -> FAIL.
- [ ] **Step 3: Implement `VideoJob`**: create work dir with `tempfile.mkdtemp(dir=work_root)`, extract `seg_001.mp4`... sequentially with `Popen` and `-progress pipe:1 -nostats`, write concat list, merge, `verify_output`, `os.replace`/`shutil.move` to the unique path, remove work dir. Map `PermissionError` and `OSError(ENOSPC)` to plain messages. Call `check_disk_space` first.
- [ ] **Step 4: Run** -> PASS (or SKIP only if FFmpeg missing; if skipped, say so in the report).
- [ ] **Step 5: Checkpoint**.

---

### Task 4: Player wrapper

**Files:**
- Create: `video_player.py`, `tests/test_video_player.py`

**Interfaces:**
- Produces: `vlc_available() -> bool`; `VLC_DOWNLOAD_URL = "https://www.videolan.org/vlc/"`; `class VlcPlayer(hwnd_getter: Callable[[], int])` with `load(path)`, `play()`, `pause()`, `stop()`, `seek_ms(ms)`, `time_ms() -> int`, `length_ms() -> int`, `set_volume(0..100)`, `is_playing() -> bool`, `release()`. If `python-vlc` import or `libvlc` load fails, `vlc_available()` returns False and constructing `VlcPlayer` raises `PlayerUnavailable`.

- [ ] **Step 1: Write failing test** `test_unavailable_when_import_fails`: patch the module's `_load_vlc` to raise `OSError`; assert `vlc_available()` is False and `VlcPlayer(...)` raises `PlayerUnavailable`.
- [ ] **Step 2: Run** `python -m unittest tests.test_video_player -v` -> FAIL.
- [ ] **Step 3: Implement** with a lazy `_load_vlc()`; embed with `set_hwnd`; `stop()` followed by `seek_ms(0)` state kept by the GUI; `seek_ms` pauses-safe (works while paused, so frame position can be set before marking).
- [ ] **Step 4: Run** -> PASS. **Manual (needs VLC installed):** later in Task 6.
- [ ] **Step 5: Checkpoint**.

---

### Task 5: GUI shell, theme, Load Video

**Files:**
- Create: `gui.py`, `main.py`, `assets/logo.png`, `assets/logo.ico` (copied from `_Shared`), `requirements.txt` (`python-vlc`)

**Interfaces:**
- Consumes: `probe`, `find_tool`, `VlcPlayer`, `vlc_available`, `format_ms`.
- Produces: `class App(tk.Tk)` with `load_video(path: Path)`; `main.py` exposes `APP_VER = "1.0"` and `main()`.

- [ ] **Step 1: Implement `main.py`**: log redirection when `sys.stdout is None`, `SetProcessDpiAwareness(1)`, `SetCurrentProcessExplicitAppUserModelID("MY.VideoSegmentEditor")`, then `App(APP_VER).mainloop()`.
- [ ] **Step 2: Implement `App` layout** per spec section 6: header (logo + title + Load Video), info line `name - duration - WxH`, video frame, transport row, seek bar, Mark buttons, table area, bottom area. Dark ttk theme (`clam` base), minimum size 900x700, resizable; `iconbitmap` set at start and again after 300 ms. Controls other than Load Video disabled until a video loads.
- [ ] **Step 3: Load Video**: file dialog (MP4, MOV, AVI, MKV, All files); probe in a worker thread; on success fill the info line and enable controls; on `ProcessingError` show its message. If FFmpeg/FFprobe are missing, a message box says what to install (`winget install Gyan.FFmpeg`) and the app stays open. If VLC is missing, the video area shows the text and a clickable link to `VLC_DOWNLOAD_URL`, and manual time entry (Task 6) stays available.
- [ ] **Step 4: Verify by running** `python main.py`: window shows with the logo, dark style, Load Video works on a real file, wrong file shows the message, window resizes without clipped controls. Record what was seen.
- [ ] **Step 5: Checkpoint**.

---

### Task 5b: Russian / English interface (added 2026-11-07)

**Files:**
- Create: `i18n.py`, `tests/test_i18n.py`
- Modify: `gui.py`, `video_processor.py`, `tests/test_video_processor.py`, `tests/test_pipeline_integration.py` (only where message text is asserted)

**Interfaces:**
- Produces: `i18n.LANGS = ("en", "ru")`; `i18n.t(key: str, **params) -> str` (current language; falls back to English, then to the key); `i18n.set_language(code: str) -> None`; `i18n.get_language() -> str`; `i18n.load_saved_language(settings_path: Path) -> str`; `i18n.save_language(settings_path: Path, code: str) -> None`; `ProcessingError(message_key: str, detail: str | None = None, **params)` where `str(exc)` stays the English text and `exc.key` / `exc.params` let the GUI call `t(exc.key, **exc.params)`.
- Consumes: everything user-visible in `gui.py` and every `ProcessingError` raise site in `video_processor.py`.

- [ ] **Step 1: Write failing tests** `tests/test_i18n.py`: every key present in `en` is present in `ru` and vice versa; the placeholders (`{name}`) of each key are identical in both languages; `t()` falls back to English for a missing Russian key and to the key itself for an unknown key; `set_language("xx")` raises `ValueError`; save/load round-trips through a temp settings file; a corrupt or missing settings file returns `"en"`; every `ProcessingError` raised by `video_processor` has a `key` that exists in both languages (grep-style test over the module source).
- [ ] **Step 2: Run** `python -m unittest tests.test_i18n -v` -> FAIL.
- [ ] **Step 3: Implement** `i18n.py` with two flat dicts; move all user-visible strings from `gui.py` into it, and give `ProcessingError` a key and params while keeping the English `str(exc)` identical so existing message assertions keep passing. Russian text is plain, natural Russian (not machine-literal); timestamps unchanged.
- [ ] **Step 4: Language button** in the header of `gui.py`: label is the other language's code (`RU` / `EN`); click calls `set_language`, saves via `save_language`, and re-applies all text (a single `apply_language()` method that re-sets every label, button, table heading and the window title; the table rows, info line values and status keep their data). Message boxes, dialogs and the status line use `t()` at the moment they are shown; the status line and last error are re-rendered from their stored key and params.
- [ ] **Step 5: Verify** `python -m unittest discover -s tests` all green; run the throwaway GUI script: load a clip, switch to RU, assert no English string from the key list remains in any widget text, switch back to EN, assert the loaded video info and enabled states are unchanged. State what could not be verified (how the Russian text looks, font fit of longer Russian words, button widths).

---

### Task 6: Playback, marking, segment table

**Files:**
- Modify: `gui.py`

**Interfaces:**
- Consumes: `VlcPlayer`, `SegmentList`, `parse_time`, `format_ms`, `SegmentError`.

- [ ] **Step 1: Playback controls**: Play, Pause, Stop (back to 0), seek slider (drag seeks, also while paused), current/total time in `HH:MM:SS.mmm`, volume slider; a 100 ms `after` tick updates the slider and time and never moves the slider while the user is dragging it.
- [ ] **Step 2: Marking**: Mark Start stores `time_ms()` and shows it on the button; Mark End calls `SegmentList.add`, `SegmentError` text shown in the status line (not a modal box, except the 10-segment notice which is a message box). Without VLC, two small time entry boxes plus an "Add segment" button call the same `add`.
- [ ] **Step 3: Table** (`ttk.Treeview`, columns `#`, `Start`, `End`, `Duration`, all `HH:MM:SS.mmm`): counter `n / 10`, buttons Move Up, Move Down, Edit, Delete, Clear All (Clear All asks to confirm), `Total selected: HH:MM:SS.mmm`, selected row highlighted, selection kept after a move. Edit opens a dialog with Start and End boxes, validated with `parse_time` and `SegmentList.edit`, errors shown inside the dialog.
- [ ] **Step 4: Verify by running** with VLC installed and a real file: play, pause, seek to an exact time, mark three segments, reorder, edit, delete, clear, hit the 10 limit. Then rename/hide VLC (or set env `VSE_FORCE_NO_VLC=1`, honoured by `vlc_available()`) and confirm the manual entry route works. Record what was and was not checked.
- [ ] **Step 5: Checkpoint**.

---

### Task 7: Create Video flow

**Files:**
- Modify: `gui.py`

**Interfaces:**
- Consumes: `VideoJob`, `ProcessingError`, `Cancelled`, `unique_output_path`.

- [ ] **Step 1: Implement the Completed button**: refuse with no segments; confirm dialog showing segment count, total duration and the exact output file name; disable Load Video, marking, table and player controls; start `VideoJob` in a worker thread whose `progress` callback puts dicts on a `queue.Queue`; an `after(100)` poll updates the progress bar, the operation line (`Extracting segment 2 of 3`, `Merging`, `Checking the result`), and the percentage.
- [ ] **Step 2: Finish states**: success shows `Done. Saved to: <path>` in a selectable text box (and a message box); failure shows the plain message, including the kept temp folder path; `Cancelled` shows the same with the kept folder. Controls re-enabled in all cases.
- [ ] **Step 3: Window close during processing**: ask "A video is being created. Stop and close?"; on Yes call `job.cancel()`, wait up to 5 s for the thread, then close; on No continue. Always `player.release()`.
- [ ] **Step 4: Verify by running** the success example from the prompt (a 5-minute video if one is available, otherwise a generated one): segments 00:15-00:30, 01:10-01:35, 03:00-03:20 give `<name> (segmented).mp4` of about 60 s; run again to see `(segmented 2)`; force a failure (e.g. unplug/rename the source mid-run or point at a read-only folder) and confirm the message. Record results.
- [ ] **Step 5: Checkpoint**.

---

### Task 8: Launcher

**Files:**
- Create: `VideoSegmentEditor.bat`

- [ ] **Step 1: Write the bat** (ASCII, CRLF): locate Python 3.11+ (`py -3.11`/`py -3`, then `python`; version check); if none, ask Y/N and install with `winget install Python.Python.3.12`, then tell the user to run the launcher again; create venv in `%LOCALAPPDATA%\VideoSegmentEditor\venv` if missing; `pip install -r requirements.txt` when `requirements.txt` is newer than a stamp file; check `ffmpeg`/`ffprobe` on PATH and ask Y/N before `winget install Gyan.FFmpeg`; check VLC (`%ProgramFiles%\VideoLAN\VLC\libvlc.dll`, also x86 path) and ask Y/N before `winget install VideoLAN.VLC`; declining either continues (app shows its own message); start `pythonw main.py` and exit. Every message is plain English. Work from `%~dp0`.
- [ ] **Step 2: Verify**: check file is ASCII and CRLF (`python -c` byte check printing `ASCII OK` / `CRLF OK`); run it on this PC and confirm the app opens. State that the winget install branches were NOT run unless they were.
- [ ] **Step 3: Checkpoint**.

---

### Task 9: README, release script, test checklist

**Files:**
- Create: `README.txt`, `build_release.ps1`, `docs/test-checklist.md`

- [ ] **Step 1: README.txt** per the standard pattern: header + `version 1.0`, CONTENTS, what it does, what you need, installation (unzip `VideoSegmentEditor.zip`; double-click `VideoSegmentEditor.bat`), usage, output naming, FFmpeg/VLC install by hand, the stream-copy vs re-encode trade-off, troubleshooting, "What it cannot do", developer notes on the Setup program (first planned as PyInstaller EXE instructions; replaced by the Setup program, spec section 12), files in this package. Counts quoted in it (max 10 segments, formats) must match the code.
- [ ] **Step 2: build_release.ps1** (ASCII, CRLF): runs `python -m unittest discover -s tests`, aborts on failure; compares the README version line with `APP_VER`; copies the whitelist (originally five `.py` files; now 14 files: seven runtime `.py` files, `requirements.txt`, `VideoSegmentEditor.bat`, `README.txt`, `LICENSE`, `assets\logo.png`, `assets\logo.ico`, `assets\logo_header.png`) to a staging folder; fails if any unlisted or private/development file is present; writes a flat zip to `VideoSegmentEditor.zip` in the `Finished tools\VideoSegmentEditor` folder next to `Work In Progress`; `-Dest <folder>` overrides for trial builds.
- [ ] **Step 3: docs/test-checklist.md**: the manual checklist from spec section 7 (load, playback, seek accuracy, marking, edit, reorder, processing, each error case, no-VLC, close during processing), with a column for result and date.
- [ ] **Step 4: Verify**: run `build_release.ps1 -Dest <scratchpad folder>`; list the zip contents and confirm only whitelisted files; unzip to a new empty folder and confirm `python -I -m py_compile` passes on all `.py` files.
- [ ] **Step 5: Checkpoint**.

---

### Task 10: Whole-project review and release

- [ ] **Step 1:** Run the full test suite; report passed/skipped counts.
- [ ] **Step 2:** Run reviewers `qa-reviewer`, `ocd-reviewer`, `asd-reviewer` with the project CLAUDE.md-equivalent rules (offline tests only, no secrets); report findings grouped as decisions / clear bugs / polish; fix nothing before the owner agrees.
- [ ] **Step 3:** After agreed fixes and passing checks, run `build_release.ps1` (standing instruction) to produce the final zip.
- [ ] **Step 4:** Report what was tested and what was not (for example the winget branches, VLC embedding on other PCs, very large files). Do not run the end-of-project "best prompt" step until the owner says the project is done.

---

## Self-review (done)

- **Spec coverage:** loading (T5), playback (T4, T6), marking and validation (T1, T6), table/edit/move/total (T1, T6), create flow, naming, verification, disk space, cancel (T2, T3, T7), error list (T2, T3, T5, T7), layout and look (T5, T6), launcher and winget (T8), README/EXE/zip/checklist (T9), reviewers (T10). `README.md` in the prompt is replaced by `README.txt` (spec section 4 call).
- **Types:** `Segment`, `SegmentList`, `VideoInfo`, `VideoJob`, `VlcPlayer` names and signatures are identical across tasks.
- **Proportion:** signatures and test names only; no function bodies.
