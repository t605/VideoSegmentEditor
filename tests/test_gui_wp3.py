"""WP3 tests of the real gui.App: DPI scaling of the layout, status levels, the dark theme details,
tooltips, tab order and the themed dialog. Real Tk window, no FFmpeg, no VLC (a dummy player stands in
for VLC where the "with preview" layout matters). Settings go to a temp folder.
"""
import gc
import os
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
os.environ["VSE_FORCE_NO_VLC"] = "1"

import tkinter as tk  # noqa: E402


def _tk_problem():
    try:
        root = tk.Tk()
        root.destroy()
    except tk.TclError as exc:
        return f"Tk cannot create a window: {exc}"
    return None


SKIP_REASON = _tk_problem()


def _display_scaling():
    """Tk keeps `tk scaling` per DISPLAY, so it outlives one App: remember the real value and put
    it back after every test that emulated another one."""
    try:
        root = tk.Tk()
        value = float(root.tk.call("tk", "scaling"))
        root.destroy()
        return value
    except tk.TclError:
        return None


REAL_SCALING = _display_scaling() if SKIP_REASON is None else None

if SKIP_REASON is None:
    import gui  # noqa: E402
    from i18n import set_language, t  # noqa: E402
    from segment_manager import format_ms  # noqa: E402
    from video_processor import VideoInfo  # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent
LONG_PATH = ("C:\\Users\\SomeLongUserName\\AppData\\Local\\VideoSegmentEditor\\work\\"
             "job_20261108-143559-abcd1234")


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


class DummyPlayer:
    """Stands in for VLC: enough for the "video preview" layout (Mark buttons instead of boxes)."""
    def __init__(self, *a, **k): pass
    def tick(self): pass
    def time_ms(self): return 0
    def release(self): pass
    def load(self, path): pass
    def play(self): pass
    def pause(self): pass
    def stop(self): pass
    def seek_ms(self, ms): pass
    def set_volume(self, v): pass


def scaling_for(percent):
    return 96 / 72 * percent / 100.0           # Tk's "points to pixels" factor; 1.3333 = 100 %


