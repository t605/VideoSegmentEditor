"""Tests for the English / Russian interface strings (Task 5b). No GUI, no FFmpeg."""
import json
import re
import string
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import i18n
from i18n import LANGS, set_language, get_language, t

ROOT = Path(__file__).resolve().parent.parent
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


class KeyParityTests(unittest.TestCase):
    def test_langs(self):
        self.assertEqual(LANGS, ("en", "ru"))

    def test_same_keys_in_both_languages(self):
        en, ru = set(i18n.STRINGS["en"]), set(i18n.STRINGS["ru"])
        self.assertEqual(sorted(en - ru), [], "keys missing in Russian")
        self.assertEqual(sorted(ru - en), [], "keys missing in English")

    def test_key_names_are_dotted_lowercase(self):
        for key in i18n.STRINGS["en"]:
            self.assertRegex(key, KEY_RE)

    def test_same_placeholders_in_both_languages(self):
        for key, text in i18n.STRINGS["en"].items():
            self.assertEqual(placeholders(text), placeholders(i18n.STRINGS["ru"][key]), key)

    def test_no_empty_texts(self):
        for lang in LANGS:
            for key, text in i18n.STRINGS[lang].items():
                self.assertTrue(text.strip(), f"{lang}:{key}")

    def test_every_template_formats(self):
        for lang in LANGS:
            for key, text in i18n.STRINGS[lang].items():
                params = {n: "x" for n in placeholders(text)}
                text.format(**params)  # must not raise


IDENTICAL_OK = {"app.name", "info.loaded"}


class WordingTests(unittest.TestCase):
    def test_russian_differs_from_english(self):
        for key, en in i18n.STRINGS["en"].items():
            if key not in IDENTICAL_OK:
                self.assertNotEqual(en, i18n.STRINGS["ru"][key], key)

    def test_reserved_names_are_not_placeholders(self):
        for lang in LANGS:
            for key, text in i18n.STRINGS[lang].items():
                bad = placeholders(text) & {"detail", "message_key", "kept_dir"}
                self.assertEqual(bad, set(), f"{lang}:{key}")

    def test_call_site_params_cover_placeholders(self):
        import ast
        tree = ast.parse((ROOT / "video_processor.py").read_text(encoding="utf-8"))
        checked = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            first = node.args[0]
            if name not in ("ProcessingError", "Cancelled", "_fail", "_emit"):
                continue
            if name == "_emit":
                first = node.args[3] if len(node.args) > 3 else None
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            given = {k.arg for k in node.keywords if k.arg}
            need = placeholders(i18n.STRINGS["en"][first.value])
            self.assertLessEqual(need, given, f"line {node.lineno}: {first.value}")
            checked += 1
        self.assertGreaterEqual(checked, 25)

    def test_missing_parameter_is_logged(self):
        import io
        from contextlib import redirect_stderr
        buf = io.StringIO()
        with redirect_stderr(buf):
            self.assertIn("{name}", t("status.reading"))
        self.assertIn("status.reading", buf.getvalue())

    def test_russian_decimal_comma_english_dot(self):
        import video_processor as vp
        exc = vp.ProcessingError("err.out_wrong_length", actual="12.3", expected="10.0")
        self.assertIn("12.3 s instead of 10.0 s", str(exc))
        self.assertIn("12,3 с", i18n.t_lang("ru", "err.out_wrong_length", actual="12.3",
                                               expected="10.0"))
        self.assertIn("10,0 с", i18n.t_lang("ru", "err.out_wrong_length", actual="12.3",
                                               expected="10.0"))

    def test_reserved_message_key_param(self):
        import video_processor as vp
        with self.assertRaises(ValueError):
            vp.ProcessingError("err.cancelled", message_key="x")

    def test_fail_with_kept_dir_param_does_not_raise_typeerror(self):
        import video_processor as vp
        job = vp.VideoJob(Path("a.mp4"), None, [], "f", "p", lambda e: None, Path("w"))
        job._work_dir = Path("C:/w/job_1")
        exc = job._fail("err.ffmpeg_failed", "d", kept_dir="old")
        self.assertIn("job_1", str(exc))
        self.assertNotIn("old", str(exc))


