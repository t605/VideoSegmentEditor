import os
import unittest
from unittest import mock

import video_player
from video_player import PlayerUnavailable, VlcPlayer, vlc_available


class FakeState:
    Stopped, Ended, NothingSpecial, Playing = "S", "E", "N", "P"
    Opening, Buffering, Paused, Error = "O", "B", "A", "X"


def make_fake_vlc():
    vlc = mock.MagicMock()
    vlc.State = FakeState
    player = vlc.Instance.return_value.media_player_new.return_value
    player.is_playing.return_value = 1
    player.get_time.return_value = 1234
    player.get_length.return_value = 5000
    player.get_state.return_value = FakeState.Playing
    player.is_seekable.return_value = 1
    return vlc, player


class UnavailableTests(unittest.TestCase):
    def test_unavailable_when_import_fails(self):
        with mock.patch.object(video_player, "_load_vlc", side_effect=OSError("no libvlc")):
            self.assertFalse(vlc_available())
            with self.assertRaises(PlayerUnavailable):
                VlcPlayer(lambda: 1)

    def test_force_no_vlc_env(self):
        vlc, _ = make_fake_vlc()
        with mock.patch.object(video_player, "_load_vlc", return_value=vlc), \
                mock.patch.dict(os.environ, {"VSE_FORCE_NO_VLC": "1"}):
            self.assertFalse(vlc_available())
            with self.assertRaises(PlayerUnavailable):
                VlcPlayer(lambda: 1)

    def test_available_with_fake_vlc(self):
        vlc, _ = make_fake_vlc()
        env = {k: v for k, v in os.environ.items() if k != "VSE_FORCE_NO_VLC"}
        with mock.patch.object(video_player, "_load_vlc", return_value=vlc), \
                mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(vlc_available())


