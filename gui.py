"""Main window of the Video Segment Editor (Task 5: shell, theme, Load Video; Task 5b: RU/EN;
Task 6: playback, marking, segment table).

Widget attributes that Tasks 6 and 7 build on (all created in App._build_*):
  Header / file:   lbl_logo, lbl_title, btn_lang (RU/EN switch), lbl_info, btn_load
  Video area:      video_frame (VLC draws into its window handle),
                   lbl_video_msg (placeholder text), lbl_vlc_link (VLC download link)
  Transport:       btn_play, btn_pause, btn_stop, seek_scale (0..SEEK_STEPS),
                   lbl_time ("current / total"), vol_scale (0..100)
  Marking:         btn_mark_start, btn_mark_end, lbl_mark_status, lbl_volume
  Segment table:   tree (columns n/start/end/duration), lbl_counter ("n / 10"),
                   btn_up, btn_down, btn_edit, btn_delete, btn_clear, lbl_total
  Bottom area:     btn_create, progress, btn_cancel_job (visible only while a video is being
                   created), lbl_operation, lbl_status, txt_output
Manual entry:      manual_frame (shown instead of the Mark buttons when there is no player),
                   ent_start, ent_end, btn_add_segment
Other state:       self.info (VideoInfo or None), self.player (VlcPlayer or None),
                   self.segments (SegmentList), self.marker (Marker),
                   self.events (queue.Queue), self.video_controls (widgets that are
                   disabled until a video is loaded). Enabled/disabled state is computed in
                   _update_controls() from: set_controls_enabled(), video loaded, player,
                   table selection, segment count and the Create Video worker (_creating /
                   _create_pending: everything except the language button is locked).
                   Create Video flow: on_create -> _confirm_and_start -> _start_job -> worker
                   thread posts create_progress / create_done / create_error / create_cancelled.
Worker results reach the GUI only through post(kind, payload) -> self.events;
_poll() runs every 100 ms, calls player.tick() and dispatches queued events to
handlers added with register_handler(kind, fn).

Texts (Task 5b): never write English text into a widget. Use
  self.set_text(widget, "key", name=value)   # remembers key+params, shows t(key, ...)
  self.set_status("key", "ok", name=value)   # same for lbl_status; level = info / ok / warn / error
                                             # (colour AND a leading glyph); flash_status() = warn
                                             # that clears itself (next user action or 8 s)
  self.show_error("dlg.cannot_open", "err.not_a_video") # translated when the dialog opens
so apply_language() can redraw every text when the language button is pressed.
Dialogs: App._show_message / App._ask_yes_no are the ONLY places that open one (ThemedDialog, dark,
button texts from i18n). Sizes: every pixel value goes through px() / App.px(): the design is
900x760 at 100 % and everything is multiplied by the UI scale (Windows display scaling).
Add the new keys to both dictionaries in i18n.py. Data (times, counters) is not text:
format it in code, or pass it as a parameter (label.total takes time=...).
"""
from __future__ import annotations

import ctypes
import functools
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter import font as tkfont
from typing import Callable

from create_flow import conversion_notes, default_work_root, progress_view
from i18n import default_settings_path, get_language, load_saved_language, \
    save_language, set_language, t
from segment_manager import (Marker, SegmentError, SegmentList, TimeError,
                             format_ms)
from video_player import (VLC_DOWNLOAD_URL, PlayerUnavailable, VlcPlayer,
                          vlc_available)
from video_processor import (Cancelled, ProcessingError, VideoInfo, VideoJob, find_tool,
                             probe, unique_output_path)

ASSETS = Path(__file__).resolve().parent / "assets"
POLL_MS = 100
SEEK_STEPS = 1000
MAX_SEGMENTS = 10
CLOSE_WAIT_S = 5.0   # how long closing waits for the worker to stop
PLAYER_FAIL_LIMIT = 3

# Dark palette (every text colour below was checked for contrast, see the WP3 report)
BG = "#1a1a1a"
PANEL = "#242424"
PANEL_ALT = "#2c2c2c"
VIDEO_BG = "#12141c"
FG = "#f0f0f0"
FG_DIM = "#a8a8a8"
FG_OFF = "#808080"          # disabled text
ACCENT = "#3fb68b"          # progress fill, success text, "start is marked" border
BORDER = "#3a3a3a"
LINK = "#6cb6ff"            # links and the keyboard focus ring
OK = ACCENT
WARN = "#ffb454"
ERR = "#ff9a8a"
CREATE_BG, CREATE_HOT, CREATE_DOWN = "#1f4a3a", "#28604b", "#17382c"
CREATE_OFF_BG, CREATE_OFF_FG = "#1c2a25", "#7f9a8f"
MARK_SET_BG, MARK_SET_HOT, MARK_SET_DOWN = "#1f3a2f", "#27493b", "#17382c"
SELECTED_BG = "#2f5d4c"
THUMB, THUMB_HOT, THUMB_OFF, TROUGH = "#c8c8c8", "#ffffff", "#4a4a4a", "#3a3a3a"
SCROLL, SCROLL_HOT = "#4a4a4a", "#6a6a6a"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_BIG = ("Segoe UI", 13, "bold")
FONT_ICON = ("Segoe UI Symbol", 12)
FONT_GLYPH = ("Segoe UI Symbol", 10)
FONT_MONO = ("Consolas", 10)

# Status levels: colour AND a leading glyph (colour is never the only cue).
STATUS_GLYPHS = {"info": "●", "ok": "✔", "warn": "⚠", "error": "✖"}
STATUS_LEVELS = tuple(STATUS_GLYPHS)
OUTPUT_MAX_LINES = 4
STATUS_FLASH_MS = 8000       # a validation message disappears after this long

# Layout design size at 100 % scaling (pixels); everything is multiplied by the UI scale.
MIN_W, MIN_H = 900, 760
DEFAULT_W, DEFAULT_H = 1100, 840
HEADING_PAD_X = 2       # table heading text offset (tuned to line up with the cells)
VIDEO_MIN_H, TABLE_MIN_H = 170, 190
VIDEO_FLOOR_H, TABLE_FLOOR_H = 96, 120   # smallest a row may be squeezed to on a small screen
FRAME_W, FRAME_H = 16, 48    # allowance for the window border and title bar (at 100 %)


def px(n: float, scale: float) -> int:
    """`n` design pixels at 100 % -> real pixels at `scale`."""
    return int(round(n * scale))


def work_area(root) -> tuple[int, int]:
    """Size of the usable desktop (without the taskbar) in real pixels."""
    if sys.platform == "win32":
        try:
            import ctypes.wintypes as wt
            rect = wt.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0):
                w, h = rect.right - rect.left, rect.bottom - rect.top
                if w > 0 and h > 0:
                    return w, h
        except Exception:
            pass
    return root.winfo_screenwidth(), root.winfo_screenheight()


def apply_dark_titlebar(window) -> bool:
    """Dark title bar (Windows 10 20H1+ / 11). Attribute 20, then 19 for older builds.
    Call it after the window exists. Errors are ignored; returns True when Windows accepted it."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes.wintypes as wt
        user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
        user32.GetParent.argtypes = [wt.HWND]
        user32.GetParent.restype = wt.HWND
        dwm.DwmSetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
        window.update_idletasks()
        hwnd = user32.GetParent(window.winfo_id())
        if not hwnd:
            return False
        value = ctypes.c_int(1)
        for attr in (20, 19):
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value),
                                         ctypes.sizeof(value)) == 0:
                return True
    except Exception:
        pass
    return False


def _player_guard(fn):
    """Wrap a handler that talks to the player: an exception never reaches Tk's default
    handler. Three consecutive failures drop the player (see App._player_failed)."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            result = fn(self, *args, **kwargs)
        except Exception as exc:
            self._player_failed(exc)
            return None
        self._player_fails = 0
        return result
    return wrapper


class Tooltip:
    """Small hover hint for a widget (shown after DELAY_MS, hidden on leave / click / destroy).

    The text is translated when the hint opens, so a language switch needs no refresh.
    It never takes the focus and never blocks: it is a plain borderless window."""
    DELAY_MS = 500

    def __init__(self, widget, key: str):
        self.widget, self.key = widget, key
        self._after = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def text(self) -> str:
        return t(self.key)

    def _schedule(self, _event=None) -> None:
        self.hide()
        try:
            self._after = self.widget.after(self.DELAY_MS, self.show)
        except tk.TclError:
            self._after = None

    def show(self) -> None:
        self._after = None
        if self._tip is not None:
            return
        try:
            scale = self.widget.winfo_toplevel().ui_scale
        except AttributeError:
            scale = 1.0
        try:
            tip = tk.Toplevel(self.widget)
            tip.withdraw()
            tip.overrideredirect(True)
            tip.configure(bg=BORDER)
            tk.Label(tip, text=self.text(), bg=PANEL_ALT, fg=FG, font=FONT,
                     padx=px(8, scale), pady=px(4, scale)).pack(padx=1, pady=1)
            tip.update_idletasks()
            x = self.widget.winfo_rootx()
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + px(4, scale)
            tip.geometry(f"+{x}+{y}")
            tip.deiconify()
            tip.attributes("-topmost", True)
            self._tip = tip
        except tk.TclError:
            self._tip = None

    def hide(self, _event=None) -> None:
        after, self._after = self._after, None
        if after is not None:
            try:
                self.widget.after_cancel(after)
            except tk.TclError:
                pass
        tip, self._tip = self._tip, None
        if tip is not None:
            try:
                tip.destroy()
            except tk.TclError:
                pass


