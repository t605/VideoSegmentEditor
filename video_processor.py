"""FFmpeg / FFprobe helpers: tool lookup, probing, naming, commands, verification."""
import errno
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from i18n import t_lang
from segment_manager import Segment

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
MIN_FREE_BYTES = 200 * 1024 * 1024
FFPROBE_TIMEOUT_S = 60
MAX_NAME_UNITS = 240          # longest file name we ever create (NTFS allows 255 per component)
PART_MIN_TOLERANCE_S = 0.25   # a cut part may differ from its segment by max(this, 3 frames)
AV_BASE_TOLERANCE_MS = 100    # |video - audio| in the result: 100 ms + 30 ms per segment
AV_PER_SEGMENT_MS = 30        # (AAC priming adds ~21 ms at every cut)
MAX_VIDEO_START_S = 0.150     # the picture must start within 150 ms of zero
MAX_VIDEO_START_VFR_S = 0.500  # variable-frame-rate sources may legitimately start later
VFR_RATE_DIFFERENCE = 0.002   # avg and nominal frame rate further apart than 0.2 % = variable
                              # (true constant-rate files have equal rates; 2 % missed mild VFR)
FRAME_SLACK = 0.03            # frame-count tolerance (share of the expected frames) for sources
                              # whose two rates differ a little but are not flagged variable
HDR_TRANSFERS = ("smpte2084", "arib-std-b67")   # PQ (HDR10 / Dolby Vision base) and HLG
HDR_TONEMAP = "mobius"        # measured closer to a plain SDR render than "hable" (wp1a2-report)
DEINTERLACE_FILTER = "bwdif=mode=send_frame:parity=auto"   # same frame rate, all frames
MAX_AAC_CHANNELS = 8          # the AAC encoder cannot do more; more channels are downmixed
OUTPUT_SIZE_FACTOR = 1.5      # output size estimate = source slice * 1.5 (high-bitrate sources)


class ProcessingError(Exception):
    """Error with a translation key, ready to show to the user.

    `message_key` is an i18n key (e.g. "err.not_a_video"); `params` fill its {placeholders}.
    str(exc) is always the English text. The GUI shows t(exc.key, **exc.params) in the
    current language. A `kept_dir` param adds the "temporary files were kept" sentence.
    `detail` holds technical text (e.g. the tail of a tool's stderr) for logs only.
    """

    def __init__(self, message_key: str, /, detail: str | None = None, **params):
        # `detail` and `message_key` are constructor names: templates must not use them as
        # {placeholders} (tests/test_i18n.py checks this).
        if "message_key" in params:
            raise ValueError("'message_key' is reserved and cannot be a message parameter")
        super().__init__(t_lang("en", message_key, **params))
        self.key = message_key
        self.params = params
        self.detail = detail or ""


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if packages.is_dir():
            for pkg in packages.glob("*FFmpeg*"):
                dirs.append(pkg)
                dirs.extend(p for p in pkg.glob("*/bin") if p.is_dir())
        dirs.append(Path(local) / "Microsoft" / "WinGet" / "Links")
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            dirs.append(Path(base) / "ffmpeg" / "bin")
            dirs.append(Path(base) / "FFmpeg" / "bin")
    dirs.append(Path("C:/ffmpeg/bin"))
    return dirs


def find_tool(name: str) -> str | None:
    """Find an executable such as ffmpeg or ffprobe; None if not found."""
    found = shutil.which(name)
    if found:
        return found
    exe = name if name.lower().endswith(".exe") else name + ".exe"
    for d in _candidate_dirs():
        candidate = d / exe
        if candidate.is_file():
            return str(candidate)
    return None


@dataclass
class AudioStream:
    index: int            # ffprobe stream index in the source
    channels: int
    sample_rate: int      # 0 when unknown
    language: str | None = None
    title: str | None = None


@dataclass
class VideoInfo:
    path: Path
    duration_ms: int
    width: int
    height: int
    fps: float
    has_audio: bool
    # --- added in WP1a-2; defaults keep older callers and tests working
    pix_fmt: str = ""
    color_transfer: str = ""     # "" when the file does not say (ffprobe "unknown" is dropped)
    color_primaries: str = ""
    color_space: str = ""        # the matrix
    color_range: str = ""
    field_order: str = ""
    audio_streams: list[AudioStream] = field(default_factory=list)
    subtitle_count: int = 0
    vfr: bool = False
    # --- added in fix round 1
    chapter_count: int = 0
    video_lead_s: float = 0.0    # the picture starts this long after the sound (>= 0)
    rate_gap: float = 0.0        # |nominal - average frame rate| / nominal

    @property
    def audio_count(self) -> int:
        """How many audio tracks the output must have (the list, else has_audio as 0/1)."""
        return len(self.audio_streams) if self.audio_streams else int(bool(self.has_audio))

    @property
    def bit_depth(self) -> int:
        m = re.search(r"(\d+)(?:le|be)$", self.pix_fmt)
        return min(int(m.group(1)), 16) if m and int(m.group(1)) >= 9 else 8

    @property
    def is_hdr(self) -> bool:
        return self.color_transfer in HDR_TRANSFERS

    @property
    def is_interlaced(self) -> bool:
        return self.field_order in ("tt", "bb", "tb", "bt")