class BehaviourTests(unittest.TestCase):
    def setUp(self):
        self.vlc, self.player = make_fake_vlc()
        patcher = mock.patch.object(video_player, "_load_vlc", return_value=self.vlc)
        patcher.start()
        self.addCleanup(patcher.stop)
        env = {k: v for k, v in os.environ.items() if k != "VSE_FORCE_NO_VLC"}
        envp = mock.patch.dict(os.environ, env, clear=True)
        envp.start()
        self.addCleanup(envp.stop)
        self.p = VlcPlayer(lambda: 4242)

    def test_embeds_in_hwnd(self):
        self.player.set_hwnd.assert_called_with(4242)

    def test_video_does_not_swallow_mouse_and_keys(self):
        self.player.video_set_mouse_input.assert_called_once_with(False)
        self.player.video_set_key_input.assert_called_once_with(False)

    def test_input_setter_failure_does_not_break_construction(self):
        for name in ("video_set_mouse_input", "video_set_key_input"):
            with self.subTest(name=name):
                vlc, player = make_fake_vlc()
                getattr(player, name).side_effect = AttributeError("old libvlc")
                with mock.patch.object(video_player, "_load_vlc", return_value=vlc):
                    p = VlcPlayer(lambda: 7)
                player.set_hwnd.assert_called_with(7)
                getattr(player, "video_set_key_input" if name.endswith("mouse_input")
                        else "video_set_mouse_input").assert_called_once_with(False)
                p.release()

    def test_times_and_volume(self):
        self.assertEqual(self.p.time_ms(), 1234)
        self.assertEqual(self.p.length_ms(), 5000)
        self.p.set_volume(150)
        self.player.audio_set_volume.assert_called_with(100)
        self.p.set_volume(-5)
        self.player.audio_set_volume.assert_called_with(0)

    def test_unknown_time_is_zero(self):
        self.player.get_time.return_value = -1
        self.player.get_length.return_value = -1
        self.assertEqual(self.p.time_ms(), 0)
        self.assertEqual(self.p.length_ms(), 0)

    # --- BL-015: the time at / after the end of the media -------------------
    def test_ended_returns_length_not_zero(self):
        self.player.get_state.return_value = FakeState.Ended
        self.player.get_time.return_value = -1
        self.assertEqual(self.p.time_ms(), 5000)

    def test_ended_with_time_below_length_returns_length(self):
        self.player.get_state.return_value = FakeState.Ended
        self.player.get_time.return_value = 4900
        self.assertEqual(self.p.time_ms(), 5000)

    def test_ended_without_length_returns_last_known_time(self):
        self.p.time_ms()                                   # playing at 1234
        self.player.get_length.return_value = -1
        self.player.get_state.return_value = FakeState.Ended
        self.player.get_time.return_value = -1
        self.assertEqual(self.p.time_ms(), 1234)

    def test_stopped_after_end_still_returns_length(self):
        self.player.get_state.return_value = FakeState.Ended
        self.player.get_time.return_value = -1
        self.p.time_ms()                                   # the player saw Ended
        self.player.get_state.return_value = FakeState.Stopped
        self.assertEqual(self.p.time_ms(), 5000)

    def test_stop_by_user_returns_zero(self):
        self.p.time_ms()
        self.p.stop()
        self.player.get_state.return_value = FakeState.Stopped
        self.player.get_time.return_value = -1
        self.assertEqual(self.p.time_ms(), 0)

    def test_stopped_before_any_play_returns_zero(self):
        self.player.get_state.return_value = FakeState.Stopped
        self.player.get_time.return_value = -1
        self.assertEqual(self.p.time_ms(), 0)

    def test_play_after_end_forgets_the_end(self):
        self.player.get_state.return_value = FakeState.Ended
        self.player.get_time.return_value = -1
        self.p.time_ms()
        self.p.play()
        self.player.get_state.return_value = FakeState.Playing
        self.player.get_time.return_value = 300
        self.assertEqual(self.p.time_ms(), 300)

    def test_playing_time_is_unchanged_and_unclamped(self):
        self.player.get_time.return_value = 5120           # a little above the length
        self.assertEqual(self.p.time_ms(), 5120)           # the GUI clamps to the video duration

    def test_unknown_time_while_playing_keeps_last_known_time(self):
        self.p.time_ms()
        self.player.get_time.return_value = -1
        self.assertEqual(self.p.time_ms(), 1234)

    def test_new_media_forgets_end_and_last_time(self):
        self.player.get_state.return_value = FakeState.Ended
        self.player.get_time.return_value = -1
        self.p.time_ms()
        self.p.load("x.mp4")
        self.player.get_state.return_value = FakeState.Stopped
        self.assertEqual(self.p.time_ms(), 0)

    def test_seek_when_seekable_is_immediate(self):
        self.p.seek_ms(900)
        self.player.set_time.assert_called_with(900)
        self.player.play.assert_not_called()

    def test_seek_while_paused_just_seeks(self):
        self.player.get_state.return_value = FakeState.Paused
        self.p.seek_ms(300)
        self.player.play.assert_not_called()
        self.player.set_time.assert_called_with(300)

    def test_seek_while_stopped_queues_and_does_not_block(self):
        self.player.get_state.return_value = FakeState.Stopped
        with mock.patch("time.sleep", side_effect=AssertionError("sleep")):
            self.p.seek_ms(700)
        self.player.play.assert_called_once()
        self.player.set_time.assert_not_called()
        self.assertEqual(self.p.time_ms(), 700)  # pending target shown

    def test_tick_applies_pending_then_repauses(self):
        self.player.get_state.return_value = FakeState.Stopped
        self.p.seek_ms(700)
        self.player.get_state.return_value = FakeState.Opening
        self.p.tick()
        self.player.set_time.assert_not_called()
        self.player.get_state.return_value = FakeState.Playing
        self.player.is_seekable.return_value = 0
        self.p.tick()
        self.player.set_time.assert_not_called()
        self.player.is_seekable.return_value = 1
        self.p.tick()
        self.player.set_time.assert_called_once_with(700)
        self.player.set_pause.assert_called_with(1)
        self.assertEqual(self.p.time_ms(), 1234)  # pending cleared

    def test_opening_and_buffering_queue_without_play(self):
        for st in (FakeState.Opening, FakeState.Buffering):
            self.player.reset_mock()
            self.player.get_state.return_value = st
            self.p.seek_ms(500)
            self.player.set_time.assert_not_called()
            self.player.play.assert_not_called()
            self.assertEqual(self.p.time_ms(), 500)
        self.player.get_state.return_value = FakeState.Playing
        self.p.tick()
        self.player.set_time.assert_called_once_with(500)
        self.player.set_pause.assert_not_called()

    def test_second_seek_after_ready_repauses(self):
        self.player.get_state.return_value = FakeState.Stopped
        self.p.seek_ms(700)
        self.player.get_state.return_value = FakeState.Playing
        self.player.is_seekable.return_value = 1
        self.p.seek_ms(1500)
        self.player.set_time.assert_called_with(1500)
        self.player.set_pause.assert_called_with(1)
        self.assertFalse(self.p._repause)
        self.p.tick()
        self.assertEqual(self.player.set_time.call_count, 1)

    def test_error_state_drops_pending(self):
        self.player.get_state.return_value = FakeState.Stopped
        self.p.seek_ms(700)
        self.player.get_state.return_value = FakeState.Error
        self.p.tick()
        self.assertEqual(self.p.time_ms(), 1234)
        self.assertFalse(self.p._repause)

    def test_pending_times_out(self):
        self.player.get_state.return_value = FakeState.Opening
        with mock.patch("time.monotonic", return_value=100.0):
            self.p.seek_ms(700)
        with mock.patch("time.monotonic", return_value=121.0):
            self.p.tick()
        self.assertEqual(self.p.time_ms(), 1234)
        self.player.set_time.assert_not_called()

    def test_timeout_after_start_pauses_playback(self):
        self.player.get_state.return_value = FakeState.Stopped
        with mock.patch("time.monotonic", return_value=100.0):
            self.p.seek_ms(700)
        self.player.play.assert_called_once()
        self.player.get_state.return_value = FakeState.Opening
        with mock.patch("time.monotonic", return_value=121.0):
            self.p.tick()
        self.player.set_pause.assert_called_with(1)
        self.assertIsNone(self.p._pending)
        self.assertFalse(self.p._repause)

    def test_tick_without_pending_is_noop(self):
        self.p.tick()
        self.player.set_time.assert_not_called()

    def test_load_parses_and_length_falls_back(self):
        media = self.vlc.Instance.return_value.media_new_path.return_value
        media.get_duration.return_value = 8000
        self.p.load("x.mp4")
        media.parse.assert_called_once()
        self.player.get_length.return_value = 0
        self.assertEqual(self.p.length_ms(), 8000)
        self.player.get_length.return_value = 5000
        self.assertEqual(self.p.length_ms(), 5000)

    def test_load_parse_failure_gives_zero(self):
        media = self.vlc.Instance.return_value.media_new_path.return_value
        media.parse.side_effect = RuntimeError("bad")
        self.p.load("x.mp4")
        self.player.get_length.return_value = 0
        self.assertEqual(self.p.length_ms(), 0)

    def test_instance_args_hide_title(self):
        self.assertIn("--no-video-title-show", self.vlc.Instance.call_args.args)

    def test_calls_after_release_are_noops(self):
        self.p.release()
        self.player.reset_mock()
        self.p.play(); self.p.pause(); self.p.stop(); self.p.seek_ms(5)
        self.p.tick(); self.p.set_volume(5); self.p.load("x")
        self.assertEqual((self.p.time_ms(), self.p.length_ms()), (0, 0))
        self.assertFalse(self.p.is_playing())
        self.assertEqual(self.player.method_calls, [])

    def test_release_twice_is_safe(self):
        self.p.release()
        self.p.release()
        self.player.release.assert_called_once()
        self.vlc.Instance.return_value.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
