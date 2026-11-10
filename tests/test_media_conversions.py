"""Unit tests for WP1a-2 (media conversions). Offline: ffprobe results are injected."""
import unittest
from pathlib import Path
from unittest import mock

import i18n
import video_processor as vp
from create_flow import conversion_notes
from segment_manager import Segment


def _info(w=1920, h=1080, fps=25.0, **kw):
    return vp.VideoInfo(Path("a.mp4"), 60000, w, h, fps, kw.pop("has_audio", True), **kw)


def _astream(index=1, channels=2, rate="48000", lang=None, title=None):
    return vp.AudioStream(index=index, channels=channels, sample_rate=int(rate),
                          language=lang, title=title)


def _cmd(info):
    return vp.extract_cmd("ffmpeg", Path("in.mp4"), Segment(0, 1000), Path("o.mp4"), info)


DEINT = vp.DEINTERLACE_FILTER


def _opt(cmd, name):
    return cmd[cmd.index(name) + 1]


def _parts(cmd):
    return _opt(cmd, "-vf").split(",")


def _vf(cmd):
    """The filter chain without the colour-tag filter that always comes last."""
    return ",".join(_parts(cmd)[:-1])


# ---------------------------------------------------------------- probe additions
def _vs(**kw):
    s = {"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "25/1",
         "r_frame_rate": "25/1", "duration": "10.0"}
    s.update(kw)
    return s


def _probe(streams):
    data = {"format": {"duration": "10.0"}, "streams": streams}
    with mock.patch.object(vp, "_run_ffprobe_json", return_value=data):
        return vp.probe(Path("a.mkv"), "ffprobe")


class ProbeFieldsTests(unittest.TestCase):
    def test_defaults_are_safe_for_old_code(self):
        info = _info()
        self.assertEqual(info.audio_streams, [])
        self.assertEqual(info.field_order, "")
        self.assertEqual(info.color_transfer, "")
        self.assertFalse(info.vfr)
        self.assertEqual(info.subtitle_count, 0)
        self.assertEqual(info.audio_count, 1)             # has_audio, nothing known more
        self.assertEqual(_info(has_audio=False).audio_count, 0)

    def test_colour_pixfmt_and_field_order(self):
        info = _probe([_vs(pix_fmt="yuv420p10le", color_transfer="smpte2084",
                           color_primaries="bt2020", color_space="bt2020nc",
                           color_range="tv", field_order="tt")])
        self.assertEqual(info.pix_fmt, "yuv420p10le")
        self.assertEqual(info.color_transfer, "smpte2084")
        self.assertEqual(info.color_primaries, "bt2020")
        self.assertEqual(info.color_space, "bt2020nc")
        self.assertEqual(info.color_range, "tv")
        self.assertEqual(info.field_order, "tt")
        self.assertEqual(info.bit_depth, 10)
        self.assertTrue(info.is_hdr)
        self.assertTrue(info.is_interlaced)

    def test_missing_tags_stay_empty(self):
        info = _probe([_vs(pix_fmt="yuv420p", color_space="unknown", field_order="progressive")])
        self.assertEqual(info.color_space, "")
        self.assertEqual(info.bit_depth, 8)
        self.assertFalse(info.is_hdr)
        self.assertFalse(info.is_interlaced)

    def test_all_audio_streams_listed_with_tags(self):
        info = _probe([
            _vs(index=0),
            {"codec_type": "audio", "index": 1, "channels": 2, "sample_rate": "48000",
             "tags": {"language": "eng", "title": "Stereo"}},
            {"codec_type": "audio", "index": 2, "channels": 6, "sample_rate": "44100",
             "tags": {"language": "rus"}},
            {"codec_type": "audio", "index": 3, "channels": 1, "sample_rate": "bad"},
            {"codec_type": "subtitle", "index": 4},
        ])
        self.assertTrue(info.has_audio)
        self.assertEqual(info.audio_count, 3)
        self.assertEqual([a.channels for a in info.audio_streams], [2, 6, 1])
        self.assertEqual(info.audio_streams[0].language, "eng")
        self.assertEqual(info.audio_streams[0].title, "Stereo")
        self.assertEqual(info.audio_streams[1].sample_rate, 44100)
        self.assertEqual(info.audio_streams[2].sample_rate, 0)
        self.assertEqual(info.subtitle_count, 1)

    def test_vfr_detection_two_percent(self):
        self.assertFalse(_probe([_vs()]).vfr)
        self.assertFalse(_probe([_vs(avg_frame_rate="30000/1001", r_frame_rate="30000/1001")]).vfr)
        self.assertFalse(_probe([_vs(avg_frame_rate="24.99/1", r_frame_rate="25/1")]).vfr)
        self.assertTrue(_probe([_vs(avg_frame_rate="5150/299", r_frame_rate="25/1")]).vfr)
        # C1: a mild gap (1.8 %, a 30 fps clip with a few seconds at 24 fps) is variable too
        self.assertTrue(_probe([_vs(avg_frame_rate="324/11", r_frame_rate="30/1")]).vfr)
        self.assertTrue(_probe([_vs(avg_frame_rate="24.9/1", r_frame_rate="25/1")]).vfr)  # 0.4 %
        self.assertFalse(_probe([_vs(avg_frame_rate="0/0")]).vfr)  # unknown: not flagged


