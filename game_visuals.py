"""生成画像を使うケーキレースのHUDと演出。描画処理はOpenCVのみ。"""
from pathlib import Path
import math
import random

import cv2
import numpy as np

ASSETS = Path(__file__).resolve().parent / 'assets' / 'generated'
COLORS = ((255, 205, 80), (160, 125, 255))
GOLD = (100, 225, 255)


def load_rgba(path):
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 3 or image.shape[2] != 4:
        raise RuntimeError(f'透過PNG素材がありません: {path}')
    if image[:, :, 3].min() == 255:
        raise RuntimeError(f'素材に透明部分がありません: {path}')
    x, y, w, h = cv2.boundingRect((image[:, :, 3] > 8).astype(np.uint8))
    return image[y:y+h, x:x+w]


def blit(frame, sprite, center, width, max_height=None, angle=0., opacity=1.):
    scale = width / sprite.shape[1]
    if max_height:
        scale = min(scale, max_height / sprite.shape[0])
    if scale <= 0:
        return
    w, h = max(1, int(sprite.shape[1]*scale)), max(1, int(sprite.shape[0]*scale))
    source = sprite if sprite.dtype == np.float32 else sprite.astype(np.float32) / 255
    if sprite.dtype != np.float32:
        source[:, :, :3] *= source[:, :, 3:4]
    image = cv2.resize(source, (w, h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    if angle:
        diagonal = int(math.hypot(w, h)) + 2
        matrix = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.)
        matrix[:, 2] += [(diagonal-w)/2, (diagonal-h)/2]
        image = cv2.warpAffine(image, matrix, (diagonal, diagonal))
        h, w = image.shape[:2]
    x, y = int(center[0]-w/2), int(center[1]-h/2)
    left, top = max(0, x), max(0, y)
    right, bottom = min(frame.shape[1], x+w), min(frame.shape[0], y+h)
    if right <= left or bottom <= top:
        return
    patch = image[top-y:bottom-y, left-x:right-x]
    target = frame[top:bottom, left:right]
    alpha = patch[:, :, 3:4] * opacity
    target[:] = np.clip(patch[:, :, :3]*255*opacity + target*(1-alpha), 0, 255).astype(np.uint8)


def text(frame, label, center, size=1., color=(255, 255, 255), thickness=2):
    font = cv2.FONT_HERSHEY_DUPLEX
    (w, h), _ = cv2.getTextSize(str(label), font, size, thickness)
    position = (int(center[0]-w/2), int(center[1]+h/2))
    cv2.putText(frame, str(label), (position[0]+2, position[1]+3), font, size, (25, 17, 30), thickness+2, cv2.LINE_AA)
    cv2.putText(frame, str(label), position, font, size, color, thickness, cv2.LINE_AA)


def panel(frame, rect, color=(38, 25, 24), opacity=.85):
    x1, y1, x2, y2 = map(int, rect)
    roi = frame[max(0, y1):min(frame.shape[0], y2), max(0, x1):min(frame.shape[1], x2)]
    if roi.size:
        roi[:] = (roi*(1-opacity)+np.array(color)*opacity).astype(np.uint8)


class GameVisuals:
    def __init__(self):
        self.cakes = []
        for i in range(5):
            image = load_rgba(ASSETS / f'cake_{i}.png').astype(np.float32) / 255
            image[:, :, :3] *= image[:, :, 3:4]
            scale = min(1., 480 / image.shape[1])
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            self.cakes.append(image)
        self.particles = []
        self.rng = random.Random()
        self.last = None
        self.result_since = None
        self.last_firework = -math.inf
        self.seen_state = None

    def burst(self, center, color, now, big=False):
        for _ in range(100 if big else 48):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(70, 480 if big else 310)
            self.particles.append((center[0], center[1], math.cos(angle)*speed,
                                   math.sin(angle)*speed-110, now, self.rng.uniform(.45, 1.1),
                                   self.rng.choice((color, GOLD, (245, 250, 255), (100, 130, 255))),
                                   self.rng.randint(3, 9)))

    def draw(self, frame, race, tracks, ratios, now, enabled=True):
        if not enabled:
            return
        h, w = frame.shape[:2]
        unit = min(w/1280, h/720)
        centers = [(w*.25, h*.78), (w*.75, h*.78)]
        for index in race.events:
            self.burst(centers[index], COLORS[index], now,
                       race.players[index].hits % race.bites_per_cake == 0)
        if race.state == 'result' and self.seen_state != 'result':
            self.result_since = now
            for x in (.15, .35, .65, .85):
                self.burst((w*x, h*.25), GOLD, now, True)
        if race.state == 'result' and now-self.result_since < 4 and now-self.last_firework > .5:
            self.last_firework = now
            self.burst((w*self.rng.uniform(.15, .85), h*.25), GOLD, now, True)
        self.seen_state = race.state
        by_id = {t.number: t for t in tracks}
        if race.state == 'waiting':
            panel(frame, (0, 0, w, 105*unit))
            text(frame, 'CHRISTMAS CAKE CHOMP!', (w/2, 30*unit), .85*unit, GOLD)
            text(frame, 'Two players: one on each side. Face the camera and move closer.',
                 (w/2, 69*unit), .52*unit)
            for i in range(2):
                center = (centers[i][0], h*.63)
                blit(frame, self.cakes[0], center, w*.17, h*.22)
                text(frame, f'PLAYER {i+1}', (center[0], h*.83), .65*unit, COLORS[i])
            text(frame, f'Face width: {race.min_face}px or more | G: mirror only', (w/2, h*.94), .48*unit)
            return
        panel(frame, (0, 0, w, 72*unit))
        text(frame, 'CHRISTMAS CAKE CHOMP!', (w*.25, 31*unit), .7*unit, GOLD)
        text(frame, f'TIME  {race.elapsed:05.1f} / {race.time_limit:.0f}s', (w*.76, 31*unit), .7*unit)
        # 競技者を顔の色枠で示す。割り当ては開始時に固定する。
        for i, player in enumerate(race.players):
            track = by_id.get(player.track_id)
            if track:
                x, y, fw, fh = track.face[:4].astype(int)
                cv2.rectangle(frame, (x, y), (x+fw, y+fh), COLORS[i], max(1, int(2*unit)), cv2.LINE_AA)
                text(frame, f'P{i+1}', (x+fw/2, max(87*unit, y-13*unit)), .65*unit, COLORS[i])
        panel(frame, (0, h*.61, w, h), opacity=.83)
        cv2.line(frame, (w//2, int(h*.64)), (w//2, h-12), (100, 94, 90), 1)
        for i, player in enumerate(race.players):
            x, y = centers[i]
            hits = min(player.hits, race.total)
            eaten = hits // race.bites_per_cake
            stage = hits % race.bites_per_cake if hits < race.total else 4
            age = now-player.last_bite
            scale = 1 + .2*math.exp(-age*8)*math.sin(age*28) if 0 <= age < .6 else 1.
            angle = math.sin(age*35)*9*math.exp(-age*6) if 0 <= age < .6 else 0.
            sprite = self.cakes[stage]
            if 0 <= age < .18 and hits and hits % 4 == 0:
                sprite = self.cakes[4]
            blit(frame, sprite, (x, y-8*unit), w*.19*scale, h*.24*scale, angle)
            text(frame, f'P{i+1}  CAKES {eaten}/{race.cakes}', (x, h*.65), .65*unit, COLORS[i])
            text(frame, f'{hits} / {race.total} BITES', (x, h*.928), .62*unit)
            # 4口ずつの進捗が見える大きな丸。
            for dot in range(race.total):
                px = int(x + (dot-(race.total-1)/2)*min(19*unit, w*.4/race.total))
                cv2.circle(frame, (px, int(h*.98)), max(2, int(5*unit)), COLORS[i] if dot < hits else (90, 80, 80), -1, cv2.LINE_AA)
            ratio = ratios.get(player.track_id)
            meter = min(1., ratio/.35) if ratio is not None else 0.
            cv2.rectangle(frame, (int(x-w*.13), int(h*.87)), (int(x+w*.13), int(h*.88)), (80, 70, 70), -1)
            cv2.rectangle(frame, (int(x-w*.13), int(h*.87)), (int(x-w*.13+w*.26*meter), int(h*.88)), COLORS[i], -1)
            if 0 <= age < .6:
                text(frame, 'CHOMP!' if hits % 4 else 'CAKE CLEAR!', (x, h*.56-age*45), (1.1 if hits % 4 else .95)*unit, GOLD, 3)
                radius = max(1, int(age*400*unit))
                cv2.circle(frame, (int(x), int(y)), radius, GOLD, max(1, int((1-age/.6)*7*unit)), cv2.LINE_AA)
        if race.state in ('ready', 'countdown', 'paused'):
            panel(frame, (w*.13, h*.25, w*.87, h*.55), (45, 32, 30), .9)
            if race.state == 'ready':
                text(frame, 'READY? KEEP YOUR MOUTH CLOSED', (w/2, h*.36), .8*unit, GOLD)
                progress = max(0., min(1., (now-race.ready_since)/1.5))
                cv2.rectangle(frame, (int(w*.25), int(h*.44)), (int(w*(.25+.5*progress)), int(h*.46)), GOLD, -1)
            elif race.state == 'countdown':
                text(frame, race.countdown(now), (w/2, h*.38), 2.8*unit, GOLD, 5)
                text(frame, 'OPEN, THEN CLOSE = ONE BITE', (w/2, h*.51), .6*unit)
            else:
                text(frame, 'PAUSED - FACE THE CAMERA', (w/2, h*.36), .9*unit, GOLD)
                text(frame, 'Both players return to resume. Progress and time are kept.', (w/2, h*.47), .53*unit)
        if race.state == 'playing' and race.elapsed < .7:
            text(frame, 'GO!', (w/2, h*.35), 2.5*unit, GOLD, 5)
        if race.state == 'result':
            panel(frame, (w*.09, h*.14, w*.91, h*.60), (48, 27, 32), .96)
            winner = 'DRAW!' if len(race.winners) == 2 else f'PLAYER {race.winners[0]+1} WINS!'
            text(frame, winner, (w/2, h*.22), 1.25*unit, GOLD, 3)
            text(frame, race.reason, (w/2, h*.295), .52*unit)
            for i, p in enumerate(race.players):
                x = w*(.30 if i == 0 else .70)
                text(frame, f'P{i+1}  {p.hits//4} CAKES / {p.hits} BITES', (x, h*.385), .6*unit, COLORS[i])
                finish = f'{p.finished:.2f}s' if p.finished is not None else 'NOT FINISHED'
                text(frame, finish, (x, h*.45), .75*unit)
                rate = p.hits/max(race.elapsed, .01)
                text(frame, f'{rate:.2f} bites/sec', (x, h*.51), .45*unit)
            text(frame, 'R: PLAY AGAIN    G: BACK TO MIRROR', (w/2, h*.565), .5*unit)
        self._particles(frame, now)

    def _particles(self, frame, now):
        self.particles = [p for p in self.particles if now-p[4] < p[5]]
        for x, y, vx, vy, born, life, color, radius in self.particles:
            age = now-born
            px, py = int(x+vx*age), int(y+vy*age+250*age*age)
            r = max(1, int(radius*(1-age/life)))
            cv2.circle(frame, (px, py), r, color, -1, cv2.LINE_AA)
