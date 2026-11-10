import shutil
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest import mock

import video_processor as vp
from segment_manager import Segment

_Usage = namedtuple("usage", "total used free")


def _info(has_audio=True):
    return vp.VideoInfo(Path("a.mp4"), 60000, 1920, 1080, 30.0, has_audio)


def _probe_json(duration="10.0", audio=True, video=True):
    streams = []
    if video:
        streams.append({"codec_type": "video", "width": 640, "height": 360,
                        "avg_frame_rate": "25/1", "duration": "9.5"})
    if audio:
        streams.append({"codec_type": "audio"})
    fmt = {"duration": duration} if duration is not None else {}
    return {"format": fmt, "streams": streams}


class UniqueOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_unique_output_path(self):
        src = self.tmp / "Workout.mp4"
        first = vp.unique_output_path(src)
        self.assertEqual(first.name, "Workout (segmented).mp4")
        self.assertEqual(first.parent, self.tmp)
        first.write_bytes(b"x")
        second = vp.unique_output_path(src)
        self.assertEqual(second.name, "Workout (segmented 2).mp4")
        second.write_bytes(b"x")
        self.assertEqual(vp.unique_output_path(src).name, "Workout (segmented 3).mp4")

    def test_unique_keeps_unicode_and_apostrophe(self):
        src = self.tmp / "it's [a] שלום.mkv"
        out = vp.unique_output_path(src)
        self.assertEqual(out.name, "it's [a] שלום (segmented).mp4")


class CommandTests(unittest.TestCase):
    def test_extract_cmd_contents(self):
        cmd = vp.extract_cmd("ffmpeg.exe", Path("in it's.mp4"), Segment(61250, 70000),
                             Path("out.mp4"), _info())
        self.assertIsInstance(cmd, list)
        self.assertTrue(all(isinstance(c, str) for c in cmd))
        self.assertEqual(cmd[0], "ffmpeg.exe")
        joined = " ".join(cmd)
        for needle in ("-c:v libx264", "-crf 18", "-c:a aac", "-map 0:a:0?",
                       "-map 0:v:0", "-pix_fmt yuv420p", "-avoid_negative_ts make_zero"):
            self.assertIn(needle, joined)
        self.assertEqual(cmd[cmd.index("-ss") + 1], "61.250")
        self.assertEqual(cmd[cmd.index("-t") + 1], "8.750")
        self.assertLess(cmd.index("-ss"), cmd.index("-i"))
        self.assertEqual(cmd[cmd.index("-i") + 1], str(Path("in it's.mp4")))
        self.assertEqual(cmd[-1], str(Path("out.mp4")))

    def test_concat_cmd(self):
        cmd = vp.concat_cmd("ffmpeg", Path("l.txt"), Path("o.mp4"))
        self.assertIsInstance(cmd, list)
        for needle in ("-f concat", "-safe 0", "-c copy", "-movflags +faststart"):
            self.assertIn(needle, " ".join(cmd))
        self.assertEqual(cmd[-1], str(Path("o.mp4")))

    def test_concat_list_escapes_quote(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        lst = tmp / "list.txt"
        vp.write_concat_list([tmp / "it's.mp4", tmp / "b.mp4"], lst)
        lines = lst.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("it'\\''s.mp4", lines[0])
        self.assertTrue(lines[0].startswith("file '") and lines[0].endswith("'"))


class ProbeTests(unittest.TestCase):
    def test_probe_reads_format_duration(self):
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=_probe_json("12.5")):
            info = vp.probe(Path("x.mp4"), "ffprobe")
        self.assertEqual(info.duration_ms, 12500)
        self.assertEqual((info.width, info.height), (640, 360))
        self.assertEqual(info.fps, 25.0)
        self.assertTrue(info.has_audio)

    def test_probe_falls_back_to_stream_duration(self):
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=_probe_json(None, audio=False)):
            info = vp.probe(Path("x.mkv"), "ffprobe")
        self.assertEqual(info.duration_ms, 9500)
        self.assertFalse(info.has_audio)

    def test_probe_rejects_unreadable(self):
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=_probe_json(video=False)):
            with self.assertRaises(vp.ProcessingError) as cm:
                vp.probe(Path("x.mp4"), "ffprobe")
        self.assertEqual(str(cm.exception), "This file could not be read as a video.")

    def test_probe_rejects_no_duration(self):
        data = _probe_json(None)
        del data["streams"][0]["duration"]
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=data):
            with self.assertRaises(vp.ProcessingError):
                vp.probe(Path("x.mp4"), "ffprobe")


class FfprobeRunTests(unittest.TestCase):
    def test_timeout_becomes_processing_error(self):
        exc = vp.subprocess.TimeoutExpired("ffprobe", 60)
        with mock.patch.object(vp.subprocess, "run", side_effect=exc):
            with self.assertRaises(vp.ProcessingError) as cm:
                vp._run_ffprobe_json("ffprobe", Path("x.mp4"))
        self.assertIn("too long", str(cm.exception))

    def test_run_args_and_stderr_tail_kept(self):
        res = mock.Mock(returncode=1, stdout=b"", stderr=b"A" * 500 + b"END")
        with mock.patch.object(vp.subprocess, "run", return_value=res) as run:
            with self.assertRaises(vp.ProcessingError) as cm:
                vp._run_ffprobe_json("ffprobe", Path("x.mp4"))
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["stdin"], vp.subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"], 60)
        self.assertEqual(str(cm.exception), "This file could not be read as a video.")
        self.assertTrue(cm.exception.detail.endswith("END"))
        self.assertLessEqual(len(cm.exception.detail), 300)


class VerifyOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = self.tmp / "o.mp4"
        self.out.write_bytes(b"data")

    def _verify(self, data, expected=10000, n=2, had_audio=True):
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=data):
            vp.verify_output(self.out, expected, n, had_audio, "ffprobe")

    def test_verify_output_rules(self):
        with self.subTest("good"):
            self._verify(_probe_json("10.2"))
        with self.subTest("missing file"):
            self.out.unlink()
            with self.assertRaises(vp.ProcessingError):
                self._verify(_probe_json("10.0"))
            self.out.write_bytes(b"data")
        with self.subTest("zero size"):
            self.out.write_bytes(b"")
            with self.assertRaises(vp.ProcessingError):
                self._verify(_probe_json("10.0"))
            self.out.write_bytes(b"data")
        with self.subTest("no video"):
            with self.assertRaises(vp.ProcessingError):
                self._verify(_probe_json("10.0", video=False))
        with self.subTest("missing audio"):
            with self.assertRaises(vp.ProcessingError):
                self._verify(_probe_json("10.0", audio=False))
        with self.subTest("no audio expected"):
            self._verify(_probe_json("10.0", audio=False), had_audio=False)
        with self.subTest("duration tolerance edge ok"):
            self._verify(_probe_json("10.7"))  # 500 + 100*2 = 700 ms
        with self.subTest("duration too long"):
            with self.assertRaises(vp.ProcessingError):
                self._verify(_probe_json("10.8"))
        with self.subTest("duration too short"):
            with self.assertRaises(vp.ProcessingError):
                self._verify(_probe_json("9.2"))


class DiskSpaceTests(unittest.TestCase):
    def test_check_disk_space_low(self):
        with mock.patch.object(vp.shutil, "disk_usage",
                               return_value=_Usage(10**12, 0, 100 * 1024 * 1024)):
            with self.assertRaises(vp.ProcessingError):
                vp.check_disk_space(Path("."), 10**6, 1000, 10000)

    def test_check_disk_space_scales_with_source(self):
        # needs 2 * 4 GB * 0.5 = 4 GB; 1 GB free is not enough
        with mock.patch.object(vp.shutil, "disk_usage",
                               return_value=_Usage(10**12, 0, 1024**3)):
            with self.assertRaises(vp.ProcessingError):
                vp.check_disk_space(Path("."), 4 * 1024**3, 5000, 10000)

    def test_check_disk_space_names_the_drive(self):
        with mock.patch.object(vp.shutil, "disk_usage",
                               return_value=_Usage(10**12, 0, 1024)):
            with self.assertRaises(vp.ProcessingError) as cm:
                vp.check_disk_space(Path(r"D:\out"), 10**6, 1000, 10000)
        self.assertEqual(cm.exception.params["drive"], "D:")
        self.assertIn("drive D:", str(cm.exception))

    def test_check_disk_space_oserror(self):
        with mock.patch.object(vp.shutil, "disk_usage", side_effect=FileNotFoundError("gone")):
            with self.assertRaises(vp.ProcessingError) as cm:
                vp.check_disk_space(Path("nope"), 1, 1, 2)
        self.assertNotIn("gone", str(cm.exception))
        self.assertIn("gone", cm.exception.detail)

    def test_check_disk_space_ok(self):
        with mock.patch.object(vp.shutil, "disk_usage",
                               return_value=_Usage(10**12, 0, 10 * 1024**3)):
            vp.check_disk_space(Path("."), 10**6, 1000, 10000)


class PartPathTests(unittest.TestCase):
    def _job(self, src):
        return vp.VideoJob(src, _info(), [Segment(0, 1000)], "ffmpeg", "ffprobe",
                           lambda ev: None, Path(src).parent / "work")

    def test_part_path_none_before_finalize_and_discard_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            job = self._job(Path(d) / "a.mp4")
            self.assertIsNone(job.part_path)
            job.discard_part()  # nothing to do, must not raise

    def test_finalize_sets_part_path_and_discard_removes_leftover(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src = d / "a.mp4"
            src.write_bytes(b"x")
            merged = d / "merged.mp4"
            merged.write_bytes(b"data")
            job = self._job(src)
            out = job._finalize(merged, d / "a (segmented).mp4")
            self.assertTrue(out.exists())
            self.assertEqual(job.part_path.name, "a (segmented).mp4.part")
            self.assertFalse(job.part_path.exists())
            job.part_path.write_bytes(b"half")  # simulate a leftover
            job.discard_part()
            self.assertFalse(job.part_path.exists())
            job.discard_part()  # second call: ignore errors


if __name__ == "__main__":
    unittest.main()