# ---------------------------------------------------------------- video filter chain
class ChainTests(unittest.TestCase):
    def test_plain_progressive_8bit_has_no_filter(self):
        self.assertEqual(_vf(_cmd(_info(pix_fmt="yuv420p", field_order="progressive"))), "")
        self.assertEqual(_vf(_cmd(_info())), "")           # nothing known: as before

    def test_interlaced_gets_deinterlace_first(self):
        for order in ("tt", "bb", "tb", "bt"):
            vf = _vf(_cmd(_info(pix_fmt="yuv420p", field_order=order)))
            self.assertTrue(vf.startswith("bwdif=mode=send_frame"), vf)
        self.assertNotIn("bwdif", _vf(_cmd(_info(field_order="progressive"))))
        self.assertNotIn("bwdif", _vf(_cmd(_info(field_order="unknown"))))

    def test_10bit_sdr_converts_to_420_8bit_with_dither(self):
        vf = _vf(_cmd(_info(pix_fmt="yuv420p10le", color_space="bt709")))
        self.assertIn("format=yuv420p", vf)
        self.assertIn("sws_dither=ed", vf)
        self.assertNotIn("tonemap", vf)

    def test_444_converts(self):
        self.assertIn("format=yuv420p", _vf(_cmd(_info(pix_fmt="yuv444p"))))

    def test_full_range_source_is_scaled_to_tv(self):
        vf = _vf(_cmd(_info(pix_fmt="yuvj420p", color_range="pc")))
        self.assertIn("out_range=tv", vf)

    def test_rgb_source_uses_explicit_matrix(self):
        self.assertIn("out_color_matrix=bt709", _vf(_cmd(_info(pix_fmt="gbrp"))))
        self.assertIn("out_color_matrix=smpte170m",
                      _vf(_cmd(_info(w=640, h=480, pix_fmt="gbrp"))))

    def test_hdr_pq_chain(self):
        vf = _vf(_cmd(_info(pix_fmt="yuv420p10le", color_transfer="smpte2084",
                            color_primaries="bt2020", color_space="bt2020nc")))
        for needle in ("sidedata=mode=delete:type=MASTERING_DISPLAY_METADATA",
                       "sidedata=mode=delete:type=CONTENT_LIGHT_LEVEL",
                       "tin=smpte2084", "t=linear", "format=gbrpf32le", "p=bt709",
                       "tonemap=tonemap=" + vp.HDR_TONEMAP, "t=bt709:m=bt709:r=tv",
                       "format=yuv420p"):
            self.assertIn(needle, vf)

    def test_hdr_hlg_uses_hlg_input_transfer(self):
        vf = _vf(_cmd(_info(pix_fmt="yuv420p10le", color_transfer="arib-std-b67",
                            color_primaries="bt2020")))
        self.assertIn("tin=arib-std-b67", vf)
        self.assertIn("tonemap", vf)

    def test_order_deinterlace_then_crop_then_hdr(self):
        # crop before the conversion: zscale cannot output odd-sized 4:2:0 (measured)
        vf = _vf(_cmd(_info(w=1921, h=1081, pix_fmt="yuv420p10le", field_order="tt",
                            color_transfer="smpte2084")))
        i_deint, i_crop, i_tm = vf.index("bwdif"), vf.index("crop="), vf.index("tonemap")
        self.assertLess(i_deint, i_crop)
        self.assertLess(i_crop, i_tm)
        self.assertLess(i_crop, vf.index("zscale"))
        self.assertTrue(vf.startswith(DEINT + ",crop=trunc(iw/2)*2:trunc(ih/2)*2,sidedata"))

    def test_crop_still_last_without_other_filters(self):
        self.assertEqual(_vf(_cmd(_info(w=321, h=241))), "crop=trunc(iw/2)*2:trunc(ih/2)*2")


