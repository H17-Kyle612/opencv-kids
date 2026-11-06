"""ゲームの開度・タイミングのデバッグ表示とCSV出力。"""
import csv

from graphics import text, panel
from .rules import MAX_SENSITIVITY


def draw_debug(frame, race, ratios, errors, timing, detect_width):
    h, w = frame.shape[:2]
    unit = min(w/1280, h/720)
    fmt = lambda value: '---' if value is None else f'{value:.3f}'
    states = {'waiting':'待機', 'ready':'準備', 'countdown':'開始前', 'playing':'競技中', 'paused':'一時停止', 'result':'終了'}
    rows = ['詳細デバッグ　@：表示切替',
            f'進行 {states[race.state]}　開度判定',
            f'開始の顔幅 {race.min_face}px　[ / ]：調整',
            f'感度 {race.sensitivity}/{MAX_SENSITIVITY}　+ / -：調整',
            f'処理 {timing.fps:.1f} FPS　撮影 {timing.camera_fps:.1f} FPS',
            f'顔 {timing.face_ms:.1f} ms　口 {timing.mouth_ms:.1f} ms　検出幅 {detect_width}',
            f'取得 {timing.capture_ms:.1f} ms　描画 {timing.render_ms:.1f} ms　表示 {timing.display_ms:.1f} ms']
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

    def write(self, race, ratios, now, timing):
        for player in race.players or [None]:
            row = dict(at=now, state=race.state, elapsed=race.elapsed, **vars(timing))
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