class TranslateTests(unittest.TestCase):
    def tearDown(self):
        set_language("en")

    def test_default_is_english(self):
        self.assertEqual(get_language(), "en")
        self.assertEqual(t("btn.load_video"), "Load Video")

    def test_switch_to_russian_and_back(self):
        set_language("ru")
        self.assertEqual(get_language(), "ru")
        self.assertEqual(t("btn.load_video"), "Загрузить видео")
        set_language("en")
        self.assertEqual(t("btn.load_video"), "Load Video")

    def test_unknown_language_raises(self):
        with self.assertRaises(ValueError):
            set_language("xx")
        self.assertEqual(get_language(), "en")

    def test_unknown_key_returns_key(self):
        self.assertEqual(t("no.such_key"), "no.such_key")

    def test_missing_russian_key_falls_back_to_english(self):
        with mock.patch.dict(i18n.STRINGS["en"], {"test.only_en": "English only"}):
            set_language("ru")
            self.assertEqual(t("test.only_en"), "English only")

    def test_parameters(self):
        self.assertEqual(t("status.reading", name="a.mp4"), "Reading a.mp4 ...")
        set_language("ru")
        self.assertIn("a.mp4", t("status.reading", name="a.mp4"))

    def test_missing_parameter_does_not_crash(self):
        self.assertIsInstance(t("status.reading"), str)

    def test_kept_dir_is_appended(self):
        text = t("err.cancelled", kept_dir="C:\\work\\job_1")
        self.assertTrue(text.startswith("Cancelled."))
        self.assertIn("C:\\work\\job_1", text)
        set_language("ru")
        self.assertIn("C:\\work\\job_1", t("err.cancelled", kept_dir="C:\\work\\job_1"))
        self.assertNotIn("C:\\work", t("err.cancelled"))

    def test_t_lang_ignores_current_language(self):
        set_language("ru")
        self.assertEqual(i18n.t_lang("en", "btn.load_video"), "Load Video")

    def test_timestamps_are_not_translated(self):
        for lang in LANGS:
            self.assertIn("{time}", i18n.STRINGS[lang]["label.total"])


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "sub" / "settings.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_round_trip(self):
        i18n.save_language(self.path, "ru")
        self.assertEqual(i18n.load_saved_language(self.path), "ru")
        i18n.save_language(self.path, "en")
        self.assertEqual(i18n.load_saved_language(self.path), "en")

    def test_file_content_uses_language_key(self):
        i18n.save_language(self.path, "ru")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["language"], "ru")

    def test_other_settings_are_kept(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({"other": 5}), encoding="utf-8")
        i18n.save_language(self.path, "ru")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data, {"other": 5, "language": "ru"})

    def test_missing_file_gives_english(self):
        self.assertEqual(i18n.load_saved_language(self.path), "en")

    def test_corrupt_file_gives_english(self):
        self.path.parent.mkdir()
        for bad in (b"{not json", b"", b"[1, 2]", b"\xff\xfe\x00", b'{"language": 5}',
                    b'{"language": "fr"}'):
            self.path.write_bytes(bad)
            self.assertEqual(i18n.load_saved_language(self.path), "en", bad)

    def test_corrupt_file_is_replaced_on_save(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b"{not json")
        i18n.save_language(self.path, "ru")
        self.assertEqual(i18n.load_saved_language(self.path), "ru")

    def test_write_failure_is_ignored(self):
        with mock.patch.object(i18n.os, "replace", side_effect=PermissionError("denied")):
            i18n.save_language(self.path, "ru")  # must not raise
        with mock.patch.object(Path, "mkdir", side_effect=OSError("no")):
            i18n.save_language(self.path, "ru")

    def test_save_rejects_unknown_language(self):
        with self.assertRaises(ValueError):
            i18n.save_language(self.path, "xx")

    def test_default_settings_path(self):
        with mock.patch.dict(i18n.os.environ, {"LOCALAPPDATA": "C:\\L"}):
            p = i18n.default_settings_path()
        self.assertEqual(p, Path("C:\\L") / "VideoSegmentEditor" / "settings.json")


