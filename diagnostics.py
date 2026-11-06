"""明示的に有効にした確認表示とローカル出力。"""
import json
import csv
import cv2
from graphics import text, panel
from cake_game import MAX_SENSITIVITY


def draw_guides(frame, tracks, mouth_points, ratios, face_guides=False, labels=True):
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


def draw_debug(frame, race, ratios, errors, fps, camera_fps, face_ms, mouth_ms, detect_width, capture_ms=0., render_ms=0., display_ms=0.):
    h, w = frame.shape[:2]
    unit = min(w/1280, h/720)
    fmt = lambda value: '---' if value is None else f'{value:.3f}'
    states = {'waiting':'待機', 'ready':'準備', 'countdown':'開始前', 'playing':'競技中', 'paused':'一時停止', 'result':'終了'}
    rows = ['詳細デバッグ　@：表示切替',
            f'進行 {states[race.state]}　開度判定',
            f'感度 {race.sensitivity}/{MAX_SENSITIVITY}　+ / -：調整',
            f'処理 {fps:.1f} FPS　撮影 {camera_fps:.1f} FPS',
            f'顔 {face_ms:.1f} ms　口 {mouth_ms:.1f} ms　検出幅 {detect_width}',
            f'取得 {capture_ms:.1f} ms　描画 {render_ms:.1f} ms　表示 {display_ms:.1f} ms']
    for i, player in enumerate(race.players):
        mouth = player.mouth
        close, opening = mouth.targets
        rows.extend([f'プレイヤー{i+1}　{mouth.phase}　{player.hits}口',
                     f'開度 {fmt(ratios.get(player.track_id))}',
                     f'開くライン {fmt(opening)}　戻るライン {fmt(close)}'])
        if player.track_id in errors:
            rows.append('口未検出：'+errors[player.track_id])
    height = min(h-90*unit, (len(rows)*27+20)*unit)
    panel(frame, (12*unit, 85*unit, 650*unit, 85*unit+height), opacity=.94)
    for i, row in enumerate(rows):
        text(frame, row, (330*unit, (103+i*27)*unit), .43*unit,
             (100,225,255) if i==0 else (245,245,245))


class MouthTrace:
    """計測時だけ有効にする、画像を含まないフレームごとの記録。"""
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open('w', newline='')
        fields = ('at','state','elapsed','player','hits','raw','phase',
                  'opening','closing','fps','camera_fps','capture_ms','face_ms','mouth_ms','render_ms','display_ms')
        self.writer = csv.DictWriter(self.file, fieldnames=fields)
        self.writer.writeheader()
        self.last_flush = 0.

    def write(self, race, ratios, now, fps, camera_fps, capture_ms, face_ms, mouth_ms, render_ms, display_ms):
        for player in race.players or [None]:
            row = dict(at=now,state=race.state,elapsed=race.elapsed,fps=fps,camera_fps=camera_fps,
                       capture_ms=capture_ms,face_ms=face_ms,mouth_ms=mouth_ms,render_ms=render_ms,display_ms=display_ms)
            if player is not None:
                mouth = player.mouth
                close, opening = mouth.targets
                row.update(player=player.track_id,hits=player.hits,raw=ratios.get(player.track_id),
                           phase=mouth.phase,opening=opening,closing=close)
            self.writer.writerow(row)
        if now-self.last_flush>=.5:
            self.file.flush()
            self.last_flush=now

    def close(self):
        self.file.close()
