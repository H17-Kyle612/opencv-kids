"""OpenCV YuNetで顔を検出する。"""
import cv2
import numpy as np


class FaceDetector:
    def __init__(self, model, max_width=640, threshold=.75):
        self.max_width = max_width
        self.detector = cv2.FaceDetectorYN.create(str(model), '', (320, 320), threshold, .3, 5000)

    def detect(self, frame):
        scale = min(1., self.max_width/frame.shape[1]) if self.max_width else 1.
        small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
        self.detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self.detector.detect(small)
        if faces is None:
            return np.empty((0, 15), np.float32)
        faces[:, :14] /= scale
        return faces
