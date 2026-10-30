"""OpenCVだけで動く、みんなのクリスマス変身カメラ。"""
import argparse
from dataclasses import dataclass
from datetime import datetime
import math
import json
from pathlib import Path
import random
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / 'models' / 'face_detection_yunet_2023mar.onnx'
WINDOW = 'Christmas Magic Camera'
HEADS = ('santa', 'antlers', 'star', 'gift', 'cross', 'none')
LOOKS = (('santa', 'none', 'beard'), ('antlers', 'red', 'none'),
         ('star', 'none', 'none'), ('gift', 'carrot', 'none'),
         ('cross', 'none', 'none'), ('none', 'none', 'wreath'))
NOSES = ('red', 'carrot', 'none')


def costume(rng):
    # 頭の素材は一つずつ。鼻と顔周りは独立して抽選。
    head = rng.choice(HEADS)
    nose = rng.choice(NOSES)
    surround = rng.choice(('beard', 'wreath', 'none'))
    if head == 'none' and nose == 'none' and surround == 'none':
        head = 'santa'
    return head, nose, surround


@dataclass
class Track:
    number: int
    face: np.ndarray
    outfit: tuple
    seen: float


def iou(a, b):
    lo = np.maximum(a[:2], b[:2])
    hi = np.minimum(a[:2] + a[2:4], b[:2] + b[2:4])
    area = float(np.prod(np.maximum(hi - lo, 0)))
    return area / max(float(a[2] * a[3] + b[2] * b[3]) - area, 1)


class Tracker:
    """位置による短期追跡。個人の顔を照合・登録する処理は行わない。"""
    def __init__(self, seed=None, ttl=1.2):
        self.rng = random.Random(seed)
        self.ttl = ttl
        self.tracks = {}
        self.next_id = 1
        self.fixed_outfit = None

    def shuffle(self):
        self.fixed_outfit = None
        for track in self.tracks.values():
            track.outfit = costume(self.rng)

    def choose(self, outfit):
        self.fixed_outfit = outfit
        for track in self.tracks.values():
            track.outfit = outfit

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
                track = Track(self.next_id, face.copy(), self.fixed_outfit or costume(self.rng), now)
                self.tracks[track.number] = track
                self.next_id += 1
                visible.append(track)
        # 見失った顔の位置には描かない。再検出用の記録だけ一定時間残す。
        return visible


