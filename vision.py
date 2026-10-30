"""OpenCVによる顔検出と口元の特徴点推定。"""
import cv2
import numpy as np


class FaceDetector:
    def __init__(self, model, max_width=960, threshold=.75):
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


class MouthEstimator:
    def __init__(self, model):
        if not hasattr(cv2, 'face'):
            raise RuntimeError('opencv-contrib-python が必要です。READMEのセットアップを実行してください。')
        self.facemark = cv2.face.createFacemarkLBF()
        self.facemark.loadModel(str(model))
        self.points = {}

    def estimate(self, frame, tracks):
        self.points = {}
        if not tracks:
            return {}
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rectangles, selected = [], []
        for track in tracks:
            x, y, w, h = track.face[:4]
            x, y = max(0, int(x)), max(0, int(y))
            w, h = min(int(w), gray.shape[1]-x), min(int(h), gray.shape[0]-y)
            if w >= 45 and h >= 45:
                rectangles.append((x, y, w, h))
                selected.append(track)
        if not selected:
            return {}
        try:
            ok, landmarks = self.facemark.fit(gray, np.array(rectangles, np.int32))
        except cv2.error:
            return {}
        if not ok:
            return {}
        ratios = {}
        for track, landmark in zip(selected, landmarks):
            pts = np.asarray(landmark).reshape(-1, 2)
            if pts.shape != (68, 2) or not np.isfinite(pts).all():
                continue
            mouth_width = np.linalg.norm(pts[48] - pts[54])
            eye_mid = (track.face[4:6] + track.face[6:8]) / 2
            eye_distance = np.linalg.norm(track.face[4:6] - track.face[6:8])
            # 横顔や大きく崩れた推定では、誤って食べ進めない。
            if not .15 * track.face[2] <= mouth_width <= .8 * track.face[2]:
                continue
            if abs(track.face[8] - eye_mid[0]) > eye_distance * .65:
                continue
            opening = sum(np.linalg.norm(pts[a] - pts[b]) for a, b in ((61, 67), (62, 66), (63, 65))) / 3
            ratio = float(opening / max(mouth_width, 1.))
            if 0 <= ratio <= 1.2:
                ratios[track.number] = ratio
                self.points[track.number] = pts
        return ratios

