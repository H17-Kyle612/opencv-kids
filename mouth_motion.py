"""唇の推定点の揺れと、映像に写った開閉の動きを区別する。"""
import time
from statistics import median
import cv2
import numpy as np


class MouthMotion:
    def __init__(self):
        self.references = {}
        self.details = {}

    def retain(self, ids):
        self.references = {k:v for k,v in self.references.items() if k in ids}
        self.details = {k:v for k,v in self.details.items() if k in ids}

    def measure(self, gray, points, track_id):
        now = time.monotonic()
        old = self.references.get(track_id)
        def refresh(direction):
            self.references[track_id] = (gray.copy(), points.astype(np.float32).copy(), now, direction)
        if old is None or old[0].shape != gray.shape:
            refresh(0)
            self.details[track_id] = (0,0.)
            return 0
        image, source, captured, direction = old
        tracked, status, _ = cv2.calcOpticalFlowPyrLK(
            image, gray, source[17:68].reshape(-1,1,2), None,
            winSize=(21,21), maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,20,.01))
        if tracked is None or status is None:
            refresh(0); self.details[track_id]=(0,0.); return 0
        tracked = tracked.reshape(-1,2)
        valid = status.reshape(-1).astype(bool) & np.isfinite(tracked).all(axis=1)
        rigid = valid[:31]
        if np.count_nonzero(rigid)<6:
            refresh(0); self.details[track_id]=(0,0.); return 0
        matrix, _ = cv2.estimateAffinePartial2D(source[17:48][rigid],tracked[:31][rigid],method=cv2.LMEDS)
        if matrix is None:
            refresh(0); self.details[track_id]=(0,0.); return 0
        expected = cv2.transform(source[17:68].reshape(1,-1,2),matrix)[0]
        across = expected[54-17]-expected[48-17]
        width = max(float(np.linalg.norm(across)),1.)
        down = np.array([-across[1],across[0]])/width
        residual = tracked-expected
        changes = [float((residual[b-17]-residual[a-17]) @ down)
                   for a,b in ((50,58),(51,57),(52,56)) if valid[a-17] and valid[b-17]]
        if len(changes)<2:
            refresh(0); self.details[track_id]=(0,0.); return 0
        change = median(changes)
        limit = max(.5,width*.003)
        if abs(change)>=limit:
            direction = 1 if change>0 else -1
            refresh(direction)
        elif now-captured>.5:
            refresh(direction)
        self.details[track_id]=(direction,change)
        return direction
