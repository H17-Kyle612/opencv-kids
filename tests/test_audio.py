import unittest
from types import SimpleNamespace
from audio import SoundEffects


class RecordedSounds(SoundEffects):
    def __init__(self):
        self.previous_state = None
        self.previous_tick = None
        self.played = []

    def play(self, name):
        self.played.append(name)


class SoundEventTests(unittest.TestCase):
    def race(self, state='playing', events=(), hits=(1, 1), elapsed=0.):
        return SimpleNamespace(state=state, events=list(events), time_limit=30., elapsed=elapsed,
                               bites_per_cake=4, players=[SimpleNamespace(hits=n) for n in hits],
                               countdown=lambda now: 3-int(now))

    def test_start_plays_once_and_two_players_have_distinct_bites(self):
        sound = RecordedSounds()
        sound.update(self.race(events=(0,)), 0.)
        sound.update(self.race(events=(1,)), .1)
        self.assertEqual(sound.played, ['start', 'bite1', 'bite2'])

    def test_simultaneous_bites_and_cake_completion_use_one_sound(self):
        sound = RecordedSounds()
        sound.previous_state = 'playing'
        sound.update(self.race(events=(0, 1)), 0.)
        sound.update(self.race(events=(0, 1), hits=(4, 3)), .1)
        self.assertEqual(sound.played, ['bite_both', 'cake'])

    def test_finish_plays_once(self):
        sound = RecordedSounds()
        sound.update(self.race(state='result'), 0.)
        sound.update(self.race(state='result'), .1)
        self.assertEqual(sound.played, ['finish'])

    def test_mirror_mode_does_not_play_stale_events(self):
        sound = RecordedSounds()
        sound.update(self.race(events=(0,)), 0., active=False)
        self.assertEqual(sound.played, [])


if __name__ == '__main__':
    unittest.main()