# ---------------------------------------------------------------- colour tags
class TagTests(unittest.TestCase):
    def _tags(self, **kw):
        last = _parts(_cmd(_info(**kw)))[-1]
        self.assertTrue(last.startswith("setparams="), last)
        opts = dict(kv.split("=") for kv in last[len("setparams="):].split(":"))
        return (opts["color_primaries"], opts["color_trc"], opts["colorspace"], opts["range"])

    def test_tags_are_written_by_the_last_filter_not_by_encoder_options(self):
        cmd = _cmd(_info(w=1921, h=1081, field_order="tt", pix_fmt="yuv420p10le"))
        self.assertTrue(_parts(cmd)[-1].startswith("setparams="))
        self.assertTrue(_parts(cmd)[-2].startswith("format="))   # the SDR conversion
        for opt in ("-color_primaries", "-color_trc", "-colorspace", "-color_range"):
            self.assertNotIn(opt, cmd)

    def test_untagged_hd_gets_bt709(self):
        self.assertEqual(self._tags(w=1280, h=720), ("bt709", "bt709", "bt709", "tv"))
        self.assertEqual(self._tags(), ("bt709", "bt709", "bt709", "tv"))

    def test_untagged_sd_gets_smpte170m(self):
        self.assertEqual(self._tags(w=720, h=576),
                         ("smpte170m", "smpte170m", "smpte170m", "tv"))
        self.assertEqual(self._tags(w=1280, h=719)[0], "smpte170m")

    def test_sensible_source_tags_are_kept(self):
        self.assertEqual(self._tags(w=720, h=576, color_primaries="bt470bg",
                                    color_transfer="bt709", color_space="bt470bg"),
                         ("bt470bg", "bt709", "bt470bg", "tv"))
        self.assertEqual(self._tags(pix_fmt="yuv420p10le", color_primaries="bt2020",
                                    color_transfer="bt2020-10", color_space="bt2020nc"),
                         ("bt2020", "bt2020-10", "bt2020nc", "tv"))

    def test_missing_individual_tags_are_filled_consistently_with_the_matrix(self):
        self.assertEqual(self._tags(w=640, h=360, color_space="bt709"),
                         ("bt709", "bt709", "bt709", "tv"))
        self.assertEqual(self._tags(w=640, h=360, color_space="bt2020nc"),
                         ("bt2020", "bt2020-10", "bt2020nc", "tv"))
        self.assertEqual(self._tags(w=640, h=360, color_space="bt470bg"),
                         ("bt470bg", "smpte170m", "bt470bg", "tv"))
        # a stated primaries tag is kept while the others are filled from the size
        self.assertEqual(self._tags(w=640, h=360, color_primaries="bt470bg"),
                         ("bt470bg", "smpte170m", "smpte170m", "tv"))

    def test_odd_tags_are_replaced(self):
        self.assertEqual(self._tags(color_primaries="smpte428", color_transfer="log100",
                                    color_space="ycgco"),
                         ("bt709", "bt709", "bt709", "tv"))

    def test_hdr_output_is_bt709_even_with_other_source_tags(self):
        self.assertEqual(self._tags(pix_fmt="yuv420p10le", color_transfer="smpte2084",
                                    color_primaries="bt2020", color_space="bt2020nc"),
                         ("bt709", "bt709", "bt709", "tv"))
        self.assertEqual(self._tags(w=3840, h=2160, color_transfer="arib-std-b67")[2], "bt709")

    def test_output_range_is_always_tv(self):
        self.assertEqual(self._tags(color_range="pc")[3], "tv")


