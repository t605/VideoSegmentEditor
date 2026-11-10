"""Offline tests of VideoSegmentEditor.bat. They only use /check or VSE_DRYRUN=1, so nothing is
installed, no winget is started and no program is launched. Windows only."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAT = ROOT / "VideoSegmentEditor.bat"
TEST_VARS = ("VSE_DRYRUN", "VSE_FAKE_MISSING", "VSE_FAKE_FAIL", "VSE_FAKE_WINGET")


@unittest.skipUnless(sys.platform == "win32", "the launcher is a Windows batch file")
class LauncherTests(unittest.TestCase):
    def run_bat(self, args=(), answer="", **env_vars):
        env = {k: v for k, v in os.environ.items() if k not in TEST_VARS}
        env.update(env_vars)
        with tempfile.TemporaryDirectory() as tmp:
            env["TEMP"] = env["TMP"] = tmp
            proc = subprocess.run(["cmd", "/c", str(BAT), *args], input=answer.encode("ascii"),
                                  capture_output=True, timeout=120, env=env, cwd=str(ROOT))
        return proc.returncode, proc.stdout.decode("cp437", "replace")

    # ------------------------------------------------------------------ file format
    def test_launcher_is_ascii_with_crlf(self):
        data = BAT.read_bytes()
        self.assertTrue(all(b < 128 for b in data), "non-ASCII byte in the launcher")
        self.assertEqual(data.count(b"\r\n"), data.count(b"\n"), "a line end is not CRLF")
        self.assertEqual(data.count(b"\r"), data.count(b"\r\n"), "a lone CR")

    def test_no_vague_time_claims_or_second_name_for_the_console(self):
        text = BAT.read_text(encoding="ascii").lower()
        self.assertNotIn("a few minutes", text)
        self.assertNotIn("terminal", text)
        self.assertNotIn("cmd window", text)

    # ------------------------------------------------------------------ the test switches
    def test_fake_missing_alone_does_nothing(self):
        """VSE_FAKE_MISSING without VSE_DRYRUN must not change what the launcher reports."""
        _, plain = self.run_bat(["/check"])
        code, faked = self.run_bat(["/check"], VSE_FAKE_MISSING="python,ffmpeg,vlc",
                                   VSE_FAKE_FAIL="python,ffmpeg,vlc", VSE_FAKE_WINGET="0")
        self.assertEqual(code, 0)
        self.assertNotIn("[test]", faked)
        self.assertNotIn("pretending", faked)

        def found(out):
            return [ln.strip() for ln in out.splitlines()
                    if ln.strip().startswith(("Python:", "FFmpeg:", "FFprobe:", "VLC:"))]
        self.assertEqual(found(plain), found(faked))
        self.assertIn("Nothing was installed or started.", faked)

    def test_dry_run_install_prints_the_screen_and_the_commands(self):
        code, out = self.run_bat(answer="Y\r\n\r\n", VSE_DRYRUN="1", VSE_FAKE_WINGET="1",
                                 VSE_FAKE_MISSING="python,ffmpeg,vlc")
        self.assertEqual(code, 0, out)
        for line in ("Missing on this computer (all free):",
                     "Windows may show a permission window for VLC. Click Yes.",
                     "If you click No, VLC is not installed.",
                     "Press Y to install, N to skip. Do not close this window while it installs.",
                     "Installing 1 of 3: Python 3.12. Please wait, do not close this window...",
                     "[dry run] winget install -e --id Python.Python.3.12",
                     "[dry run] winget install -e --id Gyan.FFmpeg",
                     "[dry run] winget install -e --id VideoLAN.VLC",
                     "Installing 3 of 3: VLC player."):
            self.assertIn(line, out)
        self.assertNotIn("a few minutes", out)
        self.assertLess(out.index("Press Y to install"), out.index("[dry run] winget"))

    def test_vlc_permission_hint_only_when_vlc_is_missing(self):
        _, out = self.run_bat(answer="N\r\n\r\n", VSE_DRYRUN="1", VSE_FAKE_WINGET="1",
                              VSE_FAKE_MISSING="ffmpeg")
        self.assertIn("Press Y to install, N to skip.", out)
        self.assertNotIn("permission window for VLC", out)

    def test_failed_install_names_the_items_and_waits_for_a_key(self):
        code, out = self.run_bat(answer="Y\r\n\r\n", VSE_DRYRUN="1", VSE_FAKE_WINGET="1",
                                 VSE_FAKE_MISSING="ffmpeg,vlc", VSE_FAKE_FAIL="ffmpeg,vlc")
        self.assertEqual(code, 0, out)
        self.assertIn("These could not be installed: FFmpeg, VLC player.", out)
        self.assertIn("Install them by hand with the steps below, then start this file again.", out)
        for part in ("ffmpeg-release-essentials.zip", "C:\\ffmpeg", "Command Prompt",
                     "winget install Gyan.FFmpeg", "To install VLC by hand"):
            self.assertIn(part, out)
        self.assertIn("press any key to close this window", out)

    def test_answer_no_installs_nothing_and_lists_what_is_missing(self):
        code, out = self.run_bat(answer="N\r\n\r\n", VSE_DRYRUN="1", VSE_FAKE_WINGET="1",
                                 VSE_FAKE_MISSING="ffmpeg,vlc")
        self.assertEqual(code, 0, out)
        self.assertIn("Nothing was installed.", out)
        self.assertIn("Still missing: FFmpeg, VLC player.", out)
        self.assertNotIn("[dry run] winget", out)

    def test_no_winget_gives_by_hand_steps_and_no_question(self):
        code, out = self.run_bat(answer="\r\n", VSE_DRYRUN="1", VSE_FAKE_WINGET="0",
                                 VSE_FAKE_MISSING="ffmpeg")
        self.assertEqual(code, 0, out)
        self.assertIn("winget (the Windows package manager) was not found", out)
        self.assertNotIn("Press Y to install", out)
        self.assertIn("ffmpeg-release-essentials.zip", out)

    def test_unknown_option_does_nothing(self):
        code, out = self.run_bat(["/bogus"], answer="\r\n")
        self.assertEqual(code, 1)
        self.assertIn("Nothing was installed or started.", out)


if __name__ == "__main__":
    unittest.main()
