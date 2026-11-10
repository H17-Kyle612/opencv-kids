"""生成画像を使うケーキレースのHUDと演出。描画処理はOpenCVのみ。"""
from pathlib import Path
import math
import random

import cv2
import numpy as np

from graphics import load_rgba, blit, text

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'generated'
COLORS = ((255, 205, 80), (160, 125, 255))
GOLD = (100, 225, 255)
PINE = (31, 66, 25)
IVORY = (236, 248, 255)


def pill(frame, center, width, height):
    x, y = center
    half_span = (width-height)/2
    cv2.line(frame, (round(x-half_span), round(y)), (round(x+half_span), round(y)),
             PINE, max(1, round(height)), cv2.LINE_AA)


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

    def burst(self, center, color, now, big=False):
        for _ in range(100 if big else 48):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(70, 480 if big else 310)
            self.particles.append((center[0], center[1], math.cos(angle)*speed,
                                   math.sin(angle)*speed-110, now, self.rng.uniform(.45, 1.1),
                                   self.rng.choice((color, GOLD, (245, 250, 255), (100, 130, 255))),
                                   self.rng.randint(3, 9)))

    def draw(self, frame, race, now):
        h, w = frame.shape[:2]
        unit = min(w/1280, h/720)
        solo = race.player_count == 1
        score_width, score_height = 218*unit, 82*unit
        inset = 22*unit + score_width/2
        y = h - 22*unit - score_height/2
        centers = [(w/2, y)] if solo else [(inset, y), (w-inset, y)]
        for index in race.events:
            x, y = centers[index]
            self.burst((x-51*unit, y), COLORS[index], now,
                       race.players[index].hits % race.bites_per_cake == 0)
        self._particles(frame, now)

        status = {'waiting': '顔を映してね', 'ready': '準備！',
                  'playing': f'残り {race.remaining:04.1f}秒',
                  'paused': '一時停止', 'result': '終了！'}
        label = status.get(race.state)
        if race.state == 'countdown':
            label = race.countdown(now)
        if race.state == 'result' and not solo:
            label = '引き分け！' if len(race.winners) == 2 else f'プレイヤー{race.winners[0]+1}の勝ち！'
        header_width = max(85, len(str(label))*31 + 62)*unit
        header_y = 46*unit
        pill(frame, (w/2, header_y), header_width, 58*unit)
        text(frame, label, (w/2, header_y), .91*unit, IVORY)

        for i, (x, y) in enumerate(centers):
            player = race.players[i] if i < len(race.players) else None
            hits = player.hits if player else 0
            eaten, stage = divmod(hits, race.bites_per_cake)
            age = now-player.last_bite if player else math.inf
            bouncing = 0 <= age < .6
            scale = 1 + .2*math.exp(-age*8)*math.sin(age*28) if bouncing else 1.
            angle = math.sin(age*35)*9*math.exp(-age*6) if bouncing else 0.
            sprite = self.cakes[4 if 0 <= age < .18 and hits and stage == 0 else stage]

            pill(frame, (x, y), score_width, score_height)

            top, bottom = round(y-35*unit), round(y+35*unit)
            left, right = round(x-96*unit), round(x-7*unit)
            cake_area = frame[top:bottom, left:right]
            blit(cake_area, sprite, (cake_area.shape[1]/2, cake_area.shape[0]/2),
                 78*unit*scale, 62*unit*scale, angle)
            count_x = x+40*unit
            text(frame, f'{eaten}個', (count_x, y-8*unit), .87*unit, IVORY)
            for dot in range(race.bites_per_cake):
                dot_x = count_x + (dot-(race.bites_per_cake-1)/2)*15*unit
                cv2.circle(frame, (round(dot_x), round(y+23*unit)), max(1, round(4*unit)),
                           GOLD if dot < stage else (77, 106, 72), -1, cv2.LINE_AA)

    def _particles(self, frame, now):
        self.particles = [p for p in self.particles if now-p[4] < p[5]]
        for x, y, vx, vy, born, life, color, radius in self.particles:
            age = now-born
            px, py = int(x+vx*age), int(y+vy*age+250*age*age)
            r = max(1, int(radius*(1-age/life)))
            cv2.circle(frame, (px, py), r, color, -1, cv2.LINE_AA)
