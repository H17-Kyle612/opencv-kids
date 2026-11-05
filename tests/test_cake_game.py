import unittest
from types import SimpleNamespace
import numpy as np
from cake_game import MouthCycle, CakeRace


def track(number, x, width=190):
    return SimpleNamespace(number=number, face=np.array([x, 100, width, width*1.15], np.float32))


class MouthTests(unittest.TestCase):
    def test_one_open_close_cycle_counts_once(self):
        mouth = MouthCycle(.025)
        sequence = [(0., .02), (.08, .02), (.16, .3), (.24, .3), (.32, .02), (.40, .02), (.50, .02), (.60, .02)]
        self.assertEqual(sum(mouth.update(ratio) for now, ratio in sequence), 1)

    def test_small_mouth_opening_counts_a_complete_cycle(self):
        mouth = MouthCycle(.025)
        sequence = [(0., .02), (.08, .02), (.16, .12), (.24, .12), (.32, .02), (.40, .02)]
        self.assertEqual(sum(mouth.update(ratio) for now, ratio in sequence), 1)

    def test_closed_mouth_noise_does_not_count(self):
        mouth = MouthCycle(.025)
        sequence = [(0., .02), (.08, .02), (.16, .03), (.24, .03), (.32, .02), (.40, .02)]
        self.assertEqual(sum(mouth.update(ratio) for now, ratio in sequence), 0)

    def test_default_counts_a_gentle_opening_that_old_threshold_rejected(self):
        sequence = (.025, .025, .07, .07, .025, .025)
        easy, old = MouthCycle(), MouthCycle(sensitivity=1)
        self.assertEqual(sum(easy.update(r) for r in sequence), 1)
        self.assertEqual(sum(old.update(r) for r in sequence), 0)

    def test_sensitivity_is_monotonic_for_different_closed_baselines(self):
        for baseline in (.005, .025, .08, .13):
            previous = 0
            for level in range(1, 11):
                mouth = MouthCycle(baseline, level)
                count = sum(mouth.update(r) for r in (baseline, baseline+.046, baseline))
                self.assertGreaterEqual(count, previous)
                previous = count
            self.assertEqual(previous, 1)

    def test_high_sensitivity_counts_without_returning_to_calibrated_closed_position(self):
        gentle, fixed = MouthCycle(.025, 8, noise_span=.025), MouthCycle(.025, 5)
        sequence = tuple(r for r in (.045, .045, .08, .045, .08, .045) for _ in range(2))
        self.assertEqual(sum(gentle.update(r) for r in sequence), 2)
        self.assertEqual(sum(fixed.update(r) for r in sequence), 0)

    def test_high_sensitivity_small_cycles_and_holding_open(self):
        mouth = MouthCycle(sensitivity=7)
        self.assertEqual(sum(mouth.update(r) for r in tuple(r for r in (.025,.025,.08,.026,.08,.027) for _ in range(2))), 2)
        for ratio in (.027,.03,.028,.031,.029)*10:
            self.assertFalse(mouth.update(ratio))
        mouth = MouthCycle(sensitivity=10)
        self.assertEqual(sum(mouth.update(r) for r in (.025,.025,.025,.065,.065,.025,.025)), 1)
        for ratio in (.025,.2,.2,.2,.2):
            self.assertFalse(mouth.update(ratio))

    def test_high_sensitivity_missing_sample_discards_partial_cycle(self):
        mouth = MouthCycle(sensitivity=7)
        self.assertEqual(sum(mouth.update(r) for r in (.025,.12,None,.025)), 0)
        self.assertEqual(sum(mouth.update(r) for r in (.025,.025,.12,.12,.025,.025)), 1)

    def test_calibrated_jitter_does_not_score_but_real_cycles_do(self):
        samples = [.02,.025,.03]*20
        mouth = MouthCycle.calibrated(samples, 10)
        self.assertAlmostEqual(mouth.noise_span, .01)
        self.assertGreater(mouth.targets[1], mouth.targets[0])
        jitter = [.02,.02,.03,.03,.022,.022]*20
        self.assertEqual(sum(mouth.update(r) for r in jitter), 0)
        real_cycle = (.022,.022,.08,.08,.022,.022)
        self.assertEqual(sum(mouth.update(r) for r in real_cycle), 1)

    def test_single_frame_opening_and_return_are_counted_without_smoothing_delay(self):
        mouth = MouthCycle(sensitivity=8, noise_span=.035)
        self.assertEqual(sum(mouth.update(r) for r in (.025,.15,.025,.15,.025)), 2)

    def test_closed_noise_and_open_mouth_jitter_do_not_make_cycles(self):
        mouth = MouthCycle(.01,8,noise_span=.02)
        closed = (.0,.035,.041,.025,.0)*20
        self.assertEqual(sum(mouth.update(r) for r in closed),0)
        mouth.update(.25)
        self.assertEqual(sum(mouth.update(r) for r in (.27,.34,.28,.33,.27)*20),0)
        self.assertTrue(mouth.update(.01))
        self.assertEqual(sum(mouth.update(r) for r in (.3,.01)*10),10)

    def test_higher_sensitivity_never_raises_the_opening_threshold(self):
        for baseline in (.005,.025,.08):
            for noise in (0.,.01,.04):
                previous=float('inf')
                for level in range(1,11):
                    close, opening=MouthCycle(baseline,level,noise).targets
                    self.assertLessEqual(opening,previous)
                    self.assertLess(close,opening)
                    previous=opening

    def test_holding_open_does_not_count(self):
        mouth = MouthCycle()
        for i in range(100):
            self.assertFalse(mouth.update(.4))

    def test_fixed_threshold_cycle_counts_without_time_or_interval_limits(self):
        mouth = MouthCycle(sensitivity=1)
        self.assertEqual(sum(mouth.update(ratio) for ratio in (.02, .3, .02, .3, .02)), 2)

    def test_lost_landmarks_cancel_partial_bite(self):
        mouth = MouthCycle()
        sequence = [(0., .02), (.1, .02), (.2, .4), (.3, .4), (.4, None), (.5, .02), (.6, .02)]
        self.assertEqual(sum(mouth.update(ratio) for now, ratio in sequence), 0)


