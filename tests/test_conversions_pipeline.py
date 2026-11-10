"""Integration tests for WP1a-2 (media conversions). They need real FFmpeg and skip without it.

Every clip is generated into a temp folder. HDR clips are made by converting the SDR test
picture to PQ / HLG with zscale, so the tone-mapped result can be compared with the SDR original.
"""
import json
import os
import shutil
import statistics
import subprocess
import tempfile
import unittest
from pathlib import Path

import video_processor as vp
from segment_manager import Segment
from video_processor import VideoJob, find_tool, probe

FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")
SKIP = "FFmpeg not found"
HAS_HDR_TOOLS = False
if FFMPEG:
    _filters = subprocess.run([FFMPEG, "-hide_banner", "-filters"], capture_output=True,
                              stdin=subprocess.DEVNULL, creationflags=vp.CREATE_NO_WINDOW
                              ).stdout.decode("utf-8", "replace")
    HAS_HDR_TOOLS = all(f" {name} " in _filters for name in ("zscale", "tonemap", "bwdif"))
REAL_VFR = Path(os.environ.get("VSE_REAL_VFR_CLIP", ""))   # optional real clip, see the test

MASTERING = ("master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)"
             "L(10000000,1):max-cll=1000,400")


BT709_TAGS = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"


def run(cmd):
    return subprocess.run(cmd, check=True, creationflags=vp.CREATE_NO_WINDOW,
                          stdin=subprocess.DEVNULL, capture_output=True)


def ff(*args):
    return run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args])


def src(seconds, size="640x360", rate=25):
    return ["-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={seconds}"]


def sine(seconds, freq=440):
    return ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}"]


def jprobe(path, *extra):
    return json.loads(run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format",
                           "-show_streams", *extra, str(path)]).stdout)


def vstream(data):
    return next(s for s in data["streams"] if s["codec_type"] == "video")


def astreams(data):
    return [s for s in data["streams"] if s["codec_type"] == "audio"]


def luma_stats(path, at=0.5):
    """(mean, standard deviation) of the 8-bit luma plane of one frame."""
    raw = run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(path),
               "-frames:v", "1", "-vf", "format=gray", "-f", "rawvideo", "-"]).stdout
    return statistics.mean(raw), statistics.pstdev(raw)


def frame_side_data(path):
    data = json.loads(run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_frames",
                           "-read_intervals", "%+#1", "-print_format", "json", str(path)]).stdout)
    names = []
    for frame in data.get("frames", []):
        names += [d.get("side_data_type", "") for d in frame.get("side_data_list", [])]
    return names


