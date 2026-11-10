"""Integration tests for VideoJob. They need real FFmpeg and skip without it."""
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import video_processor
from segment_manager import Segment
from video_processor import (Cancelled, CREATE_NO_WINDOW, ProcessingError, VideoInfo,
                             VideoJob, find_tool, probe)

FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")
SKIP = "FFmpeg not found"


def make_clip(ffmpeg, path, seconds=10, audio=True):
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=25:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac"]
    cmd.append(str(path))
    subprocess.run(cmd, check=True, creationflags=CREATE_NO_WINDOW,
                   stdin=subprocess.DEVNULL, capture_output=True)


def ffprobe_json(path):
    res = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format",
                          "-show_streams", str(path)], capture_output=True, check=True,
                         creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL)
    return json.loads(res.stdout)


@unittest.skipIf(FFMPEG is None or FFPROBE is None, SKIP)
class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vse_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.work_root = self.tmp / "work"
        self.work_root.mkdir()
        self.events = []

    def job(self, source, info, segs, progress=None):
        return VideoJob(source, info, segs, FFMPEG, FFPROBE,
                        progress or self.events.append, self.work_root)

    def test_three_segments_roundtrip(self):
        src = self.tmp / "clip.mp4"
        make_clip(FFMPEG, src)
        before = (src.stat().st_size, src.stat().st_mtime_ns)
        info = probe(src, FFPROBE)
        segs = [Segment(1000, 3000), Segment(5000, 6500), Segment(8000, 9000)]
        out = self.job(src, info, segs).run()
        self.assertEqual(out.name, "clip (segmented).mp4")
        self.assertEqual(out.parent, src.parent)
        data = ffprobe_json(out)
        self.assertAlmostEqual(float(data["format"]["duration"]), 4.5, delta=0.4)
        kinds = [s["codec_type"] for s in data["streams"]]
        self.assertIn("audio", kinds)
        v = next(s for s in data["streams"] if s["codec_type"] == "video")
        self.assertEqual((v["width"], v["height"]), (640, 360))
        self.assertEqual((src.stat().st_size, src.stat().st_mtime_ns), before)
        self.assertEqual(list(self.work_root.iterdir()), [])
        phases = [e["phase"] for e in self.events]
        self.assertEqual(phases[-1], "done")
        self.assertEqual(self.events[-1]["percent"], 100)
        pcts = [e["percent"] for e in self.events]
        self.assertEqual(pcts, sorted(pcts))
        self.assertTrue({"extract", "merge", "verify"} <= set(phases))

    def test_no_audio_source(self):
        src = self.tmp / "silent.mp4"
        make_clip(FFMPEG, src, seconds=5, audio=False)
        info = probe(src, FFPROBE)
        self.assertFalse(info.has_audio)
        out = self.job(src, info, [Segment(500, 2000), Segment(3000, 4000)]).run()
        kinds = [s["codec_type"] for s in ffprobe_json(out)["streams"]]
        self.assertNotIn("audio", kinds)

    def test_existing_output_is_not_overwritten(self):
        src = self.tmp / "clip.mp4"
        make_clip(FFMPEG, src, seconds=4)
        existing = self.tmp / "clip (segmented).mp4"
        existing.write_bytes(b"keep me")
        out = self.job(src, probe(src, FFPROBE), [Segment(0, 1500)]).run()
        self.assertEqual(out.name, "clip (segmented 2).mp4")
        self.assertEqual(existing.read_bytes(), b"keep me")

    def test_unicode_and_special_name(self):
        src = self.tmp / "וידאו it's [a]&b.mp4"
        make_clip(FFMPEG, src, seconds=4)
        out = self.job(src, probe(src, FFPROBE), [Segment(0, 1000), Segment(2000, 3000)]).run()
        self.assertEqual(out.name, "וידאו it's [a]&b (segmented).mp4")
        self.assertTrue(out.is_file())

    def test_failure_keeps_temp_dir(self):
        src = self.tmp / "garbage.mp4"
        src.write_bytes(b"this is not a video" * 1000)
        info = VideoInfo(src, 10000, 640, 360, 25.0, True)
        with self.assertRaises(ProcessingError) as ctx:
            self.job(src, info, [Segment(1000, 3000)]).run()
        dirs = [p for p in self.work_root.iterdir() if p.is_dir()]
        self.assertEqual(len(dirs), 1)
        self.assertIn(str(dirs[0]), str(ctx.exception))
        self.assertFalse((self.tmp / "garbage (segmented).mp4").exists())

    def test_cancel(self):
        src = self.tmp / "clip.mp4"
        make_clip(FFMPEG, src)
        info = probe(src, FFPROBE)
        holder = {}

        def on_progress(ev):
            self.events.append(ev)
            if ev["phase"] == "extract" and ev["segment"] == 1 and ev["percent"] > 0:
                holder["job"].cancel()

        job = self.job(src, info, [Segment(1000, 3000), Segment(5000, 6500)], on_progress)
        holder["job"] = job
        with self.assertRaises(Cancelled):
            job.run()
        self.assertFalse((self.tmp / "clip (segmented).mp4").exists())
        self.assertEqual(len([p for p in self.work_root.iterdir() if p.is_dir()]), 1)

    def _clip(self, seconds=6):
        src = self.tmp / "clip.mp4"
        make_clip(FFMPEG, src, seconds=seconds)
        return src, probe(src, FFPROBE)

    def test_finalize_failure_leaves_no_part_or_final(self):
        src, info = self._clip()
        with mock.patch.object(video_processor.os, "rename", side_effect=OSError("boom")):
            with self.assertRaises(ProcessingError) as ctx:
                self.job(src, info, [Segment(0, 1500)]).run()
        names = sorted(p.name for p in self.tmp.iterdir())
        self.assertEqual(names, ["clip.mp4", "work"])
        dirs = [p for p in self.work_root.iterdir() if p.is_dir()]
        self.assertEqual(len(dirs), 1)
        self.assertIn(str(dirs[0]), str(ctx.exception))

    def test_target_appearing_late_is_not_overwritten(self):
        src, info = self._clip()
        target = self.tmp / "clip (segmented).mp4"

        def on_progress(ev):
            self.events.append(ev)
            if ev["phase"] == "verify":
                target.write_bytes(b"late file")

        out = self.job(src, info, [Segment(0, 1500)], on_progress).run()
        self.assertEqual(out.name, "clip (segmented 2).mp4")
        self.assertEqual(target.read_bytes(), b"late file")
        self.assertTrue(out.stat().st_size > 100)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()),
                         ["clip (segmented 2).mp4", "clip (segmented).mp4", "clip.mp4", "work"])

    def test_unwritable_folder_fails_fast(self):
        src, info = self._clip()
        with mock.patch.object(video_processor.tempfile, "mkstemp",
                               side_effect=PermissionError("denied")):
            with self.assertRaises(ProcessingError) as ctx:
                self.job(src, info, [Segment(0, 1500)]).run()
        self.assertIn("Cannot save in this folder", str(ctx.exception))
        self.assertEqual(list(self.work_root.iterdir()), [])
        self.assertEqual(self.events, [])

    def test_cancel_during_merge(self):
        src, info = self._clip()
        holder = {}

        def on_progress(ev):
            self.events.append(ev)
            if ev["phase"] == "merge":
                holder["job"].cancel()

        job = self.job(src, info, [Segment(0, 1500), Segment(2000, 3000)], on_progress)
        holder["job"] = job
        with self.assertRaises(Cancelled):
            job.run()
        self.assertFalse((self.tmp / "clip (segmented).mp4").exists())
        self.assertFalse((self.tmp / "clip (segmented).mp4.part").exists())
        self.assertEqual(len([p for p in self.work_root.iterdir() if p.is_dir()]), 1)

    def test_percent_bounded_and_monotonic(self):
        src, info = self._clip()
        self.job(src, info, [Segment(0, 1500), Segment(2000, 3000)]).run()
        pcts = [e["percent"] for e in self.events]
        self.assertTrue(all(0 <= p <= 100 for p in pcts))
        self.assertEqual(pcts, sorted(pcts))

    def test_failure_detail_not_empty(self):
        src = self.tmp / "garbage.mp4"
        src.write_bytes(b"not a video" * 1000)
        info = VideoInfo(src, 10000, 640, 360, 25.0, True)
        with self.assertRaises(ProcessingError) as ctx:
            self.job(src, info, [Segment(1000, 3000)]).run()
        self.assertTrue(ctx.exception.detail.strip())


if __name__ == "__main__":
    unittest.main()