# ---------------------------------------------------------------- audio arguments
class AudioArgTests(unittest.TestCase):
    def test_bitrate_by_channels(self):
        k = vp.audio_bitrate_k
        self.assertEqual([k(c) for c in (1, 2, 6, 8)], [96, 192, 384, 512])
        self.assertEqual(k(3), 192)       # 64 per channel
        self.assertEqual(k(4), 256)
        self.assertEqual(k(5), 320)
        self.assertEqual(k(7), 448)
        self.assertEqual(k(10), 512)      # capped
        self.assertEqual(k(0), 192)       # unknown: stereo value

    def test_every_audio_stream_is_mapped_with_its_own_bitrate(self):
        cmd = _cmd(_info(audio_streams=[_astream(1, 2), _astream(2, 6), _astream(3, 1)]))
        maps = [cmd[i + 1] for i, c in enumerate(cmd) if c == "-map"]
        self.assertEqual(maps, ["0:v:0", "0:a:0", "0:a:1", "0:a:2"])
        self.assertEqual(_opt(cmd, "-b:a:0"), "192k")
        self.assertEqual(_opt(cmd, "-b:a:1"), "384k")
        self.assertEqual(_opt(cmd, "-b:a:2"), "96k")
        self.assertEqual(_opt(cmd, "-c:a"), "aac")
        self.assertNotIn("-b:a", cmd)

    def test_no_audio_stream_means_no_audio_maps(self):
        cmd = _cmd(_info(has_audio=False))
        self.assertNotIn("-c:a", cmd)
        self.assertEqual([cmd[i + 1] for i, c in enumerate(cmd) if c == "-map"], ["0:v:0"])

    def test_old_info_without_stream_list_keeps_first_track(self):
        cmd = _cmd(_info())
        self.assertIn("0:a:0?", cmd)
        self.assertEqual(_opt(cmd, "-b:a"), "192k")

    def test_more_than_8_channels_are_limited(self):
        cmd = _cmd(_info(audio_streams=[_astream(1, 12)]))
        self.assertEqual(_opt(cmd, "-ac:a:0"), "8")

    def test_concat_maps_all_streams(self):
        cmd = vp.concat_cmd("ffmpeg", Path("l.txt"), Path("o.mp4"))
        self.assertEqual(_opt(cmd, "-map"), "0")
        self.assertLess(cmd.index("-i"), cmd.index("-map"))

    def test_concat_rewrites_audio_titles(self):
        streams = [_astream(1, 2, title="Stereo"), _astream(2, 6), _astream(3, 1, title="Mono")]
        cmd = vp.concat_cmd("ffmpeg", Path("l.txt"), Path("o.mp4"), streams)
        self.assertEqual(_opt(cmd, "-metadata:s:a:0"), "title=Stereo")
        self.assertNotIn("-metadata:s:a:1", cmd)
        self.assertEqual(_opt(cmd, "-metadata:s:a:2"), "title=Mono")
        self.assertEqual(cmd[-1], str(Path("o.mp4")))


# ---------------------------------------------------------------- verification
def _v(**kw):
    s = {"codec_type": "video", "width": 640, "height": 360, "avg_frame_rate": "25/1",
         "duration": "10.0", "start_time": "0.000000"}
    s.update(kw)
    return s


def _a(duration="10.0", channels=2, start="0.000000"):
    return {"codec_type": "audio", "duration": duration, "start_time": start,
            "channels": channels}


