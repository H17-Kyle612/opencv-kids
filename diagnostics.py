"""明示的に有効にした確認表示とローカル出力。"""
import json
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


def draw_debug(frame, race, ratios, errors, fps, camera_fps, face_ms, mouth_ms, detect_width):
    h, w = frame.shape[:2]
    unit = min(w/1280, h/720)
    fmt = lambda value: '---' if value is None else f'{value:.3f}'
    states = {'waiting':'待機', 'ready':'準備', 'countdown':'開始前', 'playing':'競技中', 'paused':'一時停止', 'result':'終了'}
    mode = '振幅判定・中央値3' if race.sensitivity>=6 else '基準判定'
    rows = ['詳細デバッグ　@：表示切替',
            f'進行 {states[race.state]}　方式 {mode}',
            f'感度 {race.sensitivity}/{MAX_SENSITIVITY}　+ / -：調整',
            f'処理 {fps:.1f} FPS　カメラ設定 {camera_fps:.1f} FPS',
            f'顔 {face_ms:.1f} ms　口 {mouth_ms:.1f} ms　検出幅 {detect_width}',
            '基準は準備中に校正　R：再準備']
    for i, player in enumerate(race.players):
        mouth = player.mouth
        close, opening = mouth.targets
        rows.extend([f'プレイヤー{i+1}　{mouth.phase}　{player.hits}口',
                     f'開度 {fmt(ratios.get(player.track_id))}　平滑値 {fmt(mouth.filtered_ratio)}',
                     f'基準 {fmt(mouth.baseline)}　準備時の揺れ {fmt(mouth.noise_span)}',
                     f'開くライン {fmt(opening)}　戻るライン {fmt(close)}'])
        if mouth.sensitivity>=6:
            rows.append(f'必要振幅 {fmt(mouth.movement)}　揺れ下限 {fmt(max(.012,mouth.noise_span*2))}')
        if player.track_id in errors:
            rows.append('口未検出：'+errors[player.track_id])
    height = min(h-90*unit, (len(rows)*27+20)*unit)
    panel(frame, (12*unit, 85*unit, 650*unit, 85*unit+height), opacity=.94)
    for i, row in enumerate(rows):
        text(frame, row, (330*unit, (103+i*27)*unit), .43*unit,
             (100,225,255) if i==0 else (245,245,245))
