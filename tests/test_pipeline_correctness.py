"""Integration tests for WP1a-1 (processing correctness). They need real FFmpeg and skip without it.

All clips are generated into temp folders; nothing outside the temp folder is touched.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import video_processor as vp
from segment_manager import Segment
from video_processor import ProcessingError, VideoJob, find_tool, probe

FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")
SKIP = "FFmpeg not found"


def run(cmd):
    return subprocess.run(cmd, check=True, creationflags=vp.CREATE_NO_WINDOW,
                          stdin=subprocess.DEVNULL, capture_output=True)


def lavfi(seconds, size="640x360", rate=25):
    return ["-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={seconds}"]


def sine(seconds):
    return ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]


def make_basic(path, seconds=10, audio=True, rate=25):
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + lavfi(seconds, rate=rate)
    if audio:
        cmd += sine(seconds)
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac"]
    run(cmd + [str(path)])


def jprobe(path):
    res = run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format",
               "-show_streams", str(path)])
    return json.loads(res.stdout)


def stream(data, kind):
    return next(s for s in data["streams"] if s["codec_type"] == kind)


@unittest.skipIf(FFMPEG is None or FFPROBE is None, SKIP)
class CorrectnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vse_wp1a1_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.work_root = self.tmp / "work"
        self.work_root.mkdir()
        self.events = []

    def job(self, src, segs):
        return VideoJob(src, probe(src, FFPROBE), segs, FFMPEG, FFPROBE, self.events.append,
                        self.work_root)

    def kept_dirs(self):
        return [p for p in self.work_root.iterdir() if p.is_dir()]

    # ---- 1. BL-002: truncated file, header says more than the data holds
    def _truncated_mkv(self):
        full = self.tmp / "full.mkv"
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + lavfi(8.2) + sine(8.2)
            + ["-c:v", "libx264", "-b:v", "1M", "-pix_fmt", "yuv420p", "-c:a", "aac", str(full)])
        data = full.read_bytes()
        trunc = self.tmp / "trunc.mkv"
        trunc.write_bytes(data[: int(len(data) * 0.6)])
        full.unlink()
        return trunc

    def test_truncated_source_fails_with_part_invalid(self):
        src = self._truncated_mkv()
        info = probe(src, FFPROBE)
        self.assertGreater(info.duration_ms, 8000)  # the header still claims the full length
        segs = [Segment(1000, 3000), Segment(7000, 7400), Segment(4000, 5000)]
        with self.assertRaises(ProcessingError) as cm:
            self.job(src, segs).run()
        self.assertEqual(cm.exception.key, "err.part_invalid")
        self.assertEqual(cm.exception.params["i"], 2)
        self.assertEqual(cm.exception.params["n"], 3)
        self.assertEqual(len(self.kept_dirs()), 1)
        self.assertIn(str(self.kept_dirs()[0]), str(cm.exception))
        self.assertNotIn("done", [e["phase"] for e in self.events])
        self.assertFalse((self.tmp / "trunc (segmented).mp4").exists())

    # ---- 2. BL-003: video shorter than audio
    def _vshort(self):
        src = self.tmp / "vshort.mp4"
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + lavfi(5) + sine(8)
            + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)])
        return src

    def test_video_shorter_than_audio_fails_with_clear_key(self):
        src = self._vshort()
        with self.assertRaises(ProcessingError) as cm:
            self.job(src, [Segment(4000, 8000)]).run()
        self.assertIn(cm.exception.key, ("err.part_invalid", "err.out_av_mismatch"))
        self.assertEqual(len(self.kept_dirs()), 1)

    def test_verify_output_catches_picture_shorter_than_sound(self):
        src = self._vshort()  # video 5 s, audio 8 s; container says 8 s
        with self.assertRaises(ProcessingError) as cm:
            vp.verify_output(src, 8000, 1, True, FFPROBE, fps=25.0)
        self.assertEqual(cm.exception.key, "err.out_av_mismatch")

    def _roundtrip(self, n_segments, seg_ms=1000, seconds=None):
        seconds = seconds or (n_segments * 2 + 2)
        src = self.tmp / "src.mp4"
        make_basic(src, seconds=seconds)
        segs = [Segment(i * 2000 + 500, i * 2000 + 500 + seg_ms) for i in range(n_segments)]
        out = self.job(src, segs).run()  # verify_output runs inside; must pass
        data = jprobe(out)
        v, a = stream(data, "video"), stream(data, "audio")
        self.assertAlmostEqual(float(v["duration"]), n_segments * seg_ms / 1000, delta=0.3)
        self.assertLess(abs(float(a["duration"]) - float(v["duration"])),
                        0.1 + 0.03 * n_segments)
        self.assertLess(float(v["start_time"]), 0.15)
        return out

    def test_normal_output_one_segment(self):
        self._roundtrip(1)

    def test_normal_output_three_segments(self):
        self._roundtrip(3)

    def test_normal_output_ten_segments_with_accumulated_priming(self):
        self._roundtrip(10)

    def test_variable_frame_rate_source_still_passes(self):
        src = self.tmp / "vfr.mp4"
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + lavfi(8, rate=30) + sine(8)
            + ["-vf", "setpts='PTS+if(mod(N,7),0,0.02/TB)'", "-fps_mode", "vfr", "-c:v", "libx264",
               "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)])
        self.job(src, [Segment(500, 2500), Segment(4000, 6000)]).run()

    # ---- 3. BL-004: odd size
    def test_odd_size_source_gives_even_output(self):
        src = self.tmp / "odd321.mkv"
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + lavfi(4)
            + sine(4) + ["-vf", "scale=321:241,format=yuv444p", "-c:v", "ffv1", "-c:a",
                         "pcm_s16le", str(src)])
        info = probe(src, FFPROBE)
        self.assertEqual((info.width, info.height), (321, 241))
        out = self.job(src, [Segment(500, 2000), Segment(2500, 3500)]).run()
        v = stream(jprobe(out), "video")
        self.assertEqual((v["width"], v["height"]), (320, 240))

    def test_even_size_source_is_not_cropped(self):
        src = self.tmp / "even.mp4"
        make_basic(src, seconds=4)
        out = self.job(src, [Segment(0, 1500)]).run()
        v = stream(jprobe(out), "video")
        self.assertEqual((v["width"], v["height"]), (640, 360))

    # ---- 4. BL-010: long names
    def _long_name_run(self, stem_len):
        base = self.tmp / "base.mp4"
        make_basic(base, seconds=3)
        src = self.tmp / ("L" * stem_len + ".mp4")
        shutil.copyfile(base, src)
        out = self.job(src, [Segment(0, 1500)]).run()
        self.assertTrue(out.is_file())
        self.assertLessEqual(len(out.name), 255)
        self.assertTrue(out.name.endswith(" (segmented).mp4"))
        self.assertTrue(src.is_file())  # the source keeps its name
        self.assertEqual(self.kept_dirs(), [])
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.endswith(".part")], [])
        return out

    def test_239_char_source_name_succeeds(self):
        self._long_name_run(235)  # name incl. ".mp4" = 239 characters

    def test_245_char_source_name_succeeds(self):
        out = self._long_name_run(241)  # name incl. ".mp4" = 245 characters
        self.assertLessEqual(len(out.name.replace("(segmented)", "(segmented 99)") + ".part"), 240)

    # ---- 6. rotation
    def test_rotated_source_reports_display_size_and_outputs_upright(self):
        base = self.tmp / "port.mp4"
        make_basic(base, seconds=4)
        src = self.tmp / "rot90.mp4"
        try:
            run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-display_rotation", "90",
                 "-i", str(base), "-c", "copy", str(src)])
        except subprocess.CalledProcessError:
            self.skipTest("this FFmpeg cannot write a display rotation")
        info = probe(src, FFPROBE)
        # stored 640x360 with rotation 90 plays as 360x640
        self.assertEqual((info.width, info.height), (360, 640))
        out = self.job(src, [Segment(500, 2500)]).run()
        v = stream(jprobe(out), "video")
        self.assertEqual((v["width"], v["height"]), (360, 640))

    # ---- 7. keyframes
    def test_keyframe_spacing_is_about_two_seconds(self):
        src = self.tmp / "long.mp4"
        make_basic(src, seconds=22)
        out = self.job(src, [Segment(1000, 21000)]).run()
        res = run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                   "packet=pts_time,flags", "-of", "json", str(out)])
        pkts = json.loads(res.stdout)["packets"]
        keys = sorted(float(p["pts_time"]) for p in pkts if "K" in p["flags"])
        self.assertGreaterEqual(len(keys), 8)
        last = float(max(float(p["pts_time"]) for p in pkts))
        points = keys + [last]
        gaps = [b - a for a, b in zip(points, points[1:])]
        self.assertLessEqual(max(gaps), 2.1)
        v = stream(jprobe(out), "video")
        a = stream(jprobe(out), "audio")
        self.assertLess(abs(float(v["duration"]) - float(a["duration"])), 0.16)


if __name__ == "__main__":
    unittest.main()