def make_sprites():
    sprites = {}
    white, red, green = (245, 250, 255, 255), (45, 45, 220, 255), (55, 135, 30, 255)
    for name in ('santa', 'antlers', 'star', 'gift', 'cross', 'red', 'carrot', 'beard', 'wreath'):
        s = np.zeros((600, 400, 4), np.uint8)
        def poly(points, color):
            cv2.fillPoly(s, [np.array(points, np.int32)], color, cv2.LINE_AA)
        def circle(center, radius, color):
            cv2.circle(s, center, radius, color, -1, cv2.LINE_AA)
        def line(points, color, width):
            cv2.polylines(s, [np.array(points, np.int32)], False, color, width, cv2.LINE_AA)
        if name == 'santa':
            poly([(88, 239), (125, 133), (207, 85), (294, 160), (318, 176), (270, 174), (216, 135), (247, 239)], red)
            cv2.ellipse(s, (191, 239), (107, 22), 0, 0, 360, white, -1, cv2.LINE_AA)
            circle((309, 172), 24, white)
        elif name == 'antlers':
            for side in (-1, 1):
                def p(x, y):
                    return (200 + side * x, y)
                brown = (65, 105, 155, 255)
                line([p(70, 245), p(105, 190), p(115, 114), p(105, 83)], brown, 17)
                line([p(110, 160), p(150, 136), p(158, 108)], brown, 14)
                line([p(105, 188), p(65, 160), p(58, 132)], brown, 14)
                circle(p(70, 244), 14, red)
        elif name == 'star':
            gold = (60, 215, 255, 255)
            points = [(200 + math.sin(i * math.pi / 5) * (55 if i % 2 == 0 else 24),
                       156 - math.cos(i * math.pi / 5) * (55 if i % 2 == 0 else 24)) for i in range(10)]
            poly(points, gold)
            # 白い中心と明るい縁は常に残す。周囲の光だけをアニメーション。
            cv2.polylines(s, [np.array(points, np.int32)], True, (145, 245, 255, 255), 3, cv2.LINE_AA)
            circle((191, 143), 5, (245, 255, 255, 255))
        elif name == 'gift':
            cv2.rectangle(s, (120, 144), (280, 234), red, -1)
            cv2.rectangle(s, (111, 133), (289, 155), green, -1)
            cv2.rectangle(s, (187, 134), (213, 234), (40, 220, 255, 255), -1)
            for x, angle in ((173, -25), (227, 25)):
                cv2.ellipse(s, (x, 117), (30, 15), angle, 0, 360, (40, 220, 255, 255), 8, cv2.LINE_AA)
        elif name == 'cross':
            # 縦棒の下側を長くした金色のラテン十字。頭上に浮かぶ飾り。
            cross = [(188, 90), (212, 90), (212, 128), (250, 128),
                     (250, 152), (212, 152), (212, 218), (188, 218),
                     (188, 152), (150, 152), (150, 128), (188, 128)]
            poly(cross, (45, 175, 230, 255))
            cv2.polylines(s, [np.array(cross, np.int32)], True, (115, 225, 255, 255), 3, cv2.LINE_AA)
            line([(197, 98), (197, 208)], (210, 250, 255, 255), 3)
            line([(158, 137), (241, 137)], (210, 250, 255, 255), 3)
        elif name == 'red':
            circle((200, 350), 25, (35, 35, 245, 255))
            circle((192, 342), 7, (200, 210, 255, 255))
        elif name == 'carrot':
            poly([(184, 332), (184, 367), (273, 355)], (15, 135, 255, 255))
            line([(210, 339), (207, 351)], (10, 90, 200, 255), 3)
            line([(229, 346), (226, 357)], (10, 90, 200, 255), 3)
        elif name == 'beard':
            poly([(99, 373), (127, 448), (170, 495), (200, 515), (235, 487), (277, 439), (300, 373),
                  (254, 390), (230, 414), (170, 414), (147, 389)], white)
            for x in (130, 153, 247, 270):
                circle((x, 399), 23, white)
            # 口の中央は透明のままにする。
        elif name == 'wreath':
            for i in range(30):
                a = i * 2 * math.pi / 30
                x, y = int(200 + 150 * math.cos(a)), int(351 + 157 * math.sin(a))
                circle((x, y), 25, green if i % 2 else (45, 105, 25, 255))
                if i % 3 == 0:
                    circle((x, y), 8, red)
            poly([(200, 492), (149, 469), (149, 520)], red)
            poly([(200, 492), (251, 469), (251, 520)], red)
            circle((200, 492), 13, (45, 185, 255, 255))
        sprites[name] = s
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
        radius = 45 + 8 * math.sin(phase)
        glow = np.exp(-distance / (2 * radius ** 2)) * (75 + 20 * math.sin(phase))
        image = np.zeros_like(base)
        image[:, :, :3] = (85, 210, 255)
        image[:, :, 3] = glow.astype(np.uint8)
        alpha = base[:, :, 3:4].astype(np.float32) / 255
        old_alpha = image[:, :, 3:4].astype(np.float32) / 255
        result_alpha = alpha + old_alpha * (1 - alpha)
        color = (base[:, :, :3] * alpha + image[:, :, :3] * old_alpha * (1 - alpha)) / np.maximum(result_alpha, 1e-6)
        image[:, :, :3] = np.clip(color, 0, 255).astype(np.uint8)
        image[:, :, 3] = (result_alpha[:, :, 0] * 255).astype(np.uint8)
        for i, (x, y) in enumerate(((117, 135), (277, 105), (277, 201), (134, 215))):
            intensity = max(0., math.sin(phase + i * 1.6)) ** 3
            if intensity < .03:
                continue
            length = 5 + 15 * intensity
            vertices = np.array([(x, y-length), (x+2, y-2), (x+length*.6, y),
                                 (x+2, y+2), (x, y+length), (x-2, y+2),
                                 (x-length*.6, y), (x-2, y-2)], np.int32)
            cv2.fillPoly(image, [vertices], (245, 255, 255, int(255 * intensity)), cv2.LINE_AA)
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


