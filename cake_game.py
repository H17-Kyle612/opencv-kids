"""2人対戦の状態管理と口の開閉判定。映像・描画から独立して検証可能。"""
from dataclasses import dataclass, field
import math

import cv2
import numpy as np


class MouthCycle:
    """閉→開→閉を1口とし、開けっぱなし・検出途切れ・瞬間ノイズを数えない。"""
    def __init__(self, baseline=.025):
        self.baseline = baseline
        self.reset()

    def reset(self):
        self.armed = False
        self.opened = False
        self.open_since = None
        self.since = None
        self.last_bite = -math.inf

    def update(self, ratio, now):
        if ratio is None or not math.isfinite(ratio):
            self.reset()
            return False
        close = max(.065, self.baseline + .035)
        opening = max(.15, self.baseline + .10)
        if ratio <= close:
            self.open_since = None
            if self.since is None:
                self.since = now
            if now - self.since >= .06:
                if self.opened and now - self.last_bite >= .24:
                    self.opened = False
                    self.armed = True
                    self.last_bite = now
                    return True
                self.armed = True
        elif ratio >= opening:
            if self.open_since is None:
                self.open_since = now
            if self.armed and now - self.open_since >= .06:
                self.opened = True
                self.armed = False
            self.since = None
        else:
            self.since = None
            self.open_since = None
        return False


@dataclass
class Player:
    track_id: int
    hits: int = 0
    samples: list = field(default_factory=list)
    mouth: MouthCycle = field(default_factory=MouthCycle)
    last_bite: float = -math.inf
    finished: float | None = None


class CakeRace:
    def __init__(self, cakes=3, bites_per_cake=4, min_face=160, time_limit=90.):
        if cakes < 1 or bites_per_cake != 4 or min_face < 40 or time_limit <= 0:
            raise ValueError('cakes>=1, bites_per_cake=4, min_face>=40, time_limit>0 が必要です')
        self.cakes = cakes
        self.bites_per_cake = bites_per_cake
        self.min_face = min_face
        self.time_limit = time_limit
        self.reset()

    @property
    def total(self):
        return self.cakes * self.bites_per_cake

    def reset(self):
        self.state = 'waiting'
        self.players = []
        self.ready_since = None
        self.countdown_since = None
        self.resuming = False
        self.elapsed = 0.
        self.previous = None
        self.absent_since = None
        self.resume_since = None
        self.winners = []
        self.events = []
        self.reason = ''

    def candidates(self, tracks, width, ratios):
        valid = [t for t in tracks if t.face[2] >= self.min_face and
                 t.face[3] >= self.min_face * .9 and ratios.get(t.number) is not None]
        left = [t for t in valid if t.face[0] + t.face[2] / 2 < width * .48]
        right = [t for t in valid if t.face[0] + t.face[2] / 2 > width * .52]
        if not left or not right:
            return []
        return [max(left, key=lambda t: t.face[2]), max(right, key=lambda t: t.face[2])]

    def update(self, tracks, ratios, width, now):
        self.events = []
        dt = 0. if self.previous is None else max(now - self.previous, 0.)
        self.previous = now
        by_id = {t.number: t for t in tracks}
        if self.state == 'result':
            return
        if self.state in ('waiting', 'ready'):
            pair = self.candidates(tracks, width, ratios)
            ids = [t.number for t in pair]
            if len(pair) != 2:
                self.state = 'waiting'
                self.ready_since = None
                self.players = []
                return
            # 顔の大きさ・場所・口の推定が安定してから、同じ2人で開始。
            if [p.track_id for p in self.players] != ids:
                self.players = [Player(i) for i in ids]
                self.ready_since = now
            self.state = 'ready'
            for player in self.players:
                ratio = ratios[player.track_id]
                player.samples.append(ratio)
                player.samples = player.samples[-90:]
            if now - self.ready_since >= 1.5:
                # 開いた口を閉じた基準として学習させない。
                if any(np.median(p.samples) > .14 for p in self.players):
                    self.ready_since = now
                    for player in self.players:
                        player.samples.clear()
                    return
                for player in self.players:
                    player.mouth = MouthCycle(float(np.median(player.samples)))
                self.state = 'countdown'
                self.countdown_since = now
                self.resuming = False
            return
        present = all(p.track_id in by_id and ratios.get(p.track_id) is not None and
                      by_id[p.track_id].face[2] >= self.min_face * .75 for p in self.players)
        if not present:
            if self.state != 'paused':
                self.state = 'paused'
                self.absent_since = now
                for player in self.players:
                    player.mouth.reset()
            self.resume_since = None
            if now - self.absent_since >= 10.:
                self.reset()
                self.reason = 'Match reset: face was lost for 10 seconds'
            return
        if self.state == 'paused':
            if self.resume_since is None:
                self.resume_since = now
            if now - self.resume_since >= .8:
                self.state = 'countdown'
                self.countdown_since = now
                self.resuming = True
            return
        if self.state == 'countdown':
            # カウントダウン中は何回口を動かしても得点にならない。
            if now - self.countdown_since >= 3.:
                self.state = 'playing'
                for player in self.players:
                    player.mouth.reset()
            return
        if self.state == 'playing':
            self.elapsed += dt
            for i, player in enumerate(self.players):
                if player.mouth.update(ratios[player.track_id], now):
                    player.hits += 1
                    player.last_bite = now
                    self.events.append(i)
                    if player.hits >= self.total:
                        player.finished = self.elapsed
            finished = [i for i, p in enumerate(self.players) if p.finished is not None]
            if finished:
                # 同じフレームで完食した場合は引き分けにする。
                self.winners = finished
                self.state = 'result'
                self.reason = 'ALL CAKES FINISHED!'
            elif self.elapsed >= self.time_limit:
                best = max(p.hits for p in self.players)
                self.winners = [i for i, p in enumerate(self.players) if p.hits == best]
                self.state = 'result'
                self.reason = 'TIME UP!'

    def countdown(self, now):
        return max(1, 3 - int(now - self.countdown_since))


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
        scale = min(1., 720 / frame.shape[1])
        small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        rectangles, selected = [], []
        for track in tracks:
            x, y, w, h = track.face[:4] * scale
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
            pts = np.asarray(landmark).reshape(-1, 2) / scale
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