def _verify(streams, count, fps=25.0, vfr=False, n=1, ms=10000, fmt="10.0", **kw):
    data = {"format": {"duration": fmt}, "streams": streams}
    with mock.patch.object(vp, "_run_ffprobe_json", return_value=data), \
            mock.patch.object(Path, "is_file", return_value=True), \
            mock.patch.object(Path, "stat", return_value=mock.Mock(st_size=10)):
        vp.verify_output(Path("o.mp4"), ms, n, count, "ffprobe", fps=fps, vfr=vfr, **kw)


class AudioCountTests(unittest.TestCase):
    def _key(self, fn):
        with self.assertRaises(vp.ProcessingError) as cm:
            fn()
        return cm.exception.key

    def test_matching_count_passes(self):
        _verify([_v(), _a(), _a(), _a()], 3)
        _verify([_v(), _a()], True)           # bool still accepted
        _verify([_v()], False)
        _verify([_v()], 0)

    def test_missing_track_fails(self):
        self.assertEqual(self._key(lambda: _verify([_v(), _a()], 3)), "err.out_audio_count")

    def test_no_sound_at_all_keeps_old_key(self):
        self.assertEqual(self._key(lambda: _verify([_v()], 2)), "err.out_no_sound")
        self.assertEqual(self._key(lambda: _verify([_v()], True)), "err.out_no_sound")

    def test_extra_track_fails_too(self):
        self.assertEqual(self._key(lambda: _verify([_v(), _a(), _a()], 1)),
                         "err.out_audio_count")

    def test_av_tolerance_applies_to_every_audio_stream(self):
        self.assertEqual(self._key(lambda: _verify([_v(), _a("10.0"), _a("8.0")], 2)),
                         "err.out_av_mismatch")
        _verify([_v(), _a("10.0"), _a("10.05")], 2)

    def test_part_problem_counts_audio_streams(self):
        def problem(streams, count):
            data = {"format": {"duration": "4.0"}, "streams": streams}
            with mock.patch.object(vp, "_run_ffprobe_json", return_value=data):
                return vp.part_problem(Path("p.mp4"), Segment(0, 4000), count, 25.0, "ffprobe")
        v = _v(duration="4.0")
        self.assertIsNone(problem([v, _a("4.0"), _a("4.0")], 2))
        self.assertIn("audio", problem([v, _a("4.0")], 2))
        self.assertIn("audio", problem([v], True))
        self.assertIsNone(problem([v], 0))


class VfrVerifyTests(unittest.TestCase):
    def test_start_150ms_limit_for_cfr(self):
        with self.assertRaises(vp.ProcessingError) as cm:
            _verify([_v(start_time="0.180000", duration="9.82"), _a()], 1, vfr=False)
        self.assertEqual(cm.exception.key, "err.out_start_offset")

    def test_vfr_allows_up_to_500ms(self):
        _verify([_v(start_time="0.180000", duration="9.82"), _a()], 1, vfr=True)
        _verify([_v(start_time="0.499000", duration="9.501"), _a()], 1, vfr=True)
        with self.assertRaises(vp.ProcessingError) as cm:
            _verify([_v(start_time="0.600000", duration="9.4"), _a()], 1, vfr=True)
        self.assertEqual(cm.exception.key, "err.out_start_offset")

    def test_vfr_skips_frame_count(self):
        streams = [_v(nb_frames="100"), _a()]       # 250 expected at 25 fps
        with self.assertRaises(vp.ProcessingError) as cm:
            _verify(streams, 1, vfr=False)
        self.assertEqual(cm.exception.key, "err.out_frames_wrong")
        _verify(streams, 1, vfr=True)


