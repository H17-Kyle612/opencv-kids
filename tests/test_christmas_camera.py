import unittest
import numpy as np
from tracking import Tracker
from costume.effects import make_sprites, composite, Snow, placement, star_animation
from costume.outfits import LOOKS
from costume.scene import CostumeScene


def face(x=100, y=100):
    return np.array([x, y, 100, 120, x+30, y+35, x+70, y+35,
                     x+50, y+65, x+35, y+85, x+65, y+85, .99], np.float32)


class TrackingTests(unittest.TestCase):
    def test_all_faces_get_unique_tracks_and_survive_detection_reordering(self):
        tracker = Tracker()
        first = tracker.update(np.array([face(100), face(400)]), 0.)
        second = tracker.update(np.array([face(405), face(105)]), .05)
        self.assertEqual(len(second), 2)
        self.assertEqual({t.number for t in first}, {t.number for t in second})
        by_id = {t.number: t for t in second}
        self.assertLess(by_id[1].face[0], by_id[2].face[0])

    def test_occlusion_keeps_costume_without_drawing_ghost(self):
        tracker, scene = Tracker(), CostumeScene(seed=2)
        initial = tracker.update(np.array([face()]), 0.)[0]
        scene.update(tracker.tracks.keys())
        outfit = scene.outfits[initial.number]
        self.assertEqual(tracker.update([], .3), [])
        scene.update(tracker.tracks.keys())
        restored = tracker.update(np.array([face(105)]), .7)[0]
        self.assertEqual(initial.number, restored.number)
        scene.update(tracker.tracks.keys())
        self.assertEqual(outfit, scene.outfits[restored.number])
        self.assertEqual(tracker.update([], 2.), [])
        fresh = tracker.update(np.array([face()]), 2.1)[0]
        self.assertNotEqual(initial.number, fresh.number)
        scene.update(tracker.tracks.keys())
        self.assertNotIn(initial.number, scene.outfits)

    def test_selected_look_applies_to_current_and_new_faces(self):
        tracker, scene = Tracker(), CostumeScene(seed=3)
        tracker.update(np.array([face()]), 0.)
        scene.update(tracker.tracks.keys())
        scene.choose(LOOKS[4])
        result = tracker.update(np.array([face(), face(400)]), .1)
        scene.update(tracker.tracks.keys())
        self.assertTrue(all(scene.outfits[t.number] == LOOKS[4] for t in result))
        scene.shuffle()
        self.assertIsNone(scene.fixed_outfit)

    def test_one_existing_track_cannot_match_two_faces(self):
        tracker = Tracker()
        tracker.update(np.array([face()]), 0.)
        result = tracker.update(np.array([face(95), face(140)]), .03)
        self.assertEqual(len({t.number for t in result}), 2)


class RenderingTests(unittest.TestCase):
    def test_every_sprite_blends_on_frame_and_clips_at_edges(self):
        sprites = make_sprites()
        for name, sprite in sprites.items():
            with self.subTest(name=name):
                frame = np.zeros((480, 640, 3), np.uint8)
                composite(frame, sprite, face(200, 150))
                self.assertGreater(int(frame.sum()), 0)
                composite(frame, sprite, face(-80, -80))
                composite(frame, sprite, face(620, 460))
                self.assertEqual(frame.shape, (480, 640, 3))

    def test_head_stays_on_eyes_when_nose_position_changes(self):
        original = face()
        moved = original.copy()
        moved[8:10] += [20, 15]
        np.testing.assert_allclose(placement(original, 'santa'), placement(moved, 'santa'))
        self.assertFalse(np.allclose(placement(original, 'red'), placement(moved, 'red')))

    def test_beard_anchor_tracks_mouth_and_rotates_with_eyes(self):
        tilted = face()
        tilted[6:8] += [0, 20]
        origin = np.array([200., 402., 1.])
        matrix = placement(tilted, 'beard')
        expected_mouth = (tilted[10:12] + tilted[12:14]) / 2
        self.assertLess(np.linalg.norm(matrix @ origin - expected_mouth), tilted[2] * .11)
        self.assertNotAlmostEqual(matrix[1, 0], 0.)

    def test_star_changes_over_time_and_keeps_opaque_core(self):
        scene = CostumeScene(seed=0)
        frames = star_animation(scene.sprites['star'])
        self.assertFalse(np.array_equal(frames[0], frames[6]))
        for frame in frames:
            self.assertGreaterEqual(frame[156, 200, 3], 240)
        tracker = Tracker()
        scene.choose(LOOKS[2])
        tracks = tracker.update(np.array([face(200, 200)]), 0.)
        scene.update(tracker.tracks.keys())
        early = np.zeros((480, 640, 3), np.uint8)
        later = early.copy()
        scene.draw(early, tracks, 0., snowfall=False)
        scene.draw(later, tracks, .4, snowfall=False)
        self.assertFalse(np.array_equal(early, later))

    def test_result_crown_animates_only_on_the_winner_without_changing_costumes(self):
        tracker, scene = Tracker(), CostumeScene(seed=0)
        scene.choose(LOOKS[0])
        tracks = tracker.update(np.array([face(120, 180), face(430, 180)]), 0.)
        scene.update(tracker.tracks.keys())
        normal = np.zeros((480, 640, 3), np.uint8)
        winner = normal.copy()
        later = normal.copy()
        scene.draw(normal, tracks, 0., snowfall=False)
        scene.draw(winner, tracks, 0., winner_id=tracks[0].number, snowfall=False)
        scene.draw(later, tracks, .4, winner_id=tracks[0].number, snowfall=False)
        self.assertFalse(np.array_equal(normal[:, :320], winner[:, :320]))
        self.assertFalse(np.array_equal(winner[:, :320], later[:, :320]))
        np.testing.assert_array_equal(normal[:, 320:], winner[:, 320:])
        self.assertEqual(scene.outfits, {track.number: LOOKS[0] for track in tracks})

    def test_head_ornaments_fit_when_camera_has_little_headroom(self):
        sprites = make_sprites()
        for name in ('santa', 'antlers', 'star', 'gift', 'cross'):
            with self.subTest(name=name):
                frame = np.zeros((480, 640, 3), np.uint8)
                composite(frame, sprites[name], face(200, 20), name=name)
                ys = np.nonzero(frame.max(axis=2))[0]
                self.assertGreater(len(ys), 0)
                self.assertGreaterEqual(ys.min(), 7)

    def test_snow_does_not_change_frame_shape_or_dtype(self):
        frame = np.zeros((240, 320, 3), np.uint8)
        snow = Snow(seed=0)
        snow.draw(frame, .033, 1.)
        self.assertGreater(int(frame.sum()), 0)
        self.assertEqual(frame.dtype, np.uint8)


if __name__ == '__main__':
    unittest.main()
