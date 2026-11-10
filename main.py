"""Entry point of the Video Segment Editor."""
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

APP_VER = "1.0"


LOG_MAX_BYTES = 1024 * 1024    # app.log is renamed to app.log.1 above this size


class TimestampedLog:
    """Text stream for sys.stdout / sys.stderr under pythonw: every line gets an ISO timestamp.

    Writes a session start line (version, Python) when created. A log that is bigger than
    `max_bytes` (at start, or while running) is renamed to <name>.1 (the old .1 is replaced)
    and a fresh file is started. It never raises: a failing log must not crash the app.
    """

    encoding = "utf-8"

    def __init__(self, path, version: str, max_bytes: int = LOG_MAX_BYTES):
        self.path = Path(path)
        self.max_bytes = max_bytes
        self._pending = ""
        self._fh = None
        self._lock = threading.Lock()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_big()
        except Exception:
            pass
        self._open()
        self._emit(f"session start: Video Segment Editor {version}, "
                   f"Python {sys.version.split()[0]}")

    def _open(self) -> None:
        try:
            self._fh = open(self.path, "a", encoding="utf-8", buffering=1)
        except Exception:
            self._fh = None

    def _rotate_if_big(self) -> bool:
        try:
            if self.path.stat().st_size <= self.max_bytes:
                return False
        except OSError:
            return False
        try:
            os.replace(self.path, str(self.path) + ".1")
        except OSError:
            return False
        return True

    def _emit(self, line: str) -> None:
        try:
            if self._fh is not None and self._rotate_if_big_open():
                self._open()
            if self._fh is not None:
                stamp = datetime.now().isoformat(timespec="seconds")
                self._fh.write(f"{stamp} {line}\n")
        except Exception:
            pass

    def _rotate_if_big_open(self) -> bool:
        """Close and rotate when the file grew past the limit; True when a new file is needed."""
        try:
            if self._fh.tell() <= self.max_bytes:
                return False
            self._fh.close()
        except Exception:
            return False
        self._fh = None
        self._rotate_if_big()
        return True

    def write(self, text) -> int:
        try:
            text = str(text)
            with self._lock:
                self._pending += text
                *lines, self._pending = self._pending.split("\n")
                for line in lines:
                    if line.strip():
                        self._emit(line.rstrip("\r"))
        except Exception:
            pass
        return len(text) if isinstance(text, str) else 0

    def flush(self) -> None:
        try:
            if self._fh is not None:
                self._fh.flush()
        except Exception:
            pass

    def close(self) -> None:
        try:
            with self._lock:
                if self._pending.strip():
                    self._emit(self._pending)
                self._pending = ""
            if self._fh is not None:
                self._fh.close()
        except Exception:
            pass
        self._fh = None

    def isatty(self) -> bool:
        return False


def log_folder() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "VideoSegmentEditor"


def _redirect_output_if_needed() -> bool:
    """Under pythonw sys.stdout / sys.stderr are None: send them to app.log (timestamped).

    Returns True when the output was redirected (= there is no console)."""
    if sys.stdout is not None and sys.stderr is not None:
        return False
    log = TimestampedLog(log_folder() / "app.log", APP_VER)
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log
    return True


def startup_failure_message(folder) -> str:
    return ("Video Segment Editor could not start. Details are in the file app.log in the "
            f"folder {folder}.")


def should_show_startup_dialog(had_console: bool, environ=None) -> bool:
    environ = os.environ if environ is None else environ
    return not had_console and environ.get("VSE_NO_STARTUP_DIALOG") != "1"


def _native_message_box(text: str, title: str) -> None:
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)   # MB_ICONERROR


def report_startup_failure(redirected: bool, folder, box=None) -> None:
    """After a failed start under pythonw (nobody sees a traceback): ONE native message box.

    Skipped when a console exists or VSE_NO_STARTUP_DIALOG=1. Never raises."""
    try:
        if not should_show_startup_dialog(not redirected):
            return
        (box or _native_message_box)(startup_failure_message(folder), "Video Segment Editor")
    except Exception:
        pass


def _windows_setup() -> None:
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MY.VideoSegmentEditor")
    except Exception:
        pass


def main() -> None:
    redirected = _redirect_output_if_needed()
    _windows_setup()
    try:
        from create_flow import default_work_root, start_sweep
        start_sweep(default_work_root())       # background thread; failures ignored
    except Exception:
        pass
    try:
        from gui import App  # imported after the log redirect so import-time output is kept
        App(APP_VER).mainloop()
    except Exception:
        traceback.print_exc()
        report_startup_failure(redirected, log_folder())
        raise


if __name__ == "__main__":
    main()
