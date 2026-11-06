"""顔の位置に基づく短期追跡。"""
from dataclasses import dataclass
import math
import numpy as np

@dataclass
class Track:
    number: int
    face: np.ndarray
    seen: float


def iou(a, b):
    lo = np.maximum(a[:2], b[:2])
    hi = np.minimum(a[:2] + a[2:4], b[:2] + b[2:4])
    area = float(np.prod(np.maximum(hi - lo, 0)))
    return area / max(float(a[2] * a[3] + b[2] * b[3]) - area, 1)


class Tracker:
    """位置による短期追跡。個人の顔を照合・登録する処理は行わない。"""
    def __init__(self, ttl=1.2):
        self.ttl = ttl
        self.tracks = {}
        self.next_id = 1

    def update(self, faces, now):
        self.tracks = {k: t for k, t in self.tracks.items() if now - t.seen <= self.ttl}
        candidates = []
        for index, face in enumerate(faces):
            center = face[:2] + face[2:4] / 2
            for key, track in self.tracks.items():
                old = track.face
                distance = np.linalg.norm(center - old[:2] - old[2:4] / 2)
                scale = max(float(face[2]), float(old[2]), 1)
                overlap = iou(face, old)
                ratio = max(float(face[2]), float(old[2])) / max(min(float(face[2]), float(old[2])), 1)
                if ratio < 2 and (overlap > .1 or distance / scale < .65):
                    candidates.append((overlap - distance / scale * .3, index, key))
        used_faces, used_tracks = set(), set()
        visible = []
        for _, index, key in sorted(candidates, reverse=True):
            if index in used_faces or key in used_tracks:
                continue
            track = self.tracks[key]
            # 時間に基づく平滑化。長く見失った後は古い位置に引きずらない。
            alpha = 1 - math.exp(-max(now - track.seen, .001) / .045)
            track.face = track.face * (1 - alpha) + faces[index] * alpha
            track.seen = now
            visible.append(track)
            used_faces.add(index)
            used_tracks.add(key)
        for index, face in enumerate(faces):
            if index not in used_faces:
                track = Track(self.next_id, face.copy(), now)
                self.tracks[track.number] = track
                self.next_id += 1
                visible.append(track)
        # 見失った顔の位置には描かない。再検出用の記録だけ一定時間残す。
        return visible

