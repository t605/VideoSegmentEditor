import os
import unittest
from pathlib import Path
from unittest import mock

import i18n
from create_flow import default_work_root, progress_view


def ev(phase, segment, total, percent, key="progress.cut", **params):
    return {"phase": phase, "segment": segment, "total": total, "percent": percent,
            "message": "x", "key": key, "params": params}


class ProgressViewTests(unittest.TestCase):
    def test_extract(self):
        key, params, pct = progress_view(ev("extract", 2, 3, 40.5, i=2, n=3))
        self.assertEqual((key, params, pct), ("progress.cut", {"i": 2, "n": 3}, 40.5))

    def test_merge_verify_done(self):
        self.assertEqual(progress_view(ev("merge", 3, 3, 95.0, "progress.join")),
                         ("progress.join", {}, 95.0))
        self.assertEqual(progress_view(ev("verify", 3, 3, 99.0, "progress.verify")),
                         ("progress.verify", {}, 99.0))
        self.assertEqual(progress_view(ev("done", 3, 3, 100.0, "progress.done")),
                         ("progress.done", {}, 100.0))

    def test_percent_is_clamped(self):
        self.assertEqual(progress_view(ev("extract", 1, 1, 150, i=1, n=1))[2], 100.0)
        self.assertEqual(progress_view(ev("extract", 1, 1, -5, i=1, n=1))[2], 0.0)

    def test_unknown_phase_uses_event_key(self):
        key, params, pct = progress_view(ev("weird", 1, 1, 10, "progress.join"))
        self.assertEqual((key, params, pct), ("progress.join", {}, 10.0))

    def test_all_result_keys_exist_in_both_languages(self):
        for phase in ("extract", "merge", "verify", "done"):
            key, params, _ = progress_view(ev(phase, 1, 2, 5, i=1, n=2))
            for lang in i18n.LANGS:
                self.assertIn(key, i18n.STRINGS[lang])
                i18n.t_lang(lang, key, **params)  # fills without error


class WorkRootTests(unittest.TestCase):
    def test_under_localappdata(self):
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\L"}):
            self.assertEqual(default_work_root(),
                             Path(r"C:\L") / "VideoSegmentEditor" / "work")


class CreateKeysTests(unittest.TestCase):
    KEYS = ("dlg.create_title", "dlg.create_confirm", "dlg.create_failed_title",
            "dlg.create_done_title", "dlg.close_title", "dlg.close_message", "progress.cut",
            "progress.join", "progress.verify", "status.creating", "status.done", "out.saved")

    def test_keys_in_both_languages_and_russian_differs(self):
        for k in self.KEYS:
            self.assertIn(k, i18n.STRINGS["en"])
            self.assertIn(k, i18n.STRINGS["ru"])
            self.assertNotEqual(i18n.STRINGS["en"][k], i18n.STRINGS["ru"][k], k)

    def test_reviewed_russian_wording(self):
        ru = i18n.STRINGS["ru"]
        self.assertEqual(ru["progress.cut"], "Вырезается фрагмент {i} из {n}")
        self.assertIn("Итоговый файл: {name}", ru["dlg.create_confirm"])
        self.assertTrue(ru["status.creating"].endswith("..."))
        self.assertTrue(i18n.STRINGS["en"]["status.creating"].endswith("..."))


if __name__ == "__main__":
    unittest.main()