_LOCKED_RE = re.compile(
    r"permission denied|being used by another process|access is denied"
    r"|\bwinerror\s*(?:32|5)\b|\bwindows error (?:32|5)\b", re.IGNORECASE)


def looks_locked(text: str) -> bool:
    """True when FFmpeg / FFprobe output says the file is locked or access is denied."""
    return bool(_LOCKED_RE.search(text or ""))


def _run_ffprobe_json(ffprobe: str, path: Path) -> dict:
    cmd = [ffprobe, "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", "-show_chapters", str(path)]
    try:
        res = subprocess.run(cmd, creationflags=CREATE_NO_WINDOW, capture_output=True,
                             stdin=subprocess.DEVNULL, timeout=FFPROBE_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise ProcessingError(
            "err.probe_timeout",
            detail=f"ffprobe timed out after {FFPROBE_TIMEOUT_S} s") from exc
    except OSError as exc:
        raise ProcessingError(
            "err.ffprobe_start",
            detail=str(exc)) from exc
    if res.returncode != 0:
        tail = (res.stderr or b"").decode("utf-8", errors="replace").strip()[-300:]
        if looks_locked(tail):
            raise ProcessingError("err.source_locked", detail=tail)
        raise ProcessingError("err.not_a_video", detail=tail)
    try:
        return json.loads(res.stdout.decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise ProcessingError("err.not_a_video") from exc


def _seconds_to_ms(value) -> int | None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    return round(seconds * 1000)


def _parse_fps(text) -> float:
    try:
        num, _, den = str(text).partition("/")
        value = float(num) / float(den) if den else float(num)
        return value if value > 0 else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def _first_stream(data: dict, kind: str) -> dict | None:
    for s in data.get("streams") or []:
        if s.get("codec_type") == kind:
            return s
    return None


def _rotation(video: dict) -> int:
    """Rotation of the picture in degrees (0, 90, 180 or 270), from side data or the tag."""
    raw = None
    for side in video.get("side_data_list") or []:
        if isinstance(side, dict) and side.get("rotation") is not None:
            raw = side["rotation"]
            break
    if raw is None:
        raw = (video.get("tags") or {}).get("rotate")
    try:
        return int(round(float(raw))) % 360
    except (TypeError, ValueError):
        return 0


def _tag(stream: dict, name: str) -> str:
    """A colour property as text; "" for missing, "unknown" or "unspecified"."""
    value = str(stream.get(name) or "").strip().lower()
    return "" if value in ("unknown", "unspecified", "reserved") else value


def _rate_gap(video: dict) -> float:
    nominal = _parse_fps(video.get("r_frame_rate"))
    average = _parse_fps(video.get("avg_frame_rate"))
    return abs(nominal - average) / nominal if nominal and average else 0.0


def _is_vfr(video: dict) -> bool:
    return _rate_gap(video) > VFR_RATE_DIFFERENCE


def _float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _video_lead(data: dict, video: dict) -> float:
    """How long the picture starts after the earliest sound / container start (never < 0)."""
    starts = [_float((data.get("format") or {}).get("start_time"), None)]
    starts += [_float(s.get("start_time"), None) for s in _streams_of(data, "audio")]
    starts = [x for x in starts if x is not None]
    if not starts:
        return 0.0
    return max(0.0, _float(video.get("start_time")) - min(starts))


def lead_inside(seg: Segment, lead_s: float) -> float:
    """Seconds at the start of `seg` that have no picture because the source's picture only
    begins `lead_s` after its sound (FFmpeg starts the part where the picture starts)."""
    return max(0.0, min(lead_s - seg.start_ms / 1000.0, seg.duration_ms / 1000.0))


def _audio_streams(data: dict) -> list[AudioStream]:
    result = []
    for s in data.get("streams") or []:
        if s.get("codec_type") != "audio":
            continue
        tags = s.get("tags") or {}
        try:
            channels = int(s.get("channels") or 0)
        except (TypeError, ValueError):
            channels = 0
        try:
            rate = int(s.get("sample_rate") or 0)
        except (TypeError, ValueError):
            rate = 0
        try:
            index = int(s.get("index"))
        except (TypeError, ValueError):
            index = len(result)
        result.append(AudioStream(index, channels, rate, tags.get("language"), tags.get("title")))
    return result


def probe(path: Path, ffprobe: str) -> VideoInfo:
    try:
        data = _run_ffprobe_json(ffprobe, path)
    except ProcessingError as exc:
        if exc.key == "err.not_a_video" and not Path(path).exists():
            raise ProcessingError("err.source_missing", detail=exc.detail) from exc
        raise
    video = _first_stream(data, "video")
    if video is None:
        raise ProcessingError("err.not_a_video")
    fmt = data.get("format") or {}
    duration = _seconds_to_ms(fmt.get("duration"))
    if duration is not None and "matroska" in str(fmt.get("format_name") or ""):
        # Matroska reports the END time as its duration, so content that starts at 1.0 s
        # looks 1 s too long (other containers, e.g. MPEG-TS, already report end - start).
        offset = _seconds_to_ms(fmt.get("start_time"))
        if offset and duration > offset:
            duration -= offset
    if duration is None:
        duration = _seconds_to_ms(video.get("duration"))
    if duration is None:
        raise ProcessingError("err.not_a_video")
    fps = _parse_fps(video.get("avg_frame_rate")) or _parse_fps(video.get("r_frame_rate"))
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    if _rotation(video) in (90, 270):  # report the size the video is played at
        width, height = height, width
    return VideoInfo(
        path=Path(path),
        duration_ms=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio=_first_stream(data, "audio") is not None,
        pix_fmt=str(video.get("pix_fmt") or ""),
        color_transfer=_tag(video, "color_transfer"),
        color_primaries=_tag(video, "color_primaries"),
        color_space=_tag(video, "color_space"),
        color_range=_tag(video, "color_range"),
        field_order=_tag(video, "field_order"),
        audio_streams=_audio_streams(data),
        subtitle_count=sum(1 for st in data.get("streams") or []
                           if st.get("codec_type") == "subtitle"),
        vfr=_is_vfr(video),
        chapter_count=len(data.get("chapters") or []),
        video_lead_s=_video_lead(data, video),
        rate_gap=_rate_gap(video),
    )


def _units(text: str) -> int:
    """Length in UTF-16 code units (what NTFS counts against its 255 limit)."""
    return len(text.encode("utf-16-le", errors="surrogatepass")) // 2


def _output_stem(stem: str) -> str:
    """Source stem shortened so that `<stem> (segmented 99).mp4.part` is at most 240 units."""
    room = MAX_NAME_UNITS - _units(" (segmented 99).mp4.part")
    if _units(stem) <= room:
        return stem
    kept = []
    used = 0
    for ch in stem:
        w = _units(ch)
        if used + w > room:
            break
        kept.append(ch)
        used += w
    return "".join(kept).rstrip(" .") or "video"


def unique_output_path(source: Path) -> Path:
    """<stem> (segmented).mp4, then (segmented 2), (segmented 3)... in the source folder.

    A very long source name is shortened in the OUTPUT name only (see _output_stem).
    """
    source = Path(source)
    stem = _output_stem(source.stem)
    first = source.with_name(f"{stem} (segmented).mp4")
    if not first.exists():
        return first
    n = 2
    while True:
        candidate = source.with_name(f"{stem} (segmented {n}).mp4")
        if not candidate.exists():
            return candidate
        n += 1


def _sec(ms: int) -> str:
    whole, milli = divmod(int(ms), 1000)
    return f"{whole}.{milli:03d}"


def keyframe_interval(fps: float) -> int:
    """libx264 -g value: a keyframe about every 2 s (25..120 frames); 50 when fps is unknown."""
    if not fps or fps <= 0:
        return 50
    return max(25, min(120, round(2 * fps)))


# Colour tags we keep when a source states them (anything else is replaced by the default).
_SENSIBLE_PRIMARIES = ("bt709", "bt470bg", "smpte170m", "smpte240m", "bt2020")
_SENSIBLE_TRANSFERS = ("bt709", "smpte170m", "smpte240m", "bt470bg", "bt470m", "gamma22",
                       "gamma28", "iec61966-2-1", "bt2020-10", "bt2020-12")
_SENSIBLE_MATRICES = ("bt709", "smpte170m", "bt470bg", "smpte240m", "bt2020nc", "bt2020c", "fcc")


def output_color_tags(info: VideoInfo) -> dict[str, str]:
    """Colour tags for the output file: primaries, transfer, matrix, range.

    HDR sources are tone mapped to SDR, so they are always tagged BT.709, limited range.
    Other sources keep each of their own tags that is present and sensible. A missing or odd
    tag is filled so that the three stay consistent: from the source's matrix when that is
    sensible (a BT.2020 matrix gives BT.2020 primaries and transfer), else by the usual player
    guess for the picture size: height >= 720 means BT.709, below 720 means SMPTE 170M
    (BT.601). The range is always limited ("tv"), because the picture is converted to
    limited-range 8-bit 4:2:0 (see video_filter_chain).
    """
    if info.is_hdr:
        return {"primaries": "bt709", "transfer": "bt709", "matrix": "bt709", "range": "tv"}
    size_default = "bt709" if info.height >= 720 else "smpte170m"
    family = info.color_space if info.color_space in _SENSIBLE_MATRICES else size_default
    fill = {"bt2020nc": ("bt2020", "bt2020-10"), "bt2020c": ("bt2020", "bt2020-10"),
            "bt470bg": ("bt470bg", "smpte170m"), "fcc": ("smpte170m", "smpte170m")
            }.get(family, (family, family))
    return {
        "primaries": info.color_primaries if info.color_primaries in _SENSIBLE_PRIMARIES
        else fill[0],
        "transfer": info.color_transfer if info.color_transfer in _SENSIBLE_TRANSFERS
        else fill[1],
        "matrix": family,
        "range": "tv",
    }


def color_tag_filter(info: VideoInfo) -> str:
    """setparams filter that writes output_color_tags into the picture (the last filter)."""
    tags = output_color_tags(info)
    return (f"setparams=color_primaries={tags['primaries']}:color_trc={tags['transfer']}"
            f":colorspace={tags['matrix']}:range={tags['range']}")


def _hdr_chain(info: VideoInfo) -> list[str]:
    """Tone map PQ / HLG to BT.709 SDR (linear light, float RGB, tone map, back to 8-bit).

    The mastering-display and MaxCLL side data are deleted first: x264 would otherwise
    write them into the SDR file.
    """
    primaries = info.color_primaries or "bt2020"
    # zscale rejects "bt2020c" (constant luminance); bt2020nc is the practical choice
    matrix = "bt709" if info.color_space == "bt709" else "bt2020nc"
    rng = info.color_range if info.color_range in ("tv", "pc") else "tv"
    return [
        "sidedata=mode=delete:type=MASTERING_DISPLAY_METADATA",
        "sidedata=mode=delete:type=CONTENT_LIGHT_LEVEL",
        f"zscale=tin={info.color_transfer}:pin={primaries}:min={matrix}:rin={rng}"
        ":t=linear:npl=100",
        "format=gbrpf32le",
        "zscale=p=bt709",
        # known limit: no peak is passed (MaxCLL does not reach tonemap), so the default 1000 nit
        # is assumed and highlights of brighter masters clip
        f"tonemap=tonemap={HDR_TONEMAP}:desat=0",
        "zscale=t=bt709:m=bt709:r=tv",
        "format=yuv420p",
    ]


def _sdr_convert_chain(info: VideoInfo) -> list[str]:
    """Bring a non-HDR picture to limited-range 8-bit 4:2:0, or [] when it already is."""
    fmt = info.pix_fmt
    full_range = info.color_range == "pc" or fmt.startswith("yuvj")
    if not fmt or (fmt == "yuv420p" and not full_range):
        return []
    opts = ["out_range=tv"]
    if fmt.startswith(("gbr", "rgb", "bgr")):  # RGB has no matrix of its own: pick the tagged one
        opts.append("out_color_matrix=" + ("bt709" if info.height >= 720 else "smpte170m"))
    opts.append("sws_dither=ed")               # error diffusion when going from 10 to 8 bits
    return ["scale=" + ":".join(opts), "format=yuv420p"]


def video_filter_chain(info: VideoInfo) -> list[str]:
    """The -vf filters for one segment, in this order:

    1. deinterlace (interlaced sources only, same frame rate),
    2. crop to even width and height (libx264 + yuv420p need even sizes, SAR is kept),
    3. HDR tone mapping, or the SDR colour-format conversion (10-bit, 4:4:4, RGB, full range).

    The crop must come BEFORE the conversion, not after it: measured with FFmpeg 9.0.1, zscale
    refuses odd sizes when it outputs 4:2:0 ("image dimensions must be divisible by
    subsampling factor"), so the HDR chain would fail on an odd-sized source.
    """
    chain: list[str] = []
    if info.is_interlaced:
        chain.append(DEINTERLACE_FILTER)
    if info.width % 2 or info.height % 2:
        chain.append("crop=trunc(iw/2)*2:trunc(ih/2)*2")
    chain += _hdr_chain(info) if info.is_hdr else _sdr_convert_chain(info)
    return chain


def audio_bitrate_k(channels: int) -> int:
    """AAC bitrate in kbit/s by channel count: mono 96, stereo 192, 5.1 384, 7.1 512,
    anything else 64 per channel (at most 512); unknown (0) gets the stereo value."""
    fixed = {1: 96, 2: 192, 6: 384, 8: 512}
    if channels in fixed:
        return fixed[channels]
    if channels <= 0:
        return 192
    return min(512, 64 * channels)


def extract_cmd(ffmpeg: str, source: Path, seg: Segment, out: Path, info: VideoInfo) -> list[str]:
    """Accurate-seek extract of one segment, always re-encoded (all audio tracks kept)."""
    cmd = [
        ffmpeg, "-hide_banner", "-nostdin", "-n",
        "-ss", _sec(seg.start_ms), "-i", str(source), "-t", _sec(seg.duration_ms),
        "-map", "0:v:0",
    ]
    streams = info.audio_streams
    if streams:
        for k in range(len(streams)):
            cmd += ["-map", f"0:a:{k}"]
    elif info.has_audio:
        cmd += ["-map", "0:a:0?"]
    # The colour tags go in as the last filter. The -color_primaries / -color_trc encoder
    # options were measured to be ignored by libx264 in FFmpeg 9.0.1 (the file came out
    # "unknown"); frame properties set by setparams are what the encoder writes.
    cmd += ["-vf", ",".join(video_filter_chain(info) + [color_tag_filter(info)])]
    cmd += [
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-g", str(keyframe_interval(info.fps)),
    ]
    if streams or info.has_audio:
        # apad: a track shorter than the cut is padded with silence (-t cuts it), so that every
        # track stays in the part; without it the AAC encoder never opens an empty track
        cmd += ["-af", "apad"]
    if streams:
        cmd += ["-c:a", "aac"]
        for k, a in enumerate(streams):
            cmd += [f"-b:a:{k}", f"{audio_bitrate_k(a.channels)}k"]
            if a.channels > MAX_AAC_CHANNELS:
                cmd += [f"-ac:a:{k}", str(MAX_AAC_CHANNELS)]
    elif info.has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += [
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        str(out),
    ]
    return cmd


def concat_cmd(ffmpeg: str, list_file: Path, out: Path,
               audio_streams: list[AudioStream] | tuple = ()) -> list[str]:
    """Join the parts without re-encoding, keeping every stream (-map 0).

    The concat demuxer drops the stream titles, so they are written again from the source's
    audio list (languages survive on their own).
    """
    cmd = [
        ffmpeg, "-hide_banner", "-nostdin", "-n",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-map", "0", "-c", "copy", "-movflags", "+faststart",
    ]
    for k, a in enumerate(audio_streams):
        if a.title:
            cmd += [f"-metadata:s:a:{k}", f"title={a.title}"]
    cmd.append(str(out))
    return cmd


def write_concat_list(parts: list[Path], list_file: Path) -> None:
    lines = []
    for p in parts:
        escaped = str(p).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    Path(list_file).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _stream_seconds(stream: dict | None) -> float | None:
    if stream is None:
        return None
    try:
        value = float(stream.get("duration"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _streams_of(data: dict, kind: str) -> list[dict]:
    return [s for s in data.get("streams") or [] if s.get("codec_type") == kind]


def part_problem(part: Path, seg: Segment, had_audio: bool | int, fps: float,
                 ffprobe: str, lead_s: float = 0.0) -> str | None:
    """Check one freshly cut part. Returns None when it is fine, else a short English reason.

    `had_audio` is the number of audio tracks the source has (True counts as 1). `lead_s` is
    the source's picture lead (VideoInfo.video_lead_s): a segment that begins before it has
    that much less picture.

    FFmpeg can exit 0 and leave a header-only file ("Output file is empty") when the source
    holds less data than its header claims, so the part itself is probed.
    """
    try:
        data = _run_ffprobe_json(ffprobe, part)
    except ProcessingError as exc:
        return f"the part cannot be read ({exc.key})"
    video = _first_stream(data, "video")
    if video is None:
        return "no video stream"
    want_audio = int(had_audio)
    have_audio = len(_streams_of(data, "audio"))
    if want_audio and have_audio == 0:
        return "no audio stream"
    if have_audio != want_audio:
        return f"{have_audio} audio streams instead of {want_audio}"
    actual = _stream_seconds(video)
    if actual is None:
        ms = _seconds_to_ms((data.get("format") or {}).get("duration"))
        actual = None if ms is None else ms / 1000.0
    if actual is None:
        return "no readable duration"
    frame = 1.0 / (fps if fps and fps > 0 else 25.0)
    tolerance = max(PART_MIN_TOLERANCE_S, 3 * frame)
    wanted = seg.duration_ms / 1000.0 - lead_inside(seg, lead_s)
    if abs(actual - wanted) > tolerance + 1e-9:
        return f"video length {actual:.3f} s instead of {wanted:.3f} s"
    return None


def _frame_count(video: dict) -> int | None:
    try:
        count = int(video.get("nb_frames"))
        if count > 0:
            return count
    except (TypeError, ValueError):
        pass
    seconds = _stream_seconds(video)
    rate = _parse_fps(video.get("avg_frame_rate")) or _parse_fps(video.get("r_frame_rate"))
    if seconds is None or not rate:
        return None
    return round(seconds * rate)


def verify_output(out: Path, expected_ms: int, n_segments: int, had_audio: bool | int,
                  ffprobe: str, fps: float = 0.0, vfr: bool = False, lead_s: float = 0.0,
                  frame_slack: float = 0.0) -> None:
    """Final checks of the merged file.

    `had_audio` is the number of audio tracks the source has (True counts as 1): the result
    must have exactly that many. `fps` (of the source) enables the frame-count check.
    `vfr` marks a variable-frame-rate source: no frame-count check, and the picture may start
    up to 500 ms after zero instead of 150 ms. `lead_s` (picture lead of the source that falls
    inside the first segment) widens that start limit; `expected_ms` must already exclude it.
    `frame_slack` is an extra frame-count tolerance as a share of the expected frames.
    """
    out = Path(out)
    if not out.is_file():
        raise ProcessingError("err.out_missing")
    if out.stat().st_size <= 0:
        raise ProcessingError("err.out_empty")
    data = _run_ffprobe_json(ffprobe, out)
    video = _first_stream(data, "video")
    if video is None:
        raise ProcessingError("err.out_no_picture")
    audios = _streams_of(data, "audio")
    want_audio = int(had_audio)
    if want_audio and not audios:
        raise ProcessingError("err.out_no_sound")
    if len(audios) != want_audio:
        raise ProcessingError("err.out_audio_count", actual=len(audios), expected=want_audio)
    actual = _seconds_to_ms((data.get("format") or {}).get("duration"))
    if actual is None:
        actual = _seconds_to_ms(video.get("duration"))
    if actual is None:
        raise ProcessingError("err.out_length_unreadable")
    # picture and sound must END together (AAC priming adds ~21 ms per cut). The END time
    # (start + duration) is compared, not the durations: a stream that starts late is shorter
    # but still ends in time.
    v_sec = _stream_seconds(video)
    v_end = _float(video.get("start_time")) + (v_sec or 0.0)
    allowed = (AV_BASE_TOLERANCE_MS + AV_PER_SEGMENT_MS * n_segments) / 1000.0
    for audio in audios:                       # every audio track, same tolerance
        a_sec = _stream_seconds(audio)
        if v_sec is None or a_sec is None:
            continue
        a_end = _float(audio.get("start_time")) + a_sec
        if abs(v_end - a_end) > allowed + 1e-9:
            raise ProcessingError("err.out_av_mismatch", video=f"{v_sec:.1f}",
                                  audio=f"{a_sec:.1f}")
    try:
        start = float(video.get("start_time"))
    except (TypeError, ValueError):
        start = 0.0
    if start > (MAX_VIDEO_START_VFR_S if vfr else MAX_VIDEO_START_S) + lead_s:
        raise ProcessingError("err.out_start_offset", offset=f"{start:.1f}")
    if fps and fps > 0 and not vfr:
        expected_frames = round(expected_ms / 1000.0 * fps)
        frames = _frame_count(video)
        if frames is not None and abs(frames - expected_frames) > (
                n_segments + frame_slack * expected_frames):
            raise ProcessingError("err.out_frames_wrong", actual=frames,
                                  expected=expected_frames)
    tolerance = 500 + 100 * n_segments
    if abs(actual - expected_ms) > tolerance:
        raise ProcessingError("err.out_wrong_length", actual=f"{actual / 1000:.1f}",
                              expected=f"{expected_ms / 1000:.1f}")


def estimate_output_bytes(source_size: int, selected_ms: int, total_ms: int) -> int:
    """Rough size of the finished video: the source slice * 1.5 (high-bitrate sources)."""
    if total_ms <= 0:
        return 0
    return int(source_size * selected_ms / total_ms * OUTPUT_SIZE_FACTOR)


def _drive_label(folder) -> str:
    """The drive of a folder for messages: 'C:' (or the share name for a network folder)."""
    try:
        drive = os.path.splitdrive(os.path.abspath(str(folder)))[0]
    except (OSError, ValueError):
        drive = ""
    return drive or str(folder)


def _require_free(folder: Path, needed: float) -> None:
    try:
        free = shutil.disk_usage(folder).free
    except OSError as exc:
        raise ProcessingError("err.disk_check", detail=str(exc)) from exc
    if free < needed:
        raise ProcessingError("err.disk_low", drive=_drive_label(folder),
                              needed=f"{needed / 1024**2:.0f}", free=f"{free / 1024**2:.0f}")


def check_disk_space(out_dir: Path, source_size: int, selected_ms: int, total_ms: int) -> None:
    """Single-folder check: room for the parts and the merged file (2 x the estimate)."""
    estimate = estimate_output_bytes(source_size, selected_ms, total_ms)
    _require_free(out_dir, max(MIN_FREE_BYTES, 2 * estimate))


def _same_volume(a: Path, b: Path) -> bool:
    """True when both folders are on the same drive (drive letter / UNC share, else st_dev)."""
    drive_a = os.path.splitdrive(os.path.abspath(a))[0]
    drive_b = os.path.splitdrive(os.path.abspath(b))[0]
    if drive_a or drive_b:
        return drive_a.lower() == drive_b.lower()

    def dev(p):
        p = Path(os.path.abspath(p))
        while True:  # the folder may not exist yet: use the nearest existing parent
            try:
                return os.stat(p).st_dev
            except OSError:
                if p.parent == p:
                    return None
                p = p.parent
    da, db = dev(a), dev(b)
    return da is not None and da == db


def check_job_disk_space(out_dir: Path, work_dir: Path, source_size: int, selected_ms: int,
                         total_ms: int) -> None:
    """Free-space check for the whole job.

    estimate = source slice * 1.5. The work folder holds the parts and the merged file
    (2 x estimate), the output folder gets one more copy (1 x estimate). On the same drive
    the two needs add up. Both keep the 200 MB floor.
    """
    estimate = estimate_output_bytes(source_size, selected_ms, total_ms)
    work_need = max(MIN_FREE_BYTES, 2 * estimate)
    out_need = max(MIN_FREE_BYTES, estimate)
    if _same_volume(out_dir, work_dir):
        _require_free(out_dir, work_need + out_need)
    else:
        _require_free(out_dir, out_need)
        _require_free(work_dir, work_need)


class Cancelled(Exception):
    """Raised by VideoJob.run() after cancel(); the temp folder is kept.

    Like ProcessingError: `key` / `params` for the GUI, str(exc) is English.
    """

    def __init__(self, message_key: str = "err.cancelled", /, **params):
        if "message_key" in params:
            raise ValueError("'message_key' is reserved and cannot be a message parameter")
        super().__init__(t_lang("en", message_key, **params))
        self.key = message_key
        self.params = params


EXTRACT_SHARE = 95.0   # percent of the bar used by extraction
MERGE_END = 99.0       # merge fills EXTRACT_SHARE..MERGE_END, verify the rest


def _tail(path: Path) -> str:
    try:
        return Path(path).read_bytes()[-300:].decode("utf-8", errors="replace").strip()
    except OSError:
        return ""


def _check_writable(folder: Path) -> None:
    """Fail early (before any encoding) if the output folder cannot be written to."""
    try:
        fd, name = tempfile.mkstemp(prefix=".vse_probe_", dir=folder)
        os.close(fd)
        os.unlink(name)
    except OSError as exc:
        raise ProcessingError("err.folder_readonly",
                              detail=str(exc)) from exc


class VideoJob:
    """Cut the segments, join them and save the result next to the source."""

    def __init__(self, source: Path, info: VideoInfo, segments: list[Segment], ffmpeg: str,
                 ffprobe: str, progress: Callable[[dict], None], work_root: Path):
        self.source = Path(source)
        self.info = info
        self.segments = list(segments)
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.progress = progress
        self.work_root = Path(work_root)
        self._cancel = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._work_dir: Path | None = None
        self.part_path: Path | None = None   # the <name>.part being written by _finalize
        self._reading_source = False         # True while FFmpeg cuts a part from the source

    def discard_part(self) -> None:
        """Best-effort removal of a leftover .part file (used when the window closed early)."""
        part = self.part_path
        if part is not None:
            try:
                part.unlink()
            except OSError:
                pass

    def cancel(self) -> None:
        self._cancel.set()
        with self._lock:
            proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def _emit(self, phase, segment, percent, key, **params):
        """Progress event. `message` is English; `key` / `params` let the GUI translate it."""
        self.progress({"phase": phase, "segment": segment, "total": len(self.segments),
                       "percent": round(min(100.0, max(0.0, percent)), 1),
                       "message": t_lang("en", key, **params), "key": key, "params": params})

    def _kept_params(self) -> dict:
        return {} if self._work_dir is None else {"kept_dir": str(self._work_dir)}

    def _check_cancel(self):
        if self._cancel.is_set():
            raise Cancelled("err.cancelled", **self._kept_params())

    def _fail(self, message_key: str, detail: str = "", **params) -> ProcessingError:
        merged = {**params, **self._kept_params()}  # kept_dir of this job wins
        return ProcessingError(message_key, detail, **merged)

    def _run_ffmpeg(self, cmd: list[str], err_file: Path,
                    on_time: Callable[[float], None] | None) -> None:
        """Run one FFmpeg command; raise on failure or cancel.

        While `self._reading_source` is set (the extract step, the only one that reads the
        source) a failure is reported as "source missing" or "source locked" when FFmpeg's
        message says so."""
        source_stage = self._reading_source
        full = cmd[:-1] + ["-progress", "pipe:1", "-nostats", cmd[-1]]
        with open(err_file, "wb") as err:
            proc = subprocess.Popen(full, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=err, creationflags=CREATE_NO_WINDOW)
            with self._lock:
                self._proc = proc
            try:
                if self._cancel.is_set():
                    proc.terminate()
                for raw in proc.stdout:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if on_time and line.startswith("out_time_ms="):
                        try:
                            # despite the name, FFmpeg reports microseconds here
                            on_time(max(0, int(line.split("=", 1)[1])) / 1000.0)
                        except ValueError:
                            pass
                code = proc.wait()
            finally:
                with self._lock:
                    self._proc = None
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                proc.stdout.close()
        self._check_cancel()
        if code != 0:
            tail = _tail(err_file)
            if source_stage and not self.source.exists():
                raise self._fail("err.source_missing", tail)
            if source_stage and looks_locked(tail):
                raise self._fail("err.source_locked", tail)
            raise self._fail("err.ffmpeg_failed", tail)

    def run(self) -> Path:
        if not self.segments:
            raise ProcessingError("err.empty_list")
        selected = sum(s.duration_ms for s in self.segments)
        try:
            out_path = unique_output_path(self.source)
            try:
                source_size = self.source.stat().st_size
            except FileNotFoundError as exc:
                raise ProcessingError("err.source_missing", detail=str(exc)) from exc
            except OSError as exc:
                raise ProcessingError("err.source_unopenable", detail=str(exc)) from exc
            _check_writable(out_path.parent)
            self.work_root.mkdir(parents=True, exist_ok=True)
            check_job_disk_space(out_path.parent, self.work_root, source_size, selected,
                                 self.info.duration_ms)
            self._work_dir = Path(tempfile.mkdtemp(prefix="job_", dir=self.work_root))
            return self._run_in(self._work_dir, out_path, selected)
        except (Cancelled, ProcessingError):
            raise
        except PermissionError as exc:
            raise self._fail("err.windows_denied", str(exc)) from exc
        except OSError as exc:
            if exc.errno == errno.ENOSPC:
                raise self._fail("err.disk_full", str(exc)) from exc
            raise self._fail("err.file_problem", str(exc)) from exc

    def _finalize(self, merged: Path, out_path: Path) -> Path:
        """Copy to <name>.part beside the source, then rename without ever overwriting."""
        part = out_path.with_name(out_path.name + ".part")
        self.part_path = part
        try:
            shutil.copyfile(merged, part)
            while True:
                try:
                    os.rename(part, out_path)  # fails if the target exists (Windows)
                    return out_path
                except FileExistsError:
                    out_path = unique_output_path(self.source)
                    if out_path.with_name(out_path.name + ".part") != part:
                        new_part = out_path.with_name(out_path.name + ".part")
                        os.rename(part, new_part)
                        part = new_part
                        self.part_path = part
        except PermissionError as exc:
            raise self._fail("err.save_denied", str(exc)) from exc
        except OSError as exc:
            msg = ("err.save_disk_full" if exc.errno == errno.ENOSPC
                   else "err.save_failed")
            raise self._fail(msg, str(exc)) from exc
        finally:
            try:
                if part.exists():
                    part.unlink()
            except OSError:
                pass

    def _run_in(self, work: Path, out_path: Path, selected: int) -> Path:
        n = len(self.segments)
        parts: list[Path] = []
        done_ms = 0
        for i, seg in enumerate(self.segments, start=1):
            self._check_cancel()
            part = work / f"seg_{i:03d}.mp4"
            parts.append(part)
            base = done_ms
            self._emit("extract", i, EXTRACT_SHARE * base / selected,
                       "progress.cut", i=i, n=n)

            def on_time(ms, i=i, base=base, seg=seg):
                ms = min(ms, seg.duration_ms)
                self._emit("extract", i, EXTRACT_SHARE * (base + ms) / selected,
                           "progress.cut", i=i, n=n)

            log = work / f"seg_{i:03d}.log"
            self._reading_source = True
            try:
                self._run_ffmpeg(extract_cmd(self.ffmpeg, self.source, seg, part, self.info),
                                 log, on_time)
            finally:
                self._reading_source = False
            if not part.is_file() or part.stat().st_size <= 0:
                raise self._fail("err.segment_empty", _tail(log), i=i)
            problem = part_problem(part, seg, self.info.audio_count, self.info.fps,
                                   self.ffprobe, lead_s=self.info.video_lead_s)
            if problem is not None:
                raise self._fail("err.part_invalid", problem, i=i, n=n)
            done_ms += seg.duration_ms
            self._emit("extract", i, EXTRACT_SHARE * done_ms / selected,
                       "progress.cut_done", i=i, n=n)
        self._check_cancel()
        list_file = work / "parts.txt"
        write_concat_list(parts, list_file)
        merged = work / "merged.mp4"
        self._emit("merge", n, EXTRACT_SHARE, "progress.join")
        self._run_ffmpeg(concat_cmd(self.ffmpeg, list_file, merged, self.info.audio_streams),
                         work / "merge.log", None)
        self._check_cancel()
        self._emit("verify", n, MERGE_END, "progress.verify")
        try:
            lead = self.info.video_lead_s
            no_picture = sum(lead_inside(s, lead) for s in self.segments)
            verify_output(merged, selected - round(no_picture * 1000), n,
                          self.info.audio_count, self.ffprobe, fps=self.info.fps,
                          vfr=self.info.vfr, lead_s=lead_inside(self.segments[0], lead),
                          frame_slack=FRAME_SLACK if self.info.rate_gap > 1e-4 else 0.0)
        except ProcessingError as exc:
            raise self._fail(exc.key, exc.detail, **exc.params) from exc
        self._check_cancel()
        out_path = self._finalize(merged, out_path)
        shutil.rmtree(work, ignore_errors=True)
        self._emit("done", n, 100.0, "progress.done")
        return out_path