class RaceTests(unittest.TestCase):
    def setUp(self):
        self.race = CakeRace()
        self.tracks = [track(1, 180), track(2, 850)]
        self.now = 0.

    def test_live_sensitivity_change_preserves_score_and_time_and_clears_partial_bite(self):
        from cake_game import Player
        self.race.players = [Player(1), Player(2)]
        self.race.state = 'playing'
        self.race.elapsed = 12.
        for player in self.race.players:
            player.hits = 7
            player.mouth.update(.025)
            player.mouth.update(.2)
        self.race.set_sensitivity(10)
        self.assertEqual((self.race.state, self.race.elapsed), ('playing',12.))
        for player in self.race.players:
            self.assertEqual(player.hits, 7)
            self.assertEqual(player.mouth.sensitivity, 10)
            self.assertFalse(player.mouth.update(.025))
        self.race.reset()
        self.assertEqual(self.race.sensitivity, 10)

    def step(self, ratios=None, tracks=None, duration=.1):
        self.now += duration
        self.race.update(self.tracks if tracks is None else tracks,
                         {1: .025, 2: .025} if ratios is None else ratios, 1280, self.now)

    def start(self):
        for _ in range(60):
            self.step()
        self.assertEqual(self.race.state, 'playing')

    def bite(self, both=False):
        for ratio in (.025, .025, .3, .3, .025, .025):
            self.step({1: ratio, 2: ratio if both else .025})

    def test_unstable_calibration_does_not_start_with_an_unreachable_threshold(self):
        for index in range(20):
            self.step({1:.35 if index%5==4 else .025,2:.025})
        self.assertEqual(self.race.state, 'ready')
        self.assertIn('安定', self.race.reason)
        for _ in range(60):
            self.step()
        self.assertEqual(self.race.state, 'playing')
        self.assertLess(self.race.players[0].mouth.movement, .1)

    def test_two_large_faces_on_opposite_sides_are_required(self):
        for _ in range(30):
            self.step(tracks=[track(1, 100, 120), track(2, 850, 120)])
        self.assertEqual(self.race.state, 'waiting')
        for _ in range(30):
            self.step(tracks=[track(1, 100), track(2, 350)])
        self.assertEqual(self.race.state, 'waiting')
        self.step(tracks=[self.tracks[0]])
        self.assertEqual(self.race.state, 'waiting')

    def test_countdown_does_not_score(self):
        for _ in range(20):
            self.step()
        self.assertEqual(self.race.state, 'countdown')
        self.bite(both=True)
        self.assertEqual([p.hits for p in self.race.players], [0, 0])

    def test_cake_count_has_no_limit_and_result_waits_for_deadline(self):
        self.start()
        for _ in range(20):
            self.bite()
        self.assertEqual(self.race.state, 'playing')
        self.assertEqual(self.race.players[0].hits, 20)
        self.race.time_limit = self.race.elapsed + .15
        self.step()
        self.step()
        self.assertEqual(self.race.state, 'result')
        self.assertEqual(self.race.winners, [0])
        self.assertEqual(self.race.elapsed, self.race.time_limit)
        elapsed, hits = self.race.elapsed, self.race.players[0].hits
        self.step(duration=1)
        self.assertEqual((self.race.elapsed, self.race.players[0].hits), (elapsed, hits))

    def test_equal_scores_at_deadline_are_draw(self):
        self.start()
        for _ in range(4):
            self.bite(both=True)
        self.assertEqual(self.race.state, 'playing')
        self.race.time_limit = self.race.elapsed + .05
        self.step()
        self.assertEqual(self.race.winners, [0, 1])

    def test_mouth_sample_after_deadline_cannot_score(self):
        self.start()
        for ratio in (.025, .025, .3, .3):
            self.step({1:ratio, 2:.025})
        self.race.time_limit = self.race.elapsed + .05
        self.step({1:.025, 2:.025})
        self.assertEqual(self.race.players[0].hits, 0)
        self.assertEqual(self.race.state, 'result')

    def test_pause_freezes_both_players_and_resumes_after_countdown(self):
        self.start()
        elapsed = self.race.elapsed
        for _ in range(20):
            self.step(ratios={1: .025}, tracks=[self.tracks[0]])
        self.assertEqual(self.race.state, 'paused')
        self.assertEqual(self.race.elapsed, elapsed)
        for _ in range(10):
            self.step()
        self.assertEqual(self.race.state, 'countdown')
        self.assertEqual(self.race.elapsed, elapsed)
        for _ in range(32):
            self.step()
        self.assertEqual(self.race.state, 'playing')

    def test_lost_player_cannot_be_replaced_by_spectator(self):
        self.start()
        self.step(tracks=[self.tracks[0], track(3, 850)], ratios={1:.025, 3:.025})
        self.assertEqual(self.race.state, 'paused')
        self.assertEqual([p.track_id for p in self.race.players], [1, 2])

    def test_timeout_uses_bite_count_for_winner(self):
        self.start()
        self.bite()
        self.race.time_limit = self.race.elapsed + .15
        self.step()
        self.step()
        self.assertEqual(self.race.state, 'result')
        self.assertEqual(self.race.winners, [0])
        self.assertEqual(self.race.reason, '時間終了！')


