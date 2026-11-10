"""WP2a-2 (desktop robustness): log with timestamps and rotation, sweep of old work folders,
startup failure message, settings BOM, and clearer error causes. All offline, no Tk."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
os.environ["VSE_NO_STARTUP_DIALOG"] = "1"   # tests never pop a real message box

import create_flow  # noqa: E402
import i18n  # noqa: E402
import main  # noqa: E402
import video_processor as vp  # noqa: E402
from segment_manager import Segment  # noqa: E402

ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d ")


class TimestampedLogTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "app.log"

    def tearDown(self):
        self.dir.cleanup()

    def lines(self):
        return self.path.read_text(encoding="utf-8").splitlines()

    def test_session_start_line_has_version_and_python(self):
        log = main.TimestampedLog(self.path, "9.9")
        log.close()
        first = self.lines()[0]
        self.assertRegex(first, ISO)
        self.assertIn("9.9", first)
        self.assertIn(sys.version.split()[0], first)

    def test_every_line_gets_a_timestamp(self):
        log = main.TimestampedLog(self.path, "1.0")
        log.write("hello\nsecond")
        log.write(" half\n\nlast\n")
        log.close()
        body = self.lines()[1:]
        self.assertEqual(len(body), 3)             # blank lines are not stamped
        for line in body:
            self.assertRegex(line, ISO)
        self.assertTrue(body[0].endswith("hello"))
        self.assertTrue(body[1].endswith("second half"))
        self.assertTrue(body[2].endswith("last"))

    def test_print_works_as_stream(self):
        log = main.TimestampedLog(self.path, "1.0")
        print("via print", file=log)
        log.flush()
        self.assertTrue(self.lines()[-1].endswith("via print"))
        self.assertFalse(log.isatty())
        log.close()

    def test_old_big_log_is_rotated_at_start(self):
        self.path.write_bytes(b"x" * 2000)
        Path(str(self.path) + ".1").write_bytes(b"older")
        log = main.TimestampedLog(self.path, "1.0", max_bytes=1000)
        log.close()
        self.assertEqual(Path(str(self.path) + ".1").read_bytes(), b"x" * 2000)
        self.assertEqual(len(self.lines()), 1)     # fresh file: only the session line

    def test_small_log_is_appended(self):
        self.path.write_text("old line\n", encoding="utf-8")
        log = main.TimestampedLog(self.path, "1.0", max_bytes=1000)
        log.close()
        self.assertEqual(self.lines()[0], "old line")
        self.assertFalse(Path(str(self.path) + ".1").exists())

    def test_rotates_while_running(self):
        log = main.TimestampedLog(self.path, "1.0", max_bytes=500)
        for i in range(40):
            log.write(f"line number {i} " + "y" * 20 + "\n")
        log.close()
        self.assertTrue(Path(str(self.path) + ".1").exists())
        self.assertLess(self.path.stat().st_size, 1500)
        text = self.path.read_text(encoding="utf-8") + Path(str(self.path) + ".1").read_text(
            encoding="utf-8")
        self.assertIn("line number 39", text)

    def test_never_raises_when_the_folder_is_unwritable(self):
        with mock.patch("builtins.open", side_effect=OSError("denied")):
            log = main.TimestampedLog(self.path, "1.0")
            log.write("lost\n")
            log.flush()
            log.close()

    def test_never_raises_when_a_write_fails(self):
        log = main.TimestampedLog(self.path, "1.0")
        log._fh.close()                            # every further write raises ValueError
        log.write("lost\n")
        log.flush()
        log.close()

    def test_redirect_returns_false_with_console_and_true_without(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": d}):
            self.assertFalse(main._redirect_output_if_needed())
            with mock.patch.object(sys, "stdout", None), mock.patch.object(sys, "stderr", None):
                self.assertTrue(main._redirect_output_if_needed())
                print("under pythonw")
                self.assertTrue(isinstance(sys.stdout, main.TimestampedLog))
                sys.stdout.close()
            text = (Path(d) / "VideoSegmentEditor" / "app.log").read_text(encoding="utf-8")
            self.assertIn("under pythonw", text)


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name) / "work"
        self.root.mkdir()

    def tearDown(self):
        self.dir.cleanup()

    def make(self, name, age_days):
        p = self.root / name
        p.mkdir()
        (p / "seg_001.mp4").write_bytes(b"data")
        t = time.time() - age_days * 86400
        os.utime(p, (t, t))
        return p

    def test_old_job_folder_removed_fresh_kept(self):
        old = self.make("job_old", 8)
        fresh = self.make("job_fresh", 1)
        self.assertEqual(create_flow.sweep_old_jobs(self.root), 1)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_only_job_folders_are_touched(self):
        other = self.make("notes", 30)
        (self.root / "job_x").write_text("a file, not a folder")
        t = time.time() - 30 * 86400
        os.utime(self.root / "job_x", (t, t))
        self.assertEqual(create_flow.sweep_old_jobs(self.root), 0)
        self.assertTrue(other.exists())
        self.assertTrue((self.root / "job_x").is_file())

    def test_missing_root_is_fine(self):
        self.assertEqual(create_flow.sweep_old_jobs(self.root / "nope"), 0)

    def test_errors_are_swallowed(self):
        self.make("job_old", 9)
        with mock.patch.object(create_flow.shutil, "rmtree", side_effect=OSError("locked")):
            create_flow.sweep_old_jobs(self.root)            # must not raise
        with mock.patch.object(Path, "iterdir", side_effect=OSError("denied")):
            self.assertEqual(create_flow.sweep_old_jobs(self.root), 0)

    def test_background_start_does_not_block_and_removes(self):
        old = self.make("job_old", 8)
        th = create_flow.start_sweep(self.root)
        th.join(10)
        self.assertFalse(old.exists())


class StartupFailureTests(unittest.TestCase):
    def test_message_names_the_log_file_and_folder(self):
        text = main.startup_failure_message(Path(r"C:\Users\x\AppData\Local\VideoSegmentEditor"))
        self.assertEqual(
            text, "Video Segment Editor could not start. Details are in the file app.log in "
                  r"the folder C:\Users\x\AppData\Local\VideoSegmentEditor.")

    def test_box_only_without_console_and_without_env_switch(self):
        self.assertTrue(main.should_show_startup_dialog(False, {}))
        self.assertFalse(main.should_show_startup_dialog(True, {}))
        self.assertFalse(main.should_show_startup_dialog(False, {"VSE_NO_STARTUP_DIALOG": "1"}))

    def test_report_calls_message_box_once_and_never_raises(self):
        shown = []
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VSE_NO_STARTUP_DIALOG", None)
            main.report_startup_failure(True, Path("C:/logs"), box=lambda *a: shown.append(a))
            self.assertEqual(len(shown), 1)
            self.assertIn("app.log", shown[0][0])

            def boom(*a):
                raise OSError("no gui")
            main.report_startup_failure(True, Path("C:/logs"), box=boom)   # no exception
            shown.clear()
            main.report_startup_failure(False, Path("C:/logs"), box=lambda *a: shown.append(a))
            self.assertEqual(shown, [])

    def test_env_switch_suppresses_the_box(self):
        shown = []
        with mock.patch.dict(os.environ, {"VSE_NO_STARTUP_DIALOG": "1"}):
            main.report_startup_failure(True, Path("C:/logs"), box=lambda *a: shown.append(a))
        self.assertEqual(shown, [])

    def test_tests_never_pop_a_real_box(self):
        # the environment variable is set for the whole test run (set at the top of this file)
        self.assertEqual(os.environ.get("VSE_NO_STARTUP_DIALOG"), "1")


class SettingsBomTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "settings.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_bom_with_russian(self):
        self.path.write_bytes(b"\xef\xbb\xbf" + b'{"language": "ru"}')
        self.assertEqual(i18n.load_saved_language(self.path), "ru")

    def test_plain_file(self):
        self.path.write_bytes(b'{"language": "ru"}')
        self.assertEqual(i18n.load_saved_language(self.path), "ru")

    def test_corrupt_is_english(self):
        self.path.write_bytes(b"\xef\xbb\xbf{broken")
        self.assertEqual(i18n.load_saved_language(self.path), "en")

    def test_saved_without_bom_and_other_keys_kept_from_bom_file(self):
        self.path.write_bytes(b"\xef\xbb\xbf" + b'{"other": 1}')
        i18n.save_language(self.path, "ru")
        raw = self.path.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b'"other": 1', raw)


def _res(code=1, stderr=b""):
    return mock.Mock(returncode=code, stdout=b"", stderr=stderr)


class ErrorCauseTests(unittest.TestCase):
    LOCKED_TEXTS = [
        b"C:\\v.mp4: Permission denied",
        b"Error opening input file v.mp4.\nError opening input files: Permission denied",
        b"The process cannot access the file because it is being used by another process.",
        b"Access is denied.",
        b"[WinError 32] The process cannot access the file",
        b"[WinError 5] Access is denied",
    ]

    def test_locked_text_detection(self):
        for text in self.LOCKED_TEXTS:
            self.assertTrue(vp.looks_locked(text.decode()), text)
        for text in ("Invalid data found when processing input", "No such file or directory",
                     "frame= 32 fps=5", ""):
            self.assertFalse(vp.looks_locked(text), text)

    def test_probe_locked(self):
        for text in self.LOCKED_TEXTS:
            with mock.patch.object(vp.subprocess, "run", return_value=_res(1, text)):
                with self.assertRaises(vp.ProcessingError) as cm:
                    vp.probe(Path(__file__), "ffprobe")
            self.assertEqual(cm.exception.key, "err.source_locked", text)

    def test_probe_garbage_stays_not_a_video(self):
        with mock.patch.object(vp.subprocess, "run",
                               return_value=_res(1, b"Invalid data found when processing input")):
            with self.assertRaises(vp.ProcessingError) as cm:
                vp.probe(Path(__file__), "ffprobe")
        self.assertEqual(cm.exception.key, "err.not_a_video")

    def test_probe_missing_file(self):
        with mock.patch.object(vp.subprocess, "run",
                               return_value=_res(1, b"No such file or directory")):
            with self.assertRaises(vp.ProcessingError) as cm:
                vp.probe(Path("Z:/does/not/exist.mp4"), "ffprobe")
        self.assertEqual(cm.exception.key, "err.source_missing")

    def _job(self, tmp, source):
        info = vp.VideoInfo(path=source, duration_ms=10000, width=320, height=240, fps=25.0,
                            has_audio=False)
        return vp.VideoJob(source, info, [Segment(0, 1000)], "ffmpeg", "ffprobe",
                           lambda ev: None, Path(tmp) / "work")

    def test_job_source_vanished_before_start(self):
        with tempfile.TemporaryDirectory() as d:
            job = self._job(d, Path(d) / "gone.mp4")
            with self.assertRaises(vp.ProcessingError) as cm:
                job.run()
        self.assertEqual(cm.exception.key, "err.source_missing")

    def test_extract_locked_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "v.mp4"
            src.write_bytes(b"x")
            job = self._job(d, src)

            class FakeProc:
                def __init__(self, *a, **k):
                    k["stderr"].write(self.text)
                    self.stdout = mock.MagicMock()
                    self.stdout.__iter__.return_value = iter([])

                def wait(self):
                    return 1

                def poll(self):
                    return 1

                def terminate(self):
                    pass

            def run_with(text):
                FakeProc.text = text
                job._reading_source = True
                with mock.patch.object(vp.subprocess, "Popen", FakeProc):
                    with self.assertRaises(vp.ProcessingError) as cm:
                        job._run_ffmpeg(["ffmpeg", "out.mp4"], Path(d) / "e.log", None)
                return cm.exception.key

            self.assertEqual(run_with(b"v.mp4: Permission denied"), "err.source_locked")
            self.assertEqual(run_with(b"something else"), "err.ffmpeg_failed")
            src.unlink()
            self.assertEqual(run_with(b"something else"), "err.source_missing")

    def test_merge_stage_permission_denied_is_not_blamed_on_the_source(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "v.mp4"
            src.write_bytes(b"x")
            job = self._job(d, src)

            class FakeProc:
                def __init__(self, *a, **k):
                    k["stderr"].write(b"parts.txt: Permission denied")
                    self.stdout = mock.MagicMock()
                    self.stdout.__iter__.return_value = iter([])

                def wait(self):
                    return 1

                def poll(self):
                    return 1

            with mock.patch.object(vp.subprocess, "Popen", FakeProc):
                with self.assertRaises(vp.ProcessingError) as cm:
                    job._run_ffmpeg(["ffmpeg", "out.mp4"], Path(d) / "e.log", None)
            self.assertEqual(cm.exception.key, "err.ffmpeg_failed")

    def test_new_keys_in_both_languages_and_russian_differs(self):
        for key in ("err.source_locked", "err.source_missing", "btn.open_folder"):
            en, ru = i18n.STRINGS["en"][key], i18n.STRINGS["ru"][key]
            self.assertNotEqual(en, ru)
            self.assertTrue(re.search("[а-яА-Я]", ru))


@unittest.skipUnless(sys.platform == "win32" and vp.find_tool("ffprobe") and vp.find_tool("ffmpeg"),
                     "needs Windows and FFmpeg")
class RealLockedFileTests(unittest.TestCase):
    """A real source opened with no sharing by another process (CreateFileW share mode 0)."""

    HOLDER = r'''
import ctypes, sys, time
k = ctypes.windll.kernel32
k.CreateFileW.restype = ctypes.c_void_p
h = k.CreateFileW(sys.argv[1], 0x80000000, 0, None, 3, 0x80, None)
print("ok" if h not in (None, ctypes.c_void_p(-1).value) else "fail", flush=True)
time.sleep(int(sys.argv[2]))
'''

    def test_locked_source_gives_source_locked(self):
        d = Path(tempfile.mkdtemp(prefix="vse_lock_"))
        holder = None
        try:
            src = d / "v.mp4"
            subprocess.run([vp.find_tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                            "testsrc=size=160x120:rate=10:duration=2", "-pix_fmt", "yuv420p",
                            str(src)], check=True, creationflags=vp.CREATE_NO_WINDOW,
                           stdin=subprocess.DEVNULL)
            info = vp.probe(src, vp.find_tool("ffprobe"))      # read BEFORE it gets locked
            holder = subprocess.Popen([sys.executable, "-c", self.HOLDER, str(src), "30"],
                                      stdout=subprocess.PIPE, text=True)
            self.assertEqual(holder.stdout.readline().strip(), "ok")
            job = vp.VideoJob(src, info, [Segment(0, 1000)], vp.find_tool("ffmpeg"),
                              vp.find_tool("ffprobe"), lambda ev: None, d / "work")
            with self.assertRaises(vp.ProcessingError) as cm:
                job.run()                                    # the extract stage hits the lock
            self.assertEqual(cm.exception.key, "err.source_locked", cm.exception.detail)
            with self.assertRaises(vp.ProcessingError) as cm:
                vp.probe(src, vp.find_tool("ffprobe"))
            self.assertEqual(cm.exception.key, "err.source_locked", cm.exception.detail)
        finally:
            if holder is not None:
                holder.kill()
                holder.wait()
                holder.stdout.close()
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