@unittest.skipIf(SKIP_REASON is not None, SKIP_REASON or "")
class Wp3Base(unittest.TestCase):
    vlc_like = False

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vse_wp3_"))
        set_language("en")
        self.apps = []
        self.dialogs = []
        self._patches = [
            mock.patch.object(gui.App, "_show_message",
                              lambda app, kind, title, msg: self.dialogs.append((kind, title, msg))),
            mock.patch.object(gui.App, "_ask_yes_no", lambda app, *a, **k: True),
        ]
        if self.vlc_like:
            self._patches += [
                mock.patch.object(gui, "vlc_available", return_value=True),
                mock.patch.object(gui.App, "_ensure_player",
                                  lambda app: setattr(app, "player", DummyPlayer())),
            ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for app in self.apps:
            try:
                if REAL_SCALING:
                    app.tk.call("tk", "scaling", REAL_SCALING)
                app._closing = True
                for ident in app.tk.splitlist(app.tk.call("after", "info")):
                    app.after_cancel(ident)
                app.destroy()
            except tk.TclError:
                pass
        for p in self._patches:
            p.stop()
        set_language("en")
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.apps = []
        gc.collect()

    def make_app(self, lang="en", **kw):
        sp = self.tmp / f"settings_{len(self.apps)}.json"
        sp.write_text('{"language": "%s"}' % lang, encoding="utf-8")
        app = gui.App("1.0", settings_path=sp, **kw)
        self.apps.append(app)
        app.work_root = self.tmp / "work"
        return app

    def load(self, app, seconds=60):
        info = VideoInfo(path=Path("clip.mp4"), duration_ms=seconds * 1000, width=1280,
                         height=720, fps=25.0, has_audio=True)
        app._load_token += 1
        app._on_probe_ok((app._load_token, info))
        app.update()

    def settle(self, app, secs=0.15):
        import time
        end = time.time() + secs
        while time.time() < end:
            app.update()
            time.sleep(0.01)


# ------------------------------------------------------------------ (1) DPI
class DpiLayoutTests(Wp3Base):
    vlc_like = True
    PERCENTS = (100, 125, 150, 200)

    def states(self, app):
        """Idle, loaded with segments, and the worst bottom block (failure with a long path)."""
        yield "idle"
        self.load(app)
        for s, e in (("0:05", "0:10"), ("0:20", "0:24.5"), ("0:30", "0:33")):
            app.segments.add_text(s, e)
        app._render_table(select=1)
        yield "loaded, 3 segments"
        app.set_status("err.ffmpeg_failed", "error")
        app.set_output("err.kept", path=LONG_PATH)
        yield "failure + kept path"
        app.set_output(None)
        app.set_status("status.creating")
        app._creating = True                    # a job runs: marking locked, Cancel shown
        app._set_percent("38 %")
        app._set_operation("progress.cut", i=1, n=3)
        app._update_controls()
        yield "processing bar visible"
        app._creating = False

    def test_required_size_never_exceeds_the_minimum_at_100_125_150_200_percent(self):
        for lang in ("en", "ru"):
            for pct in self.PERCENTS:
                with self.subTest(lang=lang, scale=pct):
                    set_language(lang)
                    app = self.make_app(lang, scaling=scaling_for(pct), workarea=(3840, 2400))
                    app.update()
                    self.assertAlmostEqual(app.ui_scale, pct / 100.0, places=2)
                    min_w, min_h = app.minsize()
                    # the minimum is the design minimum times the scale (900x760 at 100 %)
                    self.assertGreaterEqual(min_w, round(900 * pct / 100) - 1)
                    self.assertGreaterEqual(min_h, round(760 * pct / 100) - 1)
                    for name in self.states(app):
                        self.settle(app)
                        app.update_idletasks()
                        self.assertLessEqual(app.winfo_reqheight(), min_h,
                                             f"{lang} {pct}% {name}: required height")

    def test_required_width_at_start_fits_the_minimum(self):
        for lang in ("en", "ru"):
            for pct in self.PERCENTS:
                with self.subTest(lang=lang, scale=pct):
                    set_language(lang)
                    app = self.make_app(lang, scaling=scaling_for(pct), workarea=(3840, 2400))
                    app.update_idletasks()
                    self.assertLessEqual(app.winfo_reqwidth(), app.minsize()[0])

    def test_default_geometry_is_scaled_and_not_below_the_minimum(self):
        for pct in self.PERCENTS:
            with self.subTest(scale=pct):
                app = self.make_app(scaling=scaling_for(pct), workarea=(3840, 2400))
                app.update()
                w, h = app.winfo_width(), app.winfo_height()
                min_w, min_h = app.minsize()
                self.assertGreaterEqual(w, min_w - 1)
                self.assertGreaterEqual(h, min_h - 1)
                if pct <= 125:      # (Windows will not make a window taller than the real screen)
                    self.assertAlmostEqual(w, round(1100 * pct / 100), delta=2)
                    self.assertAlmostEqual(h, round(840 * pct / 100), delta=2)

    def test_geometry_is_clamped_to_the_work_area_and_not_below_the_minimum(self):
        # 150 % on a 1920x1080 laptop: the usable desktop is about 1920x1032
        app = self.make_app(scaling=scaling_for(150), workarea=(1920, 1032))
        app.update()
        frame_w, frame_h = app.px(gui.FRAME_W), app.px(gui.FRAME_H)
        self.assertLessEqual(app.winfo_width(), 1920 - frame_w)
        self.assertLessEqual(app.winfo_height(), 1032 - frame_h)
        min_w, min_h = app.minsize()
        self.assertGreaterEqual(app.winfo_width(), min_w)
        self.assertGreaterEqual(app.winfo_height(), min_h)
        self.assertLessEqual(min_h, 1032 - frame_h)

    def test_small_screen_squeezes_the_video_row_not_the_texts(self):
        app = self.make_app(scaling=scaling_for(150), workarea=(1920, 1032))
        for name in self.states(app):
            self.settle(app)
        min_h = app.minsize()[1]
        self.assertLessEqual(app.winfo_reqheight(), min_h, "something is cut at the minimum")
        self.assertLess(int(app.grid_rowconfigure(2)["minsize"]), app.px(gui.VIDEO_MIN_H),
                        "the video row should have given way")
        self.assertGreaterEqual(int(app.grid_rowconfigure(2)["minsize"]),
                                app.px(gui.VIDEO_FLOOR_H))

    def test_minimum_grows_when_a_state_needs_more_room(self):
        app = self.make_app(workarea=(1920, 1080))
        app.update()
        before = app.minsize()[1]
        self.assertEqual(before, 760)
        app.lbl_status.configure(text=("line" + chr(10)) * 12, wraplength=0)   # a very tall status
        app.update_idletasks()
        app._ensure_min_fits()
        self.assertEqual(app.minsize()[1], before, "one look must not be enough (re-layout)")
        app._ensure_min_fits()
        self.assertGreater(app.minsize()[1], before)
        self.assertLessEqual(app.minsize()[1], app._max_h)

    def test_scale_is_at_least_one(self):
        app = self.make_app(scaling=1.0)
        self.assertEqual(app.ui_scale, 1.0)
        self.assertEqual(app.px(10), 10)

    def test_header_logo_is_the_exact_header_size_without_subsampling(self):
        data = (PROJECT / "assets" / "logo_header.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (46, 33))
        app = self.make_app()
        self.assertEqual((app._logo_img.width(), app._logo_img.height()), (46, 33))


# ------------------------------------------------------------------ (2) status area
class StatusTests(Wp3Base):
    vlc_like = True

    def test_first_launch_instruction_appears_once(self):
        app = self.make_app()
        app.update()
        self.assertEqual(app.lbl_status.cget("text"), "")
        self.assertEqual(app.lbl_status_glyph.cget("text"), "")
        self.assertEqual(app.lbl_video_msg.cget("text"), t("status.load_to_begin"))
        self.assertEqual(app.lbl_mark_status.cget("text"), "")

    def test_each_level_has_its_own_colour_and_glyph(self):
        app = self.make_app()
        seen_glyphs, seen_colours = set(), set()
        expect = {"info": gui.FG, "ok": gui.OK, "warn": gui.WARN, "error": gui.ERR}
        for level, colour in expect.items():
            app.set_status("status.loaded", level)
            style = str(app.lbl_status.cget("style"))
            self.assertEqual(style, f"{level}.Status.TLabel")
            self.assertEqual(ttk_lookup(app, style, "foreground"), colour)
            glyph = app.lbl_status_glyph.cget("text")
            self.assertTrue(glyph, level)
            seen_glyphs.add(glyph)
            seen_colours.add(colour)
        self.assertEqual(len(seen_glyphs), 4)
        self.assertEqual(len(seen_colours), 4)
        app.set_status(None)
        self.assertEqual(app.lbl_status_glyph.cget("text"), "")
        with self.assertRaises(ValueError):
            app.set_status("status.loaded", "loud")

    def test_status_keeps_its_key_and_follows_the_language(self):
        app = self.make_app()
        app.set_status("status.done", "ok")
        self.assertEqual(app._texts[app.lbl_status][0], "status.done")
        app.toggle_language()
        self.assertEqual(app.lbl_status.cget("text"), t("status.done"))
        self.assertEqual(app.lbl_status_glyph.cget("text"), gui.STATUS_GLYPHS["ok"])
        app.toggle_language()

    def test_validation_message_is_warn_and_cleared_by_the_next_action(self):
        app = self.make_app()
        self.load(app)
        app.ent_start.insert(0, "9:99")
        app.ent_end.insert(0, "1:00")
        app.on_add_manual()
        self.assertEqual(app._status_level, "warn")
        self.assertTrue(app._status_transient)
        self.assertTrue(app.lbl_status.cget("text"))
        self.assertIsNotNone(app._status_timer)
        app.ent_start.delete(0, "end")
        app.ent_end.delete(0, "end")
        app.ent_start.insert(0, "0:01")
        app.ent_end.insert(0, "0:02")
        app.on_add_manual()                       # a valid action: the old warning is gone
        self.assertEqual(app._status_level, "ok")
        self.assertIsNone(app._status_timer)
        self.assertEqual(app._texts[app.lbl_status][0], "mark.added")

    def test_validation_message_disappears_by_itself(self):
        app = self.make_app()
        self.load(app)
        with mock.patch.object(gui, "STATUS_FLASH_MS", 150):
            app.flash_status("err.no_start")
        self.assertTrue(app.lbl_status.cget("text"))
        self.settle(app, 0.5)
        self.assertEqual(app.lbl_status.cget("text"), "")
        self.assertEqual(app.lbl_status_glyph.cget("text"), "")

    def test_new_status_cancels_the_timer_and_keeps_the_new_message(self):
        app = self.make_app()
        with mock.patch.object(gui, "STATUS_FLASH_MS", 150):
            app.flash_status("err.no_start")
        app.set_status("status.done", "ok")
        self.assertIsNone(app._status_timer)
        self.settle(app, 0.5)
        self.assertEqual(app.lbl_status.cget("text"), t("status.done"))

    def test_failure_status_has_no_path_and_the_output_box_has_it(self):
        app = self.make_app()
        app._creating, app._create_token = True, 7
        app._on_create_error((7, "err.ffmpeg_failed", {"kept_dir": LONG_PATH},
                              "dlg.create_failed_title"))
        self.assertEqual(app.lbl_status.cget("text"), t("err.ffmpeg_failed"))
        self.assertNotIn(LONG_PATH, app.lbl_status.cget("text"))
        self.assertEqual(app._status_level, "error")
        self.assertIn(LONG_PATH, app.txt_output.get("1.0", "end"))
        self.assertTrue(app.btn_open_folder.winfo_manager())

    def test_cancel_status_is_warn_without_path(self):
        app = self.make_app()
        app._creating, app._create_token = True, 3
        app._on_create_cancelled((3, "err.cancelled", {"kept_dir": LONG_PATH}))
        self.assertEqual(app.lbl_status.cget("text"), t("err.cancelled"))
        self.assertEqual(app._status_level, "warn")
        self.assertIn(LONG_PATH, app.txt_output.get("1.0", "end"))

    def test_success_status_is_short_and_the_box_has_the_saved_path(self):
        app = self.make_app()
        app._creating, app._create_token = True, 5
        app._on_create_done((5, LONG_PATH))
        self.assertEqual(app.lbl_status.cget("text"), t("status.done"))
        self.assertEqual(app._status_level, "ok")
        box = app.txt_output.get("1.0", "end").strip()
        self.assertEqual(box, t("out.saved", path=LONG_PATH))
        self.assertNotIn(t("status.done"), box)          # no duplicate "Done."

    def test_output_box_wraps_by_character_and_shows_the_whole_path(self):
        app = self.make_app(workarea=(1920, 1080))
        app.geometry("900x760")
        app.update()
        self.assertEqual(app.txt_output.cget("wrap"), "char")
        app.set_output("err.kept", path=LONG_PATH + "\\" + "x" * 60)
        self.settle(app, 0.3)
        lines = int(app.txt_output.cget("height"))
        self.assertGreaterEqual(lines, 2)
        self.assertLessEqual(lines, gui.OUTPUT_MAX_LINES)
        # every character is inside the visible lines: last text index is on a visible display line
        self.assertTrue(app.txt_output.bbox("end-2c"), "the end of the path is not visible")
        app.set_output(None)
        self.settle(app, 0.2)
        self.assertEqual(int(app.txt_output.cget("height")), 1)

    def test_percent_and_operation_rows_exist_only_while_creating(self):
        app = self.make_app()
        app.update()
        self.assertFalse(app.lbl_percent.winfo_ismapped())
        self.assertFalse(app.lbl_operation.winfo_ismapped())
        app._set_percent("12 %")
        app._set_operation("op.merge")
        app.update()
        self.assertTrue(app.lbl_percent.winfo_ismapped())
        self.assertTrue(app.lbl_operation.winfo_ismapped())
        app._set_percent(None)
        app._set_operation(None)
        app.update()
        self.assertFalse(app.lbl_percent.winfo_ismapped())
        self.assertFalse(app.lbl_operation.winfo_ismapped())


def ttk_lookup(app, style, option):
    from tkinter import ttk
    return ttk.Style(app).lookup(style, option)


class MarkHintTests(Wp3Base):
    vlc_like = True

    def test_hint_is_recomputed_from_the_state(self):
        for lang in ("en", "ru"):
            set_language(lang)
            app = self.make_app(lang)
            app.update()
            self.assertEqual(app.lbl_mark_status.cget("text"), "")          # no video: disabled
            self.assertFalse(app.lbl_mark_status.winfo_ismapped())
            self.load(app)
            self.assertEqual(app.lbl_mark_status.cget("text"), t("mark.hint"))
            self.assertTrue(app.lbl_mark_status.winfo_ismapped())
            app.marker.mark_start(1000, app.segments)
            app._refresh_mark_labels()
            self.assertEqual(app.lbl_mark_status.cget("text"),
                             t("mark.pending", time=format_ms(1000)))
            app.marker.clear()
            for i in range(gui.MAX_SEGMENTS):
                app.segments.add_text(f"0:{i:02d}", f"0:{i:02d}.5")
            app._render_table()
            self.assertEqual(app.lbl_mark_status.cget("text"),
                             t("mark.limit", max=gui.MAX_SEGMENTS))
            app._creating = True                     # a job runs: marking is locked
            app._update_controls()
            self.assertEqual(app.lbl_mark_status.cget("text"), "")
            app._creating = False

    def test_limit_text_says_ten(self):
        self.assertEqual(t("mark.limit", max=10), "Limit of 10 segments reached. Delete one to add another.")

    def test_mark_start_button_is_tinted_once_a_start_exists(self):
        app = self.make_app()
        self.load(app)
        self.assertEqual(str(app.btn_mark_start.cget("style")), "Mark.TButton")
        app.marker.mark_start(2000, app.segments)
        app._refresh_mark_labels()
        self.assertEqual(str(app.btn_mark_start.cget("style")), "MarkSet.Mark.TButton")
        self.assertEqual(str(app.btn_mark_end.cget("style")), "Mark.TButton")
        app.marker.clear()
        app._refresh_mark_labels()
        self.assertEqual(str(app.btn_mark_start.cget("style")), "Mark.TButton")


# ------------------------------------------------------------------ (3) style block
class StyleTests(Wp3Base):
    def test_focus_ring_styles(self):
        from tkinter import ttk
        app = self.make_app()
        s = ttk.Style(app)
        self.assertEqual(s.lookup("TButton", "focuscolor"), gui.LINK)
        for style in ("TButton", "Create.TButton", "Mark.TButton", "MarkSet.Mark.TButton",
                      "Icon.TButton", "TEntry"):
            self.assertEqual(s.lookup(style, "bordercolor", ["focus"]), gui.LINK, style)
        self.assertEqual(s.lookup("Horizontal.TScale", "background", ["focus"]), gui.LINK)
        self.assertEqual(s.lookup("Treeview", "bordercolor", ["focus"]), gui.LINK)

    def test_sliders_light_thumb_dim_when_disabled(self):
        from tkinter import ttk
        s = ttk.Style(self.make_app())
        self.assertEqual(s.lookup("Horizontal.TScale", "background"), gui.THUMB)
        self.assertEqual(s.lookup("Horizontal.TScale", "troughcolor"), gui.TROUGH)
        self.assertEqual(s.lookup("Horizontal.TScale", "background", ["disabled"]), gui.THUMB_OFF)
        self.assertEqual(s.lookup("Horizontal.TScale", "lightcolor", ["disabled"]), gui.THUMB_OFF)
        self.assertEqual(s.lookup("Horizontal.TScale", "bordercolor", ["disabled"]), gui.BORDER)

    def test_scrollbar_is_quiet_and_hides_itself_when_everything_fits(self):
        from tkinter import ttk
        app = self.make_app()
        s = ttk.Style(app)
        self.assertEqual(s.lookup("Vertical.TScrollbar", "background"), gui.SCROLL)
        self.assertEqual(str(s.lookup("Vertical.TScrollbar", "gripcount")), "0")
        self.load(app)
        app.update()
        self.assertFalse(app.sb.winfo_ismapped(), "scrollbar visible on an empty table")
        for i in range(gui.MAX_SEGMENTS):
            app.segments.add_text(f"0:{i:02d}", f"0:{i:02d}.5")
        app._render_table()
        self.settle(app, 0.3)
        self.assertTrue(app.sb.winfo_ismapped(), "scrollbar missing with 10 rows")
        app.segments.clear()
        app._render_table()
        self.settle(app, 0.3)
        self.assertFalse(app.sb.winfo_ismapped())

    def test_disabled_text_and_create_styles(self):
        from tkinter import ttk
        s = ttk.Style(self.make_app())
        self.assertEqual(gui.FG_OFF, "#808080")
        self.assertEqual(s.lookup("TButton", "foreground", ["disabled"]), gui.FG_OFF)
        self.assertEqual(s.lookup("Create.TButton", "background", ["disabled"]), gui.CREATE_OFF_BG)
        self.assertEqual(s.lookup("Create.TButton", "foreground", ["disabled"]), gui.CREATE_OFF_FG)
        self.assertNotEqual(s.lookup("Create.TButton", "background", ["disabled"]),
                            s.lookup("TButton", "background", ["disabled"]))

    def test_dead_start_style_is_gone(self):
        self.assertNotIn("Start.TButton", (PROJECT / "gui.py").read_text(encoding="utf-8"))

    def test_row_numbers_use_the_normal_text_colour(self):
        from tkinter import ttk
        s = ttk.Style(self.make_app())
        self.assertEqual(s.lookup("Treeview", "foreground"), gui.FG)
        source = (PROJECT / "gui.py").read_text(encoding="utf-8")
        self.assertNotIn("tag_configure", source)        # no per-column / per-row colour

    def test_empty_table_hint_shows_only_without_rows(self):
        app = self.make_app()
        self.load(app)
        app.update()
        self.assertTrue(app.lbl_empty.winfo_ismapped())
        self.assertEqual(app.lbl_empty.cget("text"), t("table.empty"))
        app.segments.add_text("0:01", "0:02")
        app._render_table(select=0)
        app.update()
        self.assertFalse(app.lbl_empty.winfo_ismapped())
        app.toggle_language()
        self.assertEqual(app.lbl_empty.cget("text"), t("table.empty"))
        app.toggle_language()

    def test_contrast_of_every_text_colour(self):
        text_pairs = [
            (gui.FG, gui.BG), (gui.FG, gui.PANEL), (gui.FG_DIM, gui.BG), (gui.FG_DIM, gui.PANEL_ALT),
            (gui.OK, gui.BG), (gui.WARN, gui.BG), (gui.ERR, gui.BG), (gui.LINK, gui.VIDEO_BG),
            (gui.FG, gui.CREATE_BG), (gui.FG, gui.CREATE_HOT), (gui.FG, gui.MARK_SET_BG),
            (gui.FG, gui.SELECTED_BG), (gui.FG, gui.PANEL_ALT),
        ]
        for fg, bg in text_pairs:
            self.assertGreaterEqual(ratio(fg, bg), 4.5, f"{fg} on {bg}")
        # disabled text is exempt from WCAG, but must stay readable
        self.assertGreaterEqual(ratio(gui.FG_OFF, gui.BG), 4.4)
        self.assertGreaterEqual(ratio(gui.FG_OFF, gui.PANEL), 3.9)
        self.assertGreaterEqual(ratio(gui.CREATE_OFF_FG, gui.CREATE_OFF_BG), 4.5)
        # non-text parts need 3:1
        for fg, bg in ((gui.LINK, gui.PANEL_ALT), (gui.LINK, gui.CREATE_BG), (gui.LINK, gui.BG),
                       (gui.THUMB, gui.TROUGH), (gui.LINK, gui.TROUGH),
                       (gui.ACCENT, gui.MARK_SET_BG)):
            self.assertGreaterEqual(ratio(fg, bg), 3.0, f"{fg} on {bg}")


# ------------------------------------------------------------------ (4) small items
class SmallItemTests(Wp3Base):
    vlc_like = True

    def test_tooltips_for_the_three_transport_buttons_in_both_languages(self):
        app = self.make_app()
        for tip, key, en, ru in ((app.tip_play, "tip.play", "Play", "Воспроизвести"),
                                 (app.tip_pause, "tip.pause", "Pause", "Пауза"),
                                 (app.tip_stop, "tip.stop", "Stop", "Остановить")):
            self.assertEqual(tip.key, key)
            set_language("en")
            self.assertEqual(tip.text(), en)
            set_language("ru")
            self.assertEqual(tip.text(), ru)
        set_language("en")
        self.assertEqual(gui.Tooltip.DELAY_MS, 500)

    def test_tooltip_opens_after_the_delay_and_closes_on_leave(self):
        app = self.make_app()
        app.update()
        tip = app.tip_play
        with mock.patch.object(gui.Tooltip, "DELAY_MS", 80):
            tip._schedule()
            self.assertIsNotNone(tip._after)
            self.assertIsNone(tip._tip)               # not yet: it is delayed
            self.settle(app, 0.4)
            self.assertIsNotNone(tip._tip)
            self.assertEqual(tip._tip.winfo_children()[0].cget("text"), "Play")
            tip.hide()
            self.assertIsNone(tip._tip)
            tip._schedule()
            tip.hide()                                # leaving before it opened cancels it
            self.settle(app, 0.3)
            self.assertIsNone(tip._tip)

    def test_tooltip_is_not_focusable_and_never_blocks(self):
        app = self.make_app()
        app.update()
        app.tip_stop.show()
        self.assertTrue(app.tip_stop._tip.overrideredirect())
        app.update()                                   # returns at once: no modal loop
        app.tip_stop.hide()

    def test_tab_order_is_the_visual_order(self):
        app = self.make_app()
        self.load(app)
        app.segments.add_text("0:05", "0:10")
        app.segments.add_text("0:20", "0:24")
        app._render_table(select=0)
        app.marker.mark_start(1000, app.segments)
        app._refresh_mark_labels()
        app.update()
        expected = [app.btn_lang, app.btn_load, app.btn_play, app.btn_pause, app.btn_stop,
                    app.seek_scale, app.vol_scale, app.btn_mark_start, app.btn_mark_end, app.tree,
                    app.btn_up, app.btn_down, app.btn_edit, app.btn_delete, app.btn_clear,
                    app.btn_create]
        order, w = [], app.btn_lang
        for _ in range(60):
            order.append(w)
            w = w.tk_focusNext()
            if w is None or w == app.btn_lang:
                break
        visible = [x for x in order if x in expected]
        want = [x for x in expected if x in visible]
        self.assertEqual([str(x) for x in visible], [str(x) for x in want])
        for must in (app.btn_lang, app.btn_load, app.btn_play, app.btn_create):
            self.assertIn(must, visible)
        # top-to-bottom, left-to-right: the language button is above Load Video
        self.assertLess(app.btn_lang.winfo_rooty(), app.btn_load.winfo_rooty())

    def test_dark_title_bar_tries_attribute_20_then_19_and_ignores_errors(self):
        app = self.make_app()
        app.update()
        calls = []

        def fake(hwnd, attr, ptr, size):
            calls.append(attr)
            return 1 if attr == 20 else 0              # an older Windows rejects 20, accepts 19

        with mock.patch.object(gui.ctypes, "windll", create=True) as windll:
            windll.dwmapi.DwmSetWindowAttribute = fake
            windll.user32.GetParent.return_value = 1234
            if sys.platform == "win32":
                self.assertTrue(gui.apply_dark_titlebar(app))
                self.assertEqual(calls, [20, 19])
                calls.clear()
                windll.dwmapi.DwmSetWindowAttribute = lambda *a: calls.append(a[1]) or 0
                self.assertTrue(gui.apply_dark_titlebar(app))
                self.assertEqual(calls, [20])           # accepted at once: no second call
                windll.dwmapi.DwmSetWindowAttribute = mock.Mock(side_effect=OSError("boom"))
                self.assertFalse(gui.apply_dark_titlebar(app))   # errors are ignored

    def test_dark_title_bar_on_a_real_window_does_not_raise(self):
        app = self.make_app()
        app.update()
        self.assertIn(gui.apply_dark_titlebar(app), (True, False))

    def test_edit_dialog_has_a_reserved_error_line_and_a_fixed_size(self):
        app = self.make_app()
        self.load(app)
        app.segments.add_text("0:05", "0:10")
        app._render_table(select=0)
        app.on_edit()
        dlg = app._edit_dialog
        self.assertIsNotNone(dlg)
        dlg.update()
        self.assertEqual(dlg.resizable(), (False, False))
        before = (dlg.winfo_reqwidth(), dlg.winfo_reqheight(), dlg.winfo_width(), dlg.winfo_height())
        dlg.ent_start.delete(0, "end")
        dlg.ent_start.insert(0, "99:99:99")
        dlg.apply()                                    # invalid: the error line is filled
        dlg.update()
        self.assertTrue(dlg.lbl_error.cget("text").startswith(gui.STATUS_GLYPHS["warn"]))
        after = (dlg.winfo_reqwidth(), dlg.winfo_reqheight(), dlg.winfo_width(), dlg.winfo_height())
        self.assertEqual(before, after, "the dialog changed size when the error appeared")
        dlg.destroy()


# ------------------------------------------------------------------ (5) themed dialogs
class ThemedDialogTests(Wp3Base):
    def dialog(self, app, kind="question", yes_no=True):
        buttons = ([(t("btn.yes"), True), (t("btn.no"), False)] if yes_no
                   else [(t("btn.ok"), True)])
        return gui.ThemedDialog(app, "Title", "Message text", buttons, kind=kind,
                                cancel_value=False if yes_no else True)

    def labels(self, dlg):
        return [b.cget("text") for b, _ in dlg.buttons]

    def test_builds_with_english_and_russian_labels(self):
        for lang, yes_no, ok in (("en", ["Yes", "No"], ["OK"]), ("ru", ["Да", "Нет"], ["ОК"])):
            set_language(lang)
            app = self.make_app(lang)
            d1 = self.dialog(app)
            self.assertEqual(self.labels(d1), yes_no)
            self.assertEqual(d1.lbl_message.cget("text"), "Message text")
            self.assertEqual(d1.title(), "Title")
            d1.destroy()
            d2 = self.dialog(app, "error", yes_no=False)
            self.assertEqual(self.labels(d2), ok)
            d2.destroy()
        set_language("en")

    def test_specific_labels_for_create_and_cancel(self):
        app = self.make_app()
        self.assertEqual((t("btn.create_video"), t("btn.cancel")), ("Create Video", "Cancel"))
        set_language("ru")
        self.assertEqual((t("btn.create_video"), t("btn.cancel")), ("Создать видео", "Отмена"))
        set_language("en")
        self.assertTrue(app)

    def test_click_enter_and_escape_answer(self):
        app = self.make_app()
        app.update()
        # click "No"
        d = self.dialog(app)
        d.after(60, lambda: d.buttons[1][0].invoke())
        self.assertIs(d.show(), False)
        # Enter on the first (focused) button = Yes
        d = self.dialog(app)
        self.assertTrue(d.bind("<Return>"))
        d.after(60, d._on_return)
        self.assertIs(d.show(), True)
        # Enter on the focused "No" = No
        d = self.dialog(app)
        d.after(60, lambda: (d.buttons[1][0].focus_force(), d.update(), d._on_return()))
        self.assertIs(d.show(), False)
        # Esc = cancel value
        d = self.dialog(app)
        self.assertTrue(d.bind("<Escape>"))
        d.after(60, lambda: d.event_generate("<Escape>"))
        d.after(200, lambda: d._finish(d.cancel_value))       # in case the key event is not routed
        self.assertIs(d.show(), False)
        # the close box = cancel value
        d = self.dialog(app)
        d.after(60, lambda: d.protocol("WM_DELETE_WINDOW") and d.tk.call(d.protocol("WM_DELETE_WINDOW")))
        d.after(250, lambda: d._finish(d.cancel_value))
        self.assertIs(d.show(), False)
        # an OK dialog
        d = self.dialog(app, "info", yes_no=False)
        d.after(60, lambda: d.buttons[0][0].invoke())
        self.assertIs(d.show(), True)

    def test_real_seam_methods_use_the_dialog(self):
        for p in self._patches[:2]:
            p.stop()                                       # use the real _ask_yes_no / _show_message
        try:
            app = self.make_app()
            app.update()
            seen = []

            def click(index):
                for w in app.winfo_children():
                    if isinstance(w, gui.ThemedDialog):
                        seen.append([b.cget("text") for b, _ in w.buttons])
                        w.buttons[index][0].invoke()
                        return
                app.after(40, lambda: click(index))
            app.after(60, lambda: click(0))
            self.assertTrue(app._ask_yes_no("T", "M"))
            app.after(60, lambda: click(1))
            self.assertFalse(app._ask_yes_no("T", "M", yes_key="btn.create_video",
                                             no_key="btn.cancel"))
            app.after(60, lambda: click(0))
            app._show_message("error", "T", "M")
            self.assertEqual(seen, [["Yes", "No"], ["Create Video", "Cancel"], ["OK"]])
        finally:
            for p in self._patches[:2]:
                p.start()

    def test_closing_the_main_window_destroys_the_dialog(self):
        app = self.make_app()
        app.update()
        d = self.dialog(app)
        self.assertTrue(d.winfo_exists())
        app._shutdown()
        with self.assertRaises(tk.TclError):
            d.winfo_exists()

    def test_main_window_closing_while_the_dialog_waits_returns_the_cancel_value(self):
        app = self.make_app()
        app.update()
        d = self.dialog(app)
        d.after(80, app._shutdown)
        self.assertIs(d.show(), False)

    def test_dialog_is_centered_over_the_main_window_and_modal(self):
        app = self.make_app(workarea=(1920, 1080))
        app.geometry("900x760+100+50")
        app.update()
        d = self.dialog(app)
        d.update_idletasks()
        x = int(d.geometry().split("+")[1])            # where it was put (it is not shown yet)
        self.assertAlmostEqual(x + d.winfo_reqwidth() // 2,
                               app.winfo_rootx() + app.winfo_width() // 2, delta=40)
        self.assertEqual(str(d.transient()), str(app))       # stays on top of the main window
        d.after(120, lambda: d.buttons[0][0].invoke())
        d.show()

    def test_every_dialog_goes_through_the_two_seam_methods(self):
        source = (PROJECT / "gui.py").read_text(encoding="utf-8")
        self.assertNotIn("messagebox", source)
        self.assertEqual(source.count("ThemedDialog("), 3)    # class def + the two seam methods


if __name__ == "__main__":
    unittest.main()
