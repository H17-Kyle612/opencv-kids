"""OpenCVの画像合成と日本語文字描画の共通処理。"""
import math
import json
from pathlib import Path
from functools import lru_cache
import cv2
import numpy as np

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

def panel(frame, rect, color=(38, 25, 24), opacity=.85):
    x1, y1, x2, y2 = map(int, rect)
    roi = frame[max(0, y1):min(frame.shape[0], y2), max(0, x1):min(frame.shape[1], x2)]
    if roi.size:
        roi[:] = (roi*(1-opacity)+np.array(color)*opacity).astype(np.uint8)



@lru_cache(maxsize=1)
def _font_atlas():
    folder = Path(__file__).resolve().parent / 'assets' / 'fonts'
    atlas = cv2.imread(str(folder/'japanese.png'), cv2.IMREAD_GRAYSCALE)
    if atlas is None:
        raise RuntimeError('日本語フォントの文字画像がありません')
    return atlas, json.loads((folder/'japanese.json').read_text())


@lru_cache(maxsize=512)
def _text_mask(label, pixels):
    atlas, info = _font_atlas()
    scale = pixels/info['size']
    glyphs, pen = [], 0.
    for char in label:
        if char not in info['glyphs']:
            raise RuntimeError(f'文字画像にない文字です: {char}（tools/build_font.py で再作成）')
        glyph = info['glyphs'][char]
        x, y, w, h = glyph['rect']
        left, top = glyph['offset']
        if w and h:
            glyphs.append((atlas[y:y+h, x:x+w], int(math.floor((pen+left)*scale)), int(math.floor(top*scale))))
        pen += glyph['advance']
    if not glyphs:
        return np.zeros((1, max(1, int(pen*scale))), np.uint8)
    left = min(g[1] for g in glyphs)
    top = min(g[2] for g in glyphs)
    width = max(g[1]+max(1, round(g[0].shape[1]*scale)) for g in glyphs)-left
    height = max(g[2]+max(1, round(g[0].shape[0]*scale)) for g in glyphs)-top
    mask = np.zeros((height+4, width+4), np.uint8)
    for image, x, y in glyphs:
        resized = cv2.resize(image, (max(1, round(image.shape[1]*scale)), max(1, round(image.shape[0]*scale))), interpolation=cv2.INTER_AREA)
        x, y = x-left+2, y-top+2
        roi = mask[y:y+resized.shape[0], x:x+resized.shape[1]]
        np.maximum(roi, resized, out=roi)
    return mask


def _tint_mask(frame, mask, x, y, color):
    left, top = max(0, x), max(0, y)
    right, bottom = min(frame.shape[1], x+mask.shape[1]), min(frame.shape[0], y+mask.shape[0])
    if right <= left or bottom <= top:
        return
    alpha = mask[top-y:bottom-y, left-x:right-x, None].astype(np.float32)/255
    target = frame[top:bottom, left:right]
    target[:] = (target*(1-alpha)+np.asarray(color)*alpha).astype(np.uint8)


def text(frame, label, center, size=1., color=(255, 255, 255), thickness=2):
    mask = _text_mask(str(label), max(10, round(size*38)))
    x, y = int(center[0]-mask.shape[1]/2), int(center[1]-mask.shape[0]/2)
    outline = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    _tint_mask(frame, outline, x+1, y+2, (25, 17, 30))
    _tint_mask(frame, mask, x, y, color)
