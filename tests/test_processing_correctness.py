"""Unit tests for WP1a-1 (processing correctness). Offline: ffprobe results are injected."""
import shutil
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest import mock

import i18n
import video_processor as vp
from segment_manager import Segment

_Usage = namedtuple("usage", "total used free")
MB = 1024 ** 2
GB = 1024 ** 3


def _info(fps=25.0, w=1920, h=1080, has_audio=True):
    return vp.VideoInfo(Path("a.mp4"), 60000, w, h, fps, has_audio)


def _stream(kind, **kw):
    s = {"codec_type": kind}
    s.update(kw)
    return s


def _data(video_dur="10.0", audio_dur="10.0", fmt="10.0", frames=None, fps="25/1",
          v_start="0.000000", audio=True, video=True):
    streams = []
    if video:
        v = _stream("video", width=640, height=360, avg_frame_rate=fps, duration=video_dur,
                    start_time=v_start)
        if frames is not None:
            v["nb_frames"] = str(frames)
        streams.append(v)
    if audio:
        streams.append(_stream("audio", duration=audio_dur, start_time="0.000000"))
    return {"format": {"duration": fmt} if fmt is not None else {}, "streams": streams}


# --------------------------------------------------------------------------- 1. part check
class PartProblemTests(unittest.TestCase):
    def _problem(self, data, seg=Segment(1000, 5000), had_audio=True, fps=25.0):
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=data):
            return vp.part_problem(Path("p.mp4"), seg, had_audio, fps, "ffprobe")

    def test_good_part(self):
        self.assertIsNone(self._problem(_data("4.0", "4.02", "4.02")))

    def test_within_tolerance(self):
        # tolerance = max(0.25 s, 3 frames = 0.12 s) = 0.25 s
        self.assertIsNone(self._problem(_data("4.24", "4.24", "4.24")))
        self.assertIsNone(self._problem(_data("3.76", "3.76", "3.76")))

    def test_outside_tolerance(self):
        self.assertIsNotNone(self._problem(_data("4.26", "4.26", "4.26")))
        self.assertIsNotNone(self._problem(_data("3.74", "3.74", "3.74")))

    def test_three_frames_wins_at_low_fps(self):
        # 10 fps: 3 frames = 0.3 s > 0.25 s
        seg = Segment(0, 4000)
        self.assertIsNone(self._problem(_data("4.29", "4.29", "4.29", fps="10/1"), seg, fps=10.0))
        self.assertIsNotNone(self._problem(_data("4.31", "4.31", "4.31", fps="10/1"), seg, fps=10.0))

    def test_header_only_part_has_no_duration(self):
        data = _data(video_dur=None, audio_dur=None, fmt=None)
        data["streams"][0].pop("duration")
        self.assertIsNotNone(self._problem(data))

    def test_zero_duration(self):
        self.assertIsNotNone(self._problem(_data("0.000000", "0.0", "0.0")))

    def test_no_video_stream(self):
        self.assertIsNotNone(self._problem(_data(video=False)))

    def test_audio_missing_only_if_source_had_audio(self):
        self.assertIsNotNone(self._problem(_data(audio=False), had_audio=True))
        self.assertIsNone(self._problem(_data("4.0", fmt="4.0", audio=False), had_audio=False))

    def test_unreadable_part_is_a_problem_not_an_exception(self):
        with mock.patch.object(vp, "_run_ffprobe_json",
                               side_effect=vp.ProcessingError("err.not_a_video")):
            self.assertIsNotNone(vp.part_problem(Path("p.mp4"), Segment(0, 1000), True, 25.0,
                                                 "ffprobe"))

    def test_unknown_fps_uses_default(self):
        self.assertIsNone(self._problem(_data("4.0", "4.0", "4.0"), fps=0.0))


