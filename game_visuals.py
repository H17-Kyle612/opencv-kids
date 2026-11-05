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
        solo = race.player_count == 1
        centers = [(w*.5, h*.85)] if solo else [(w*.25, h*.85), (w*.75, h*.85)]
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
        statuses = {'waiting':'顔を映してね', 'ready':'準備！　口を閉じて待ってね',
                    'playing':'', 'paused':'一時停止', 'result':'終了！'}
        status = race.countdown(now) if race.state == 'countdown' else statuses[race.state]
        if race.state == 'result' and not solo:
            status = '引き分け！' if len(race.winners) == 2 else f'プレイヤー{race.winners[0]+1}の勝ち！'
        panel(frame, (0, 0, w, 72*unit))
        if status:
            text(frame, status, (w*.28, 33*unit), .65*unit, GOLD)
        text(frame, f'残り {max(0., race.time_limit-race.elapsed):04.1f}秒', (w*.77, 33*unit), .7*unit)
        panel(frame, (0, h*.69, w, h), opacity=.75)
        if not solo:
            cv2.line(frame, (w//2, int(h*.72)), (w//2, h-12), (100, 94, 90), 1)
        if not race.players:
            for i in range(race.player_count):
                blit(frame, self.cakes[0], centers[i], w*.17, h*.19)
            return
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
            # 画像は専用領域で切り抜き、拡大・回転中も個数の文字に重ねない。
            cake_area = frame[int(h*.765):int(h*.95)]
            blit(cake_area, sprite, (x, cake_area.shape[0]/2), w*.19*scale, cake_area.shape[0]*.8*scale, angle)
            text(frame, f'{"あなた" if solo else f"プレイヤー{i+1}"}　{eaten}個', (x, h*.725), .65*unit, COLORS[i])
            # 4口ずつの進捗が見える大きな丸。
            for dot in range(race.bites_per_cake):
                px = int(x + (dot-(race.bites_per_cake-1)/2)*30*unit)
                cv2.circle(frame, (px, int(h*.98)), max(2, int(5*unit)), COLORS[i] if dot < stage else (90, 80, 80), -1, cv2.LINE_AA)
            if 0 <= age < .6:
                radius = max(1, int(age*400*unit))
                cv2.circle(frame, (int(x), int(y)), radius, GOLD, max(1, int((1-age/.6)*7*unit)), cv2.LINE_AA)
        self._particles(frame, now)

    def _particles(self, frame, now):
        self.particles = [p for p in self.particles if now-p[4] < p[5]]
        for x, y, vx, vy, born, life, color, radius in self.particles:
            age = now-born
            px, py = int(x+vx*age), int(y+vy*age+250*age*age)
            r = max(1, int(radius*(1-age/life)))
            cv2.circle(frame, (px, py), r, color, -1, cv2.LINE_AA)
