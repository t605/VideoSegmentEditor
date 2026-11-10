"""Segment list logic and time helpers (no GUI, no FFmpeg).

Errors are keyed: SegmentError and TimeError carry .key (an i18n key from i18n.py) and
.params; str(exc) is always the English text, the GUI shows t(exc.key, **exc.params).
"""
import re
from dataclasses import dataclass

from i18n import t_lang


class KeyedError(ValueError):
    """ValueError with an i18n key and parameters (same pattern as ProcessingError)."""

    def __init__(self, message_key: str, /, **params):
        # 'message_key' and 'detail' are reserved: templates must not use them as placeholders.
        for reserved in ("message_key", "detail"):
            if reserved in params:
                raise ValueError(f"{reserved!r} is reserved and cannot be a message parameter")
        super().__init__(t_lang("en", message_key, **params))
        self.key = message_key
        self.params = params


class SegmentError(KeyedError):
    pass


class TimeError(KeyedError):
    """A time text could not be understood (raised by parse_time)."""


def format_ms(ms: int) -> str:
    """Format integer milliseconds as HH:MM:SS.mmm."""
    ms = int(ms)
    if ms < 0:
        raise TimeError("err.time_negative")
    total_s, milli = divmod(ms, 1000)
    total_m, s = divmod(total_s, 60)
    h, m = divmod(total_m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


_NUM = re.compile(r"^\d+(\.\d{1,3})?$", re.ASCII)
_WHOLE = re.compile(r"^\d+$", re.ASCII)


def parse_time(text: str) -> int:
    """Parse HH:MM:SS.mmm, MM:SS, MM:SS.m or SS into milliseconds."""
    if text is None or not str(text).strip():
        raise TimeError("err.time_empty")
    shown = str(text)
    parts = shown.strip().split(":")
    if len(parts) > 3:
        raise TimeError("err.time_invalid", text=shown)
    *lead, sec = parts
    if not _NUM.match(sec) or not all(_WHOLE.match(p) for p in lead):
        raise TimeError("err.time_invalid", text=shown)
    if lead and float(sec) >= 60:
        raise TimeError("err.time_seconds", text=shown)
    if len(lead) == 2 and int(lead[1]) >= 60:
        raise TimeError("err.time_minutes", text=shown)
    whole, _, frac = sec.partition(".")
    ms = int(whole) * 1000 + (int(frac.ljust(3, "0")) if frac else 0)
    for unit, p in zip((60000, 3600000), reversed(lead)):
        ms += int(p) * unit
    return ms


@dataclass
class Segment:
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class SegmentList:
    def __init__(self, duration_ms: int, max_segments: int = 10):
        self.duration_ms = duration_ms
        self.max_segments = max_segments
        self.items: list[Segment] = []

    def _check(self, start_ms: int, end_ms: int) -> None:
        if start_ms < 0:
            raise SegmentError("err.seg_start_negative")
        if end_ms <= start_ms:
            raise SegmentError("err.seg_end_not_after")
        if end_ms > self.duration_ms:
            raise SegmentError("err.seg_past_end", duration=format_ms(self.duration_ms))

    def _check_index(self, index: int) -> None:
        if not (isinstance(index, int) and 0 <= index < len(self.items)):
            raise SegmentError("err.seg_bad_index")

    def _check_room(self) -> None:
        if self.is_full():
            raise SegmentError("err.seg_max", max=self.max_segments)

    def is_full(self) -> bool:
        return len(self.items) >= self.max_segments

    def add(self, start_ms: int, end_ms: int) -> Segment:
        self._check_room()
        self._check(start_ms, end_ms)
        seg = Segment(start_ms, end_ms)
        self.items.append(seg)
        return seg

    def add_text(self, start_text: str, end_text: str) -> Segment:
        """Add a segment typed as text (any form parse_time accepts)."""
        self._check_room()
        return self.add(parse_time(start_text), parse_time(end_text))

    def edit(self, index: int, start_ms: int, end_ms: int) -> None:
        self._check_index(index)
        self._check(start_ms, end_ms)
        seg = self.items[index]
        seg.start_ms, seg.end_ms = start_ms, end_ms

    def edit_text(self, index: int, start_text: str, end_text: str) -> None:
        self._check_index(index)
        self.edit(index, parse_time(start_text), parse_time(end_text))

    def delete(self, index: int) -> None:
        self._check_index(index)
        del self.items[index]

    def clear(self) -> None:
        self.items.clear()

    def move(self, index: int, delta: int) -> int:
        """Move a segment up (delta -1) or down (+1); returns its new index."""
        self._check_index(index)
        new = index + delta
        if not 0 <= new < len(self.items):
            return index
        self.items[index], self.items[new] = self.items[new], self.items[index]
        return new

    def total_ms(self) -> int:
        return sum(s.duration_ms for s in self.items)

    def __len__(self) -> int:
        return len(self.items)


class Marker:
    """The pending Mark Start / Mark End state (pure logic, used by the GUI)."""

    def __init__(self) -> None:
        self.start_ms: int | None = None

    def mark_start(self, ms: int, segments: SegmentList) -> None:
        if segments.is_full():
            raise SegmentError("err.seg_max", max=segments.max_segments)
        if ms < 0:
            raise SegmentError("err.seg_start_negative")
        if ms >= segments.duration_ms:
            raise SegmentError("err.seg_start_late", duration=format_ms(segments.duration_ms))
        self.start_ms = int(ms)

    def mark_end(self, ms: int, segments: SegmentList) -> Segment:
        """Add start..ms as a segment. On any error the start mark is kept."""
        if self.start_ms is None:
            raise SegmentError("err.no_start")
        seg = segments.add(self.start_ms, int(ms))
        self.start_ms = None
        return seg

    def clear(self) -> None:
        self.start_ms = None
