import unittest

import i18n
from segment_manager import (Marker, Segment, SegmentError, SegmentList, TimeError,
                             format_ms, parse_time)


class TimeTests(unittest.TestCase):
    def test_format_ms(self):
        self.assertEqual(format_ms(65250), "00:01:05.250")
        self.assertEqual(format_ms(0), "00:00:00.000")
        self.assertEqual(format_ms(3723004), "01:02:03.004")

    def test_parse_time_forms(self):
        self.assertEqual(parse_time("1:05"), 65000)
        self.assertEqual(parse_time("00:00:12.500"), 12500)
        self.assertEqual(parse_time("7"), 7000)
        self.assertEqual(parse_time("1:05.5"), 65500)

    def test_parse_time_rejects(self):
        for bad in ("abc", "", "1:99", "-5"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_time(bad)


class SegmentListTests(unittest.TestCase):
    def setUp(self):
        self.sl = SegmentList(100000)

    def test_add_valid(self):
        seg = self.sl.add(1000, 5000)
        self.assertEqual(seg, Segment(1000, 5000))
        self.assertEqual(seg.duration_ms, 4000)
        self.assertEqual(len(self.sl), 1)

    def test_end_must_exceed_start(self):
        with self.assertRaises(SegmentError):
            self.sl.add(5000, 5000)
        with self.assertRaises(SegmentError):
            self.sl.add(5000, 4000)

    def test_cannot_exceed_duration(self):
        with self.assertRaises(SegmentError):
            self.sl.add(0, 100001)
        self.sl.add(0, 100000)

    def test_negative_start_rejected(self):
        with self.assertRaises(SegmentError):
            self.sl.add(-1, 500)

    def test_max_ten(self):
        for i in range(10):
            self.sl.add(i * 1000, i * 1000 + 500)
        self.assertTrue(self.sl.is_full())
        with self.assertRaises(SegmentError) as cm:
            self.sl.add(0, 100)
        self.assertIn("10", str(cm.exception))

    def test_move_up_down_and_edges(self):
        for i in range(3):
            self.sl.add(i * 1000, i * 1000 + 500)
        self.assertEqual(self.sl.move(0, -1), 0)
        self.assertEqual(self.sl.move(2, 1), 2)
        self.assertEqual(self.sl.move(0, 1), 1)
        self.assertEqual(self.sl.items[0].start_ms, 1000)
        self.assertEqual(self.sl.items[1].start_ms, 0)
        self.assertEqual(self.sl.move(1, -1), 0)
        self.assertEqual(self.sl.items[0].start_ms, 0)

    def test_edit_validates_and_keeps_old_on_error(self):
        self.sl.add(1000, 2000)
        with self.assertRaises(SegmentError):
            self.sl.edit(0, 3000, 2000)
        with self.assertRaises(SegmentError):
            self.sl.edit(0, 0, 100001)
        self.assertEqual(self.sl.items[0], Segment(1000, 2000))
        self.sl.edit(0, 500, 2500)
        self.assertEqual(self.sl.items[0], Segment(500, 2500))

    def test_delete_clear_total(self):
        self.sl.add(0, 1000)
        self.sl.add(2000, 5000)
        self.assertEqual(self.sl.total_ms(), 4000)
        self.sl.delete(0)
        self.assertEqual(self.sl.total_ms(), 3000)
        self.sl.clear()
        self.assertEqual(len(self.sl), 0)
        self.assertEqual(self.sl.total_ms(), 0)

    def test_overlap_allowed(self):
        self.sl.add(1000, 2000)
        self.sl.add(1000, 2000)
        self.assertEqual(len(self.sl), 2)


class KeyedErrorTests(unittest.TestCase):
    """Errors carry an i18n key + params; str() stays the exact English text."""

    def tearDown(self):
        i18n.set_language("en")

    def _raises(self, fn, *args):
        try:
            fn(*args)
        except (SegmentError, TimeError) as exc:
            return exc
        self.fail("no error raised")

    def test_parse_time_errors_are_keyed(self):
        cases = [("", "err.time_empty", {}),
                 ("abc", "err.time_invalid", {"text": "abc"}),
                 ("1:2:3:4", "err.time_invalid", {"text": "1:2:3:4"}),
                 ("1:99", "err.time_seconds", {"text": "1:99"}),
                 ("1:75:00", "err.time_minutes", {"text": "1:75:00"}),
                 ("1:00:75", "err.time_seconds", {"text": "1:00:75"})]
        for text, key, params in cases:
            with self.subTest(text=text):
                exc = self._raises(parse_time, text)
                self.assertIsInstance(exc, ValueError)
                self.assertEqual(exc.key, key)
                self.assertEqual(exc.params, params)
                self.assertEqual(str(exc), i18n.t_lang("en", key, **params))

    def test_parse_time_message_text_is_unchanged(self):
        self.assertEqual(str(self._raises(parse_time, "abc")),
                         "'abc' is not a valid time. Use hours:minutes:seconds, for example 00:01:05.250. "
                         "Short forms: 1:05 = 1 minute 5 seconds, 65 = 65 seconds.")
        self.assertEqual(str(self._raises(parse_time, "")),
                         "Please type a time. Use hours:minutes:seconds, for example 00:01:05.250. "
                         "Short forms: 1:05 = 1 minute 5 seconds, 65 = 65 seconds.")
        self.assertEqual(str(self._raises(parse_time, "1:99")),
                         "Seconds must be below 60 in '1:99'.")

    def test_none_is_empty(self):
        self.assertEqual(self._raises(parse_time, None).key, "err.time_empty")

    def test_format_ms_negative_is_keyed(self):
        exc = self._raises(format_ms, -1)
        self.assertEqual(exc.key, "err.time_negative")

    def test_text_with_braces_does_not_break(self):
        exc = self._raises(parse_time, "{x}")
        self.assertIn("{x}", str(exc))

    def test_segment_errors_are_keyed(self):
        sl = SegmentList(100000)
        e = self._raises(sl.add, -1, 500)
        self.assertEqual((e.key, e.params), ("err.seg_start_negative", {}))
        e = self._raises(sl.add, 5, 5)
        self.assertEqual((e.key, e.params), ("err.seg_end_not_after", {}))
        e = self._raises(sl.add, 0, 100001)
        self.assertEqual(e.key, "err.seg_past_end")
        self.assertEqual(e.params, {"duration": "00:01:40.000"})
        self.assertEqual(str(e), "The end time is past the end of the video (00:01:40.000).")
        for i in range(10):
            sl.add(i, i + 1)
        e = self._raises(sl.add, 0, 5)
        self.assertEqual((e.key, e.params), ("err.seg_max", {"max": 10}))
        self.assertEqual(str(e), "You can have at most 10 segments. Delete one to add another.")

    def test_str_is_english_whatever_the_language(self):
        i18n.set_language("ru")
        e = self._raises(SegmentList(10).add, 5, 5)
        self.assertEqual(str(e), "The end time must be after the start time.")
        self.assertNotEqual(i18n.t(e.key, **e.params), str(e))

    def test_reserved_param_names(self):
        with self.assertRaises(ValueError):
            SegmentError("err.seg_max", message_key="x")
        with self.assertRaises(ValueError):
            SegmentError("err.seg_max", detail="x")


class TextEntryTests(unittest.TestCase):
    def setUp(self):
        self.sl = SegmentList(100000)

    def test_add_text_short_forms(self):
        seg = self.sl.add_text("1:05", "01:10.500")
        self.assertEqual(seg, Segment(65000, 70500))

    def test_add_text_bad_start_reported_first(self):
        with self.assertRaises(TimeError) as cm:
            self.sl.add_text("x", "y")
        self.assertEqual(cm.exception.params, {"text": "x"})
        self.assertEqual(len(self.sl), 0)

    def test_add_text_bad_end(self):
        with self.assertRaises(TimeError) as cm:
            self.sl.add_text("1", "y")
        self.assertEqual(cm.exception.params, {"text": "y"})

    def test_add_text_full_list_checked_before_text(self):
        for i in range(10):
            self.sl.add(i, i + 1)
        with self.assertRaises(SegmentError) as cm:
            self.sl.add_text("x", "y")
        self.assertEqual(cm.exception.key, "err.seg_max")

    def test_edit_text_valid_and_invalid_keep_old(self):
        self.sl.add(1000, 2000)
        self.sl.edit_text(0, "0:01", "0:03")
        self.assertEqual(self.sl.items[0], Segment(1000, 3000))
        with self.assertRaises(TimeError):
            self.sl.edit_text(0, "zz", "0:03")
        with self.assertRaises(SegmentError):
            self.sl.edit_text(0, "0:05", "0:03")
        self.assertEqual(self.sl.items[0], Segment(1000, 3000))

    def test_bad_index_is_a_keyed_error_not_indexerror(self):
        self.sl.add(1000, 2000)
        for bad in (-1, 1, 5):
            with self.assertRaises(SegmentError) as cm:
                self.sl.edit(bad, 0, 10)
            self.assertEqual(cm.exception.key, "err.seg_bad_index")
            with self.assertRaises(SegmentError):
                self.sl.delete(bad)
            with self.assertRaises(SegmentError):
                self.sl.move(bad, 1)
        self.assertEqual(len(self.sl), 1)


class MarkerTests(unittest.TestCase):
    def setUp(self):
        self.sl = SegmentList(100000)
        self.m = Marker()

    def test_end_without_start_refused(self):
        with self.assertRaises(SegmentError) as cm:
            self.m.mark_end(5000, self.sl)
        self.assertEqual(cm.exception.key, "err.no_start")
        self.assertEqual(len(self.sl), 0)

    def test_mark_start_then_end_adds_and_clears_start(self):
        self.m.mark_start(1000, self.sl)
        self.assertEqual(self.m.start_ms, 1000)
        seg = self.m.mark_end(4000, self.sl)
        self.assertEqual(seg, Segment(1000, 4000))
        self.assertIsNone(self.m.start_ms)

    def test_failed_end_keeps_start(self):
        self.m.mark_start(5000, self.sl)
        for end in (5000, 4000, 100001):
            with self.assertRaises(SegmentError):
                self.m.mark_end(end, self.sl)
            self.assertEqual(self.m.start_ms, 5000)
        self.assertEqual(len(self.sl), 0)

    def test_mark_start_again_replaces(self):
        self.m.mark_start(1000, self.sl)
        self.m.mark_start(2000, self.sl)
        self.assertEqual(self.m.start_ms, 2000)

    def test_start_at_or_past_end_of_video_refused(self):
        with self.assertRaises(SegmentError) as cm:
            self.m.mark_start(100000, self.sl)
        self.assertEqual(cm.exception.key, "err.seg_start_late")
        self.assertIsNone(self.m.start_ms)

    def test_negative_start_refused(self):
        with self.assertRaises(SegmentError):
            self.m.mark_start(-5, self.sl)

    def test_full_list_refuses_mark_start(self):
        for i in range(10):
            self.sl.add(i, i + 1)
        with self.assertRaises(SegmentError) as cm:
            self.m.mark_start(50, self.sl)
        self.assertEqual(cm.exception.key, "err.seg_max")

    def test_clear(self):
        self.m.mark_start(5, self.sl)
        self.m.clear()
        self.assertIsNone(self.m.start_ms)


if __name__ == "__main__":
    unittest.main()
