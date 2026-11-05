import unittest
from unittest.mock import patch
import cv2
import numpy as np
from cake_game import MouthCycle
from mouth_motion import MouthMotion


class MouthMotionTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.image = rng.integers(0, 256, (240, 320), dtype=np.uint8)
        self.points = rng.uniform([60, 40], [260, 130], (68, 2)).astype(np.float32)
        self.points[48] = (100, 180)
        self.points[54] = (200, 180)
        for a, b, x in ((50, 58, 130), (51, 57, 150), (52, 56, 170)):
            self.points[a] = (x, 170)
            self.points[b] = (x, 190)
        self.motion = MouthMotion()
        self.motion.measure(self.image, self.points, 1)

    def test_static_image_ignores_estimator_jitter(self):
        jittered = self.points.copy()
        jittered[48:, 1] += 10
        self.assertEqual(self.motion.measure(self.image, jittered, 1), 0)

    def test_head_translation_is_not_lip_motion(self):
        matrix = np.float32([[1, 0, 3], [0, 1, 2]])
        image = cv2.warpAffine(self.image, matrix, (320, 240))
        self.assertEqual(self.motion.measure(image, self.points + [3, 2], 1), 0)

    def test_actual_local_image_motion_detects_open_then_close(self):
        image = self.image.copy()
        image[182:214, 112:190] = self.image[180:212, 112:190]
        moved = self.points.copy()
        moved[[58, 57, 56], 1] += 2
        self.assertEqual(self.motion.measure(image, moved, 1), 1)
        self.assertEqual(self.motion.measure(self.image, self.points, 1), -1)

    def test_failed_flow_cannot_open(self):
        with patch('mouth_motion.cv2.calcOpticalFlowPyrLK', return_value=(None, None, None)):
            self.assertEqual(self.motion.measure(self.image, self.points, 1), 0)

    def test_ratio_jitter_needs_independent_open_and_close(self):
        cycle = MouthCycle(baseline=.025, sensitivity=8)
        self.assertFalse(cycle.update(.02, 0))
        for _ in range(20):
            self.assertFalse(cycle.update(.12, 0))
            self.assertFalse(cycle.update(.02, 0))
        self.assertFalse(cycle.update(.12, 1))
        self.assertFalse(cycle.update(.02, 1))
        self.assertTrue(cycle.update(.02, -1))
        for _ in range(20):
            self.assertFalse(cycle.update(.12, -1))
            self.assertFalse(cycle.update(.02, -1))
        self.assertFalse(cycle.update(.12, 1))
        self.assertTrue(cycle.update(.02, -1))

    def test_removed_face_drops_image_reference(self):
        self.motion.retain(set())
        self.assertFalse(self.motion.references)
        self.assertFalse(self.motion.details)