# ---------------------------------------------------------------- fix round 1
class EndTimeRuleTests(unittest.TestCase):
    """C2/C3: picture and sound are compared by where they END (start + duration)."""

    def _key(self, streams, **kw):
        with self.assertRaises(vp.ProcessingError) as cm:
            _verify(streams, kw.pop("count", 1), **kw)
        return cm.exception.key

    def test_late_audio_start_is_fine(self):
        # audiodelay.mp4: audio starts 0.479 s late, so its duration is shorter but it ends in time
        _verify([_v(duration="12.0"), _a("11.521", start="0.479000")], 1, ms=12000, fmt="12.0")

    def test_late_picture_start_is_fine(self):
        # real vfr.mp4, two segments: picture 0.18 + 5.38 = sound 0.0 + 5.56
        _verify([_v(duration="5.38", start_time="0.180000"), _a("5.56")], 1, n=2, ms=5400,
                fmt="5.56", vfr=True)

    def test_picture_really_shorter_than_sound_still_fails(self):
        self.assertEqual(self._key([_v(duration="5.0"), _a("8.0")], ms=8000, fmt="8.0"),
                         "err.out_av_mismatch")
        self.assertEqual(self._key([_v(duration="10.0"), _a("9.8")]), "err.out_av_mismatch")

    def test_every_audio_track_is_compared_by_end_time(self):
        self.assertEqual(self._key([_v(), _a("10.0"), _a("9.0", start="0.5")], count=2),
                         "err.out_av_mismatch")
        _verify([_v(), _a("10.0"), _a("9.5", start="0.5")], 2)

    def test_tolerance_is_100ms_plus_30ms_per_segment(self):
        _verify([_v(duration="10.0"), _a("10.12")], 1, n=1)          # 120 ms <= 130 ms
        self.assertEqual(self._key([_v(duration="10.0"), _a("10.14")], n=1), "err.out_av_mismatch")
        _verify([_v(duration="10.0"), _a("10.19")], 1, n=3)          # 190 ms <= 190 ms


class LeadTests(unittest.TestCase):
    """C4: a source whose picture starts after the sound."""

    def test_lead_inside(self):
        self.assertAlmostEqual(vp.lead_inside(Segment(0, 3000), 0.4), 0.4)
        self.assertAlmostEqual(vp.lead_inside(Segment(200, 3000), 0.4), 0.2)
        self.assertEqual(vp.lead_inside(Segment(2000, 5000), 0.4), 0.0)
        self.assertAlmostEqual(vp.lead_inside(Segment(0, 300), 0.4), 0.3)   # capped by the length
        self.assertEqual(vp.lead_inside(Segment(0, 3000), 0.0), 0.0)

    def _part(self, video_dur, seg, lead=0.0):
        data = {"format": {}, "streams": [_v(duration=video_dur), _a(video_dur)]}
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=data):
            return vp.part_problem(Path("p.mp4"), seg, 1, 25.0, "ffprobe", lead_s=lead)

    def test_part_at_the_start_is_shorter_by_the_lead(self):
        self.assertIsNotNone(self._part("2.6", Segment(0, 3000)))           # old rule: too short
        self.assertIsNone(self._part("2.6", Segment(0, 3000), lead=0.4))
        self.assertIsNone(self._part("3.0", Segment(2000, 5000), lead=0.4))  # not affected
        self.assertIsNotNone(self._part("2.0", Segment(0, 3000), lead=0.4))  # a real loss

    def test_start_limit_is_widened_by_the_lead(self):
        late = [_v(start_time="0.400000", duration="9.6"), _a()]
        with self.assertRaises(vp.ProcessingError) as cm:
            _verify(late, 1)
        self.assertEqual(cm.exception.key, "err.out_start_offset")
        _verify(late, 1, lead_s=0.4, ms=9600)      # the caller excludes the lead
        with self.assertRaises(vp.ProcessingError):
            _verify([_v(start_time="0.600000", duration="9.4"), _a()], 1, lead_s=0.4)


class FrameSlackTests(unittest.TestCase):
    def _frames(self, frames, **kw):
        _verify([_v(nb_frames=str(frames)), _a()], 1, **kw)

    def test_cfr_is_strict(self):
        self._frames(250)
        self._frames(251)
        with self.assertRaises(vp.ProcessingError):
            self._frames(255)

    def test_slack_is_proportional(self):
        self._frames(255, frame_slack=0.03)       # 1 + 7.5
        with self.assertRaises(vp.ProcessingError):
            self._frames(270, frame_slack=0.03)


