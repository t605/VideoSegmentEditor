"""Smoke tests of the real gui.App (WP6): real Tk window, real FFmpeg, no VLC, no production changes.

All runtime data (work folder, settings.json, app.log) goes to a temp LOCALAPPDATA; the dialog seam
(App._show_message / App._ask_yes_no) is replaced by recorders. The whole class is skipped when Tk cannot open a window or FFmpeg /
FFprobe are not found.

WP2a-1 (Cancel button, worker terminal event, player degrade, non-blocking close) is covered by the
tests named test_cancel_*, test_bl016_*, test_bl019_*, test_bl018_*.
"""
import gc
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.dont_write_bytecode = True          # never write __pycache__ into the project from here
os.environ["VSE_FORCE_NO_VLC"] = "1"    # must be set before gui is imported / used

import tkinter as tk  # noqa: E402

import video_processor  # noqa: E402
from video_processor import CREATE_NO_WINDOW, find_tool  # noqa: E402

FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")


def _tk_problem():
    try:
        root = tk.Tk()
        root.destroy()
    except tk.TclError as exc:
        return f"Tk cannot create a window: {exc}"
    return None


TK_PROBLEM = _tk_problem()
SKIP_REASON = None
if TK_PROBLEM:
    SKIP_REASON = TK_PROBLEM
elif not FFMPEG or not FFPROBE:
    SKIP_REASON = "FFmpeg / FFprobe not found"

if SKIP_REASON is None:
    import gui  # noqa: E402
    from i18n import get_language, set_language, t  # noqa: E402
    from segment_manager import format_ms  # noqa: E402


def make_clip(path, seconds=3.6):
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=25:duration={seconds}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(cmd, check=True, creationflags=CREATE_NO_WINDOW,
                   stdin=subprocess.DEVNULL, capture_output=True)


def probe_duration(path):
    res = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format",
                          str(path)], capture_output=True, check=True,
                         creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL)
    return float(json.loads(res.stdout)["format"]["duration"])


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slow_extract_cmd(ffmpeg, source, seg, out, info):
    """A real FFmpeg that runs for minutes (used only to be cancelled)."""
    return [ffmpeg, "-hide_banner", "-nostdin", "-n", "-f", "lavfi", "-i",
            "testsrc2=size=1280x720:rate=25:duration=600", "-c:v", "libx264",
            "-preset", "veryslow", "-pix_fmt", "yuv420p", str(out)]