class ThemedDialog(tk.Toplevel):
    """The one dark, modal message / question window (replaces the native message boxes, whose
    button texts follow the Windows language instead of the program language).

    `buttons` is a list of (text, value). Enter presses the focused button (the first one is
    focused when the dialog opens), Esc or the close box returns `cancel_value`. `show()` blocks
    (a nested event loop, so the poll loop keeps running) and returns the chosen value. Closing
    the main window destroys the dialog (it is a child of it)."""
    KIND_GLYPH = {"info": ("ℹ", LINK), "error": ("✖", ERR),
                  "question": ("?", LINK)}

    def __init__(self, app, title: str, message: str, buttons, kind: str = "info",
                 cancel_value=None):
        super().__init__(app)
        self.withdraw()
        self.app = app
        s = getattr(app, "ui_scale", 1.0)
        self.result = cancel_value
        self.cancel_value = cancel_value
        self._done = False
        self._grab_after = None
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        try:
            self.iconbitmap(str(ASSETS / "logo.ico"))
        except tk.TclError:
            pass
        body = ttk.Frame(self, padding=px(16, s))
        body.grid(row=0, column=0, sticky="nsew")
        glyph, colour = self.KIND_GLYPH.get(kind, self.KIND_GLYPH["info"])
        self.lbl_glyph = tk.Label(body, text=glyph, bg=BG, fg=colour, font=("Segoe UI Symbol", 18))
        self.lbl_glyph.grid(row=0, column=0, sticky="n", padx=(0, px(12, s)))
        self.lbl_message = ttk.Label(body, text=message, justify="left", wraplength=px(440, s))
        self.lbl_message.grid(row=0, column=1, sticky="nw")
        row = ttk.Frame(body)
        row.grid(row=1, column=0, columnspan=2, sticky="e", pady=(px(16, s), 0))
        self.buttons: list[tuple[ttk.Button, object]] = []
        for i, (text, value) in enumerate(buttons):
            btn = ttk.Button(row, text=text, width=11,
                             command=lambda v=value: self._finish(v))
            btn.grid(row=0, column=i, padx=(0 if i == 0 else px(8, s), 0))
            self.buttons.append((btn, value))
        self.bind("<Return>", self._on_return)
        self.bind("<Escape>", lambda _e: self._finish(self.cancel_value))
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(self.cancel_value))
        self.transient(app)
        self.update_idletasks()
        self._center()
        apply_dark_titlebar(self)
        if self.buttons:
            self.buttons[0][0].focus_set()

    def _center(self) -> None:
        app = self.app
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_reqwidth()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _on_return(self, _event=None) -> None:
        focus = self.focus_get()
        for btn, value in self.buttons:
            if btn is focus:
                self._finish(value)
                return
        if self.buttons:
            self._finish(self.buttons[0][1])

    def _finish(self, value) -> None:
        if self._done:
            return
        self._done = True
        self.result = value
        if self._grab_after is not None:
            try:
                self.after_cancel(self._grab_after)
            except tk.TclError:
                pass
            self._grab_after = None
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass  # not visible yet; the dialog still works without the grab

    def show(self):
        """Open the dialog, wait for the answer and return it."""
        try:
            self.deiconify()
            self.update_idletasks()
            self._grab()
            self._grab_after = self.after(50, self._grab)
            self.focus_force()
            self.wait_window(self)
        except tk.TclError:
            pass          # the main window was closed while the dialog was open
        return self.result