class ProbeRoundOneTests(unittest.TestCase):
    def _probe_full(self, streams, fmt=None, chapters=0):
        data = {"format": {"duration": "10.0", **(fmt or {})}, "streams": streams,
                "chapters": [{}] * chapters}
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=data):
            return vp.probe(Path("a.mkv"), "ffprobe")

    def test_video_lead_from_stream_starts(self):
        info = self._probe_full([_vs(start_time="0.400000"),
                                 {"codec_type": "audio", "start_time": "0.000000"}])
        self.assertAlmostEqual(info.video_lead_s, 0.4)

    def test_no_lead_when_audio_starts_late_or_no_audio(self):
        info = self._probe_full([_vs(start_time="0.000000"),
                                 {"codec_type": "audio", "start_time": "0.479000"}])
        self.assertEqual(info.video_lead_s, 0.0)
        self.assertEqual(self._probe_full([_vs(start_time="0.4")]).video_lead_s, 0.0)

    def test_lead_is_relative_to_the_container_start(self):
        info = self._probe_full([_vs(start_time="1.400000"),
                                 {"codec_type": "audio", "start_time": "1.000000"}],
                                fmt={"start_time": "1.000000"})
        self.assertAlmostEqual(info.video_lead_s, 0.4)
        info = self._probe_full([_vs(start_time="1.0"), {"codec_type": "audio",
                                                          "start_time": "1.0"}],
                                fmt={"start_time": "1.0"})
        self.assertEqual(info.video_lead_s, 0.0)

    def test_matroska_duration_excludes_the_start_offset(self):
        # I3: 10 s of content starting at 1.0 s is reported as 11.0 s by Matroska
        info = self._probe_full([_vs()], fmt={"duration": "11.023", "start_time": "1.000000",
                                              "format_name": "matroska,webm"})
        self.assertEqual(info.duration_ms, 10023)

    def test_other_containers_already_report_the_length(self):
        # MPEG-TS: duration is end minus start already; subtracting again would cut the end off
        info = self._probe_full([_vs()], fmt={"duration": "10.021", "start_time": "1.458667",
                                              "format_name": "mpegts"})
        self.assertEqual(info.duration_ms, 10021)

    def test_chapters_are_counted(self):
        self.assertEqual(self._probe_full([_vs()], chapters=3).chapter_count, 3)
        self.assertEqual(self._probe_full([_vs()]).chapter_count, 0)

    def test_rate_gap_is_stored_for_the_frame_slack(self):
        info = self._probe_full([_vs(avg_frame_rate="2499/100", r_frame_rate="25/1")])
        self.assertAlmostEqual(info.rate_gap, 0.0004, places=5)
        self.assertEqual(self._probe_full([_vs()]).rate_gap, 0.0)


class AudioPadTests(unittest.TestCase):
    def test_apad_keeps_a_short_track_present(self):
        # I1: a track shorter than the cut must still come out (silence-padded, cut by -t)
        for info in (_info(audio_streams=[_astream(1, 2), _astream(2, 2)]), _info()):
            cmd = _cmd(info)
            self.assertEqual(_opt(cmd, "-af"), "apad")
            self.assertLess(cmd.index("-af"), cmd.index("-c:a"))
            self.assertGreater(cmd.index("-af"), cmd.index("-i"))

    def test_no_audio_no_filter(self):
        self.assertNotIn("-af", _cmd(_info(has_audio=False)))


