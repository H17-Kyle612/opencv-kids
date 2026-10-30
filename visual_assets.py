"""画像生成した透過PNGを、顔追従用の基準キャンバスへ配置する。"""
import cv2
import numpy as np
from game_visuals import ASSETS, load_rgba

# 基準点は christmas_camera.placement と共通。
BOXES = {
    'santa': (80, 70, 240, 190),
    'beard': (99, 373, 202, 142),
    'antlers': (38, 70, 324, 180),
    'star': (142, 98, 116, 116),
    'gift': (110, 85, 180, 149),
    'cross': (150, 82, 100, 140),
    'red': (175, 325, 50, 50),
    'wreath': (38, 183, 324, 348),
}


def load_accessories():
    sprites = {}
    for name, (x, y, w, h) in BOXES.items():
        source = load_rgba(ASSETS / f'{name}.png')
        scale = min(w/source.shape[1], h/source.shape[0])
        sw, sh = max(1, round(source.shape[1]*scale)), max(1, round(source.shape[0]*scale))
        # プリマルチプライで縮小し、透明部分の黒が輪郭に混ざるのを防ぐ。
        alpha = source[:, :, 3:4].astype(np.float32) / 255
        data = np.concatenate((source[:, :, :3].astype(np.float32)*alpha, alpha*255), axis=2)
        resized = cv2.resize(data, (sw, sh), interpolation=cv2.INTER_AREA)
        a = resized[:, :, 3:4]/255
        resized[:, :, :3] = resized[:, :, :3]/np.maximum(a, 1e-6)
        canvas = np.zeros((600, 400, 4), np.uint8)
        left, top = x+(w-sw)//2, y+(h-sh)//2
        canvas[top:top+sh, left:left+sw] = np.clip(resized, 0, 255).astype(np.uint8)
        sprites[name] = canvas
    return sprites
