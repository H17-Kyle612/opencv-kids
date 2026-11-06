"""衣装の選択、雪、ミラー表示をまとめる。"""
import random

import cv2

from graphics import text
from .effects import Snow, draw_outfit, make_sprites
from .outfits import LOOKS, random_outfit

UP_KEYS = (0xF700, 2490368, 65362)
DOWN_KEYS = (0xF701, 2621440, 65364)


class CostumeScene:
    def __init__(self, head_offset=0., *, seed=None):
        self.head_offset = head_offset
        self.rng = random.Random(seed)
        self.sprites = make_sprites()
        self.snow = Snow()
        self.outfits = {}
        self.fixed_outfit = None
        self.show_help = True

    def update(self, tracked_ids):
        # 一時的に見失った顔にも同じ衣装を維持する。
        for number in self.outfits.keys() - tracked_ids:
            del self.outfits[number]
        for number in tracked_ids:
            if number not in self.outfits:
                self.outfits[number] = self.fixed_outfit or random_outfit(self.rng)

    def shuffle(self):
        self.fixed_outfit = None
        for number in self.outfits:
            self.outfits[number] = random_outfit(self.rng)

    def choose(self, outfit):
        self.fixed_outfit = outfit
        for number in self.outfits:
            self.outfits[number] = outfit

    def handle_key(self, key):
        if key in (ord(' '), ord('r'), ord('R')):
            self.shuffle()
        elif ord('1') <= key <= ord('6'):
            self.choose(LOOKS[key - ord('1')])
        elif key in UP_KEYS or key in DOWN_KEYS:
            change = -.025 if key in UP_KEYS else .025
            self.head_offset = min(.5, max(-.5, self.head_offset + change))
        elif key in (ord('h'), ord('H')):
            self.show_help = not self.show_help

    def draw(self, frame, tracks, now, *, dt=0., winner_id=None, snowfall=True):
        if snowfall:
            self.snow.draw(frame, dt, now)
        for track in sorted(tracks, key=lambda track: track.face[2]):
            head, nose, surround = self.outfits[track.number]
            outfit = ('crown' if track.number == winner_id else head, nose, surround)
            draw_outfit(frame, track, outfit, self.sprites, now, self.head_offset)

    def draw_help(self, frame, face_count, fps):
        if not self.show_help:
            return
        bottom, width = frame.shape[:2]
        cv2.rectangle(frame, (0, bottom-58), (width, bottom), (30, 28, 24), -1)
        text(frame, f'クリスマス変身！  {face_count}人  毎秒{fps:.0f}コマ  飾り位置 {self.head_offset:+.2f}',
             (width/2, bottom-37), .55)
        text(frame, '空白：変身  1〜6：素材  ↑↓：位置  G：対戦  S：写真  F：全画面  Q：終了',
             (width/2, bottom-13), .43)
