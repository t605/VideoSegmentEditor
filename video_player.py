"""Thin wrapper around python-vlc / libvlc for the Video Segment Editor.

No Tkinter imports here: the GUI passes a callable that returns the native
window handle (hwnd) the video should be drawn into.
"""
from __future__ import annotations

import os
import time
from typing import Callable

VLC_DOWNLOAD_URL = "https://www.videolan.org/vlc/"


PENDING_TIMEOUT_S = 20.0


class PlayerUnavailable(RuntimeError):
    """VLC (python-vlc or libvlc) is missing or cannot be loaded."""


def _load_vlc():
    """Import python-vlc lazily. Raises ImportError/OSError if unusable."""
    import vlc  # noqa: WPS433 (lazy on purpose)
    return vlc


def vlc_available() -> bool:
    if os.environ.get("VSE_FORCE_NO_VLC") == "1":
        return False
    try:
        _load_vlc()
    except Exception:  # python-vlc raises ImportError, OSError or others
        return False
    return True


class VlcPlayer:
    """All methods are non-blocking. Call tick() from the GUI's after() loop
    (about every 100 ms) so queued seeks are applied once VLC is ready."""

    def __init__(self, hwnd_getter: Callable[[], int]):
        if os.environ.get("VSE_FORCE_NO_VLC") == "1":
            raise PlayerUnavailable("VLC is disabled (VSE_FORCE_NO_VLC=1).")
        try:
            self._vlc = _load_vlc()
            self._instance = self._vlc.Instance("--no-xlib", "--quiet",
                                                "--no-video-title-show")
            self._player = self._instance.media_player_new()
        except Exception as exc:
            raise PlayerUnavailable(f"VLC could not be loaded: {exc}") from exc
        if self._instance is None or self._player is None:
            raise PlayerUnavailable("VLC could not be started.")
        # Let Tk keep mouse and keyboard input (Delete / Enter) when the video is clicked.
        for setter in (self._player.video_set_mouse_input, self._player.video_set_key_input):
            try:
                setter(False)
            except Exception:
                pass
        self._hwnd_getter = hwnd_getter
        self._released = False
        self._pending: int | None = None   # queued seek target (ms)
        self._repause = False              # pause again after queued seek
        self._pending_since = 0.0          # monotonic time the seek was queued
        self._duration = 0                 # from media parse (ms)
        self._last_ms = 0                  # last known position (ms)
        self._ended = False                # VLC reported the end of the media
        self._player.set_hwnd(int(hwnd_getter()))

    # --- helpers -----------------------------------------------------
    def _seekable(self) -> bool:
        st = self._vlc.State
        try:
            return (self._player.get_state() in (st.Playing, st.Paused)
                    and bool(self._player.is_seekable()))
        except Exception:
            return False

    # --- loading -----------------------------------------------------
    def load(self, path: str) -> None:
        if self._released:
            return
        self._pending = None
        self._repause = False
        self._duration = 0
        self._last_ms = 0
        self._ended = False
        media = self._instance.media_new_path(str(path))
        try:
            media.parse()  # synchronous for local files
            self._duration = max(0, int(media.get_duration()))
        except Exception:
            self._duration = 0
        self._player.set_media(media)
        self._player.set_hwnd(int(self._hwnd_getter()))

    # --- transport ---------------------------------------------------
    def play(self) -> None:
        if self._released:
            return
        self._repause = False
        self._ended = False
        self._player.play()

    def pause(self) -> None:
        """Pause (never toggles to playing)."""
        if self._released:
            return
        self._player.set_pause(1)

    def stop(self) -> None:
        if self._released:
            return
        self._pending = None
        self._repause = False
        self._last_ms = 0
        self._ended = False
        self._player.stop()

    def seek_ms(self, ms: int) -> None:
        """Seek to ms without blocking. If VLC is not seekable yet (stopped,
        opening, buffering) the target is queued and tick() applies it."""
        if self._released:
            return
        ms = max(0, int(ms))
        if self._seekable():
            self._pending = None
            self._player.set_time(ms)
            if self._repause:  # started only to reach a seekable state
                self._repause = False
                self._player.set_pause(1)
            return
        if self._pending is None:
            self._pending_since = time.monotonic()
        self._pending = ms
        st = self._vlc.State
        if self._player.get_state() in (st.Stopped, st.Ended, st.NothingSpecial):
            # A stopped player ignores set_time: start it, tick() re-pauses.
            self._repause = True
            self._ended = False
            self._player.play()

    def tick(self) -> None:
        """Apply a queued seek once the player is ready. Call from the GUI
        thread's after() loop."""
        if self._released or self._pending is None:
            return
        st = self._vlc.State
        timed_out = time.monotonic() - self._pending_since > PENDING_TIMEOUT_S
        if self._player.get_state() == st.Error or timed_out:
            if timed_out and self._repause:
                self._player.set_pause(1)  # we started playback; don't leave it running
            self._pending = None   # give up: stop showing a stale target
            self._repause = False
            return
        if self._seekable():
            target, self._pending = self._pending, None
            self._player.set_time(target)
            if self._repause:
                self._repause = False
                self._player.set_pause(1)

    def time_ms(self) -> int:
        """Current position. At or after the end of the media (VLC state Ended, or Stopped
        after the end; get_time() may then be -1) this is the media length, not 0."""
        if self._released:
            return 0
        if self._pending is not None:
            return self._pending
        st = self._vlc.State
        state = self._player.get_state()
        t = int(self._player.get_time())
        if state == st.Ended or (state == st.Stopped and self._ended):
            self._ended = True
            return self.length_ms() or self._last_ms
        if t < 0:
            return self._last_ms      # position unknown for a moment: keep the last known one
        self._last_ms = t
        return t

    def length_ms(self) -> int:
        if self._released:
            return 0
        n = int(self._player.get_length())
        return n if n > 0 else self._duration

    def set_volume(self, volume: int) -> None:
        if self._released:
            return
        self._player.audio_set_volume(max(0, min(100, int(volume))))

    def is_playing(self) -> bool:
        if self._released:
            return False
        return bool(self._player.is_playing())

    def release(self) -> None:
        """Free VLC resources. Safe to call more than once."""
        if self._released:
            return
        self._released = True
        self._pending = None
        for fn in (self._player.stop, self._player.release, self._instance.release):
            try:
                fn()
            except Exception:
                pass
