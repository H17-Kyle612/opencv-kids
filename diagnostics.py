"""明示的に有効にした確認表示とローカル出力。"""
from dataclasses import dataclass
import json
import cv2
from graphics import text


@dataclass
class FrameTiming:
    fps: float = 0.
    camera_fps: float = 0.
    capture_ms: float = 0.
    face_ms: float = 0.
    mouth_ms: float = 0.
    render_ms: float = 0.
    display_ms: float = 0.


def draw_points(frame, points, color, radius):
    for x, y in points.astype(int):
        cv2.circle(frame, (int(x), int(y)), radius, color, -1, cv2.LINE_AA)


def draw_landmarks(frame, tracks, landmarks):
    for track in tracks:
        draw_points(frame, track.face[4:14].reshape(5, 2), (70, 255, 150), 3)
    for points in landmarks.values():
        draw_points(frame, points[:48], (245, 215, 90), 2)
        draw_points(frame, points[48:68], (30, 255, 90), 2)


def draw_guides(frame, tracks, mouth_points, ratios, face_guides=False, labels=True, face_widths=False):
    if face_guides:
        for track in tracks:
            draw_points(frame, track.face[4:14].reshape(5, 2), (70, 255, 150), 3)
            x, y, w, h = track.face[:4].astype(int)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (70, 255, 150), 1)
            if face_widths:
                text(frame, f'{track.face[2]:.0f}px', (x+w/2, y+h+12), .42, (70, 255, 150))
    for track_id, points in mouth_points.items():
        draw_points(frame, points[60:68], (30, 255, 90), 2)
        x, y = points[54]
        if labels:
            text(frame, f'{ratios.get(track_id, 0):.3f}', (x+35, y), .4, (30, 255, 90))


def write_preview(path, frame, tracks, race, fps, ratios):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem+'.tmp'+path.suffix)
    if not cv2.imwrite(str(temporary), frame):
        raise RuntimeError(f'確認画像を保存できませんでした: {temporary}')
    temporary.replace(path)
    info = {'faces': len(tracks), 'fps': round(fps, 1), 'state': race.state,
            'bites': [p.hits for p in race.players], 'time': round(race.elapsed, 2),
            'ratios': {str(k): round(v, 3) for k, v in ratios.items()}}
    path.with_suffix('.json').write_text(json.dumps(info))