class App(tk.Tk):
    def __init__(self, version: str = "1.0", settings_path: Path | None = None,
                 scaling: float | None = None, workarea: tuple[int, int] | None = None):
        super().__init__()
        # `scaling` (Tk points-to-pixel factor, 1.3333 = 100 %) and `workarea` exist so tests and
        # the emulation scripts can pretend to be a 125 / 150 / 200 % display. Real runs pass none.
        if scaling is not None:
            self.tk.call("tk", "scaling", float(scaling))
        self.ui_scale = max(1.0, round(self.winfo_fpixels("1i") / 96.0, 3))
        self._workarea = workarea
        self.version = version
        self.settings_path = Path(settings_path) if settings_path else default_settings_path()
        set_language(load_saved_language(self.settings_path))
        self._texts: dict = {}      # widget -> (key, params) for apply_language()
        self._headings: dict = {}   # tree column -> key
        self.title(t("app.title"))
        self.configure(bg=BG)

        self.info: VideoInfo | None = None
        self.player: VlcPlayer | None = None
        self.segments = SegmentList(0, MAX_SEGMENTS)
        self.marker = Marker()
        self._controls_on = False
        self._preview_failed = False   # VLC is installed but this file could not be previewed
        self._seeking = False          # the user is dragging the seek slider
        self._loading = False          # a video is being probed: table/marks are locked
        self._edit_dialog = None
        self._seek_updating = False    # the tick is moving the slider (not the user)
        self._last_seek_t = 0.0
        self.events: queue.Queue = queue.Queue()
        self.video_controls: list[tk.Widget] = []
        self._handlers: dict[str, Callable] = {}
        self._load_token = 0
        self._closing = False
        # Create Video flow (Task 7)
        self.work_root = default_work_root()
        self._create_pending = False   # confirm dialog about to open / open
        self._creating = False         # the worker thread is running
        self._job: VideoJob | None = None
        self._worker: threading.Thread | None = None
        self._create_token = 0
        self._cancel_requested = threading.Event()
        self._output = None            # (key, params) shown in txt_output
        self._kept_folder: str | None = None   # folder named in the output box (Open folder)
        self._close_asking = False
        self._cancel_asking = False    # the "stop creating?" question is open
        self._close_deadline = 0.0
        self._close_waiting = False    # close confirmed: waiting (without blocking) for the worker
        self._player_fails = 0         # consecutive player failures (3 = drop the player)
        self._deferred_dialogs: list = []   # results that arrived while the close question was open
        self._status_level = "info"
        self._status_timer = None      # after() id of the "clear this warning" timer
        self._status_transient = False # the status is a validation message (cleared on next action)
        self._out_width = 0
        self._min_w = self._min_h = 0
        self._over_checks = 0
        self._max_h = 0

        self._set_icon()
        self.after(300, self._set_icon)
        self._build_style()
        self._build_header()
        self._build_video_area()
        self._build_transport()
        self._build_marking()
        self._build_table()
        self._build_bottom()

        self.register_handler("probe_ok", self._on_probe_ok)
        self.register_handler("probe_error", self._on_probe_error)
        self.register_handler("tools_missing", self._on_tools_missing)
        self.register_handler("create_progress", self._on_create_progress)
        self.register_handler("create_done", self._on_create_done)
        self.register_handler("create_error", self._on_create_error)
        self.register_handler("create_cancelled", self._on_create_cancelled)

        self._apply_mode()
        self._render_table()
        self.set_controls_enabled(False)
        self._show_video_placeholder()
        self._fit_window()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Map>", self._on_first_map)
        self.after(POLL_MS, self._poll)

    # ------------------------------------------------------------ icon / theme / size
    def _set_icon(self) -> None:
        try:
            self.iconbitmap(str(ASSETS / "logo.ico"))
        except tk.TclError:
            pass

    def _on_first_map(self, event=None) -> None:
        if event is not None and event.widget is not self:
            return
        self.unbind("<Map>")
        apply_dark_titlebar(self)
        self.after(300, lambda: None if self._closing else apply_dark_titlebar(self))

    def px(self, n: float) -> int:
        """Design pixels (at 100 %) -> real pixels at this window's UI scale."""
        return px(n, self.ui_scale)

    def _fit_window(self) -> None:
        """Minimum size, default size and position, all scaled to the display.

        minsize / geometry used to be fixed pixels: at 125 % and up the minimum was smaller than
        the layout needs. Now they are the design size times the UI scale, limited to the usable
        desktop, and never smaller than what the layout asks for. On a screen too small for that,
        the growing rows (video, table) give up height instead of the buttons and texts."""
        wa_w, wa_h = self._workarea or work_area(self)
        frame_w, frame_h = self.px(FRAME_W), self.px(FRAME_H)
        max_w, max_h = max(400, wa_w - frame_w), max(300, wa_h - frame_h)
        self._max_h = max_h
        self.update_idletasks()
        min_w = min(max(self.px(MIN_W), self.winfo_reqwidth()), max_w)
        min_h = min(self.px(MIN_H), max_h)
        self._squeeze(self.winfo_reqheight() - min_h)
        min_h = min(max(min_h, self.winfo_reqheight()), max_h)
        self._min_w, self._min_h = min_w, min_h
        self.minsize(min_w, min_h)
        w = max(min_w, min(self.px(DEFAULT_W), max_w))
        h = max(min_h, min(self.px(DEFAULT_H), max_h))
        x = max(0, (wa_w - w - frame_w) // 2)
        y = max(0, (wa_h - h - frame_h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _squeeze(self, over: int) -> int:
        """A screen too small for the layout: take `over` pixels from the video row (down to its
        floor), then show 2 table rows instead of 3. Returns what could not be taken."""
        if over <= 0:
            return 0
        cur = int(self.grid_rowconfigure(2)["minsize"])
        take = min(over, max(0, cur - self.px(VIDEO_FLOOR_H)))
        if take:
            self.rowconfigure(2, minsize=cur - take)
            over -= take
        row_h = self.px(28)
        if over > 0 and int(self.tree.cget("height")) > 2:
            self.tree.configure(height=2)
            tcur = int(self.grid_rowconfigure(5)["minsize"])
            self.rowconfigure(5, minsize=max(self.px(TABLE_FLOOR_H), tcur - row_h))
            over -= row_h
        self.update_idletasks()
        return max(0, over)

    def _ensure_min_fits(self) -> None:
        """The window never asks for more height than its minimum: if a state (a long path, a
        longer translation) needs more room, the minimum grows (up to the screen) instead of
        clipping. Only the height: the requested width follows the current width (the table
        columns stretch with the window), so it says nothing about what is needed. A need must
        last for two checks in a row (200 ms), so a half-finished re-layout does not count."""
        if self._min_h <= 0:
            return
        req_h = self.winfo_reqheight()
        if req_h > self._max_h:       # more than the screen can hold: the video row gives way
            self._squeeze(req_h - self._max_h)
            req_h = self.winfo_reqheight()
        if req_h <= self._min_h:
            self._over_checks = 0
            return
        self._over_checks += 1
        if self._over_checks >= 2:
            self._min_h = min(req_h, self._max_h)
            self.minsize(self._min_w, self._min_h)
            self._over_checks = 0

    def _build_style(self) -> None:
        sc = self.ui_scale

        def pad(*v):
            return tuple(px(x, sc) for x in v)

        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    troughcolor=PANEL_ALT, font=FONT, focuscolor=LINK)
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=FG)
        focus = dict(bordercolor=[("focus", LINK)], lightcolor=[("focus", LINK)],
                     darkcolor=[("focus", LINK)])
        s.configure("TEntry", fieldbackground=PANEL, foreground=FG, insertcolor=FG,
                    padding=pad(4, 3))
        s.map("TEntry", foreground=[("disabled", FG_OFF)],
              fieldbackground=[("disabled", PANEL)], **focus)
        s.configure("Error.TLabel", foreground=ERR)
        s.configure("Warn.TLabel", foreground=WARN)
        s.configure("Dim.TLabel", foreground=FG_DIM)
        s.configure("Title.TLabel", font=FONT_TITLE)
        s.configure("Heading.TLabel", font=FONT_BOLD)
        # status line: one style per level (colour) + a glyph label beside it (shape)
        s.configure("Status.TLabel", font=FONT_BOLD)
        s.configure("Glyph.Status.TLabel", font=FONT_GLYPH)
        for level, colour in (("info", FG), ("ok", OK), ("warn", WARN), ("error", ERR)):
            s.configure(f"{level}.Status.TLabel", foreground=colour)
            s.configure(f"{level}.Glyph.Status.TLabel", foreground=colour)
        # buttons: height about 32 px at 100 %
        s.configure("TButton", background=PANEL_ALT, foreground=FG, padding=pad(12, 6),
                    borderwidth=1, relief="flat", anchor="center")
        button_map = dict(
            background=[("disabled", PANEL), ("pressed", "#1f1f1f"), ("active", "#383838")],
            foreground=[("disabled", FG_OFF)], **focus)
        s.map("TButton", **button_map)
        s.configure("Icon.TButton", font=FONT_ICON, padding=pad(8, 6))
        s.map("Icon.TButton", **button_map)
        s.configure("Mark.TButton", font=FONT, padding=pad(10, 6))
        s.map("Mark.TButton", **button_map)
        s.configure("MarkSet.Mark.TButton", background=MARK_SET_BG, bordercolor=ACCENT,
                    lightcolor=ACCENT, darkcolor=ACCENT)
        s.map("MarkSet.Mark.TButton",
              background=[("disabled", PANEL), ("pressed", MARK_SET_DOWN),
                          ("active", MARK_SET_HOT)],
              foreground=[("disabled", FG_OFF)],
              bordercolor=[("focus", LINK), ("disabled", BORDER)],
              lightcolor=[("focus", LINK), ("disabled", BORDER)],
              darkcolor=[("focus", LINK), ("disabled", BORDER)])
        s.configure("Stop.TButton", padding=pad(10, 1))   # beside the progress bar: low, so
        # the window needs no more height while a video is being created
        s.map("Stop.TButton", **button_map)
        s.configure("Create.TButton", font=FONT_BIG, padding=pad(10, 8), background=CREATE_BG)
        s.map("Create.TButton",
              background=[("disabled", CREATE_OFF_BG), ("pressed", CREATE_DOWN),
                          ("active", CREATE_HOT)],
              foreground=[("disabled", CREATE_OFF_FG)], **focus)
        # sliders: light thumb on a darker trough, dim when disabled, blue when focused
        s.configure("Horizontal.TScale", background=THUMB, troughcolor=TROUGH,
                    bordercolor=BORDER, lightcolor=THUMB, darkcolor=THUMB)
        s.map("Horizontal.TScale",
              background=[("disabled", THUMB_OFF), ("focus", LINK), ("active", THUMB_HOT)],
              lightcolor=[("disabled", THUMB_OFF), ("focus", LINK)],
              darkcolor=[("disabled", THUMB_OFF), ("focus", LINK)],
              bordercolor=[("disabled", BORDER)], troughcolor=[("disabled", PANEL_ALT)])
        s.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=PANEL_ALT,
                    bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG,
                    rowheight=px(28, sc), borderwidth=0)
        s.configure("Treeview.Heading", background=BG, foreground=FG, font=FONT_BOLD,
                    relief="flat", padding=pad(HEADING_PAD_X, 6))
        s.map("Treeview.Heading", background=[("active", BG)])
        s.map("Treeview", background=[("selected", SELECTED_BG)],
              foreground=[("selected", FG)], bordercolor=[("focus", LINK)])
        s.configure("Vertical.TScrollbar", background=SCROLL, troughcolor=PANEL,
                    bordercolor=PANEL, lightcolor=SCROLL, darkcolor=SCROLL,
                    arrowcolor=FG_DIM, gripcount=0)
        s.map("Vertical.TScrollbar",
              background=[("active", SCROLL_HOT), ("disabled", PANEL)],
              lightcolor=[("active", SCROLL_HOT), ("disabled", PANEL)],
              darkcolor=[("active", SCROLL_HOT), ("disabled", PANEL)])

    # ------------------------------------------------------------------ layout
    def _build_header(self) -> None:
        sc = self.ui_scale
        self.columnconfigure(0, weight=1)
        # rows: 0 header, 1 info, 2 video (grows), 3 transport, 4 marks, 5 table, 6 bottom
        self.rowconfigure(2, weight=2, minsize=self.px(VIDEO_MIN_H))
        self.rowconfigure(5, weight=2, minsize=self.px(TABLE_MIN_H))

        header = ttk.Frame(self, padding=(px(16, sc), px(8, sc), px(16, sc), 0))
        header.grid(row=0, column=0, sticky="ew")
        self.lbl_logo = ttk.Label(header)
        self._load_logo()
        self.lbl_logo.pack(side="left", padx=(0, px(12, sc)))
        self.lbl_title = ttk.Label(header, style="Title.TLabel")
        self.set_text(self.lbl_title, "app.name")
        self.lbl_title.pack(side="left")
        self.btn_lang = ttk.Button(header, width=4, command=self.toggle_language)
        self.set_text(self.btn_lang, "lang.button")  # shows the OTHER language: RU / EN
        self.btn_lang.pack(side="right")

        info_row = ttk.Frame(self, padding=(px(16, sc), px(4, sc), px(16, sc), px(4, sc)))
        info_row.grid(row=1, column=0, sticky="ew")
        info_row.columnconfigure(0, weight=1)
        self.lbl_info = ttk.Label(info_row, style="Dim.TLabel")
        self.set_text(self.lbl_info, "info.none")
        self.lbl_info.grid(row=0, column=0, sticky="w")
        self.btn_load = ttk.Button(info_row, command=self.choose_video)
        self.set_text(self.btn_load, "btn.load_video")
        self.btn_load.grid(row=0, column=1, sticky="e", padx=(px(12, sc), 0))

    def _load_logo(self) -> None:
        """assets/logo_header.png is rendered at the exact header size; the old logo.png
        (shrunk by whole numbers) is the fallback. No PIL: Tk reads the PNG itself."""
        for name, target in (("logo_header.png", None), ("logo.png", 33)):
            try:
                img = tk.PhotoImage(master=self, file=str(ASSETS / name))
            except tk.TclError:
                continue
            if target and img.height() > target + 3:
                img = img.subsample(max(1, round(img.height() / target)))
            self._logo_img = img  # keep a reference
            self.lbl_logo.configure(image=img)
            return
        self.lbl_logo.configure(text="MY")

    def _build_video_area(self) -> None:
        sc = self.ui_scale
        wrap = ttk.Frame(self, padding=(px(16, sc), 0, px(16, sc), 0))
        wrap.grid(row=2, column=0, sticky="nsew")
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        self.video_frame = tk.Frame(wrap, bg=VIDEO_BG, highlightthickness=0)
        self.video_frame.grid(row=0, column=0, sticky="nsew")
        # Placeholder text sits on top of the video frame; hidden once VLC shows video.
        self.lbl_video_msg = tk.Label(self.video_frame, bg=VIDEO_BG, fg=FG_DIM, font=FONT,
                                      justify="center", wraplength=px(400, sc))
        self.video_frame.bind("<Configure>", lambda e: self.lbl_video_msg.configure(
            wraplength=max(px(200, sc), e.width - px(48, sc))))
        self.lbl_vlc_link = tk.Label(self.video_frame, text=VLC_DOWNLOAD_URL, bg=VIDEO_BG,
                                     fg=LINK, font=("Segoe UI", 10, "underline"),
                                     cursor="hand2")
        self.lbl_vlc_link.bind("<Button-1>", lambda _e: webbrowser.open(VLC_DOWNLOAD_URL))

    def _build_transport(self) -> None:
        sc = self.ui_scale
        row = ttk.Frame(self, padding=(px(16, sc), px(8, sc), px(16, sc), 0))
        row.grid(row=3, column=0, sticky="ew")
        row.columnconfigure(3, weight=1)
        self.btn_play = ttk.Button(row, text="▶", style="Icon.TButton", width=3,
                                   command=self.on_play)
        self.btn_pause = ttk.Button(row, text="⏸", style="Icon.TButton", width=3,
                                    command=self.on_pause)
        self.btn_stop = ttk.Button(row, text="■", style="Icon.TButton", width=3,
                                   command=self.on_stop)
        self.tip_play = Tooltip(self.btn_play, "tip.play")
        self.tip_pause = Tooltip(self.btn_pause, "tip.pause")
        self.tip_stop = Tooltip(self.btn_stop, "tip.stop")
        self.btn_play.grid(row=0, column=0, padx=(0, px(4, sc)))
        self.btn_pause.grid(row=0, column=1, padx=(0, px(4, sc)))
        self.btn_stop.grid(row=0, column=2, padx=(0, px(12, sc)))
        self.seek_scale = ttk.Scale(row, from_=0, to=SEEK_STEPS, orient="horizontal",
                                    command=self._on_seek_scale)
        self.seek_scale.bind("<ButtonPress-1>", self._seek_press, add="+")
        self.seek_scale.bind("<ButtonRelease-1>", self._seek_release, add="+")
        self.seek_scale.grid(row=0, column=3, sticky="ew")
        self.lbl_time = ttk.Label(row, text="00:00:00.000 / 00:00:00.000", font=FONT_MONO)
        self.lbl_time.grid(row=0, column=4, padx=(px(12, sc), px(12, sc)))
        self.lbl_volume = ttk.Label(row, style="Dim.TLabel")
        self.set_text(self.lbl_volume, "label.volume")
        self.lbl_volume.grid(row=0, column=5, padx=(0, px(8, sc)))
        self.vol_scale = ttk.Scale(row, from_=0, to=100, orient="horizontal",
                                   length=px(90, sc), command=self._on_volume)
        self.vol_scale.set(100)
        self.vol_scale.grid(row=0, column=6)

    def _build_marking(self) -> None:
        sc = self.ui_scale
        row = ttk.Frame(self, padding=(px(16, sc), px(8, sc), px(16, sc), 0))
        row.grid(row=4, column=0, sticky="ew")
        row.columnconfigure((0, 1), weight=1, uniform="mark")
        self.btn_mark_start = ttk.Button(row, style="Mark.TButton", command=self.on_mark_start)
        self.btn_mark_end = ttk.Button(row, style="Mark.TButton", command=self.on_mark_end)
        self.set_text(self.btn_mark_start, "btn.mark_start")
        self.set_text(self.btn_mark_end, "btn.mark_end")
        self.btn_mark_start.grid(row=0, column=0, sticky="ew", padx=(0, px(8, sc)))
        self.btn_mark_end.grid(row=0, column=1, sticky="ew", padx=(px(8, sc), 0))
        # capped, so that a long hint never makes the window ask for more than its minimum width
        row.bind("<Configure>", lambda e: self.lbl_mark_status.configure(
            wraplength=max(px(200, sc), min(e.width - px(32, sc), px(836, sc)))))
        self.lbl_mark_status = ttk.Label(row, text="", style="Dim.TLabel",  # use set_text
                                          wraplength=px(800, sc), justify="left")
        self.lbl_mark_status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(px(4, sc), 0))
        # No-VLC route: two time boxes + "Add segment" replace the Mark buttons.
        self.manual_frame = ttk.Frame(row)
        self.manual_frame.grid(row=0, column=0, columnspan=2, sticky="w")
        self.lbl_manual_start = ttk.Label(self.manual_frame)
        self.set_text(self.lbl_manual_start, "col.start")
        self.ent_start = ttk.Entry(self.manual_frame, width=14, font=FONT_MONO)
        self.lbl_manual_end = ttk.Label(self.manual_frame)
        self.set_text(self.lbl_manual_end, "col.end")
        self.ent_end = ttk.Entry(self.manual_frame, width=14, font=FONT_MONO)
        self.btn_add_segment = ttk.Button(self.manual_frame, command=self.on_add_manual)
        self.set_text(self.btn_add_segment, "btn.add_segment")
        self.lbl_manual_start.grid(row=0, column=0, padx=(0, px(8, sc)))
        self.ent_start.grid(row=0, column=1, padx=(0, px(16, sc)))
        self.lbl_manual_end.grid(row=0, column=2, padx=(0, px(8, sc)))
        self.ent_end.grid(row=0, column=3, padx=(0, px(16, sc)))
        self.btn_add_segment.grid(row=0, column=4)
        for ent in (self.ent_start, self.ent_end):
            ent.bind("<Return>", lambda _e: self.on_add_manual())
        self.manual_frame.grid_remove()

    def _build_table(self) -> None:
        sc = self.ui_scale
        box = ttk.Frame(self, padding=(px(16, sc), px(8, sc), px(16, sc), 0))
        box.grid(row=5, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(1, weight=1)
        head = ttk.Frame(box)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, px(8, sc)))
        head.columnconfigure(0, weight=1)
        self.lbl_segments = ttk.Label(head, style="Heading.TLabel")
        self.set_text(self.lbl_segments, "label.selected_segments")
        self.lbl_segments.grid(row=0, column=0, sticky="w")
        self.lbl_counter = ttk.Label(head, text=f"0 / {MAX_SEGMENTS}", style="Dim.TLabel")
        self.lbl_counter.grid(row=0, column=1, sticky="e")

        self.tree = ttk.Treeview(box, columns=("n", "start", "end", "duration"),
                                 show="headings", selectmode="browse", height=3)
        for col, key, width, anchor in (("n", "col.n", 50, "w"), ("start", "col.start", 160, "w"),
                                        ("end", "col.end", 160, "w"),
                                        ("duration", "col.duration", 160, "w")):
            self._headings[col] = key
            self.tree.heading(col, text=t(key), anchor="w")
            self.tree.column(col, width=px(width, sc), minwidth=px(50, sc), anchor=anchor,
                             stretch=(col != "n"))
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_controls())
        self.tree.bind("<Delete>", lambda _e: self.on_delete())
        self.tree.bind("<Return>", lambda _e: self.after(0, self.on_edit))
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        # hint over the empty table (hidden as soon as there is a row)
        self.lbl_empty = tk.Label(self.tree, bg=PANEL, fg=FG_DIM, font=FONT)
        self.set_text(self.lbl_empty, "table.empty")
        self.sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.sb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=self._on_tree_scroll)

        btns = ttk.Frame(box, padding=(0, px(8, sc), 0, 0))
        btns.grid(row=2, column=0, columnspan=2, sticky="ew")
        btns.columnconfigure(0, weight=1)
        self.lbl_total = ttk.Label(btns, style="Dim.TLabel")
        self.set_text(self.lbl_total, "label.total", time=format_ms(0))
        self.lbl_total.grid(row=0, column=0, sticky="w")
        self.btn_up = ttk.Button(btns, command=lambda: self.on_move(-1))
        self.btn_down = ttk.Button(btns, command=lambda: self.on_move(1))
        self.btn_edit = ttk.Button(btns, command=self.on_edit)
        self.btn_delete = ttk.Button(btns, command=self.on_delete)
        self.btn_clear = ttk.Button(btns, command=self.on_clear)
        for b, key in ((self.btn_up, "btn.up"), (self.btn_down, "btn.down"),
                       (self.btn_edit, "btn.edit"), (self.btn_delete, "btn.delete"),
                       (self.btn_clear, "btn.clear")):
            self.set_text(b, key)
        for i, b in enumerate((self.btn_up, self.btn_down, self.btn_edit,
                               self.btn_delete, self.btn_clear), start=1):
            b.grid(row=0, column=i, padx=(px(8, sc), 0))

    def _on_tree_scroll(self, lo, hi) -> None:
        """Scrollbar that hides itself while every row is visible."""
        self.sb.set(lo, hi)
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.sb.grid_remove()
        else:
            self.sb.grid()

    def _build_bottom(self) -> None:
        sc = self.ui_scale
        box = ttk.Frame(self, padding=(px(16, sc), px(8, sc), px(16, sc), px(12, sc)))
        box.grid(row=6, column=0, sticky="ew")
        box.columnconfigure(0, weight=1)
        self.btn_create = ttk.Button(box, style="Create.TButton", command=self.on_create)
        self.set_text(self.btn_create, "btn.create")
        self.btn_create.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar = ttk.Frame(box)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(px(8, sc), px(4, sc)))
        bar.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(bar, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew")
        self.lbl_percent = ttk.Label(bar, text="", width=5, anchor="e", font=FONT_MONO)
        self.lbl_percent.grid(row=0, column=1, padx=(px(8, sc), 0))
        self.lbl_percent.grid_remove()       # shown only while a video is being created
        self.btn_cancel_job = ttk.Button(bar, style="Stop.TButton", command=self.on_cancel_job)
        self.set_text(self.btn_cancel_job, "btn.cancel_job")
        self.btn_cancel_job.grid(row=0, column=2, padx=(px(12, sc), 0))
        self.btn_cancel_job.state(["disabled"])
        self.btn_cancel_job.grid_remove()    # shown only while a video is being created
        self.lbl_operation = ttk.Label(box, text="", style="Dim.TLabel")
        self.lbl_operation.grid(row=2, column=0, columnspan=2, sticky="w")
        self.lbl_operation.grid_remove()     # shown only while a video is being created
        # status line: glyph + one short sentence (the level decides colour and glyph)
        self.status_row = ttk.Frame(box)
        self.status_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, px(4, sc)))
        self.status_row.columnconfigure(1, weight=1)
        self.lbl_status_glyph = ttk.Label(self.status_row, text="", width=2,
                                          style="info.Glyph.Status.TLabel")
        self.lbl_status_glyph.grid(row=0, column=0, sticky="nw")
        self.lbl_status = ttk.Label(self.status_row, wraplength=px(800, sc), justify="left",
                                    style="info.Status.TLabel")
        self.lbl_status.grid(row=0, column=1, sticky="w")
        self.status_row.bind("<Configure>", lambda e: self.lbl_status.configure(
            wraplength=max(px(200, sc), e.width - px(40, sc))))
        self.txt_output = tk.Text(box, height=1, wrap="char", bg=PANEL, fg=FG, font=FONT_MONO,
                                  relief="flat", highlightthickness=1,
                                  highlightbackground=BORDER, highlightcolor=LINK,
                                  insertbackground=FG, state="disabled")
        self.txt_output.grid(row=4, column=0, sticky="ew")
        self.txt_output.bind("<Configure>", self._on_output_resize)
        self.btn_open_folder = ttk.Button(box, style="Stop.TButton", command=self.on_open_folder)
        self.set_text(self.btn_open_folder, "btn.open_folder")
        self.btn_open_folder.grid(row=4, column=1, sticky="n", padx=(px(8, sc), 0))
        self.btn_open_folder.grid_remove()   # shown only while a kept folder is shown
        self.video_controls = [
            self.btn_play, self.btn_pause, self.btn_stop, self.seek_scale, self.vol_scale,
            self.btn_mark_start, self.btn_mark_end, self.ent_start, self.ent_end,
            self.btn_add_segment, self.btn_up, self.btn_down, self.btn_edit,
            self.btn_delete, self.btn_clear, self.btn_create,
        ]

    # ---------------------------------------------------------- public helpers
    def set_controls_enabled(self, enabled: bool) -> None:
        """Master switch (Task 7 turns it off while a video is being created)."""
        self._controls_on = bool(enabled)
        self._update_controls()

    @property
    def manual_mode(self) -> bool:
        """True when there is no preview: segments are typed, not marked."""
        return not vlc_available() or self._preview_failed

    def _update_controls(self) -> None:
        on = self._controls_on and self.info is not None and not self._busy()
        player_ok = on and self.player is not None
        idx = self._selected_index()
        n = len(self.segments)

        def enable(widgets, flag: bool) -> None:
            for w in widgets:
                w.state(["!disabled"] if flag else ["disabled"])

        enable((self.btn_load,), not self._loading and not self._create_active())
        enable((self.btn_play, self.btn_pause, self.btn_stop, self.seek_scale,
                self.vol_scale), self._controls_on and self.info is not None
               and self.player is not None and not self._create_active())
        enable((self.btn_mark_start, self.btn_mark_end), player_ok)
        enable((self.ent_start, self.ent_end, self.btn_add_segment), on)
        enable((self.btn_up,), on and idx is not None and idx > 0)
        enable((self.btn_down,), on and idx is not None and idx < n - 1)
        enable((self.btn_edit, self.btn_delete), on and idx is not None)
        enable((self.btn_clear,), on and n > 0)
        enable((self.btn_create,), on and n > 0)  # `on` is False while the worker runs
        creating = self._creating and not self._closing
        if creating:
            self.btn_cancel_job.grid()
        else:
            self.btn_cancel_job.grid_remove()
        enable((self.btn_cancel_job,), creating and not self._cancel_asking
               and not self._close_asking and not self._close_waiting
               and not self._cancel_requested.is_set())
        self._refresh_mark_labels()

    def _create_active(self) -> bool:
        """True from the click on Create Video until the result is shown."""
        return self._creating or self._create_pending

    def _busy(self) -> bool:
        """A video is being probed or created: editing is locked."""
        return self._loading or self._create_active()

    def _apply_mode(self) -> None:
        """Show the Mark buttons (player) or the manual time boxes (no player)."""
        if self.manual_mode:
            self.btn_mark_start.grid_remove()
            self.btn_mark_end.grid_remove()
            self.manual_frame.grid()
        else:
            self.manual_frame.grid_remove()
            self.btn_mark_start.grid()
            self.btn_mark_end.grid()
        self._refresh_mark_labels()

    def _refresh_mark_labels(self) -> None:
        """Mark buttons and the hint line, recomputed from the state every time: the hint is
        empty while marking is not possible and says 'limit reached' at 10 / 10."""
        marked = self.marker.start_ms is not None
        if not marked:
            self.set_text(self.btn_mark_start, "btn.mark_start")
        else:
            self.set_text(self.btn_mark_start, "btn.mark_start_set",
                          time=format_ms(self.marker.start_ms))
        self.btn_mark_start.configure(
            style="MarkSet.Mark.TButton" if marked else "Mark.TButton")
        active = (self._controls_on and self.info is not None and not self._busy()
                  and (self.manual_mode or self.player is not None))
        if not active:
            key, params = None, {}
        elif len(self.segments) >= MAX_SEGMENTS:
            key, params = "mark.limit", {"max": MAX_SEGMENTS}
        elif self.manual_mode:
            key, params = "mark.manual_hint", {}
        elif not marked:
            key, params = "mark.hint", {}
        else:
            key, params = "mark.pending", {"time": format_ms(self.marker.start_ms)}
        self.set_text(self.lbl_mark_status, key, **params)
        if key is None:
            self.lbl_mark_status.grid_remove()    # no empty line: the rows below move up
        else:
            self.lbl_mark_status.grid()

    def set_text(self, widget, key: str | None, **params) -> None:
        """Show t(key, **params) in `widget` and remember key+params for apply_language().

        key=None clears the text (and forgets it).
        """
        if key is None:
            self._texts.pop(widget, None)
            widget.configure(text="")
            return
        self._texts[widget] = (key, params)
        widget.configure(text=t(key, **params))

    def set_status(self, key: str | None, level: str = "info", **params) -> None:
        """The one status line. `level` (info / ok / warn / error) picks colour AND glyph.
        key=None clears it. A new status replaces the old one and cancels its timer."""
        if level not in STATUS_LEVELS:
            raise ValueError(f"unknown status level {level!r}")
        self._cancel_status_timer()
        self._status_transient = False
        self._status_level = level if key is not None else "info"
        self.set_text(self.lbl_status, key, **params)
        self._style_status()

    def _style_status(self) -> None:
        level = self._status_level
        has_text = self.lbl_status in self._texts
        self.lbl_status.configure(style=f"{level}.Status.TLabel")
        self.lbl_status_glyph.configure(style=f"{level}.Glyph.Status.TLabel",
                                        text=STATUS_GLYPHS[level] if has_text else "")

    def flash_status(self, key: str, **params) -> None:
        """A validation message (level warn). It is cleared by the next user action or after
        STATUS_FLASH_MS, whichever comes first."""
        self.set_status(key, "warn", **params)
        self._status_transient = True
        try:
            self._status_timer = self.after(STATUS_FLASH_MS, self._clear_transient_status)
        except tk.TclError:
            self._status_timer = None

    def _cancel_status_timer(self) -> None:
        timer, self._status_timer = self._status_timer, None
        if timer is not None:
            try:
                self.after_cancel(timer)
            except tk.TclError:
                pass

    def _clear_transient_status(self) -> None:
        """Remove a validation message (called by the timer and at the start of user actions)."""
        if self._status_transient and not self._closing:
            self.set_status(None)

    def apply_language(self) -> None:
        """Redraw every translated text in the current language (data is kept)."""
        self.title(t("app.title"))
        for widget, (key, params) in list(self._texts.items()):
            widget.configure(text=t(key, **params))
        for col, key in self._headings.items():
            self.tree.heading(col, text=t(key))
        self._render_output()
        self._style_status()
        self.update_idletasks()

    def toggle_language(self) -> None:
        new = "ru" if get_language() == "en" else "en"
        set_language(new)
        save_language(self.settings_path, new)  # never raises on a write failure
        self.apply_language()

    def set_output(self, key: str | None, **params) -> None:
        """Keyed text in the output box; re-rendered when the language changes."""
        self._output = None if key is None else (key, params)
        kept = params.get("path") if key == "err.kept" else None
        self._kept_folder = str(kept) if kept else None
        if self._kept_folder:
            self.btn_open_folder.grid()
        else:
            self.btn_open_folder.grid_remove()
        self._render_output()

    def on_open_folder(self) -> None:
        """Open the kept temporary folder in Explorer. Errors are ignored."""
        folder = self._kept_folder
        if not folder:
            return
        try:
            os.startfile(folder)
        except Exception as exc:
            print(f"could not open {folder}: {exc!r}", file=sys.stderr)

    def _render_output(self) -> None:
        if self._output is None:
            self.set_output_text("")
        else:
            key, params = self._output
            self.set_output_text(t(key, **params))

    def set_output_text(self, text: str) -> None:
        """Show the final output path in a selectable (read-only) box."""
        self.txt_output.configure(state="normal")
        self.txt_output.delete("1.0", "end")
        self.txt_output.insert("1.0", text)
        self.txt_output.configure(state="disabled")
        self._fit_output_height()

    def _fit_output_height(self) -> None:
        """The output box is as high as its text needs (1 to 4 lines, wrapped by character, so a
        long path with no spaces is never cut off). Counted from the font (Consolas is
        monospaced): Tk's own -displaylines count is computed lazily and came back too small."""
        txt = self.txt_output
        try:
            txt.update_idletasks()
            width = txt.winfo_width()
            if width <= 1:            # not laid out yet: the <Configure> event fits it later
                return
            inner = (int(str(txt.cget("padx"))) + int(str(txt.cget("highlightthickness")))
                     + int(str(txt.cget("borderwidth"))))
            char_w = max(1, tkfont.Font(root=self, font=FONT_MONO).measure("0"))
            per_line = max(1, (width - 2 * inner) // char_w)
            text = txt.get("1.0", "end-1c")
            lines = sum(max(1, -(-len(part) // per_line)) for part in text.splitlines() or [""])
            lines = max(1, min(OUTPUT_MAX_LINES, lines))
            if lines != int(txt.cget("height")):
                txt.configure(height=lines)
        except (tk.TclError, ValueError, TypeError):
            pass

    def _on_output_resize(self, event) -> None:
        if event.width != self._out_width:      # only a width change can change the line count
            self._out_width = event.width
            self.after_idle(self._fit_output_height)

    def register_handler(self, kind: str, fn: Callable) -> None:
        self._handlers[kind] = fn

    def post(self, kind: str, payload=None) -> None:
        """Thread-safe: workers call this to hand a result to the GUI."""
        self.events.put((kind, payload))

    def show_error(self, title_key: str, message_key: str, **params) -> None:
        # Deferred so a modal dialog never opens inside _poll() or a handler.
        # Texts are translated when the dialog opens, in the language of that moment.
        self.after(0, lambda: self._show_message(
            "error", t(title_key), t(message_key, **params)))

    def show_info(self, title_key: str, message_key: str, **params) -> None:
        self.after(0, lambda: self._show_message(
            "info", t(title_key), t(message_key, **params)))

    # The two methods below are the ONLY places that open a dialog (tests replace them).
    def _show_message(self, kind: str, title: str, message: str) -> None:
        """Dark OK dialog; `kind` is "info" or "error". Returns when it is closed."""
        ThemedDialog(self, title, message, [(t("btn.ok"), True)], kind=kind,
                     cancel_value=True).show()

    def _ask_yes_no(self, title: str, message: str, yes_key: str = "btn.yes",
                    no_key: str = "btn.no") -> bool:
        """Dark question dialog; True only for the first button. Esc / close box = False."""
        return bool(ThemedDialog(self, title, message,
                                 [(t(yes_key), True), (t(no_key), False)],
                                 kind="question", cancel_value=False).show())

    # --------------------------------------------------------------- poll loop
    def _poll(self) -> None:
        if self._closing:
            return
        # Re-arm first: nothing below (handlers, dialogs) can stop the loop.
        self.after(POLL_MS, self._poll)
        if self.player is not None:
            self._poll_player()
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            handler = self._handlers.get(kind)
            if handler is not None:
                try:
                    handler(payload)
                except Exception:  # keep the loop alive; traceback goes to the log
                    import traceback
                    traceback.print_exc()
        self._ensure_min_fits()

    @_player_guard
    def _poll_player(self) -> None:
        self.player.tick()
        self._update_playback_display()

    def _player_failed(self, exc: Exception) -> None:
        """Count a failure of the player. After PLAYER_FAIL_LIMIT in a row: release it and
        switch to the manual route (one traceback in the log, not one per tick)."""
        self._player_fails += 1
        if self._player_fails < PLAYER_FAIL_LIMIT:
            print(f"player call failed ({self._player_fails} of {PLAYER_FAIL_LIMIT}): {exc!r}",
                  file=sys.stderr)
            return
        import traceback
        traceback.print_exception(exc, file=sys.stderr)
        self._player_fails = 0
        player, self.player = self.player, None
        if player is not None:
            try:
                player.release()
            except Exception:
                pass
        self._preview_failed = True
        self._seeking = False
        self._show_preview_failed()
        self._apply_mode()
        self._update_controls()

    def _show_preview_failed(self) -> None:
        self._show_video_placeholder()
        self.lbl_vlc_link.place_forget()   # VLC is installed; only this file / player failed
        self.set_text(self.lbl_video_msg, "video.preview_failed")

    # ------------------------------------------------------------ video area
    def _show_video_placeholder(self) -> None:
        if vlc_available():
            self.set_text(self.lbl_video_msg, "status.load_to_begin")
            self.lbl_vlc_link.place_forget()
            self.lbl_video_msg.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.set_text(self.lbl_video_msg, "video.vlc_missing")
            self.lbl_video_msg.place(relx=0.5, rely=0.5, anchor="s")
            self.lbl_vlc_link.place(relx=0.5, rely=0.5, y=6, anchor="n")

    def _hide_video_placeholder(self) -> None:
        self.lbl_video_msg.place_forget()
        self.lbl_vlc_link.place_forget()

    def _hwnd(self) -> int:
        self.update_idletasks()
        return self.video_frame.winfo_id()

    def _ensure_player(self) -> None:
        if self.player is not None or not vlc_available():
            return
        try:
            self.player = VlcPlayer(self._hwnd)
        except PlayerUnavailable:
            self.player = None

    # ------------------------------------------------------------- Load Video
    def choose_video(self) -> None:
        if self._create_active():
            return
        self._clear_transient_status()
        path = filedialog.askopenfilename(
            parent=self, title=t("dlg.choose_video"),
            filetypes=[(t("ft.video"), "*.mp4 *.mov *.avi *.mkv"),
                       ("MP4", "*.mp4"), ("MOV", "*.mov"), ("AVI", "*.avi"),
                       ("MKV", "*.mkv"), (t("ft.all"), "*.*")])
        if not path:
            return
        if len(self.segments) and not self._confirm(
                "dlg.new_video_title", "dlg.new_video_message", name=Path(path).name,
                n=len(self.segments)):
            return
        self.load_video(Path(path))

    def load_video(self, path: Path) -> None:
        """Probe `path` in a worker thread; results arrive through the queue."""
        path = Path(path)
        if self._create_active():
            return
        self._load_token += 1
        token = self._load_token
        if self._kept_folder:
            self.set_output(None)        # the old failure's folder note goes with its button
        self.btn_load.state(["disabled"])
        self._loading = True
        self._update_controls()
        self.set_status("status.reading", name=path.name)
        threading.Thread(target=self._probe_worker, args=(path, token), daemon=True).start()

    def _probe_worker(self, path: Path, token: int) -> None:
        """Worker thread. Always ends by posting exactly one terminal event."""
        posted = False

        def post(kind, payload):
            nonlocal posted
            posted = True
            self.post(kind, payload)

        try:
            ffprobe = find_tool("ffprobe")
            ffmpeg = find_tool("ffmpeg")
            if not ffprobe or not ffmpeg:
                post("tools_missing", token)
                return
            info = probe(path, ffprobe)
            post("probe_ok", (token, info))
        except ProcessingError as exc:
            post("probe_error", (token, exc.key, exc.params))
        except BaseException as exc:  # never show a traceback; never die silently
            print(f"probe failed for {path}: {exc!r}", file=sys.stderr)
            post("probe_error", (token, "err.not_a_video", {}))
        finally:
            if not posted:
                self.post("probe_error", (token, "err.not_a_video", {}))

    def _on_probe_ok(self, payload) -> None:
        token, info = payload
        if token != self._load_token:
            return
        self.btn_load.state(["!disabled"])
        self._loading = False
        self._close_edit_dialog()
        self.info = info
        self.set_text(self.lbl_info, "info.loaded", name=info.path.name,
                      duration=format_ms(info.duration_ms), width=info.width,
                      height=info.height)
        self.lbl_info.configure(foreground=FG)
        self.lbl_time.configure(text=f"{format_ms(0)} / {format_ms(info.duration_ms)}")
        # A new video starts with an empty list and no pending start mark.
        self.segments = SegmentList(info.duration_ms, MAX_SEGMENTS)
        self.marker.clear()
        self._seek_updating = True
        self.seek_scale.set(0)
        self._seek_updating = False
        self._seeking = False
        self.set_status("status.loaded", "ok")
        self._ensure_player()
        self._preview_failed = False
        if self.player is not None:
            self._hide_video_placeholder()
            try:
                self.player.load(str(info.path))
                self.player.set_volume(int(float(self.vol_scale.get())))
            except Exception as exc:
                print(f"VLC load failed: {exc!r}", file=sys.stderr)
                self.player.release()
                self.player = None
                self._preview_failed = True
                self._show_preview_failed()
        else:
            self._preview_failed = vlc_available()  # installed, but the player did not start
            self._show_video_placeholder()
        self._apply_mode()
        self._render_table()
        self.set_controls_enabled(True)
        self.event_generate("<<VideoLoaded>>")

    def _on_probe_error(self, payload) -> None:
        token, key, params = payload
        if token != self._load_token:
            return
        self.btn_load.state(["!disabled"])
        self._loading = False
        self._update_controls()
        self.set_status(key, "error", **params)
        self.show_error("dlg.cannot_open", key, **params)

    def _on_tools_missing(self, token) -> None:
        if token != self._load_token:
            return
        self.btn_load.state(["!disabled"])
        self._loading = False
        self._update_controls()
        self.set_status("status.ffmpeg_missing", "error")
        self.show_error("dlg.ffmpeg_missing", "ffmpeg.help")

    # --------------------------------------------------------------- playback
    def _total_ms(self) -> int:
        return self.info.duration_ms if self.info is not None else 0

    def _scale_to_ms(self, value: float) -> int:
        total = self._total_ms()
        return max(0, min(total, round(float(value) / SEEK_STEPS * total)))

    def _show_time(self, ms: int) -> None:
        self.lbl_time.configure(text=f"{format_ms(ms)} / {format_ms(self._total_ms())}")

    def _update_playback_display(self) -> None:
        """Called every 100 ms: move the slider and the time (never while dragging)."""
        if self.player is None or self.info is None or self._seeking:
            return
        total = self._total_ms()
        ms = max(0, min(self.player.time_ms(), total))
        self._seek_updating = True
        try:
            self.seek_scale.set(ms / total * SEEK_STEPS if total else 0)
        finally:
            self._seek_updating = False
        self._show_time(ms)

    @_player_guard
    def on_play(self) -> None:
        if self.player is None or self._create_active():
            return
        self._clear_transient_status()
        self.player.play()
        self.player.set_volume(int(float(self.vol_scale.get())))

    @_player_guard
    def on_pause(self) -> None:
        if self.player is not None:
            self._clear_transient_status()
            self.player.pause()

    @_player_guard
    def on_stop(self) -> None:
        if self.player is None:
            return
        self._clear_transient_status()
        self.player.stop()
        self._seek_updating = True
        self.seek_scale.set(0)
        self._seek_updating = False
        self._show_time(0)

    @_player_guard
    def _on_volume(self, value) -> None:
        if self.player is not None:
            self.player.set_volume(int(float(value)))

    @_player_guard
    def _on_seek_scale(self, value) -> None:
        """Slider moved by the user (mouse drag or keyboard); ignore the tick's own moves."""
        if self._seek_updating or self.player is None or self.info is None:
            return
        ms = self._scale_to_ms(value)
        self._show_time(ms)
        now = time.monotonic()
        if self._seeking and now - self._last_seek_t < 0.08:
            return  # dragging: the final position is sent on release
        self._last_seek_t = now
        self.player.seek_ms(ms)

    def _seek_press(self, _event) -> None:
        if self.seek_scale.instate(["!disabled"]):
            self._seeking = True

    def _seek_release(self, _event) -> None:
        # The class binding sets the final value after this one, so finish when idle.
        self.after_idle(self._finish_seek)

    @_player_guard
    def _finish_seek(self) -> None:
        try:
            if self._seeking and self.player is not None and self.info is not None:
                self.player.seek_ms(self._scale_to_ms(self.seek_scale.get()))
        finally:
            self._seeking = False

    # ----------------------------------------------------------------- marking
    def _report_segment_error(self, exc) -> None:
        """Segment limit: message box. Everything else: the status line (key + params)."""
        if exc.key == "err.seg_max":
            self.show_info("dlg.max_segments", exc.key, **exc.params)
        else:
            self.flash_status(exc.key, **exc.params)

    def _marked_time_ms(self) -> int:
        """The player position for a mark, kept inside the video (VLC can report a few ms
        past the end, or the end itself after "play to the end")."""
        return max(0, min(int(self.player.time_ms()), self._total_ms()))

    @_player_guard
    def on_mark_start(self) -> None:
        if self.player is None or self.info is None or self._busy():
            return
        self._clear_transient_status()
        try:
            self.marker.mark_start(self._marked_time_ms(), self.segments)
        except SegmentError as exc:
            self._report_segment_error(exc)
            return
        self._refresh_mark_labels()

    @_player_guard
    def on_mark_end(self) -> None:
        if self.player is None or self.info is None or self._busy():
            return
        self._clear_transient_status()
        try:
            seg = self.marker.mark_end(self._marked_time_ms(), self.segments)
        except SegmentError as exc:
            self._report_segment_error(exc)
            return
        self._segment_added(seg)

    def on_add_manual(self) -> None:
        if self.info is None or not self._controls_on or self._busy():
            return
        self._clear_transient_status()
        try:
            seg = self.segments.add_text(self.ent_start.get(), self.ent_end.get())
        except (SegmentError, TimeError) as exc:
            self._report_segment_error(exc)
            return
        self.ent_start.delete(0, "end")
        self.ent_end.delete(0, "end")
        self._segment_added(seg)
        self.ent_start.focus_set()

    def _segment_added(self, seg) -> None:
        idx = len(self.segments) - 1
        self._render_table(select=idx)
        self._refresh_mark_labels()
        self.set_status("mark.added", "ok", n=idx + 1, start=format_ms(seg.start_ms),
                        end=format_ms(seg.end_ms))

    # ------------------------------------------------------------------- table
    def _render_table(self, select: int | None = None) -> None:
        """Redraw all rows from self.segments (data), then select row `select`."""
        self.tree.delete(*self.tree.get_children())
        for i, seg in enumerate(self.segments.items):
            self.tree.insert("", "end", iid=str(i), values=(
                i + 1, format_ms(seg.start_ms), format_ms(seg.end_ms),
                format_ms(seg.duration_ms)))
        if select is not None and 0 <= select < len(self.segments):
            iid = str(select)
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
        if len(self.segments):
            self.lbl_empty.place_forget()
        else:
            self.lbl_empty.place(relx=0.5, rely=0.58, anchor="center")
        self.lbl_counter.configure(text=f"{len(self.segments)} / {MAX_SEGMENTS}")
        self.set_text(self.lbl_total, "label.total", time=format_ms(self.segments.total_ms()))
        self._update_controls()

    def _selected_index(self) -> int | None:
        """Index of the selected row, or None. Always a valid index for self.segments."""
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            idx = int(sel[0])
        except ValueError:
            return None
        return idx if 0 <= idx < len(self.segments) else None

    def _can_edit_table(self) -> bool:
        return self._controls_on and self.info is not None and not self._busy()

    def on_move(self, delta: int) -> None:
        idx = self._selected_index()
        if idx is None or not self._can_edit_table():
            return
        self._clear_transient_status()
        try:
            new = self.segments.move(idx, delta)
        except SegmentError:
            return
        self._render_table(select=new)

    def on_delete(self) -> None:
        idx = self._selected_index()
        if idx is None or not self._can_edit_table():
            return
        self._clear_transient_status()
        try:
            self.segments.delete(idx)
        except SegmentError:
            return
        left = len(self.segments)
        self._render_table(select=min(idx, left - 1) if left else None)
        self.set_status("status.segment_deleted", n=idx + 1)

    def on_clear(self) -> None:
        n = len(self.segments)
        if n == 0 or not self._can_edit_table():
            return
        self._clear_transient_status()
        if not self._confirm("dlg.clear_title",
                             "dlg.clear_message_one" if n == 1 else "dlg.clear_message", n=n):
            return
        self.segments.clear()
        self._render_table()
        self.set_status("status.cleared")

    def _confirm(self, title_key: str, message_key: str, yes_key: str = "btn.yes",
                 no_key: str = "btn.no", **params) -> bool:
        return bool(self._ask_yes_no(t(title_key), t(message_key, **params),
                                     yes_key=yes_key, no_key=no_key))

    def _on_tree_double_click(self, event) -> None:
        if self.tree.identify_row(event.y):
            self.after(0, self.on_edit)

    def on_edit(self) -> None:
        idx = self._selected_index()
        if idx is None or not self._can_edit_table():
            return
        self._clear_transient_status()
        if self._edit_dialog is not None and self._edit_dialog.winfo_exists():
            self._edit_dialog.lift()
            self._edit_dialog.focus_force()
            return
        self._edit_dialog = EditDialog(self, idx)

    def _close_edit_dialog(self) -> None:
        dlg, self._edit_dialog = self._edit_dialog, None
        if dlg is not None and dlg.winfo_exists():
            dlg.destroy()

    def _segment_edited(self, idx: int) -> None:
        self._render_table(select=idx)
        self.set_status("status.segment_edited", n=idx + 1)

    # ------------------------------------------------------------------ close
    def on_close(self) -> None:
        if self._closing or self._close_asking or self._close_waiting:
            return
        if self._creating:
            # Ask from the event loop, never inside _poll() or a handler.
            self._close_asking = True
            self.after(0, self._confirm_close)
            return
        self._shutdown()

    def _confirm_close(self) -> None:
        keep_running = False
        try:
            keep_running = bool(self._creating and not self._confirm(
                "dlg.close_title", "dlg.close_message"))
        finally:
            self._close_asking = False
        if keep_running:
            self._flush_deferred()
            self._update_controls()
            return
        self._deferred_dialogs = []
        if self._creating:
            # Stop the job, then wait WITHOUT blocking the window (it keeps repainting).
            self._cancel_requested.set()
            job = self._job
            if job is not None:
                job.cancel()
            self._close_waiting = True
            self._close_deadline = time.monotonic() + CLOSE_WAIT_S
            self.set_status("status.stopping")
            self._update_controls()
            self.after(POLL_MS, self._wait_worker_for_close)
            return
        self._shutdown()

    def _wait_worker_for_close(self) -> None:
        if self._closing:
            return
        worker, job = self._worker, self._job
        if worker is None or not worker.is_alive():
            self._shutdown()
            return
        if time.monotonic() >= self._close_deadline:
            if job is not None:
                job.cancel()        # best effort: ask the FFmpeg child to stop once more
                job.discard_part()  # best effort: no half-written .part beside the source
            self._shutdown()
            return
        self.after(POLL_MS, self._wait_worker_for_close)

    def _shutdown(self) -> None:
        self._closing = True
        try:
            self._close_edit_dialog()
            if self.player is not None:
                try:
                    self.player.release()
                finally:
                    self.player = None
        finally:
            try:   # no timer may fire on the destroyed window
                for ident in self.tk.splitlist(self.tk.call("after", "info")):
                    self.after_cancel(ident)
            except tk.TclError:
                pass
            self.destroy()

    def _notify(self, show, *args, **kwargs) -> None:
        """show_info / show_error, but never stacked on top of the close / cancel question,
        and never while the window is waiting to close."""
        if self._closing or self._close_waiting:
            return
        if self._close_asking or self._cancel_asking:
            self._deferred_dialogs.append((show, args, kwargs))
        else:
            show(*args, **kwargs)

    def _flush_deferred(self) -> None:
        """Show the results that arrived while a question was open."""
        pending, self._deferred_dialogs = self._deferred_dialogs, []
        for show, args, kwargs in pending:
            show(*args, **kwargs)

    # ------------------------------------------------------------ Create Video
    def on_create(self) -> None:
        """Create Video button: check, confirm (from the event loop), then start the worker."""
        if self._create_active() or self._loading or self.info is None:
            return
        if len(self.segments) == 0:
            self.flash_status("err.empty_list")
            self.show_info("dlg.create_title", "err.empty_list")
            return
        self._create_pending = True      # the button is disabled at once: no double click
        self._update_controls()
        self.after(0, self._confirm_and_start)

    def _confirm_and_start(self) -> None:
        ok = False
        try:
            if self.info is None or self._closing:
                return
            out = unique_output_path(self.info.path)
            lines = ["- " + t(key, **params) for key, params in conversion_notes(self.info)]
            notes = t("dlg.create_notes", list="\n".join(lines)) + "\n\n" if lines else ""
            ok = self._confirm("dlg.create_title", "dlg.create_confirm",
                               yes_key="btn.create_video", no_key="btn.cancel",
                               n=len(self.segments),
                               total=format_ms(self.segments.total_ms()),
                               name=out.name, folder=str(out.parent), notes=notes)
        except Exception as exc:  # never leave the controls locked
            print(f"create confirm failed: {exc!r}", file=sys.stderr)
            self._create_pending = False
            if not self._closing:
                self._update_controls()
                self.set_status("err.file_problem", "error")
                self.show_error("dlg.create_failed_title", "err.file_problem")
            return
        finally:
            self._create_pending = False
            if not self._closing:
                self._update_controls()   # every exit path unlocks the controls
        if self._closing:
            return
        if not ok:
            return
        self._start_job()

    # ------------------------------------------------------------ Cancel button
    def on_cancel_job(self) -> None:
        """Cancel button: ask (from the event loop), then stop the running job."""
        if (not self._creating or self._cancel_asking or self._close_asking
                or self._close_waiting or self._closing):
            return
        self._cancel_asking = True      # the button is disabled at once: no stacked dialogs
        self._update_controls()
        self.after(0, self._confirm_cancel_job)

    def _confirm_cancel_job(self) -> None:
        stop = False
        try:
            if self._closing:
                return
            stop = bool(self._creating and self._confirm(
                "dlg.cancel_job_title", "dlg.cancel_job_message"))
        except Exception as exc:  # never leave the button locked
            print(f"cancel question failed: {exc!r}", file=sys.stderr)
        finally:
            self._cancel_asking = False
        if self._closing:
            return
        if stop and self._creating and not self._close_waiting:
            self._cancel_requested.set()
            job = self._job
            if job is not None:
                job.cancel()
            self.set_status("status.stopping")
        self._update_controls()
        self._flush_deferred()

    def _start_job(self) -> None:
        self._close_edit_dialog()
        if self.player is not None:
            try:
                self.player.pause()
            except Exception:
                pass
        self._create_token += 1
        token = self._create_token
        self._creating = True
        try:
            self._cancel_requested.clear()
            self._job = None
            self.progress.configure(value=0)
            self._set_percent("0 %")
            self._set_operation("progress.cut", i=1, n=len(self.segments))
            self.set_output(None)
            self.set_status("status.creating")
            self._update_controls()
            source, info = self.info.path, self.info
            segs = list(self.segments.items)
            self._worker = threading.Thread(target=self._create_worker,
                                            args=(token, source, info, segs, self.work_root),
                                            daemon=True)
            self._worker.start()
        except Exception as exc:  # no worker is running: unlock everything
            print(f"could not start the job: {exc!r}", file=sys.stderr)
            self._creating = False
            self._worker = None
            self._job = None
            self.progress.configure(value=0)
            self._set_percent(None)
            self._set_operation(None)
            self._update_controls()
            self.set_status("err.file_problem", "error")
            self.show_error("dlg.create_failed_title", "err.file_problem")

    def _create_worker(self, token, source, info, segs, work_root) -> None:
        """Runs in the worker thread: no Tk calls here, only self.post().

        Always ends by posting exactly one terminal event (done / error / cancelled), even
        when the thread is hit by a BaseException (KeyboardInterrupt, SystemExit, ...).
        """
        posted = False

        def post(kind, payload):
            nonlocal posted
            posted = True
            self.post(kind, payload)

        try:
            ffmpeg, ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
            if not ffmpeg or not ffprobe:
                post("create_error", (token, "ffmpeg.help", {}, "dlg.ffmpeg_missing"))
                return
            job = VideoJob(source, info, segs, ffmpeg, ffprobe,
                           lambda ev: self.post("create_progress", (token, ev)), work_root)
            self._job = job
            if self._cancel_requested.is_set():  # cancelled before the job existed
                job.cancel()
            out = job.run()
            post("create_done", (token, str(out)))
        except Cancelled as exc:
            post("create_cancelled", (token, exc.key, exc.params))
        except ProcessingError as exc:
            print(f"create failed: {exc.key} {exc.params} {exc.detail}", file=sys.stderr)
            post("create_error", (token, exc.key, exc.params, "dlg.create_failed_title"))
        except BaseException as exc:  # never show a traceback; never die silently
            print(f"create failed: {exc!r}", file=sys.stderr)
            post("create_error", (token, "err.file_problem", {}, "dlg.create_failed_title"))
        finally:
            if not posted:
                self.post("create_error",
                          (token, "err.file_problem", {}, "dlg.create_failed_title"))

    def _on_create_progress(self, payload) -> None:
        token, ev = payload
        if token != self._create_token or not self._creating:
            return
        key, params, percent = progress_view(ev)
        self._set_operation(key, **params)
        self.progress.configure(value=percent)
        self._set_percent(f"{percent:.0f} %")

    def _create_finished(self, token) -> bool:
        """Common end of every path: re-enable the controls. False for a stale token."""
        if token != self._create_token or not self._creating:
            return False
        self._creating = False
        self._job = None
        self.progress.configure(value=0)
        self._set_percent(None)
        self._set_operation(None)
        self._update_controls()
        return True

    def _set_percent(self, text: str | None) -> None:
        """The percent label exists only while a video is being created (the bar is full
        width when idle)."""
        if text is None:
            self.lbl_percent.configure(text="")
            self.lbl_percent.grid_remove()
        else:
            self.lbl_percent.configure(text=text)
            self.lbl_percent.grid()

    def _set_operation(self, key: str | None, **params) -> None:
        """What the job is doing now; the row is hidden when idle."""
        self.set_text(self.lbl_operation, key, **params)
        if key is None:
            self.lbl_operation.grid_remove()
        else:
            self.lbl_operation.grid()

    def _on_create_done(self, payload) -> None:
        token, path = payload
        if not self._create_finished(token):
            return
        self.set_status("status.done", "ok")
        self.set_output("out.saved", path=path)
        self._notify(self.show_info, "dlg.create_done_title", "out.saved", path=path)

    def _on_create_error(self, payload) -> None:
        token, key, params, title_key = payload
        if not self._create_finished(token):
            return
        self.set_status(key, "error", **self._short(params))   # the path is in the output box
        self._show_kept(params)
        self._notify(self.show_error, title_key, key, **params)

    def _on_create_cancelled(self, payload) -> None:
        token, key, params = payload
        if not self._create_finished(token):
            return
        self.set_status(key, "warn", **self._short(params))
        self._show_kept(params)

    @staticmethod
    def _short(params: dict) -> dict:
        """Status text without the kept-folder sentence: the output box shows the path."""
        return {k: v for k, v in params.items() if k != "kept_dir"}

    def _show_kept(self, params: dict) -> None:
        """Failure/cancel: the kept temp folder goes into the selectable box (copyable)."""
        kept = params.get("kept_dir")
        if kept:
            self.set_output("err.kept", path=str(kept))
        else:
            self.set_output(None)


class EditDialog(tk.Toplevel):
    """Edit one segment: Start and End boxes (HH:MM:SS.mmm or short forms).

    Errors are shown inside the dialog (in the language of the moment it was opened).
    Enter = OK, Esc = Cancel. Not blocking (no wait_window), so the poll loop keeps running.
    """

    def __init__(self, app: App, index: int):
        super().__init__(app)
        self.app = app
        self.index = index
        seg = app.segments.items[index]
        sc = getattr(app, "ui_scale", 1.0)
        self.title(t("dlg.edit_title", n=index + 1))
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app)
        try:
            self.iconbitmap(str(ASSETS / "logo.ico"))
        except tk.TclError:
            pass
        body = ttk.Frame(self, padding=px(16, sc))
        body.grid(row=0, column=0, sticky="nsew")
        self.lbl_hint = ttk.Label(body, text=t("dlg.edit_hint"), style="Dim.TLabel")
        self.lbl_hint.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, px(12, sc)))
        ttk.Label(body, text=t("col.start")).grid(row=1, column=0, sticky="w",
                                                  padx=(0, px(12, sc)))
        self.ent_start = ttk.Entry(body, width=16, font=FONT_MONO)
        self.ent_start.grid(row=1, column=1, sticky="w", pady=px(2, sc))
        ttk.Label(body, text=t("col.end")).grid(row=2, column=0, sticky="w",
                                                padx=(0, px(12, sc)))
        self.ent_end = ttk.Entry(body, width=16, font=FONT_MONO)
        self.ent_end.grid(row=2, column=1, sticky="w", pady=px(2, sc))
        # The error line has a reserved, fixed-size place (2 lines): the dialog never changes size.
        line = tkfont.Font(root=self, font=FONT).metrics("linespace")
        err_box = ttk.Frame(body, width=px(380, sc), height=2 * line + px(4, sc))
        err_box.grid(row=3, column=0, columnspan=2, sticky="w", pady=(px(8, sc), 0))
        err_box.grid_propagate(False)
        self.lbl_error = ttk.Label(err_box, text="", style="Warn.TLabel",
                                   wraplength=px(380, sc), justify="left")
        self.lbl_error.grid(row=0, column=0, sticky="nw")
        btns = ttk.Frame(body)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(px(12, sc), 0))
        self.btn_ok = ttk.Button(btns, text=t("btn.ok"), command=self.apply)
        self.btn_cancel = ttk.Button(btns, text=t("btn.cancel"), command=self.destroy)
        self.btn_ok.grid(row=0, column=0, padx=(0, px(8, sc)))
        self.btn_cancel.grid(row=0, column=1)
        self.ent_start.insert(0, format_ms(seg.start_ms))
        self.ent_end.insert(0, format_ms(seg.end_ms))
        self.bind("<Return>", self._on_return)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_reqwidth()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        apply_dark_titlebar(self)
        self.ent_start.focus_set()
        self.ent_start.selection_range(0, "end")
        self.after(50, self._grab)

    def _on_return(self, _event=None) -> None:
        if self.focus_get() is self.btn_cancel:  # Enter on Cancel means cancel
            self.destroy()
        else:
            self.apply()

    def _grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass  # window not visible yet; the dialog still works without the grab

    def apply(self) -> None:
        try:
            self.app.segments.edit_text(self.index, self.ent_start.get(), self.ent_end.get())
        except (SegmentError, TimeError) as exc:
            self.lbl_error.configure(text=f"{STATUS_GLYPHS['warn']} {t(exc.key, **exc.params)}")
            bad_end = isinstance(exc, TimeError) and exc.params.get("text") == self.ent_end.get()
            (self.ent_end if bad_end else self.ent_start).focus_set()
            return
        self.destroy()
        self.app._segment_edited(self.index)