class SourceKeyTests(unittest.TestCase):
    """Grep-style: every key literal used in the code exists in both languages."""

    def _namespaces(self):
        return {k.split(".")[0] for k in i18n.STRINGS["en"]}

    def _check(self, filename):
        text = (ROOT / filename).read_text(encoding="utf-8")
        literals = set(re.findall(r'"([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)"', text))
        used = {s for s in literals if s.split(".")[0] in self._namespaces()}
        self.assertTrue(used, filename)
        for key in sorted(used):
            self.assertIn(key, i18n.STRINGS["en"], f"{filename}: {key}")
            self.assertIn(key, i18n.STRINGS["ru"], f"{filename}: {key}")

    def test_video_processor_keys_exist(self):
        self._check("video_processor.py")

    def test_gui_keys_exist(self):
        self._check("gui.py")

    def test_segment_manager_keys_exist(self):
        self._check("segment_manager.py")

    def test_segment_manager_call_sites_are_keyed_and_cover_placeholders(self):
        import ast
        tree = ast.parse((ROOT / "segment_manager.py").read_text(encoding="utf-8"))
        checked = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            if name not in ("SegmentError", "TimeError"):
                continue
            first = node.args[0] if node.args else None
            self.assertTrue(isinstance(first, ast.Constant) and isinstance(first.value, str),
                            f"line {node.lineno}: first argument must be a key literal")
            self.assertIn(first.value, i18n.STRINGS["en"], f"line {node.lineno}")
            given = {k.arg for k in node.keywords if k.arg}
            need = placeholders(i18n.STRINGS["en"][first.value])
            self.assertLessEqual(need, given, f"line {node.lineno}: {first.value}")
            checked += 1
        self.assertGreaterEqual(checked, 14)

    def test_segment_manager_has_no_english_sentence_in_raise_sites(self):
        src = (ROOT / "segment_manager.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'raise (?:Segment|Time)Error\(\s*f?"[^"]* [^"]*"', src), [])

    def test_no_english_sentence_left_in_error_sites(self):
        src = (ROOT / "video_processor.py").read_text(encoding="utf-8")
        for name in ("ProcessingError", "Cancelled", "_fail", "_emit"):
            bad = re.findall(name + r'\(\s*(?:[^"()]*,\s*)?f?"[^"]* [^"]*"', src)
            self.assertEqual(bad, [], name)

    def test_every_raise_site_has_a_literal_key(self):
        src = (ROOT / "video_processor.py").read_text(encoding="utf-8")
        sites = re.findall(r'raise (?:self\._fail|ProcessingError|Cancelled)\(\s*([^,)\s]+)', src)
        self.assertGreaterEqual(len(sites), 20)
        for first in sites:
            self.assertTrue(first.startswith('"err.') or first in ("exc.key", "msg"), first)


class ProcessingErrorTests(unittest.TestCase):
    def tearDown(self):
        set_language("en")

    def test_str_is_english_and_key_params_available(self):
        import video_processor as vp
        set_language("ru")  # str() must stay English whatever the interface language
        exc = vp.ProcessingError("err.not_a_video", detail="tail")
        self.assertEqual(str(exc), "This file could not be read as a video.")
        self.assertEqual(exc.key, "err.not_a_video")
        self.assertEqual(exc.params, {})
        self.assertEqual(exc.detail, "tail")
        self.assertNotEqual(t(exc.key, **exc.params), str(exc))

    def test_params_and_detail_default(self):
        import video_processor as vp
        exc = vp.ProcessingError("err.segment_empty", i=2)
        self.assertEqual(exc.detail, "")
        self.assertEqual(exc.params, {"i": 2})
        self.assertEqual(str(exc), t("err.segment_empty", i=2))

    def test_kept_dir_in_message(self):
        import video_processor as vp
        exc = vp.ProcessingError("err.ffmpeg_failed", "d", kept_dir="C:\\w\\job_x")
        self.assertIn("C:\\w\\job_x", str(exc))
        self.assertEqual(str(exc), t(exc.key, **exc.params))

    def test_cancelled_has_key(self):
        import video_processor as vp
        exc = vp.Cancelled("err.cancelled", kept_dir="C:\\w")
        self.assertEqual(exc.key, "err.cancelled")
        self.assertIn("C:\\w", str(exc))

    def test_progress_events_carry_key_and_params(self):
        import video_processor as vp
        events = []
        job = vp.VideoJob(Path("a.mp4"), None, [], "ffmpeg", "ffprobe", events.append,
                          Path("w"))
        job._emit("extract", 1, 10.0, "progress.cut", i=1, n=3)
        self.assertEqual(events[0]["message"], "Cutting segment 1 of 3")
        self.assertEqual(events[0]["key"], "progress.cut")
        self.assertEqual(events[0]["params"], {"i": 1, "n": 3})


class ReviewWordingTests(unittest.TestCase):
    """Wording decided in the review round of 2026-11-09 (one hint, one progress vocabulary ...)."""
    HINT = ("Use hours:minutes:seconds, for example 00:01:05.250. "
            "Short forms: 1:05 = 1 minute 5 seconds, 65 = 65 seconds.")

    def test_time_hint_is_the_same_everywhere_in_english(self):
        en = i18n.STRINGS["en"]
        self.assertEqual(en["dlg.edit_hint"], self.HINT)
        for key in ("err.time_empty", "err.time_invalid", "mark.manual_hint"):
            self.assertIn(self.HINT, en[key], key)
        for lang in LANGS:   # the old short form of the hint must be gone
            for key, text in i18n.STRINGS[lang].items():
                self.assertNotIn("01:05.250, 1:05 or 65", text, key)

    def test_main_button_and_dialog_use_one_name(self):
        en, ru = i18n.STRINGS["en"], i18n.STRINGS["ru"]
        self.assertEqual({en["btn.create"], en["dlg.create_title"], en["btn.create_video"]},
                         {"Create Video"})
        self.assertEqual({ru["btn.create"], ru["dlg.create_title"], ru["btn.create_video"]},
                         {"Создать видео"})
        self.assertIn("Set end point", en["btn.mark_end"])

    def test_one_progress_vocabulary(self):
        for lang in LANGS:
            self.assertEqual([k for k in i18n.STRINGS[lang] if k.startswith("op.")], [])
        en = i18n.STRINGS["en"]
        self.assertEqual(en["progress.cut"], "Cutting segment {i} of {n}")
        self.assertEqual(en["progress.join"], "Joining the segments")
        self.assertEqual(en["progress.verify"], "Checking the finished video")

    def test_failures_end_with_the_retry_advice(self):
        advice = "Try again. If it happens again, try a different video file."
        for key in ("err.out_wrong_length", "err.ffmpeg_failed", "err.file_problem",
                    "err.out_no_sound", "err.part_invalid"):
            self.assertTrue(i18n.STRINGS["en"][key].endswith(advice), key)
            self.assertTrue(i18n.STRINGS["ru"][key].endswith(
                "Попробуйте ещё раз. Если ошибка повторится, попробуйте другой видеофайл."), key)

    def test_limit_messages_say_what_to_do(self):
        self.assertTrue(i18n.STRINGS["en"]["err.seg_max"].endswith("Delete one to add another."))
        self.assertTrue(i18n.STRINGS["en"]["mark.limit"].endswith("Delete one to add another."))

    def test_disk_messages_name_the_drive(self):
        self.assertIn("drive {drive}", i18n.STRINGS["en"]["err.disk_low"])
        self.assertIn("{drive}", i18n.STRINGS["ru"]["err.disk_low"])
        self.assertIn("drive of the folder", i18n.STRINGS["en"]["err.disk_check"])

    def test_kept_message_names_the_sweep_age(self):
        from create_flow import SWEEP_DAYS
        for lang in LANGS:
            self.assertIn(str(SWEEP_DAYS), t_lang_(lang, "err.kept"))
            self.assertIn(str(SWEEP_DAYS), t_lang_(lang, "dlg.cancel_job_message"))

    def test_ffmpeg_help_says_how_to_open_command_prompt(self):
        text = i18n.STRINGS["en"]["ffmpeg.help"]
        for part in ("Windows key", "cmd", "Command Prompt", "winget install Gyan.FFmpeg",
                     "close this program and open it again"):
            self.assertIn(part, text)
        self.assertNotIn("terminal", text.lower())

    def test_every_conversion_note_has_a_consequence(self):
        for lang in LANGS:
            for key, text in i18n.STRINGS[lang].items():
                if key.startswith("note."):
                    self.assertIn(";", text, key)


def t_lang_(lang, key):
    return i18n.t_lang(lang, key, path="P")


if __name__ == "__main__":
    unittest.main()