class SoloTests(unittest.TestCase):
    def setUp(self):
        self.race = CakeRace(player_count=1)
        self.tracks = [track(1, 545)]
        self.now = 0.

    def step(self, ratio=.025, tracks=None, duration=.1):
        self.now += duration
        self.race.update(self.tracks if tracks is None else tracks,
                         {1: ratio}, 1280, self.now)

    def start(self):
        for _ in range(60):
            self.step()
        self.assertEqual(self.race.state, 'playing')

    def test_center_face_starts_and_largest_face_is_selected(self):
        faces = [track(2, 10, 170), track(1, 545, 210)]
        self.assertEqual(self.race.candidates(faces, 1280)[0].number, 1)
        self.start()
        self.assertEqual([p.track_id for p in self.race.players], [1])

    def test_scores_unlimited_cakes_and_finishes_without_winner(self):
        self.start()
        for _ in range(12):
            for ratio in (.025, .025, .3, .3, .025, .025):
                self.step(ratio)
        self.assertEqual(self.race.players[0].hits, 12)
        self.assertEqual(self.race.state, 'playing')
        self.step(duration=30.)
        self.assertEqual(self.race.state, 'result')
        self.assertEqual(self.race.elapsed, 30.)
        self.assertEqual(self.race.winners, [])
        self.step(.3)
        self.assertEqual(self.race.players[0].hits, 12)

    def test_spectator_cannot_take_over_and_absence_freezes_timer(self):
        self.start()
        elapsed = self.race.elapsed
        self.step(tracks=[track(2, 545)])
        self.assertEqual(self.race.state, 'paused')
        self.assertEqual(self.race.elapsed, elapsed)
        self.assertEqual(self.race.players[0].track_id, 1)
        for _ in range(42):
            self.step()
        self.assertEqual(self.race.state, 'playing')

    def test_switching_modes_resets_game_and_restores_two_face_requirement(self):
        self.start()
        self.race.set_player_count(2)
        self.step()
        self.assertEqual(self.race.state, 'waiting')
        self.assertEqual(self.race.players, [])
        self.assertEqual(self.race.elapsed, 0.)
        self.race.set_player_count(1)
        self.step()
        self.assertEqual(self.race.state, 'ready')
        with self.assertRaises(ValueError):
            self.race.set_player_count(3)


if __name__ == '__main__':
    unittest.main()