class RoundOneSmallTests(unittest.TestCase):
    def test_bt2020c_matrix_is_given_to_zscale_as_bt2020nc(self):
        chain = ",".join(vp._hdr_chain(_info(color_transfer="smpte2084", color_space="bt2020c")))
        self.assertIn("min=bt2020nc", chain)
        self.assertNotIn("bt2020c", chain)

    def test_full_range_source_is_announced(self):
        self.assertEqual([k for k, _ in conversion_notes(_info(pix_fmt="yuvj420p",
                                                                 color_range="pc"))],
                         ["note.color_format"])

    def test_chapters_note_only_with_chapters(self):
        self.assertEqual([k for k, _ in conversion_notes(_info(subtitle_count=1))],
                         ["note.subtitles_dropped"])
        self.assertEqual([k for k, _ in conversion_notes(_info(chapter_count=2))],
                         ["note.chapters_dropped"])
        self.assertEqual([k for k, _ in conversion_notes(_info(subtitle_count=1,
                                                                 chapter_count=2))],
                         ["note.subtitles_dropped", "note.chapters_dropped"])
        for lang in ("en", "ru"):
            self.assertNotIn("chapter" if lang == "en" else "глав",
                             i18n.STRINGS[lang]["note.subtitles_dropped"].lower())

    def test_russian_messages_do_not_depend_on_the_number(self):
        # I4: "1 кадров" / "1 звуковых дорожек" would be wrong grammar
        ru = i18n.STRINGS["ru"]
        self.assertEqual(ru["err.out_frames_wrong"],
                         "Число кадров в готовом видео: {actual}, ожидалось примерно {expected}. "
                         "Часть изображения могла пропасть.")
        self.assertEqual(ru["err.out_audio_count"],
                         "Число звуковых дорожек в готовом видео: {actual}, "
                         "ожидалось: {expected}.")
        en = i18n.STRINGS["en"]
        self.assertIn("{actual}", en["err.out_frames_wrong"])
        self.assertNotIn("audio tracks instead", en["err.out_audio_count"])


# ---------------------------------------------------------------- notes before creating
class ConversionNotesTests(unittest.TestCase):
    def _keys(self, **kw):
        return [k for k, _ in conversion_notes(_info(**kw))]

    def test_nothing_converted_gives_no_notes(self):
        self.assertEqual(self._keys(pix_fmt="yuv420p", field_order="progressive"), [])
        self.assertEqual(self._keys(), [])
        self.assertEqual(self._keys(audio_streams=[_astream()]), [])

    def test_hdr(self):
        self.assertEqual(self._keys(pix_fmt="yuv420p10le", color_transfer="smpte2084"),
                         ["note.hdr_to_sdr"])

    def test_10bit_and_444(self):
        self.assertEqual(self._keys(pix_fmt="yuv420p10le"), ["note.color_format"])
        self.assertEqual(self._keys(pix_fmt="yuv444p"), ["note.color_format"])

    def test_interlaced_odd_size(self):
        self.assertEqual(self._keys(w=321, h=240, field_order="bb"),
                         ["note.deinterlace", "note.odd_size"])

    def test_audio_tracks_and_subtitles(self):
        keys = conversion_notes(_info(audio_streams=[_astream(1), _astream(2), _astream(3)],
                                      subtitle_count=2))
        self.assertEqual(keys, [("note.audio_tracks", {"n": 3}),
                                ("note.subtitles_dropped", {"n": 2})])

    def test_single_audio_track_is_not_news(self):
        self.assertEqual(self._keys(audio_streams=[_astream()]), [])


class NoteKeysTests(unittest.TestCase):
    KEYS = {"note.hdr_to_sdr": {}, "note.color_format": {}, "note.deinterlace": {},
            "note.odd_size": {}, "note.audio_tracks": {"n": 3}, "note.chapters_dropped": {},
            "note.subtitles_dropped": {"n": 2}, "dlg.create_notes": {"list": "a; b"},
            "err.out_audio_count": {"actual": 1, "expected": 3}}

    def test_keys_exist_and_russian_differs(self):
        for key, params in self.KEYS.items():
            for lang in ("en", "ru"):
                self.assertIn(key, i18n.STRINGS[lang], key)
                i18n.t_lang(lang, key, **params)
            self.assertNotEqual(i18n.STRINGS["en"][key], i18n.STRINGS["ru"][key], key)

    def test_confirm_text_without_notes_is_unchanged_in_shape(self):
        params = dict(n=1, total="0:01", name="a.mp4", folder="D:\\x", notes="")
        text = i18n.t_lang("en", "dlg.create_confirm", **params)
        self.assertIn("Folder: D:\\x\n\nYour original video", text)
        text = i18n.t_lang("en", "dlg.create_confirm", **{**params, "notes": "NOTE\n\n"})
        self.assertIn("Folder: D:\\x\n\nNOTE\n\nYour original", text)


if __name__ == "__main__":
    unittest.main()