class PartInJobTests(unittest.TestCase):
    """VideoJob must fail with err.part_invalid (segment i of n) and keep the temp folder."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = self.tmp / "a.mp4"
        self.src.write_bytes(b"x" * 100)

    def test_header_only_part_fails_the_job(self):
        segs = [Segment(0, 1000), Segment(2000, 3000)]
        job = vp.VideoJob(self.src, _info(), segs, "ffmpeg", "ffprobe", lambda e: None,
                          self.tmp / "work")

        def fake_ffmpeg(cmd, err_file, on_time):
            Path(cmd[-1]).write_bytes(b"h" * 261)  # exit 0, header only

        with mock.patch.object(job, "_run_ffmpeg", side_effect=fake_ffmpeg), \
                mock.patch.object(vp, "part_problem", return_value="no duration"), \
                mock.patch.object(vp, "check_job_disk_space"):
            with self.assertRaises(vp.ProcessingError) as cm:
                job.run()
        self.assertEqual(cm.exception.key, "err.part_invalid")
        self.assertEqual(cm.exception.params["i"], 1)
        self.assertEqual(cm.exception.params["n"], 2)
        self.assertIn("kept_dir", cm.exception.params)
        self.assertTrue(Path(cm.exception.params["kept_dir"]).is_dir())
        self.assertEqual(cm.exception.detail, "no duration")


# --------------------------------------------------------------------------- 2. verify_output
class VerifyOutputStreamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = self.tmp / "o.mp4"
        self.out.write_bytes(b"data")

    def _verify(self, data, expected=10000, n=2, had_audio=True, fps=25.0):
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=data):
            vp.verify_output(self.out, expected, n, had_audio, "ffprobe", fps=fps)

    def _key(self, data, **kw):
        with self.assertRaises(vp.ProcessingError) as cm:
            self._verify(data, **kw)
        return cm.exception.key

    def test_good_with_priming(self):
        # audio 42 ms longer than video (2 segments x ~21 ms priming): allowed (100 + 60 ms)
        self._verify(_data("10.0", "10.042", "10.042", frames=250))

    def test_av_mismatch_edge(self):
        # allowed difference for n=2: 100 + 30*2 = 160 ms
        self._verify(_data("10.0", "10.16", "10.16", frames=250))
        self.assertEqual(self._key(_data("10.0", "10.17", "10.17", frames=250)),
                         "err.out_av_mismatch")

    def test_audio_shorter_than_video_also_fails(self):
        self.assertEqual(self._key(_data("10.0", "9.8", "10.0", frames=250)),
                         "err.out_av_mismatch")

    def test_av_mismatch_params(self):
        with self.assertRaises(vp.ProcessingError) as cm:
            self._verify(_data("1.0", "4.0", "4.0", frames=25), expected=4000, n=1)
        self.assertEqual(cm.exception.params, {"video": "1.0", "audio": "4.0"})

    def test_av_not_compared_without_audio(self):
        self._verify(_data("10.0", fmt="10.0", frames=250, audio=False), had_audio=False)

    def test_frame_count_edge(self):
        # expected 250 frames, tolerance +-1 per segment = 2
        self._verify(_data("10.0", "10.0", "10.0", frames=252))
        self._verify(_data("10.0", "10.0", "10.0", frames=248))
        self.assertEqual(self._key(_data("10.0", "10.0", "10.0", frames=253)),
                         "err.out_frames_wrong")
        self.assertEqual(self._key(_data("10.0", "10.0", "10.0", frames=247)),
                         "err.out_frames_wrong")

    def test_frame_count_params(self):
        with self.assertRaises(vp.ProcessingError) as cm:
            self._verify(_data("10.0", "10.0", "10.0", frames=200))
        self.assertEqual(cm.exception.params, {"actual": 200, "expected": 250})

    def test_frame_count_falls_back_to_duration_times_fps(self):
        self._verify(_data("10.0", "10.0", "10.0"))  # no nb_frames: 10.0 * 25 = 250
        self.assertEqual(self._key(_data("9.8", "9.8", "10.0")), "err.out_frames_wrong")

    def test_frame_check_skipped_without_fps(self):
        self._verify(_data("10.0", "10.0", "10.0", frames=5), fps=0.0)

    def test_start_time_edge(self):
        self._verify(_data("10.0", "10.0", "10.0", frames=250, v_start="0.149"))
        self.assertEqual(self._key(_data("10.0", "10.0", "10.0", frames=250, v_start="0.151")),
                         "err.out_start_offset")

    def test_start_time_missing_is_ignored(self):
        data = _data("10.0", "10.0", "10.0", frames=250)
        del data["streams"][0]["start_time"]
        self._verify(data)

    def test_container_length_check_kept(self):
        # streams consistent with each other but both far too short
        self.assertEqual(self._key(_data("8.0", "8.0", "8.0", frames=200), fps=0.0),
                         "err.out_wrong_length")

    def test_old_rules_still_work(self):
        self.assertEqual(self._key(_data(video=False)), "err.out_no_picture")
        self.assertEqual(self._key(_data(audio=False)), "err.out_no_sound")
        unreadable = {"format": {}, "streams": [_stream("video", avg_frame_rate="25/1"),
                                                _stream("audio")]}
        self.assertEqual(self._key(unreadable), "err.out_length_unreadable")


# --------------------------------------------------------------------------- 3. odd size
class OddSizeCommandTests(unittest.TestCase):
    def _cmd(self, w, h, **kw):
        return vp.extract_cmd("ffmpeg", Path("in.mp4"), Segment(0, 1000), Path("o.mp4"),
                              _info(w=w, h=h, **kw))

    # since WP1a-2 the filter chain always ends with the colour-tag filter (setparams)
    @staticmethod
    def _vf(cmd):
        return cmd[cmd.index("-vf") + 1]

    def test_even_size_has_no_crop(self):
        self.assertNotIn("crop", self._vf(self._cmd(1920, 1080)))

    def test_odd_width_gets_crop(self):
        vf = self._vf(self._cmd(321, 240))
        self.assertTrue(vf.startswith("crop=trunc(iw/2)*2:trunc(ih/2)*2,setparams="), vf)

    def test_odd_height_gets_crop(self):
        self.assertIn("crop=", self._vf(self._cmd(640, 241)))

    def test_both_odd(self):
        self.assertIn("crop=", self._vf(self._cmd(321, 241)))

    def test_filter_is_an_output_option(self):
        cmd = self._cmd(321, 241)
        self.assertGreater(cmd.index("-vf"), cmd.index("-i"))
        self.assertLess(cmd.index("-vf"), cmd.index("-c:v"))


# --------------------------------------------------------------------------- 4. name length
def _units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


class NameLengthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_short_name_unchanged(self):
        self.assertEqual(vp.unique_output_path(self.tmp / "clip.mp4").name,
                         "clip (segmented).mp4")

    def test_240_char_stem_is_truncated(self):
        src = self.tmp / ("N" * 240 + ".mp4")
        out = vp.unique_output_path(src)
        self.assertTrue(out.name.endswith(" (segmented).mp4"))
        self.assertLessEqual(len(out.name + ".part"), 255)
        # the longest name that can occur stays within 240 characters
        longest = out.name.replace("(segmented)", "(segmented 99)") + ".part"
        self.assertLessEqual(len(longest), 240)
        self.assertEqual(out.parent, self.tmp)

    def test_boundary_stem_not_truncated(self):
        limit = 240 - len(" (segmented 99).mp4.part")
        out = vp.unique_output_path(self.tmp / ("N" * limit + ".mp4"))
        self.assertEqual(out.name, "N" * limit + " (segmented).mp4")
        out = vp.unique_output_path(self.tmp / ("N" * (limit + 1) + ".mp4"))
        self.assertEqual(out.name, "N" * limit + " (segmented).mp4")

    def test_unicode_counts_characters_not_bytes(self):
        limit = 240 - len(" (segmented 99).mp4.part")
        stem = "Ж" * limit  # 2 bytes each in UTF-8, one character each
        out = vp.unique_output_path(self.tmp / (stem + ".mkv"))
        self.assertEqual(out.name, stem + " (segmented).mp4")

    def test_astral_characters_count_as_two(self):
        # NTFS limits UTF-16 code units: an emoji is two of them
        out = vp.unique_output_path(self.tmp / ("\U0001F600" * 200 + ".mp4"))
        self.assertLessEqual(_units(out.name + ".part"), 255)
        self.assertLessEqual(_units(out.name.replace("(segmented)", "(segmented 99)") + ".part"),
                             240)
        self.assertNotIn("\ufffd", out.name)

    def test_uniqueness_still_works_after_truncation(self):
        src = self.tmp / ("N" * 300 + ".mp4")
        first = vp.unique_output_path(src)
        first.write_bytes(b"x")
        second = vp.unique_output_path(src)
        self.assertNotEqual(first, second)
        self.assertTrue(second.name.endswith(" (segmented 2).mp4"))
        self.assertLessEqual(_units(second.name + ".part"), 255)

    def test_source_is_never_renamed_or_touched(self):
        src = self.tmp / ("N" * 300 + ".mp4")
        out = vp.unique_output_path(src)
        self.assertEqual(out.parent, src.parent)            # beside the source
        self.assertTrue(out.name.startswith("N" * 20))      # named after it (shortened)
        self.assertNotEqual(out, src)
        self.assertFalse(src.exists())  # we never created it; nothing was created either
        self.assertFalse(out.exists())


# --------------------------------------------------------------------------- 5. disk guard
class JobDiskSpaceTests(unittest.TestCase):
    def _check(self, out_dir, work_dir, free_by_folder, source=4 * GB, sel=5000, total=10000):
        def usage(folder):
            return _Usage(10 ** 13, 0, free_by_folder[str(folder)])
        with mock.patch.object(vp.shutil, "disk_usage", side_effect=usage):
            vp.check_job_disk_space(Path(out_dir), Path(work_dir), source, sel, total)

    def test_estimate_formula(self):
        self.assertEqual(vp.estimate_output_bytes(4 * GB, 5000, 10000), int(4 * GB * 0.5 * 1.5))
        self.assertEqual(vp.estimate_output_bytes(4 * GB, 5000, 0), 0)

    def test_different_drives_each_checked_separately_ok(self):
        # estimate 3 GB: work needs 6 GB, output needs 3 GB
        self._check("D:\\out", "C:\\work", {"D:\\out": 3 * GB + MB, "C:\\work": 6 * GB + MB})

    def test_different_drives_work_drive_too_small(self):
        with self.assertRaises(vp.ProcessingError) as cm:
            self._check("D:\\out", "C:\\work", {"D:\\out": 100 * GB, "C:\\work": 5 * GB})
        self.assertEqual(cm.exception.key, "err.disk_low")

    def test_different_drives_output_drive_too_small(self):
        with self.assertRaises(vp.ProcessingError) as cm:
            self._check("D:\\out", "C:\\work", {"D:\\out": 2 * GB, "C:\\work": 100 * GB})
        self.assertEqual(cm.exception.key, "err.disk_low")

    def test_same_drive_needs_the_sum(self):
        # 6 GB (work) + 3 GB (output) = 9 GB on one drive: 8 GB is not enough ...
        with self.assertRaises(vp.ProcessingError) as cm:
            self._check("C:\\out", "C:\\work", {"C:\\out": 8 * GB, "C:\\work": 8 * GB})
        self.assertEqual(cm.exception.key, "err.disk_low")
        self.assertEqual(cm.exception.params["needed"], f"{9 * GB / MB:.0f}")
        # ... while each of the two needs alone would have passed (which the old code allowed)
        self._check("C:\\out", "C:\\work", {"C:\\out": 9 * GB + MB, "C:\\work": 9 * GB + MB})

    def test_same_drive_is_case_insensitive(self):
        with self.assertRaises(vp.ProcessingError):
            self._check("c:\\out", "C:\\work", {"c:\\out": 8 * GB, "C:\\work": 8 * GB})

    def test_floor_of_200_mb(self):
        with self.assertRaises(vp.ProcessingError):
            self._check("D:\\o", "C:\\w", {"D:\\o": 100 * MB, "C:\\w": GB}, source=1000)
        self._check("D:\\o", "C:\\w", {"D:\\o": 201 * MB, "C:\\w": 201 * MB}, source=1000)

    def test_same_drive_floor_is_sum_of_floors(self):
        with self.assertRaises(vp.ProcessingError):
            self._check("C:\\o", "C:\\w", {"C:\\o": 399 * MB, "C:\\w": 399 * MB}, source=1000)
        self._check("C:\\o", "C:\\w", {"C:\\o": 401 * MB, "C:\\w": 401 * MB}, source=1000)

    def test_oserror_keeps_disk_check_key(self):
        with mock.patch.object(vp.shutil, "disk_usage", side_effect=FileNotFoundError("gone")):
            with self.assertRaises(vp.ProcessingError) as cm:
                vp.check_job_disk_space(Path("D:\\x"), Path("C:\\y"), 1, 1, 2)
        self.assertEqual(cm.exception.key, "err.disk_check")

    def test_same_volume_helper(self):
        self.assertTrue(vp._same_volume(Path("C:\\a"), Path("c:\\b\\c")))
        self.assertFalse(vp._same_volume(Path("C:\\a"), Path("D:\\a")))

    def test_same_volume_without_drive_letters_uses_st_dev(self):
        def fake_stat(p, *a, **k):
            return mock.Mock(st_dev=1 if "same" in str(p) else 2)
        with mock.patch.object(vp.os.path, "splitdrive", side_effect=lambda p: ("", p)), \
                mock.patch.object(vp.os, "stat", side_effect=fake_stat):
            self.assertTrue(vp._same_volume(Path("/same/a"), Path("/same/b")))
            self.assertFalse(vp._same_volume(Path("/same/a"), Path("/other/b")))

    def test_legacy_single_folder_check_still_available(self):
        with mock.patch.object(vp.shutil, "disk_usage", return_value=_Usage(10 ** 12, 0, MB)):
            with self.assertRaises(vp.ProcessingError):
                vp.check_disk_space(Path("."), 10 ** 6, 1000, 10000)


# --------------------------------------------------------------------------- 6. rotation
def _rot_data(rotation_tag=None, side_rotation=None, w=360, h=640):
    v = _stream("video", width=w, height=h, avg_frame_rate="30/1", duration="10.0")
    if rotation_tag is not None:
        v["tags"] = {"rotate": str(rotation_tag)}
    if side_rotation is not None:
        v["side_data_list"] = [{"side_data_type": "Display Matrix", "rotation": side_rotation}]
    return {"format": {"duration": "10.0"}, "streams": [v]}


class RotationTests(unittest.TestCase):
    def _probe(self, data):
        with mock.patch.object(vp, "_run_ffprobe_json", return_value=data):
            return vp.probe(Path("x.mp4"), "ffprobe")

    def test_side_data_90_swaps(self):
        info = self._probe(_rot_data(side_rotation=90))
        self.assertEqual((info.width, info.height), (640, 360))

    def test_side_data_minus_90_swaps(self):
        info = self._probe(_rot_data(side_rotation=-90))
        self.assertEqual((info.width, info.height), (640, 360))

    def test_side_data_270_swaps(self):
        info = self._probe(_rot_data(side_rotation=270))
        self.assertEqual((info.width, info.height), (640, 360))

    def test_tag_rotate_swaps(self):
        info = self._probe(_rot_data(rotation_tag=90))
        self.assertEqual((info.width, info.height), (640, 360))
        info = self._probe(_rot_data(rotation_tag=270))
        self.assertEqual((info.width, info.height), (640, 360))

    def test_180_and_zero_do_not_swap(self):
        for kw in ({"side_rotation": 180}, {"side_rotation": 0}, {"rotation_tag": 180}, {}):
            info = self._probe(_rot_data(**kw))
            self.assertEqual((info.width, info.height), (360, 640), kw)

    def test_garbage_rotation_ignored(self):
        info = self._probe(_rot_data(rotation_tag="abc"))
        self.assertEqual((info.width, info.height), (360, 640))

    def test_odd_size_filter_uses_either_dimension(self):
        # display size (swapped) of a rotated 361x640 clip is 640x361: still odd
        info = self._probe(_rot_data(side_rotation=90, w=361, h=640))
        cmd = vp.extract_cmd("ffmpeg", Path("in.mp4"), Segment(0, 1000), Path("o.mp4"), info)
        self.assertIn("crop=", cmd[cmd.index("-vf") + 1])


# --------------------------------------------------------------------------- 7. keyframes
class KeyframeArgumentTests(unittest.TestCase):
    def _g(self, fps):
        cmd = vp.extract_cmd("ffmpeg", Path("in.mp4"), Segment(0, 1000), Path("o.mp4"),
                             _info(fps=fps))
        self.assertLess(cmd.index("-g"), cmd.index("-c:a"))
        return int(cmd[cmd.index("-g") + 1])

    def test_values(self):
        self.assertEqual(self._g(25.0), 50)
        self.assertEqual(self._g(30.0), 60)
        self.assertEqual(self._g(29.97), 60)
        self.assertEqual(self._g(60.0), 120)

    def test_clamped(self):
        self.assertEqual(self._g(5.0), 25)
        self.assertEqual(self._g(120.0), 120)
        self.assertEqual(self._g(240.0), 120)

    def test_unknown_fps_falls_back_to_50(self):
        self.assertEqual(self._g(0.0), 50)

    def test_g_is_next_to_libx264_options(self):
        cmd = vp.extract_cmd("ffmpeg", Path("in.mp4"), Segment(0, 1000), Path("o.mp4"), _info())
        self.assertGreater(cmd.index("-g"), cmd.index("-c:v"))


# --------------------------------------------------------------------------- i18n of new keys
class NewKeyTests(unittest.TestCase):
    KEYS = {
        "err.part_invalid": {"i": 2, "n": 5},
        "err.out_av_mismatch": {"video": "1.0", "audio": "4.0"},
        "err.out_frames_wrong": {"actual": 200, "expected": 250},
        "err.out_start_offset": {"offset": "0.2"},
    }

    def test_keys_in_both_languages_and_fill(self):
        for key, params in self.KEYS.items():
            en = i18n.t_lang("en", key, **params)
            ru = i18n.t_lang("ru", key, **params)
            self.assertNotEqual(en, key)
            self.assertNotEqual(ru, key)
            self.assertNotEqual(en, ru)
            self.assertNotIn("{", en + ru)

    def test_error_text_is_english(self):
        exc = vp.ProcessingError("err.part_invalid", i=1, n=3)
        self.assertIn("Segment 1 of 3", str(exc))


if __name__ == "__main__":
    unittest.main()
