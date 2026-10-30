"""生成素材の顔への配置、星の光、雪の描画。"""
import math
import cv2
import numpy as np
from tracking import HEADS
from graphics import load_rgba
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / 'assets' / 'generated'

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


def make_sprites():
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

def placement(face, name='red', head_offset=0.):
    """素材ごとに基準点を分け、鼻の動きで帽子やひげがずれるのを抑える。"""
    eyes = sorted((face[4:6], face[6:8]), key=lambda point: point[0])
    right = eyes[1] - eyes[0]
    right = right / max(float(np.linalg.norm(right)), 1.)
    down = np.array([-right[1], right[0]])
    eye_center = (eyes[0] + eyes[1]) / 2
    mouth = (face[10:12] + face[12:14]) / 2
    width = max(float(face[2]), 1.)
    angle = math.degrees(math.atan2(float(right[1]), float(right[0])))
    if name in HEADS:
        origin = (200, 239)
        target = eye_center - down * width * (.40 - head_offset)
    elif name == 'beard':
        origin = (200, 402)
        target = mouth + down * width * .09
    elif name == 'wreath':
        origin = (200, 351)
        target = (eye_center + mouth) / 2
    else:
        origin = (200, 350)
        target = face[8:10]
    matrix = cv2.getRotationMatrix2D(origin, -angle, width / 200)
    matrix[:, 2] += target - np.array(origin)
    return matrix


def composite(frame, sprite, face, opacity=1., name='red', head_offset=0.):
    matrix = placement(face, name, head_offset)
    if name in HEADS:
        # 頭上が狭いときは取り付け位置を保ったまま飾りだけ小さくする。
        x, y, w, h = cv2.boundingRect((sprite[:, :, 3] > 12).astype(np.uint8))
        bounds = np.array([[[x, y], [x+w, y], [x+w, y+h], [x, y+h]]], np.float32)
        top = float(cv2.transform(bounds, matrix)[0, :, 1].min())
        anchor = matrix @ np.array([200., 239., 1.])
        if top < 8 and anchor[1] > 8:
            factor = min(1., max(.05, (anchor[1] - 8) / max(anchor[1] - top, 1.)))
            matrix[:, :2] *= factor
            matrix[:, 2] = anchor - matrix[:, :2] @ np.array([200., 239.])
    corners = cv2.transform(np.array([[[0., 0.], [400., 0.], [400., 600.], [0., 600.]]]), matrix)[0]
    low = np.maximum(np.floor(corners.min(axis=0)).astype(int), (0, 0))
    high = np.minimum(np.ceil(corners.max(axis=0)).astype(int), (frame.shape[1], frame.shape[0]))
    w, h = high - low
    if w <= 0 or h <= 0:
        return
    matrix[:, 2] -= low
    # プリマルチプライで補間し、半透明の光や縁に黒いにじみを作らない。
    source = sprite.astype(np.float32) / 255
    source[:, :, :3] *= source[:, :, 3:4]
    patch = cv2.warpAffine(source, matrix, (int(w), int(h)), flags=cv2.INTER_LINEAR)
    alpha = patch[:, :, 3:4] * opacity
    roi = frame[low[1]:high[1], low[0]:high[0]]
    roi[:] = np.clip(patch[:, :, :3] * (255 * opacity) + roi * (1 - alpha), 0, 255).astype(np.uint8)


def star_animation(base, count=24):
    """柔らかい後光、白金の本体、時間差で瞬く小さな光を事前生成。"""
    yy, xx = np.mgrid[:600, :400]
    distance = (xx - 200) ** 2 + (yy - 156) ** 2
    frames = []
    for index in range(count):
        phase = index * math.tau / count
        radius = 63 + 13 * math.sin(phase)
        glow = np.exp(-distance / (2 * radius ** 2)) * (155 + 65 * math.sin(phase))
        image = np.zeros_like(base)
        image[:, :, :3] = (85, 210, 255)
        image[:, :, 3] = glow.astype(np.uint8)
        alpha = base[:, :, 3:4].astype(np.float32) / 255
        old_alpha = image[:, :, 3:4].astype(np.float32) / 255
        result_alpha = alpha + old_alpha * (1 - alpha)
        color = (base[:, :, :3] * alpha + image[:, :, :3] * old_alpha * (1 - alpha)) / np.maximum(result_alpha, 1e-6)
        image[:, :, :3] = np.clip(color, 0, 255).astype(np.uint8)
        image[:, :, 3] = (result_alpha[:, :, 0] * 255).astype(np.uint8)
        for i, (x, y) in enumerate(((108, 122), (282, 93), (286, 207), (124, 227), (200, 70), (315, 159), (91, 177), (235, 244))):
            intensity = max(0., math.sin(phase + i * 1.6)) ** 3
            if intensity < .03:
                continue
            length = 8 + 23 * intensity
            vertices = np.array([(x, y-length), (x+2, y-2), (x+length*.6, y),
                                 (x+2, y+2), (x, y+length), (x-2, y+2),
                                 (x-length*.6, y), (x-2, y-2)], np.int32)
            cv2.fillPoly(image, [vertices], (245, 255, 255, int(255 * intensity)), cv2.LINE_AA)
        # 放射状の長い光芒。中心の星は消さず、周囲の光が強弱を繰り返す。
        strength = .5 + .5*math.sin(phase)
        for ray in range(8):
            angle = ray*math.pi/4 + .07*math.sin(phase)
            inner = 63
            outer = 80 + 23*strength
            a = (int(200+math.cos(angle)*inner), int(156+math.sin(angle)*inner))
            b = (int(200+math.cos(angle)*outer), int(156+math.sin(angle)*outer))
            cv2.line(image, a, b, (225, 250, 255, int(100+150*strength)), 2, cv2.LINE_AA)
        frames.append(image)
    return frames


class Snow:
    def __init__(self, seed=None, count=100):
        rng = np.random.default_rng(seed)
        self.x = rng.random(count)
        self.y = rng.random(count)
        self.speed = rng.uniform(.035, .12, count)
        self.radius = rng.integers(1, 4, count)
        self.phase = rng.uniform(0, math.tau, count)

    def draw(self, frame, dt, now):
        self.y = (self.y + self.speed * min(dt, .1)) % 1
        h, w = frame.shape[:2]
        layer = frame.copy()
        for x, y, r, phase in zip(self.x, self.y, self.radius, self.phase):
            px = int(((x + .012 * math.sin(now + phase)) % 1) * w)
            cv2.circle(layer, (px, int(y * h)), int(r), (255, 255, 255), -1, cv2.LINE_AA)
        cv2.addWeighted(layer, .65, frame, .35, 0, dst=frame)


def render(frame, tracks, sprites, now, head_offset=0.):
    if '_star_frames' not in sprites:
        sprites['_star_frames'] = star_animation(sprites['star'])
    for track in sorted(tracks, key=lambda t: t.face[2]):
        head, nose, surround = track.outfit
        for name in (surround, head, nose):
            if name == 'none':
                continue
            sprite = sprites[name]
            if name == 'star':
                frames = sprites['_star_frames']
                sprite = frames[int((now + track.number * .31) * 16) % len(frames)]
            composite(frame, sprite, track.face, name=name, head_offset=head_offset)