@unittest.skipIf(SKIP_REASON is not None, SKIP_REASON or "")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.class_tmp = Path(tempfile.mkdtemp(prefix="vse_gui_class_"))
        cls.master_clip = cls.class_tmp / "master.mp4"
        make_clip(cls.master_clip)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.class_tmp, ignore_errors=True)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vse_gui_"))
        self.localappdata = self.tmp / "localappdata"
        self.localappdata.mkdir()
        self.media = self.tmp / "media"
        self.media.mkdir()
        self.src = self.media / "clip.mp4"
        shutil.copyfile(self.master_clip, self.src)
        self._old_env = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = str(self.localappdata)
        set_language("en")

        self.dialogs = []        # (kind, title, message)
        self.confirm_answer = True
        self.confirms = []
        # The ONLY two places that open a dialog are App._show_message and App._ask_yes_no.
        self.yes_labels = []     # (yes_key, no_key) of every question
        self._seam_patches = [
            mock.patch.object(
                gui.App, "_show_message",
                lambda app, kind, title, msg: self._recorder(kind, title, msg)),
            mock.patch.object(
                gui.App, "_ask_yes_no",
                lambda app, title, msg, yes_key="btn.yes", no_key="btn.no":
                    self._record_question(title, msg, yes_key, no_key)),
        ]
        for patch in self._seam_patches:
            patch.start()
        self.app = None
        self.procs = []
        try:
            self.app = gui.App("1.0")
        except Exception:
            self._cleanup()
            raise

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        app = self.app
        if app is not None:
            try:
                app._closing = True
                job, worker = app._job, app._worker
                if job is not None:
                    job.cancel()
                if worker is not None:
                    worker.join(timeout=10)
                for p in self.procs:
                    if p.poll() is None:
                        p.kill()
                try:
                    for ident in app.tk.splitlist(app.tk.call("after", "info")):
                        app.after_cancel(ident)     # no "invalid command name" noise
                    app.destroy()
                except tk.TclError:
                    pass
            except Exception:
                pass
        for patch in self._seam_patches:
            patch.stop()
        set_language("en")
        if self._old_env is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self._old_env
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.app = None
        # Free the destroyed window HERE, in the main thread. If the garbage collector ran in
        # a worker thread instead, a Tk image's __del__ would call into Tcl from that thread
        # and block it (the next test's FFmpeg would never start).
        gc.collect()

    # ------------------------------------------------------------ helpers
    def _recorder(self, kind, title, msg):
        self.dialogs.append((kind, title, msg))

    def _confirm(self, title, msg):
        self.confirms.append((title, msg))
        return self.confirm_answer

    def _record_question(self, title, msg, yes_key, no_key):
        self.yes_labels.append((yes_key, no_key))
        return self._confirm(title, msg)

    def kinds(self, kind):
        return [d for d in self.dialogs if d[0] == kind]

    def pump(self, until=None, timeout=10.0):
        end = time.time() + timeout
        while time.time() < end:
            self.app.update()
            if until is not None and until():
                return True
            time.sleep(0.02)
        return until() if until is not None else None

    def load(self):
        self.app.load_video(self.src)
        ok = self.pump(lambda: self.app.info is not None, 15)
        self.assertTrue(ok, "video did not load")
        self.pump(timeout=0.2)

    def add_segment(self, start, end):
        self.app.ent_start.delete(0, "end")
        self.app.ent_end.delete(0, "end")
        self.app.ent_start.insert(0, start)
        self.app.ent_end.insert(0, end)
        self.app.on_add_manual()

    def enabled(self, widget):
        return widget.instate(["!disabled"])

    def states(self):
        a = self.app
        return tuple(self.enabled(w) for w in a.video_controls + [a.btn_load])

    def work_dirs(self):
        root = Path(self.app.work_root)
        return list(root.iterdir()) if root.exists() else []

    def create_and_wait(self, timeout=30):
        n = len(self.dialogs)
        self.app.on_create()
        self.assertTrue(self.pump(lambda: not self.app._create_active(), timeout),
                        "create did not finish")
        self.pump(lambda: len(self.dialogs) > n, 3)
        self.pump(timeout=0.2)

    def start_slow_create(self):
        """Two segments, FFmpeg replaced by a minutes-long real encode; returns when it runs."""
        self.load()
        self.add_segment("00:00:00.500", "00:00:01.500")
        self.add_segment("00:00:02.000", "00:00:03.000")
        patch_cmd = mock.patch.object(video_processor, "extract_cmd", slow_extract_cmd)
        patch_cmd.start()
        self.addCleanup(patch_cmd.stop)
        pp = mock.patch.object(subprocess, "Popen", self._popen_recorder())
        pp.start()
        self.addCleanup(pp.stop)
        self.app.on_create()
        self.assertTrue(self.pump(lambda: self.app._creating, 5), "create did not start")
        self.assertTrue(self.pump(lambda: any(p.poll() is None for p in self.procs), 10),
                        "no FFmpeg process started")

    def _popen_recorder(self):
        real = subprocess.Popen

        def rec(*a, **k):
            p = real(*a, **k)
            self.procs.append(p)
            return p
        return rec

    # ------------------------------------------------------------ (1) initial state
    def test_01_initial_state(self):
        a = self.app
        self.assertFalse(self.enabled(a.btn_create))
        for w in a.video_controls:
            self.assertFalse(self.enabled(w), f"{w} should be disabled before a video is loaded")
        self.assertTrue(self.enabled(a.btn_load))
        self.assertIsNone(a.info)
        self.assertEqual(a.lbl_counter.cget("text"), "0 / 10")
        self.assertEqual(a.lbl_info.cget("text"), t("info.none"))

    # ------------------------------------------------------------ (2) load
    def test_02_load_clip(self):
        self.load()
        a = self.app
        text = a.lbl_info.cget("text")
        self.assertIn("clip.mp4", text)
        self.assertIn(format_ms(a.info.duration_ms), text)
        self.assertIn("320", text)
        self.assertIn("240", text)
        self.assertAlmostEqual(a.info.duration_ms, 3600, delta=300)
        self.assertTrue(self.enabled(a.ent_start))
        self.assertTrue(self.enabled(a.ent_end))
        self.assertTrue(self.enabled(a.btn_add_segment))
        self.assertTrue(self.enabled(a.btn_load))
        self.assertFalse(self.enabled(a.btn_play))      # no VLC: no player
        self.assertTrue(a.manual_mode)
        self.assertEqual(self.kinds("error"), [])

    # ------------------------------------------------------------ (3) manual route + limit
    def test_03_manual_segments_and_limit(self):
        self.load()
        a = self.app
        self.add_segment("00:00:00.000", "00:00:01.000")
        self.assertEqual(len(a.segments), 1)
        self.assertEqual(a.lbl_counter.cget("text"), "1 / 10")
        self.assertIn(format_ms(1000), a.lbl_total.cget("text"))
        self.assertEqual(a.ent_start.get(), "")
        self.add_segment("00:00:02.000", "00:00:02.500")
        self.assertEqual(a.lbl_counter.cget("text"), "2 / 10")
        self.assertIn(format_ms(1500), a.lbl_total.cget("text"))
        self.assertEqual(len(a.tree.get_children()), 2)
        for i in range(8):
            self.add_segment("00:00:00.100", f"00:00:00.{200 + i * 50:03d}")
        self.assertEqual(len(a.segments), 10)
        self.assertEqual(a.lbl_counter.cget("text"), "10 / 10")
        self.assertEqual(self.kinds("info"), [])
        self.add_segment("00:00:00.100", "00:00:00.900")      # the 11th
        self.assertEqual(len(a.segments), 10)
        self.pump(lambda: self.kinds("info"), 3)
        infos = self.kinds("info")
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0][1], t("dlg.max_segments"))
        self.assertEqual(infos[0][2], t("err.seg_max", max=10))
        self.assertEqual(a.ent_start.get(), "00:00:00.100")  # input kept, not silently lost

    # ------------------------------------------------------------ (4) create needs a segment
    def test_04_create_disabled_without_segments(self):
        self.load()
        a = self.app
        self.assertFalse(self.enabled(a.btn_create))
        a.on_create()                       # handler also refuses politely
        self.pump(lambda: self.kinds("info"), 3)
        self.assertEqual(self.confirms, [])
        self.assertFalse(a._creating)
        self.assertEqual(self.kinds("info")[0][2], t("err.empty_list"))
        self.add_segment("00:00:00.000", "00:00:01.000")
        self.assertTrue(self.enabled(a.btn_create))
        a.segments.clear()
        a._render_table()
        self.assertFalse(self.enabled(a.btn_create))

    # ------------------------------------------------------------ (5) full create x2
    def test_05_full_create_twice(self):
        self.load()
        a = self.app
        self.add_segment("00:00:00.500", "00:00:01.500")
        self.add_segment("00:00:02.000", "00:00:03.000")
        before = (sha(self.src), self.src.stat().st_mtime_ns, self.src.stat().st_size)
        self.create_and_wait()
        out1 = self.media / "clip (segmented).mp4"
        self.assertTrue(out1.is_file(), self.dialogs)
        self.assertAlmostEqual(probe_duration(out1), 2.0, delta=0.5 + 0.2)
        self.assertEqual(len(self.confirms), 1)
        self.assertEqual(self.yes_labels, [("btn.create_video", "btn.cancel")])  # not Yes / No
        self.assertEqual(self.kinds("error"), [])
        self.assertEqual(self.kinds("info")[-1][1], t("dlg.create_done_title"))
        self.assertTrue(self.enabled(a.btn_create))
        self.assertTrue(self.enabled(a.btn_add_segment))
        self.assertTrue(self.enabled(a.btn_load))
        self.assertEqual(a.lbl_status.cget("text"), t("status.done"))
        self.assertIn(out1.name, a.txt_output.get("1.0", "end"))
        self.assertEqual(self.work_dirs(), [])
        self.assertEqual((sha(self.src), self.src.stat().st_mtime_ns, self.src.stat().st_size),
                         before)
        self.assertFalse(list(self.media.glob("*.part")))
        self.create_and_wait()
        out2 = self.media / "clip (segmented 2).mp4"
        self.assertTrue(out2.is_file())
        self.assertTrue(out1.is_file())
        self.assertAlmostEqual(probe_duration(out2), 2.0, delta=0.7)
        self.assertEqual(self.work_dirs(), [])
        self.assertEqual(sha(self.src), before[0])

    # ------------------------------------------------------------ (6) failure path
    def test_06_failure_keeps_work_folder_and_unlocks(self):
        self.load()
        a = self.app
        self.add_segment("00:00:00.500", "00:00:01.500")
        self.src.write_bytes(b"this is no longer a video" * 200)
        with mock.patch.object(sys, "stderr", io.StringIO()):
            self.create_and_wait()
        errors = self.kinds("error")
        self.assertEqual(len(errors), 1, self.dialogs)
        self.assertEqual(errors[0][1], t("dlg.create_failed_title"))
        self.assertNotIn("{", errors[0][2])
        self.assertTrue(errors[0][2].strip())
        self.assertEqual([d for d in self.kinds("info")
                          if d[1] == t("dlg.create_done_title")], [])
        self.assertEqual(a._texts[a.lbl_status][0], "err.ffmpeg_failed")
        self.assertTrue(self.enabled(a.btn_create))
        self.assertTrue(self.enabled(a.btn_load))
        self.assertFalse(a._creating)
        kept = [p for p in self.work_dirs() if p.name.startswith("job_")]
        self.assertEqual(len(kept), 1)
        self.assertIn(kept[0].name, a.txt_output.get("1.0", "end"))
        self.assertFalse((self.media / "clip (segmented).mp4").exists())

    # ------------------------------------------------------------ (7) locked while creating
    def test_07_locked_while_creating_language_works(self):
        self.start_slow_create()
        a = self.app
        self.assertFalse(self.enabled(a.btn_create))
        self.assertFalse(self.enabled(a.btn_load))
        self.assertFalse(self.enabled(a.btn_add_segment))
        confirms_before = len(self.confirms)
        token = a._load_token
        n = len(a.segments)
        a.on_create()
        a.load_video(self.src)
        self.assertEqual(a._load_token, token)
        a.ent_start.delete(0, "end")
        a.ent_end.delete(0, "end")
        a.ent_start.insert(0, "00:00:00.100")
        a.ent_end.insert(0, "00:00:00.200")
        a.on_add_manual()
        a.tree.selection_set("0")
        a.on_delete()
        a.on_clear()
        a.on_move(1)
        a.on_edit()
        self.pump(timeout=0.4)
        self.assertEqual(len(a.segments), n)
        self.assertEqual(len(self.confirms), confirms_before)
        self.assertTrue(a._creating)
        self.assertFalse(a._loading)
        self.assertIsNone(a._edit_dialog)
        key, params = a._texts[a.lbl_status]
        self.assertEqual(key, "status.creating")
        op_before = a.lbl_operation.cget("text")
        self.assertTrue(op_before)
        a.toggle_language()
        self.assertEqual(get_language(), "ru")
        self.assertEqual(a.lbl_status.cget("text"), t("status.creating"))
        okey, oparams = a._texts[a.lbl_operation]
        self.assertEqual(a.lbl_operation.cget("text"), t(okey, **oparams))
        self.assertNotEqual(a.lbl_operation.cget("text"), op_before)
        self.assertTrue(a._creating)
        a.toggle_language()
        self.assertEqual(get_language(), "en")
        self.assertEqual(a.lbl_operation.cget("text"), t(okey, **oparams))

    # ------------------------------------------------------------ (8) language switch keeps state
    def test_08_language_switch_keeps_state(self):
        self.load()
        a = self.app
        self.add_segment("00:00:00.500", "00:00:01.500")
        self.add_segment("00:00:02.000", "00:00:03.000")
        a.tree.selection_set("0")
        self.pump(timeout=0.2)
        info_en = a.lbl_info.cget("text")
        items = [(s.start_ms, s.end_ms) for s in a.segments.items]
        states = self.states()
        self.assertEqual(a.tree.selection(), ("0",))
        a.toggle_language()
        self.assertEqual(get_language(), "ru")
        self.assertEqual(a.lbl_info.cget("text"), t("info.loaded", name="clip.mp4",
                         duration=format_ms(a.info.duration_ms), width=320, height=240))
        self.assertEqual(a.btn_create.cget("text"), t("btn.create"))
        self.assertEqual([(s.start_ms, s.end_ms) for s in a.segments.items], items)
        self.assertEqual(a.tree.selection(), ("0",))
        self.assertEqual(self.states(), states)
        self.assertEqual(a.lbl_counter.cget("text"), "2 / 10")
        settings = self.localappdata / "VideoSegmentEditor" / "settings.json"
        self.assertTrue(settings.is_file())
        self.assertIn("ru", json.loads(settings.read_text(encoding="utf-8")).values())
        a.toggle_language()
        self.assertEqual(get_language(), "en")
        self.assertEqual(a.lbl_info.cget("text"), info_en)
        self.assertEqual([(s.start_ms, s.end_ms) for s in a.segments.items], items)
        self.assertEqual(a.tree.selection(), ("0",))
        self.assertEqual(self.states(), states)
        self.assertIn("en", json.loads(settings.read_text(encoding="utf-8")).values())

    # ------------------------------------------------------------ (9) close while creating
    def test_09a_close_while_creating_yes_cancels(self):
        self.start_slow_create()
        a = self.app
        self.confirm_answer = True
        before = len(self.confirms)          # the "create?" question was already answered
        a.on_close()
        self.assertTrue(self.pump(lambda: a._closing, 15), "window did not close")
        self.assertEqual(len(self.confirms), before + 1)
        self.assertEqual(self.confirms[-1][0], t("dlg.close_title"))
        self.assertTrue(self.procs)
        self.assertTrue(all(p.poll() is not None for p in self.procs),
                        "an FFmpeg process started by the test is still running")
        with self.assertRaises(tk.TclError):
            a.winfo_exists()
        kept = [p for p in self.work_dirs() if p.name.startswith("job_")]
        self.assertEqual(len(kept), 1)
        self.assertFalse((self.media / "clip (segmented).mp4").exists())
        self.assertFalse(list(self.media.glob("*.part")))

    def test_09b_close_while_creating_no_keeps_running(self):
        self.start_slow_create()
        a = self.app
        before = len(self.confirms)
        self.confirm_answer = False
        a.on_close()
        self.assertTrue(self.pump(lambda: len(self.confirms) == before + 1, 5))
        self.assertEqual(self.confirms[-1][0], t("dlg.close_title"))
        self.pump(timeout=0.5)
        self.assertFalse(a._closing)
        self.assertTrue(a._creating)
        self.assertFalse(a._close_asking)
        self.assertTrue(any(p.poll() is None for p in self.procs))
        self.assertTrue(a.winfo_exists())
        self.assertFalse(self.enabled(a.btn_create))

    # ------------------------------------------------------------ known defects
    def test_bl016_baseexception_in_worker_unlocks_gui(self):
        """BL-016: a BaseException in the create worker leaves the GUI locked (no error status)."""
        self.load()
        a = self.app
        self.add_segment("00:00:00.500", "00:00:01.500")

        class Boom(BaseException):
            pass

        def boom(self_job):
            raise Boom("simulated")

        with mock.patch.object(gui.VideoJob, "run", boom), \
                mock.patch.object(threading, "excepthook", lambda args: None), \
                mock.patch.object(sys, "stderr", io.StringIO()):
            a.on_create()
            self.pump(lambda: a._creating or a._worker is not None, 3)
            self.pump(lambda: not a._create_active(), 3)
            unlocked = not a._create_active()
        self.assertTrue(unlocked, "GUI still locked after the worker died")
        self.assertTrue(self.enabled(a.btn_create))
        self.assertTrue(a._texts[a.lbl_status][0].startswith("err."))

    def test_bl019_failing_player_degrades_to_manual_route(self):
        """BL-019: a player whose tick/time_ms raise floods stderr every 100 ms and stays active."""
        self.load()
        a = self.app

        class BadPlayer:
            def tick(self):
                raise RuntimeError("tick broke")

            def time_ms(self):
                raise RuntimeError("time_ms broke")

            def release(self):
                pass

            def pause(self):
                pass

            def set_volume(self, v):
                pass

        a.player = BadPlayer()
        buf = io.StringIO()
        with mock.patch.object(sys, "stderr", buf):
            self.pump(timeout=1.5)
        floods = buf.getvalue().count("Traceback")
        self.assertLessEqual(floods, 1, f"{floods} tracebacks in 1.5 s")
        self.assertIsNone(a.player, "player was not dropped")
        self.assertTrue(a.manual_mode)
        self.assertTrue(self.enabled(a.btn_add_segment))

    def test_bl019_single_failure_does_not_degrade_and_counter_resets(self):
        self.load()
        a = self.app

        class Flaky:
            def __init__(self):
                self.calls = 0
                self.fail = set()

            def tick(self):
                self.calls += 1
                if self.calls in self.fail:
                    raise RuntimeError("blip")

            def time_ms(self):
                return 500

            def release(self):
                pass

            def pause(self):
                pass

            def set_volume(self, v):
                pass

        p = Flaky()
        p.fail = {1, 2, 4, 5}                     # never three in a row
        a.player = p
        with mock.patch.object(sys, "stderr", io.StringIO()):
            for _ in range(8):
                a._poll()
        self.assertIs(a.player, p, "two failures in a row must not drop the player")
        self.assertFalse(a._preview_failed)

    def test_bl019_user_handler_exception_is_contained(self):
        self.load()
        a = self.app

        class Bad:
            def play(self):
                raise RuntimeError("play broke")

            def pause(self):
                raise RuntimeError("pause broke")

            def stop(self):
                raise RuntimeError("stop broke")

            def time_ms(self):
                raise RuntimeError("time broke")

            def seek_ms(self, ms):
                raise RuntimeError("seek broke")

            def set_volume(self, v):
                raise RuntimeError("vol broke")

            def tick(self):
                pass

            def release(self):
                pass

        a.player = Bad()
        buf = io.StringIO()
        with mock.patch.object(sys, "stderr", buf):
            for fn in (a.on_play, a.on_pause, a.on_stop, a.on_mark_start, a.on_mark_end):
                fn()                              # nothing may escape
        self.assertIsNone(a.player, "three consecutive failures must drop the player")
        self.assertTrue(a._preview_failed)
        self.assertTrue(a.manual_mode)
        self.assertLessEqual(buf.getvalue().count("Traceback"), 1)
        self.assertEqual(a.lbl_video_msg.cget("text"), t("video.preview_failed"))

    # ------------------------------------------------------------ BL-015: marks at the end
    def test_bl015_marks_are_clamped_to_the_video_length(self):
        self.load()
        a = self.app
        dur = a.info.duration_ms

        class Ended:
            def __init__(self, ms):
                self.ms = ms

            def time_ms(self):
                return self.ms

            def tick(self):
                pass

            def release(self):
                pass

        a.player = Ended(500)
        a.on_mark_start()
        self.assertEqual(a.marker.start_ms, 500)
        a.player = Ended(dur + 120)               # VLC reports a little past the end
        a.on_mark_end()
        self.assertEqual(len(a.segments), 1)
        self.assertEqual(a.segments.items[0].end_ms, dur)
        self.assertEqual(self.kinds("info"), [])
        self.assertNotEqual(a._texts[a.lbl_status][0], "err.seg_past_end")

    # ------------------------------------------------------------ WP2a-1: Cancel button (BL-017)
    def test_cancel_button_disabled_when_idle(self):
        a = self.app
        self.assertFalse(self.enabled(a.btn_cancel_job))
        self.load()
        self.add_segment("00:00:00.500", "00:00:01.500")
        self.assertFalse(self.enabled(a.btn_cancel_job))
        self.assertEqual(a.btn_cancel_job.cget("text"), t("btn.cancel_job"))

    def test_cancel_button_enabled_while_creating_and_fits_minimum_size(self):
        self.start_slow_create()
        a = self.app
        self.pump(timeout=0.3)
        self.assertTrue(a.btn_cancel_job.winfo_ismapped())
        self.assertTrue(self.enabled(a.btn_cancel_job))
        a.update_idletasks()
        self.assertLessEqual(a.winfo_reqheight(), 760, "required height exceeds the minimum")
        self.assertLessEqual(a.winfo_reqwidth(), 900)
        a.toggle_language()                       # the Russian text must fit as well
        a.update_idletasks()
        self.assertLessEqual(a.winfo_reqheight(), 760)
        self.assertEqual(a.btn_cancel_job.cget("text"), t("btn.cancel_job"))
        a.toggle_language()

    def test_cancel_confirm_no_keeps_running(self):
        self.start_slow_create()
        a = self.app
        self.confirm_answer = False
        before = len(self.confirms)
        a.on_cancel_job()
        self.assertTrue(self.pump(lambda: len(self.confirms) == before + 1, 5))
        self.assertEqual(self.confirms[-1][0], t("dlg.cancel_job_title"))
        self.assertEqual(self.confirms[-1][1], t("dlg.cancel_job_message"))
        self.pump(timeout=0.5)
        self.assertTrue(a._creating)
        self.assertTrue(any(p.poll() is None for p in self.procs))
        self.assertTrue(self.enabled(a.btn_cancel_job), "button must be usable again after No")
        self.assertFalse(self.enabled(a.btn_create))

    def test_cancel_double_click_does_not_stack_dialogs(self):
        self.start_slow_create()
        a = self.app
        self.confirm_answer = False
        before = len(self.confirms)
        a.on_cancel_job()
        a.on_cancel_job()
        a.on_cancel_job()
        self.pump(timeout=0.6)
        self.assertEqual(len(self.confirms), before + 1)

    def test_cancel_confirm_yes_cancels_and_unlocks(self):
        self.start_slow_create()
        a = self.app
        self.confirm_answer = True
        a.on_cancel_job()
        self.assertTrue(self.pump(lambda: not a._create_active(), 10), "did not stop")
        self.pump(timeout=0.3)
        self.assertEqual(self.confirms[-1][0], t("dlg.cancel_job_title"))
        self.assertTrue(all(p.poll() is not None for p in self.procs), "FFmpeg still running")
        self.assertFalse(list(self.media.glob("*.part")))
        self.assertFalse((self.media / "clip (segmented).mp4").exists())
        self.assertEqual(a._texts[a.lbl_status][0], "err.cancelled")
        kept = [p for p in self.work_dirs() if p.name.startswith("job_")]
        self.assertEqual(len(kept), 1)
        self.assertIn(kept[0].name, a.txt_output.get("1.0", "end"))
        self.assertTrue(self.enabled(a.btn_create))
        self.assertTrue(self.enabled(a.btn_load))
        self.assertFalse(self.enabled(a.btn_cancel_job))
        self.assertEqual(float(a.progress.cget("value")), 0.0)
        self.assertEqual(self.kinds("error"), [])

    def test_cancel_answered_after_job_finished_does_nothing(self):
        """The job ends while the question is open: Yes must not break anything."""
        self.start_slow_create()
        a = self.app
        a.on_cancel_job()
        a._creating = False                       # simulate: the result arrived meanwhile
        self.pump(timeout=0.5)
        self.assertFalse(a._cancel_requested.is_set())
        a._creating = True                        # let tearDown stop the real worker

    # ------------------------------------------------------------ WP2a-2: Open folder button
    def test_open_folder_button_idle_failure_cancel_and_load(self):
        a = self.app
        self.assertFalse(a.btn_open_folder.winfo_ismapped())
        self.load()
        self.add_segment("00:00:00.500", "00:00:01.500")
        with mock.patch.object(video_processor, "extract_cmd",
                               lambda *args: [FFMPEG, "-hide_banner", "-nostdin", "-n",
                                              "-i", "no_such_input.mp4", str(args[3])]):
            self.create_and_wait()
        self.pump(timeout=0.2)
        kept = [p for p in self.work_dirs() if p.name.startswith("job_")]
        self.assertEqual(len(kept), 1)
        self.assertIn(kept[0].name, a.txt_output.get("1.0", "end"))
        self.assertTrue(a.btn_open_folder.winfo_ismapped())
        self.assertEqual(a.btn_open_folder.cget("text"), "Open folder")
        with mock.patch.object(gui.os, "startfile", create=True) as sf:
            a.btn_open_folder.invoke()
        sf.assert_called_once_with(str(kept[0]))
        with mock.patch.object(gui.os, "startfile", create=True,
                               side_effect=OSError("no")) as sf:
            a.on_open_folder()                      # errors are ignored
        a.update_idletasks()
        self.assertLessEqual(a.winfo_reqheight(), 760)
        w_en = a.winfo_reqwidth()
        a.btn_open_folder.grid_remove()
        a.update_idletasks()
        # the button must not widen the window request (the long status text decides it)
        self.assertEqual(w_en, a.winfo_reqwidth())
        a.btn_open_folder.grid()
        a.update_idletasks()
        h_en = a.winfo_reqheight()
        a.toggle_language()
        a.update_idletasks()
        self.assertEqual(a.btn_open_folder.cget("text"), "Открыть папку")
        self.assertLessEqual(a.winfo_reqheight(), 760)
        self.assertLessEqual(a.winfo_reqwidth(), 900)
        print(f"\n[open-folder] required size EN {w_en}x{h_en}, "
              f"RU {a.winfo_reqwidth()}x{a.winfo_reqheight()}", file=sys.__stderr__)
        a.toggle_language()
        # loading another video hides it again (and clears the kept-folder text)
        self.load()
        self.assertFalse(a.btn_open_folder.winfo_ismapped())
        self.assertNotIn("job_", a.txt_output.get("1.0", "end"))

    def test_open_folder_button_not_shown_after_success(self):
        self.load()
        self.add_segment("00:00:00.500", "00:00:01.500")
        self.create_and_wait()
        self.assertFalse(self.app.btn_open_folder.winfo_ismapped())

    def test_open_folder_hidden_when_next_job_starts(self):
        a = self.app
        a.set_output("err.kept", path=str(self.localappdata))
        a.update_idletasks()
        self.assertTrue(a.btn_open_folder.winfo_ismapped())
        a.set_output(None)
        a.update_idletasks()
        self.assertFalse(a.btn_open_folder.winfo_ismapped())

    # ------------------------------------------------------------ small items
    def test_confirm_and_start_without_info_unlocks_controls(self):
        self.load()
        a = self.app
        self.add_segment("00:00:00.500", "00:00:01.500")
        a._create_pending = True
        a.info = None
        with mock.patch.object(a, "_update_controls") as upd:
            a._confirm_and_start()
        self.assertFalse(a._create_pending)
        self.assertTrue(upd.called)
        self.assertEqual(self.confirms, [])

    def test_probe_worker_always_posts_one_terminal_event(self):
        a = self.app

        class Boom(BaseException):
            pass

        with mock.patch.object(gui, "probe", side_effect=Boom("x")), \
                mock.patch.object(sys, "stderr", io.StringIO()):
            a._probe_worker(self.src, 1)
        kinds = []
        while not a.events.empty():
            kinds.append(a.events.get_nowait()[0])
        self.assertEqual(kinds, ["probe_error"])

    def test_bl016_keyboard_interrupt_in_create_worker_posts_error(self):
        a = self.app
        with mock.patch.object(gui.VideoJob, "run", side_effect=KeyboardInterrupt), \
                mock.patch.object(sys, "stderr", io.StringIO()):
            a._create_worker(1, self.src, mock.Mock(), [], self.localappdata)
        events = []
        while not a.events.empty():
            events.append(a.events.get_nowait())
        self.assertEqual([e[0] for e in events], ["create_error"])
        self.assertEqual(events[0][1][1], "err.file_problem")

    # ------------------------------------------------------------ WP2a-1: close without blocking (BL-018)
    def _tick_counter(self):
        stamps = []

        def tick():
            stamps.append(time.monotonic())
            if not self.app._closing:
                try:
                    self.app.after(50, tick)
                except tk.TclError:
                    pass
        self.app.after(50, tick)
        return stamps

    def test_bl018_close_yes_keeps_event_loop_ticking(self):
        self.start_slow_create()
        a = self.app
        stamps = self._tick_counter()
        self.confirm_answer = True
        t0 = time.monotonic()
        a.on_close()
        self.assertTrue(self.pump(lambda: a._closing, 10), "window did not close")
        self.assertLess(time.monotonic() - t0, 6.5)
        self.assertTrue(all(p.poll() is not None for p in self.procs))
        gaps = [b - x for x, b in zip(stamps, stamps[1:])]
        self.assertLess(max(gaps, default=0), 0.5)

    def test_bl018_stuck_worker_closes_at_deadline_without_freezing(self):
        self.start_slow_create()
        a = self.app
        job = a._job
        self.assertIsNotNone(job)
        real_cancel = job.cancel
        job.cancel = lambda: None                 # the worker does not stop by itself
        try:
            stamps = self._tick_counter()
            self.confirm_answer = True
            t0 = time.monotonic()
            a.on_close()
            self.assertTrue(self.pump(lambda: a._closing, 12), "window did not close")
            took = time.monotonic() - t0
            self.assertGreaterEqual(took, 4.5)
            self.assertLess(took, 6.5)
            gaps = [b - x for x, b in zip(stamps, stamps[1:])]
            self.assertLess(max(gaps), 0.5, "the event loop froze while waiting")
            self.assertGreater(len(stamps), 40)   # about 5 s / 50 ms: the loop never stopped
            self.assertEqual(len(self.kinds("error")) + len(self.kinds("info")), 0)
        finally:
            job.cancel = real_cancel
            real_cancel()                         # now really stop the FFmpeg child

    def test_bl018_result_during_stopping_wait_opens_no_dialog(self):
        self.start_slow_create()
        a = self.app
        self.confirm_answer = True
        a.on_close()
        self.assertTrue(self.pump(lambda: a._close_waiting or a._closing, 5))
        self.assertTrue(a._close_waiting)
        a._notify(a.show_info, "dlg.create_done_title", "status.done")
        self.pump(lambda: a._closing, 10)
        self.assertEqual(self.dialogs, [])


if __name__ == "__main__":
    unittest.main()