def demo(sprites):
    frame = np.full((900, 1440, 3), (46, 30, 25), np.uint8)
    outfits = [('santa', 'none', 'beard'), ('antlers', 'red', 'none'), ('gift', 'carrot', 'none'),
               ('star', 'none', 'wreath'), ('cross', 'none', 'none'), ('antlers', 'red', 'beard')]
    tracks = []
    for i, outfit in enumerate(outfits):
        x, y = 250 + (i % 3) * 470, 270 + (i // 3) * 420
        cv2.ellipse(frame, (x, y), (75, 94), 0, 0, 360, (175, 215, 245), -1, cv2.LINE_AA)
        for eye_x in (x - 27, x + 27):
            cv2.circle(frame, (eye_x, y - 22), 7, (40, 40, 40), -1, cv2.LINE_AA)
        cv2.ellipse(frame, (x, y + 25), (25, 16), 0, 0, 180, (40, 40, 40), 3, cv2.LINE_AA)
        face = np.array([x - 75, y - 94, 150, 188, x - 27, y - 22, x + 27, y - 22,
                         x, y, x - 25, y + 25, x + 25, y + 25, .99], np.float32)
        tracks.append(Track(i, face, outfit, 0))
    Snow(seed=42, count=160).draw(frame, 0, 0)
    render(frame, tracks, sprites, 0)
    cv2.putText(frame, 'CHRISTMAS MAGIC CAMERA', (420, 45), cv2.FONT_HERSHEY_SIMPLEX, 1, (220, 245, 255), 2, cv2.LINE_AA)
    save(frame, 'christmas_preview')


def save(frame, prefix='christmas'):
    folder = ROOT / 'outputs'
    folder.mkdir(exist_ok=True)
    path = folder / f'{prefix}_{datetime.now():%Y%m%d_%H%M%S_%f}.png'
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f'画像を保存できませんでした: {path}')
    print(f'保存しました: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=0, help='カメラ番号（既定: 0）')
    parser.add_argument('--detect-width', type=int, default=960, help='検出用画像の最大幅（既定: 960）')
    parser.add_argument('--threshold', type=float, default=.75, help='顔検出のしきい値（既定: 0.75）')
    parser.add_argument('--fullscreen', action='store_true')
    parser.add_argument('--head-offset', type=float, default=0., help='頭の飾りの上下位置（顔幅に対する比率、正で下）')
    parser.add_argument('--control-file', type=Path, help='任意のローカルJSONから素材・頭の上下位置を変更')
    parser.add_argument('--preview-file', type=Path, help='確認用の投影画像を0.5秒ごとにローカル保存（任意）')
    parser.add_argument('--demo', action='store_true', help='カメラを使わず素材一覧画像を保存')
    args = parser.parse_args()
    if not math.isfinite(args.head_offset) or not -.5 <= args.head_offset <= .5:
        parser.error('--head-offset は -0.5〜0.5 です')
    if args.preview_file and args.preview_file.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
        parser.error('--preview-file は .jpg / .jpeg / .png を指定してください')
    if args.detect_width < 160 or not 0 < args.threshold <= 1:
        parser.error('--detect-width は160以上、--threshold は0より大きく1以下です')
    sprites = make_sprites()
    if args.demo:
        demo(sprites)
        return
    if not MODEL.is_file():
        raise RuntimeError(f'顔検出モデルがありません: {MODEL}')
    detector = cv2.FaceDetectorYN.create(str(MODEL), '', (320, 320), args.threshold, .3, 5000)
    cap = cv2.VideoCapture(args.camera)
    tracker, snow = Tracker(), Snow()
    fullscreen, hud, guides = args.fullscreen, True, False
    head_offset, last_preview = args.head_offset, 0.
    control_stamp, last_control = None, 0.
    try:
        if not cap.isOpened():
            raise RuntimeError('カメラを開けません。macOSのカメラ権限と --camera 番号を確認してください。')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, 1280, 720)
        if fullscreen:
            cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        last = time.monotonic()
        fps = 0.
        print('SPACE/R: シャッフル | 1-6: 素材確認 | ↑↓: 頭の飾り位置 | D: 位置ガイド | S: 保存 | F: 全画面 | H: 説明 | Q/ESC: 終了', flush=True)
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError('カメラ映像を取得できません。接続や他アプリのカメラ使用を確認してください。')
            frame = cv2.flip(frame, 1)
            now = time.monotonic()
            dt, last = now - last, now
            fps = .9 * fps + .1 / max(dt, .001)
            scale = min(1., args.detect_width / frame.shape[1])
            small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
            detector.setInputSize((small.shape[1], small.shape[0]))
            _, faces = detector.detect(small)
            if faces is None:
                faces = np.empty((0, 15), np.float32)
            else:
                faces[:, :14] /= scale
            if args.control_file and now - last_control >= .5:
                last_control = now
                try:
                    stamp = args.control_file.stat().st_mtime_ns
                    if stamp != control_stamp:
                        control_stamp = stamp
                        controls = json.loads(args.control_file.read_text())
                        look = controls.get('look', 0)
                        offset = controls.get('head_offset', head_offset)
                        if type(look) is not int or not 0 <= look <= len(LOOKS):
                            raise ValueError('look は0〜6の整数です')
                        if not isinstance(offset, (int, float)) or not math.isfinite(offset) or not -.5 <= offset <= .5:
                            raise ValueError('head_offset は -0.5〜0.5 です')
                        if look == 0:
                            tracker.shuffle()
                        else:
                            tracker.choose(LOOKS[look-1])
                        head_offset = float(offset)
                        print(f'確認設定: look={look}, head_offset={head_offset:+.3f}', flush=True)
                except FileNotFoundError:
                    pass
                except (OSError, ValueError, AttributeError) as error:
                    print(f'確認設定を読み込めません: {error}', flush=True)
            visible = tracker.update(faces, now)
            snow.draw(frame, dt, now)
            render(frame, visible, sprites, now, head_offset)
            # 写真には操作説明を含めない。
            display = frame.copy() if hud or guides else frame
            if guides:
                for track in visible:
                    points = track.face[4:14].reshape(5, 2).astype(int)
                    for x, y in points:
                        cv2.circle(display, (int(x), int(y)), 3, (70, 255, 150), -1, cv2.LINE_AA)
                    x, y, w, h = track.face[:4].astype(int)
                    cv2.rectangle(display, (x, y), (x+w, y+h), (70, 255, 150), 1)
            if hud:
                # 頭上の星や帽子を隠さないよう、操作説明は画面下に置く。
                bottom = display.shape[0]
                cv2.rectangle(display, (0, bottom-58), (display.shape[1], bottom), (30, 28, 24), -1)
                for text, y in ((f'CHRISTMAS MAGIC | Faces: {len(visible)} | {fps:.0f} FPS | Head offset: {head_offset:+.2f}', bottom-35),
                                ('SPACE: Shuffle  1-6: Looks  Up/Down: Fit  D: Guides  S: Photo  F: Fullscreen  H: Help  Q: Quit', bottom-11)):
                    cv2.putText(display, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX, .5, (235, 245, 255), 1, cv2.LINE_AA)
            if args.preview_file and now - last_preview >= .5:
                args.preview_file.parent.mkdir(parents=True, exist_ok=True)
                temporary = args.preview_file.with_name(args.preview_file.stem + '.tmp' + args.preview_file.suffix)
                if not cv2.imwrite(str(temporary), display):
                    raise RuntimeError(f'確認画像を保存できませんでした: {temporary}')
                temporary.replace(args.preview_file)
                last_preview = now
            cv2.imshow(WINDOW, display)
            key = cv2.waitKeyEx(1)
            if key in (27, ord('q'), ord('Q')):
                break
            if key in (32, ord('r'), ord('R')):
                tracker.shuffle()
            elif ord('1') <= key <= ord('6'):
                tracker.choose(LOOKS[key - ord('1')])
            elif key in (0xF700, 2490368, 65362):
                head_offset = max(-.5, head_offset - .025)
            elif key in (0xF701, 2621440, 65364):
                head_offset = min(.5, head_offset + .025)
            elif key in (ord('d'), ord('D')):
                guides = not guides
            elif key in (ord('s'), ord('S')):
                save(frame)
            elif key in (ord('h'), ord('H')):
                hud = not hud
            elif key in (ord('f'), ord('F')):
                fullscreen = not fullscreen
                cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (RuntimeError, cv2.error) as error:
        raise SystemExit(f'エラー: {error}')
