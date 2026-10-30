"""2人対戦の状態管理と口の開閉判定。映像・描画から独立して検証可能。"""
from dataclasses import dataclass, field
import math

from statistics import median


class MouthCycle:
    """閉→開→閉を1口とする。継続時間・加点間隔の制限は設けない。"""
    def __init__(self, baseline=.025):
        self.baseline = baseline
        self.reset()

    def reset(self):
        self.armed = False
        self.opened = False

    def update(self, ratio):
        if ratio is None or not math.isfinite(ratio):
            self.reset()
            return False
        close = max(.065, self.baseline + .035)
        opening = max(.11, self.baseline + .07)
        if ratio <= close:
            bite = self.opened
            self.opened = False
            self.armed = True
            return bite
        if ratio >= opening and self.armed:
            self.opened = True
            self.armed = False
        return False


@dataclass
class Player:
    track_id: int
    hits: int = 0
    samples: list = field(default_factory=list)
    mouth: MouthCycle = field(default_factory=MouthCycle)
    last_bite: float = -math.inf


class CakeRace:
    bites_per_cake = 4

    def __init__(self, min_face=160, time_limit=30.):
        if min_face < 40 or not math.isfinite(time_limit) or time_limit <= 0:
            raise ValueError('min_face>=40、time_limit>0 が必要です')
        self.min_face = min_face
        self.time_limit = time_limit
        self.reset()

    def reset(self):
        self.state = 'waiting'
        self.players = []
        self.ready_since = None
        self.countdown_since = None
        self.elapsed = 0.
        self.previous = None
        self.absent_since = None
        self.resume_since = None
        self.winners = []
        self.events = []
        self.reason = ''

    def candidates(self, tracks, width, ratios=None):
        valid = [t for t in tracks if t.face[2] >= self.min_face and
                 t.face[3] >= self.min_face * .9 and
                 (ratios is None or ratios.get(t.number) is not None)]
        left = [t for t in valid if t.face[0] + t.face[2] / 2 < width * .48]
        right = [t for t in valid if t.face[0] + t.face[2] / 2 > width * .52]
        if not left or not right:
            return []
        return [max(left, key=lambda t: t.face[2]), max(right, key=lambda t: t.face[2])]

    def mouth_targets(self, tracks, width):
        if self.players:
            wanted = {p.track_id for p in self.players}
            return [t for t in tracks if t.number in wanted]
        return self.candidates(tracks, width)

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
                if any(median(p.samples) > .14 for p in self.players):
                    self.ready_since = now
                    for player in self.players:
                        player.samples.clear()
                    return
                for player in self.players:
                    player.mouth = MouthCycle(float(median(player.samples)))
                self.state = 'countdown'
                self.countdown_since = now
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
                self.reason = '顔が10秒間映らなかったため、待機に戻りました'
            return
        if self.state == 'paused':
            if self.resume_since is None:
                self.resume_since = now
            if now - self.resume_since >= .8:
                self.state = 'countdown'
                self.countdown_since = now
            return
        if self.state == 'countdown':
            # カウントダウン中は何回口を動かしても得点にならない。
            if now - self.countdown_since >= 3.:
                self.state = 'playing'
                for player in self.players:
                    player.mouth.reset()
            return
        if self.state == 'playing':
            self.elapsed = min(self.time_limit, self.elapsed + dt)
            if self.elapsed >= self.time_limit:
                best = max(p.hits for p in self.players)
                self.winners = [i for i, p in enumerate(self.players) if p.hits == best]
                self.state = 'result'
                self.reason = '時間終了！'
                return
            for i, player in enumerate(self.players):
                if player.mouth.update(ratios[player.track_id]):
                    player.hits += 1
                    player.last_bite = now
                    self.events.append(i)

    def countdown(self, now):
        return max(1, 3 - int(now - self.countdown_since))