@unittest.skipIf(FFMPEG is None or FFPROBE is None, SKIP)
class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vse_wp1a2_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.work_root = self.tmp / "work"
        self.work_root.mkdir()

    # ---- helpers
    def run_job(self, source, segs=((500, 2000),)):
        info = probe(source, FFPROBE)
        events = []
        job = VideoJob(source, info, [Segment(a, b) for a, b in segs], FFMPEG, FFPROBE,
                       events.append, self.work_root)
        out = job.run()   # verify_output runs inside and must pass
        return info, out

    def make_sdr(self, name="sdr.mp4", seconds=3):
        path = self.tmp / name
        ff(*src(seconds), *sine(seconds), "-vf", BT709_TAGS + ",format=yuv420p", "-c:v",
           "libx264", "-c:a", "aac", str(path))
        return path

    def make_hdr(self, transfer, name, size="640x360", seconds=3, codec="libx265",
                 pix_fmt="yuv420p10le", metadata=True):
        path = self.tmp / name
        vf = (f"scale={size.replace('x', ':')},format=yuv444p," if size != "640x360" else "")
        vf += ("setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv,"
               "zscale=t=linear:npl=203,format=gbrpf32le,"
              f"zscale=p=bt2020:t={transfer}:m=bt2020nc:r=tv,format={pix_fmt}")
        cmd = [*src(seconds, size), *sine(seconds), "-vf", vf, "-c:v", codec]
        if codec == "libx265":
            params = (f"colorprim=bt2020:transfer={transfer}:colormatrix=bt2020nc:"
                      + (MASTERING + ":" if metadata and transfer == "smpte2084" else "")
                      + "log-level=error")
            cmd += ["-x265-params", params]
        else:   # (the -color_* encoder options are ignored by this FFmpeg; tag via a filter)
            cmd[cmd.index("-vf") + 1] += (f",setparams=color_primaries=bt2020:color_trc={transfer}"
                                          ":colorspace=bt2020nc:range=tv")
        ff(*cmd, "-c:a", "aac", str(path))
        return path

    def assert_sdr_output(self, out, tags=("bt709", "bt709", "bt709", "tv")):
        v = vstream(jprobe(out))
        self.assertEqual(v["pix_fmt"], "yuv420p")
        self.assertEqual((v["color_primaries"], v["color_transfer"], v["color_space"],
                          v["color_range"]), tags)
        self.assertIn(v.get("field_order", "progressive"), ("progressive", "unknown"))
        return v

    # ---- HDR
    def _assert_tone_mapped(self, hdr_path, hdr_name):
        info, out = self.run_job(hdr_path)
        self.assertTrue(info.is_hdr, hdr_name)
        self.assertEqual(info.bit_depth, 10)
        self.assert_sdr_output(out)
        side = frame_side_data(out)
        self.assertNotIn("Mastering display metadata", side)
        self.assertNotIn("Content light level metadata", side)
        # compare with the SDR original of the same picture, cut the same way
        _, sdr_out = self.run_job(self.make_sdr())
        ref_mean, ref_sd = luma_stats(sdr_out)
        mean, sd = luma_stats(out)
        self.assertGreater(mean, 0.70 * ref_mean, f"{hdr_name} too dark: {mean:.1f}/{ref_mean:.1f}")
        self.assertLess(mean, 1.15 * ref_mean, f"{hdr_name} too bright: {mean:.1f}/{ref_mean:.1f}")
        self.assertGreater(sd, 0.60 * ref_sd, f"{hdr_name} flat: {sd:.1f}/{ref_sd:.1f}")
        self.assertLess(sd, 1.20 * ref_sd, f"{hdr_name} harsh: {sd:.1f}/{ref_sd:.1f}")
        return out

    @unittest.skipUnless(HAS_HDR_TOOLS, "needs zscale, tonemap and bwdif")
    def test_hdr10_pq_with_mastering_data_becomes_sdr(self):
        src_path = self.make_hdr("smpte2084", "pq.mp4")
        self.assertIn("Mastering display metadata", frame_side_data(src_path))  # sanity
        self._assert_tone_mapped(src_path, "PQ")

    @unittest.skipUnless(HAS_HDR_TOOLS, "needs zscale, tonemap and bwdif")
    def test_hlg_becomes_sdr(self):
        self._assert_tone_mapped(self.make_hdr("arib-std-b67", "hlg.mp4"), "HLG")

    @unittest.skipUnless(HAS_HDR_TOOLS, "needs zscale, tonemap and bwdif")
    def test_pq_without_side_data_becomes_sdr(self):
        self._assert_tone_mapped(self.make_hdr("smpte2084", "pq_nometa.mp4", metadata=False),
                                 "PQ without metadata")

    @unittest.skipUnless(HAS_HDR_TOOLS, "needs zscale, tonemap and bwdif")
    def test_hdr_with_odd_size_is_cropped_before_tone_mapping(self):
        path = self.make_hdr("smpte2084", "pq_odd.mkv", size="641x361", codec="libx264",
                             pix_fmt="yuv444p10le")
        info, out = self.run_job(path)
        self.assertEqual((info.width, info.height), (641, 361))
        v = self.assert_sdr_output(out)
        self.assertEqual((v["width"], v["height"]), (640, 360))

    # ---- 10-bit, 4:4:4, range, RGB
    def test_10bit_sdr_becomes_8bit_and_keeps_source_tags(self):
        path = self.tmp / "ten.mkv"
        ff(*src(3), *sine(3), "-vf", BT709_TAGS + ",format=yuv420p10le", "-c:v", "libx264",
           "-profile:v", "high10", "-c:a", "aac", str(path))
        info, out = self.run_job(path)
        self.assertEqual(info.bit_depth, 10)
        self.assert_sdr_output(out)
        ref_mean, ref_sd = luma_stats(self.run_job(self.make_sdr())[1])
        mean, sd = luma_stats(out)
        self.assertAlmostEqual(mean, ref_mean, delta=4)
        self.assertAlmostEqual(sd, ref_sd, delta=4)

    def test_untagged_10bit_sd_gets_smpte170m(self):
        path = self.tmp / "ten_untagged.mkv"
        ff(*src(3), *sine(3), "-vf", "format=yuv420p10le", "-c:v", "libx264", "-profile:v",
           "high10", "-c:a", "aac", str(path))
        info, out = self.run_job(path)
        self.assertEqual(info.color_space, "")
        self.assert_sdr_output(out, ("smpte170m",) * 3 + ("tv",))

    def test_untagged_hd_gets_bt709(self):
        path = self.tmp / "hd.mp4"
        ff(*src(2, "1280x720"), *sine(2), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a",
           "aac", str(path))
        _, out = self.run_job(path, [(0, 1000)])
        self.assert_sdr_output(out)

    def test_yuv444_becomes_420(self):
        path = self.tmp / "c444.mkv"
        ff(*src(3), *sine(3), "-c:v", "libx264", "-pix_fmt", "yuv444p", "-c:a", "aac", str(path))
        info, out = self.run_job(path)
        self.assertEqual(info.pix_fmt, "yuv444p")
        self.assert_sdr_output(out, ("smpte170m",) * 3 + ("tv",))

    def test_full_range_source_is_converted_to_tv_without_changing_the_picture(self):
        path = self.tmp / "full.mp4"
        ff(*src(3), *sine(3), "-vf", "scale=out_range=pc,format=yuvj420p", "-c:v", "libx264",
           "-c:a", "aac", str(path))
        info, out = self.run_job(path)
        self.assertEqual(info.color_range, "pc")
        self.assert_sdr_output(out, ("smpte170m",) * 3 + ("tv",))
        ref_mean, _ = luma_stats(self.make_sdr())
        self.assertAlmostEqual(luma_stats(out)[0], ref_mean, delta=6)

    def test_rgb_source(self):
        path = self.tmp / "rgb.mkv"
        ff(*src(3), *sine(3), "-vf", "format=gbrp", "-c:v", "ffv1", "-c:a", "pcm_s16le",
           str(path))
        info, out = self.run_job(path)
        self.assertTrue(info.pix_fmt.startswith(("gbr", "bgr", "rgb")), info.pix_fmt)
        self.assert_sdr_output(out, ("smpte170m",) * 3 + ("tv",))
        ref_mean, _ = luma_stats(self.make_sdr())
        self.assertAlmostEqual(luma_stats(out)[0], ref_mean, delta=8)

    # ---- interlaced
    def test_interlaced_source_comes_out_progressive_at_same_frame_rate(self):
        path = self.tmp / "tff.mkv"
        ff(*src(3, rate=50), *sine(3), "-vf", "interlace=scan=tff,format=yuv420p", "-c:v",
           "libx264", "-flags", "+ildct+ilme", "-x264opts", "tff=1", "-c:a", "aac", str(path))
        info = probe(path, FFPROBE)
        if not info.is_interlaced:
            self.skipTest(f"could not generate an interlaced clip (field_order={info.field_order!r})")
        info, out = self.run_job(path)
        v = self.assert_sdr_output(out, ("smpte170m",) * 3 + ("tv",))
        self.assertEqual(v["field_order"], "progressive")
        self.assertEqual(v["r_frame_rate"], "25/1")
        frames = int(v["nb_frames"])
        self.assertAlmostEqual(frames, 38, delta=2)      # 1.5 s at 25 fps

    def test_progressive_source_gets_no_deinterlace_filter(self):
        info = probe(self.make_sdr(), FFPROBE)
        self.assertNotIn(vp.DEINTERLACE_FILTER, vp.video_filter_chain(info))

    # ---- audio
    def make_multi_audio(self):
        path = self.tmp / "multi.mkv"
        ff(*src(4), *sine(4, 440), *sine(4, 880), *sine(4, 220),
           "-map", "0:v", "-map", "1:a", "-map", "2:a", "-map", "3:a",
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a:0", "aac", "-ac:a:0", "2", "-c:a:1", "ac3", "-ac:a:1", "6",
           "-c:a:2", "aac", "-ac:a:2", "1",
           "-metadata:s:a:0", "language=eng", "-metadata:s:a:0", "title=Stereo mix",
           "-metadata:s:a:1", "language=rus", "-metadata:s:a:1", "title=Five one",
           "-metadata:s:a:2", "language=deu", str(path))
        return path

    def test_all_audio_tracks_kept_with_channels_language_and_title(self):
        path = self.make_multi_audio()
        info = probe(path, FFPROBE)
        self.assertEqual([a.channels for a in info.audio_streams], [2, 6, 1])
        info, out = self.run_job(path, [(500, 1500), (2000, 3000)])
        audio = astreams(jprobe(out))
        self.assertEqual([a["channels"] for a in audio], [2, 6, 1])
        self.assertEqual([a["tags"].get("language") for a in audio], ["eng", "rus", "deu"])
        self.assertEqual(audio[0]["tags"].get("name") or audio[0]["tags"].get("title"),
                         "Stereo mix")
        self.assertEqual(audio[1]["tags"].get("name") or audio[1]["tags"].get("title"),
                         "Five one")
        rates = [int(a["bit_rate"]) for a in audio]
        self.assertGreater(rates[1], 250_000)       # 5.1 is no longer squeezed into 192k
        self.assertLess(rates[2], 130_000)          # mono stays near 96k
        self.assertTrue(all(a["codec_name"] == "aac" for a in audio))
        # all tracks as long as the picture
        v = float(vstream(jprobe(out))["duration"])
        for a in audio:
            self.assertLess(abs(float(a["duration"]) - v), 0.1 + 0.03 * 2)

    def test_mono_source_stays_mono(self):
        path = self.tmp / "mono.mp4"
        ff(*src(3), *sine(3), "-ac", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a",
           "aac", str(path))
        _, out = self.run_job(path)
        audio = astreams(jprobe(out))
        self.assertEqual([a["channels"] for a in audio], [1])
        self.assertLess(int(audio[0]["bit_rate"]), 130_000)

    def test_source_without_audio_has_no_audio_track(self):
        path = self.tmp / "silent.mp4"
        ff(*src(3), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path))
        _, out = self.run_job(path)
        self.assertEqual(astreams(jprobe(out)), [])

    # ---- VFR false failure of the previous package
    def test_generated_vfr_source_is_flagged_and_passes(self):
        # the first 12 frames are dropped and frames 6..9 of every ten too, the others keep
        # their times: a variable frame rate. (It does not reproduce the 0.18 s late start of
        # the real clip - FFmpeg re-times the cut - which is covered by the unit tests and
        # by test_real_vfr_clip_passes_end_to_end.)
        vid = self.tmp / "v.mp4"
        ff(*src(8, rate=30), "-vf", "select='gte(n,12)*lt(mod(n,10),6)'", "-fps_mode",
           "passthrough", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vid))
        aud = self.tmp / "a.m4a"
        ff(*sine(8), "-c:a", "aac", str(aud))
        path = self.tmp / "vfr_late.mp4"
        ff("-i", str(vid), "-i", str(aud), "-map", "0:v", "-map", "1:a", "-c", "copy", str(path))
        info = probe(path, FFPROBE)
        self.assertTrue(info.vfr, f"generated clip should be variable frame rate (fps {info.fps})")
        _, out = self.run_job(path, [(0, 2000), (4000, 6000)])
        self.assertLessEqual(float(vstream(jprobe(out))["start_time"]), vp.MAX_VIDEO_START_VFR_S)

    @unittest.skipUnless(REAL_VFR.is_file(), "set VSE_REAL_VFR_CLIP to a real VFR clip to run")
    def test_real_vfr_clip_passes_end_to_end(self):
        path = self.tmp / "vfr.mp4"
        shutil.copyfile(REAL_VFR, path)
        info = probe(path, FFPROBE)
        self.assertTrue(info.vfr)
        for segs in ([(0, 2000), (3000, 5000)], [(500, 3000), (6000, 9000)]):   # 2nd: review C3
            _, out = self.run_job(path, segs)
            self.assertTrue(out.is_file())
            out.unlink()

    def test_constant_frame_rate_source_is_not_flagged_vfr(self):
        info = probe(self.make_sdr(), FFPROBE)
        self.assertFalse(info.vfr)
        self.assertEqual(info.rate_gap, 0.0)

    # ---- fix round 1: valid sources the first checks rejected (review C1-C4, I1, I3)
    def _base_av(self, seconds=9, size="320x180"):
        vid, aud = self.tmp / "bv.mp4", self.tmp / "ba.m4a"
        ff(*src(seconds, size), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vid))
        ff(*sine(seconds), "-c:a", "aac", str(aud))
        return vid, aud

    def make_late_audio(self):
        vid, aud = self._base_av()
        path = self.tmp / "audiodelay.mp4"
        ff("-i", str(vid), "-itsoffset", "0.48", "-i", str(aud), "-map", "0:v", "-map", "1:a",
           "-c", "copy", str(path))
        a = astreams(jprobe(path))[0]
        self.assertGreater(float(a["start_time"]), 0.4)       # the clip really is what we want
        return path

    def make_late_video(self):
        vid, aud = self._base_av()
        path = self.tmp / "videodelay.mp4"
        ff("-itsoffset", "0.4", "-i", str(vid), "-i", str(aud), "-map", "0:v", "-map", "1:a",
           "-c", "copy", str(path))
        self.assertAlmostEqual(float(vstream(jprobe(path))["start_time"]), 0.4, places=2)
        return path

    def test_c2_audio_that_starts_late_passes_for_cuts_at_zero(self):
        path = self.make_late_audio()
        for segs in ([(0, 2500)], [(0, 2500), (5000, 8000)], [(0, 9000)], [(2000, 6000)]):
            _, out = self.run_job(path, segs)
            out.unlink()

    def test_c4_picture_that_starts_late_passes_for_cuts_at_zero(self):
        path = self.make_late_video()
        info = probe(path, FFPROBE)
        self.assertAlmostEqual(info.video_lead_s, 0.4, places=2)
        for segs in ([(0, 3000)], [(0, 3000), (5000, 7000)], [(2000, 5000)], [(0, 8500)]):
            _, out = self.run_job(path, segs)
            out.unlink()

    def test_c4_a_truncated_source_still_fails(self):
        # the lead must not hide real damage: a source cut short in the middle
        full = self.tmp / "full.mkv"
        ff(*src(8.2), *sine(8.2), "-c:v", "libx264", "-b:v", "1M", "-pix_fmt", "yuv420p",
           "-c:a", "aac", str(full))
        data = full.read_bytes()
        trunc = self.tmp / "trunc.mkv"
        trunc.write_bytes(data[: int(len(data) * 0.6)])
        with self.assertRaises(vp.ProcessingError) as cm:
            self.run_job(trunc, [(1000, 3000), (7000, 7400)])
        self.assertEqual(cm.exception.key, "err.part_invalid")

    def test_c4_picture_shorter_than_sound_still_fails(self):
        vid, aud = self.tmp / "sv.mp4", self.tmp / "sa.m4a"
        ff(*src(5), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vid))
        ff(*sine(8), "-c:a", "aac", str(aud))
        path = self.tmp / "vshort.mp4"
        ff("-i", str(vid), "-i", str(aud), "-map", "0:v", "-map", "1:a", "-c", "copy", str(path))
        with self.assertRaises(vp.ProcessingError):
            self.run_job(path, [(4000, 8000)])

    def make_mixed_rate(self):
        """10 s at 30 fps followed by 1 s at 24 fps in one stream: nominal 30, average 1.8 % less."""
        parts = []
        for rate, secs in ((30, 10), (24, 1)):      # joined as MPEG-TS pieces: times stay exact
            part = self.tmp / f"m{rate}.ts"
            ff(*src(secs, "320x180", rate), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-f",
               "mpegts", str(part))
            parts.append(part.as_posix())
        out = self.tmp / "mixed.mp4"
        ff("-i", "concat:" + "|".join(parts), *sine(11), "-map", "0:v", "-map", "1:a",
           "-c:v", "copy", "-c:a", "aac", str(out))
        return out

    def test_c1_mildly_variable_frame_rate_passes(self):
        path = self.make_mixed_rate()
        info = probe(path, FFPROBE)
        gap = abs(info.fps - 30.0) / 30.0
        self.assertTrue(0.005 < gap < 0.02, f"clip should have a 0.5-2 % rate gap, got {gap}")
        self.assertTrue(info.vfr)
        for segs in ([(0, 5000)], [(9500, 10800)], [(0, 5000), (9500, 10800)]):
            _, out = self.run_job(path, segs)
            out.unlink()

    def test_i1_audio_track_shorter_than_the_cut_stays_in_the_output(self):
        path = self.tmp / "multishort.mkv"
        ff(*src(10, "320x180"), *sine(10, 440), *sine(4, 880), "-map", "0:v", "-map", "1:a",
           "-map", "2:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path))
        self.assertEqual(len(probe(path, FFPROBE).audio_streams), 2)
        for segs in ([(5000, 8000)], [(3000, 6000)], [(0, 3000)]):
            _, out = self.run_job(path, segs)
            self.assertEqual(len(astreams(jprobe(out))), 2, segs)
            out.unlink()

    def test_i3_matroska_with_a_start_offset_reports_the_content_length(self):
        vid, aud = self._base_av(seconds=6)
        path = self.tmp / "offset.mkv"
        ff("-itsoffset", "1.0", "-i", str(vid), "-itsoffset", "1.0", "-i", str(aud), "-map",
           "0:v", "-map", "1:a", "-c", "copy", str(path))
        raw = float(jprobe(path)["format"]["duration"])
        self.assertGreater(raw, 6.5)                      # the container says ~7.0
        info = probe(path, FFPROBE)
        self.assertAlmostEqual(info.duration_ms / 1000.0, 6.0, delta=0.1)
        self.run_job(path, [(3000, info.duration_ms - 100)])  # the last stretch exists


if __name__ == "__main__":
    unittest.main()
