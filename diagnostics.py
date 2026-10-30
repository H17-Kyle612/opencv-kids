"""明示的に有効にした確認表示とローカル出力。"""
import json
import cv2
from graphics import text


def draw_guides(frame, tracks, mouth_points, ratios, face_guides=False):
    if face_guides:
        for track in tracks:
            for x, y in track.face[4:14].reshape(5, 2).astype(int):
                cv2.circle(frame, (int(x), int(y)), 3, (70, 255, 150), -1, cv2.LINE_AA)
            x, y, w, h = track.face[:4].astype(int)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (70, 255, 150), 1)
    for track_id, points in mouth_points.items():
        for x, y in points[60:68].astype(int):
            cv2.circle(frame, (int(x), int(y)), 2, (30, 255, 90), -1, cv2.LINE_AA)
        x, y = points[54]
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
