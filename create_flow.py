"""Pure helpers for the Create Video flow (no Tk, no FFmpeg), so they can be unit-tested."""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

SWEEP_DAYS = 7


def default_work_root() -> Path:
    r"""%LOCALAPPDATA%\VideoSegmentEditor\work (created by VideoJob when needed)."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "VideoSegmentEditor" / "work"


def sweep_old_jobs(work_root, max_age_days: float = SWEEP_DAYS, now: float | None = None) -> int:
    """Delete `job_*` folders in the work root that were last changed more than `max_age_days`
    ago (kept after a failure or a cancel). Touches nothing else; every error is ignored.
    Returns how many folders were removed."""
    removed = 0
    try:
        limit = (time.time() if now is None else now) - max_age_days * 86400
        for entry in list(Path(work_root).iterdir()):
            try:
                if (not entry.name.startswith("job_") or entry.is_symlink()
                        or not entry.is_dir() or entry.stat().st_mtime >= limit):
                    continue
                shutil.rmtree(entry, ignore_errors=True)
                if not entry.exists():
                    removed += 1
            except Exception:
                continue
    except Exception:
        pass
    return removed


def start_sweep(work_root) -> threading.Thread:
    """Run sweep_old_jobs in a background thread so that the window never waits for it."""
    th = threading.Thread(target=sweep_old_jobs, args=(work_root,), daemon=True)
    th.start()
    return th


def progress_view(event: dict) -> tuple[str, dict, float]:
    """Map a VideoJob progress event to (i18n key, params, percent 0..100)."""
    try:
        percent = float(event.get("percent", 0.0))
    except (TypeError, ValueError):
        percent = 0.0
    percent = max(0.0, min(100.0, percent))
    phase = event.get("phase")
    if phase == "extract":
        return "progress.cut", {"i": event.get("segment", 1), "n": event.get("total", 1)}, percent
    if phase == "merge":
        return "progress.join", {}, percent
    if phase == "verify":
        return "progress.verify", {}, percent
    if phase == "done":
        return "progress.done", {}, percent
    return event.get("key", "progress.done"), dict(event.get("params") or {}), percent


def conversion_notes(info) -> list[tuple[str, dict]]:
    """(i18n key, params) for each conversion the output will go through; [] when none.

    `info` is a video_processor.VideoInfo. HDR already implies 8-bit 4:2:0, so the colour
    format note is only given for non-HDR sources. A single audio track is not news.
    """
    notes: list[tuple[str, dict]] = []
    if info.is_hdr:
        notes.append(("note.hdr_to_sdr", {}))
    elif (info.pix_fmt and info.pix_fmt != "yuv420p") or info.color_range == "pc":
        notes.append(("note.color_format", {}))   # 10-bit, 4:4:4, RGB, full range
    if info.is_interlaced:
        notes.append(("note.deinterlace", {}))
    if info.width % 2 or info.height % 2:
        notes.append(("note.odd_size", {}))
    if len(info.audio_streams) > 1:
        notes.append(("note.audio_tracks", {"n": len(info.audio_streams)}))
    if info.subtitle_count:
        notes.append(("note.subtitles_dropped", {"n": info.subtitle_count}))
    if info.chapter_count:
        notes.append(("note.chapters_dropped", {}))
    return notes
