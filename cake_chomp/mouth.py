"""OpenCVで唇の特徴点と開度を推定する。"""
from statistics import median

import cv2
import numpy as np


def mouth_measurement(points):
    """横ずれを除いた内唇3組の開度。空間的な中央値で単独点のずれを抑える。"""
    across = points[54]-points[48]
    width = float(np.linalg.norm(across))
    unit = across/max(width,1.)
    down = np.array([-unit[1],unit[0]])
    gaps = [float((points[b]-points[a]) @ down) for a,b in ((61,67),(62,66),(63,65))]
    return width, max(0.,median(gaps))/max(width,1.)


class MouthEstimator:
    def __init__(self, model):
        if not hasattr(cv2, 'face'):
            raise RuntimeError('opencv-contrib-python が必要です。READMEのセットアップを実行してください。')
        self.facemark = cv2.face.createFacemarkLBF()
        self.facemark.loadModel(str(model))
        self.points = {}
        self.errors = {}

    def estimate(self, frame, tracks):
        self.points = {}
        self.errors = {track.number:'特徴点なし' for track in tracks}
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
                self.errors[track.number] = '特徴点が不安定'
                continue
            self.points[track.number] = pts
            mouth_width, ratio = mouth_measurement(pts)
            eye_mid = (track.face[4:6] + track.face[6:8]) / 2
            eye_distance = np.linalg.norm(track.face[4:6] - track.face[6:8])
            # 横顔や大きく崩れた推定では、誤って食べ進めない。
            if not .15 * track.face[2] <= mouth_width <= .8 * track.face[2]:
                self.errors[track.number] = '口幅が不安定'
                continue
            if abs(track.face[8] - eye_mid[0]) > eye_distance * .65:
                self.errors[track.number] = '横向き'
                continue
            if 0 <= ratio <= 1.2:
                ratios[track.number] = ratio
                self.errors.pop(track.number, None)
        return ratios
