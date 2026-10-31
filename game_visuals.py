"""生成画像を使うケーキレースのHUDと演出。描画処理はOpenCVのみ。"""
from pathlib import Path
import math
import random

import cv2
import numpy as np

from graphics import load_rgba, blit, panel, text

ASSETS = Path(__file__).resolve().parent / 'assets' / 'generated'
COLORS = ((255, 205, 80), (160, 125, 255))
GOLD = (100, 225, 255)


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
        panel(frame, (0, h-28*unit, w, h))
        text(frame, f'口の感度 {race.sensitivity}/5　+：上げる　-：下げる',
             (w/2, h-10*unit), .38*unit)
        solo = race.player_count == 1
        centers = [(w*.5, h*.78)] if solo else [(w*.25, h*.78), (w*.75, h*.78)]
        mode = '1人チャレンジ' if solo else '2人対戦'
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
            text(frame, f'ケーキぱくぱく！　{mode}', (w/2, 30*unit), .85*unit, GOLD)
            text(frame, '顔を大きく映してね' if solo else '左右に1人ずつ、顔を大きく映してね',
                 (w/2, 69*unit), .52*unit)
            for i in range(race.player_count):
                center = (centers[i][0], h*.63)
                blit(frame, self.cakes[0], center, w*.17, h*.22)
                text(frame, 'あなた' if solo else f'プレイヤー{i+1}', (center[0], h*.83), .65*unit, COLORS[i])
            text(frame, f'顔の幅 {race.min_face}px以上で開始　M：1人／2人　G：変身ミラー', (w/2, h*.94), .48*unit)
            return
        panel(frame, (0, 0, w, 72*unit))
        text(frame, f'ケーキぱくぱく！　{mode}', (w*.25, 31*unit), .58*unit, GOLD)
        text(frame, f'残り {max(0., race.time_limit-race.elapsed):04.1f}秒', (w*.76, 31*unit), .7*unit)
        # 競技者を顔の色枠で示す。割り当ては開始時に固定する。
        for i, player in enumerate(race.players):
            track = by_id.get(player.track_id)
            if track:
                x, y, fw, fh = track.face[:4].astype(int)
                cv2.rectangle(frame, (x, y), (x+fw, y+fh), COLORS[i], max(1, int(2*unit)), cv2.LINE_AA)
                text(frame, 'あなた' if solo else f'プレイヤー{i+1}', (x+fw/2, max(87*unit, y-13*unit)), .65*unit, COLORS[i])
        panel(frame, (0, h*.61, w, h), opacity=.83)
        if not solo:
            cv2.line(frame, (w//2, int(h*.64)), (w//2, h-12), (100, 94, 90), 1)
        for i, player in enumerate(race.players):
            x, y = centers[i]
            hits = player.hits
            eaten = hits // race.bites_per_cake
            stage = hits % race.bites_per_cake
            age = now-player.last_bite
            scale = 1 + .2*math.exp(-age*8)*math.sin(age*28) if 0 <= age < .6 else 1.
            angle = math.sin(age*35)*9*math.exp(-age*6) if 0 <= age < .6 else 0.
            sprite = self.cakes[stage]
            if 0 <= age < .18 and hits and stage == 0:
                sprite = self.cakes[4]
            blit(frame, sprite, (x, y-8*unit), w*.19*scale, h*.24*scale, angle)
            text(frame, f'{"あなた" if solo else f"プレイヤー{i+1}"}　{eaten}個', (x, h*.65), .65*unit, COLORS[i])
            text(frame, f'合計 {hits}口　次のケーキ {stage}/{race.bites_per_cake}口', (x, h*.928), .62*unit)
            # 4口ずつの進捗が見える大きな丸。
            for dot in range(race.bites_per_cake):
                px = int(x + (dot-(race.bites_per_cake-1)/2)*30*unit)
                cv2.circle(frame, (px, int(h*.98)), max(2, int(5*unit)), COLORS[i] if dot < stage else (90, 80, 80), -1, cv2.LINE_AA)
            ratio = ratios.get(player.track_id)
            meter = min(1., ratio/.35) if ratio is not None else 0.
            cv2.rectangle(frame, (int(x-w*.13), int(h*.87)), (int(x+w*.13), int(h*.88)), (80, 70, 70), -1)
            cv2.rectangle(frame, (int(x-w*.13), int(h*.87)), (int(x-w*.13+w*.26*meter), int(h*.88)), COLORS[i], -1)
            if 0 <= age < .6:
                text(frame, 'ぱくっ！' if stage else 'おかわり！', (x, h*.56-age*45), (1.1 if stage else .95)*unit, GOLD, 3)
                radius = max(1, int(age*400*unit))
                cv2.circle(frame, (int(x), int(y)), radius, GOLD, max(1, int((1-age/.6)*7*unit)), cv2.LINE_AA)
        if race.state in ('ready', 'countdown', 'paused'):
            panel(frame, (w*.13, h*.25, w*.87, h*.55), (45, 32, 30), .9)
            if race.state == 'ready':
                text(frame, '準備！　口を閉じて待ってね', (w/2, h*.36), .8*unit, GOLD)
                progress = max(0., min(1., (now-race.ready_since)/1.5))
                cv2.rectangle(frame, (int(w*.25), int(h*.44)), (int(w*(.25+.5*progress)), int(h*.46)), GOLD, -1)
            elif race.state == 'countdown':
                text(frame, race.countdown(now), (w/2, h*.38), 2.8*unit, GOLD, 5)
                text(frame, '口を開いて、閉じると1口！', (w/2, h*.51), .6*unit)
            else:
                text(frame, '一時停止　顔を正面に向けてね', (w/2, h*.36), .9*unit, GOLD)
                text(frame, '顔が戻ると再開。時間と得点はそのまま！' if solo else '2人が戻ると再開。時間と得点はそのまま！', (w/2, h*.47), .53*unit)
        if race.state == 'playing' and race.elapsed < .7:
            text(frame, 'スタート！', (w/2, h*.35), 2.5*unit, GOLD, 5)
        if race.state == 'result':
            panel(frame, (w*.09, h*.14, w*.91, h*.60), (48, 27, 32), .96)
            winner = 'チャレンジ終了！' if solo else ('引き分け！' if len(race.winners) == 2 else f'プレイヤー{race.winners[0]+1}の勝ち！')
            text(frame, winner, (w/2, h*.22), 1.25*unit, GOLD, 3)
            text(frame, race.reason, (w/2, h*.295), .52*unit)
            for i, p in enumerate(race.players):
                x = w*.5 if solo else w*(.30 if i == 0 else .70)
                text(frame, f'{"あなた" if solo else f"プレイヤー{i+1}"}　{p.hits//race.bites_per_cake}個＋{p.hits%race.bites_per_cake}/{race.bites_per_cake}個', (x, h*.385), .6*unit, COLORS[i])
                text(frame, f'食べた回数 {p.hits}口', (x, h*.45), .75*unit)
                rate = p.hits/max(race.elapsed, .01)
                text(frame, f'毎秒 {rate:.2f}口', (x, h*.51), .45*unit)
            text(frame, 'R：もう一度　M：1人／2人　G：変身ミラー', (w/2, h*.565), .5*unit)
        self._particles(frame, now)

    def _particles(self, frame, now):
        self.particles = [p for p in self.particles if now-p[4] < p[5]]
        for x, y, vx, vy, born, life, color, radius in self.particles:
            age = now-born
            px, py = int(x+vx*age), int(y+vy*age+250*age*age)
            r = max(1, int(radius*(1-age/life)))
            cv2.circle(frame, (px, py), r, color, -1, cv2.LINE_AA)
