"""クリスマスカメラの起動、入力、処理順の制御。"""
import argparse
from datetime import datetime
import math
from pathlib import Path
import time
import cv2
from accessories import make_sprites, render, Snow
from tracking import Tracker, LOOKS
from vision import FaceDetector, MouthEstimator
from cake_game import CakeRace
from game_visuals import GameVisuals
from graphics import text
from diagnostics import draw_guides, write_preview
from audio import SoundEffects

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / 'models' / 'face_detection_yunet_2023mar.onnx'
WINDOW = 'クリスマス ぱくぱく対戦'

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
    parser.add_argument('--detect-width', type=int, default=960, help='顔検出の最大幅（既定: 960、0で入力を縮小しない）')
    parser.add_argument('--threshold', type=float, default=.75, help='顔検出のしきい値（既定: 0.75）')
    parser.add_argument('--fullscreen', action='store_true')
    parser.add_argument('--no-sound', action='store_true', help='効果音を再生しない')
    parser.add_argument('--commentary', action='store_true', help='Codex App ServerによるAI音声実況を有効にする')
    parser.add_argument('--players', type=int, choices=(1, 2), default=2, help='1: 1人チャレンジ、2: 2人対戦（既定）')
    parser.add_argument('--mirror-only', action='store_true', help='ゲームを自動開始しない')
    parser.add_argument('--min-face', type=int, default=160, help='ゲーム開始に必要な顔幅（既定: 160px）')
    parser.add_argument('--time-limit', type=float, default=30., help='制限時間（秒、既定: 30）')
    parser.add_argument('--mouth-sensitivity', type=int, choices=range(1, 6), default=4, help='口の感度（1〜5、大きいほど小さな開閉で反応。既定: 4）')
    parser.add_argument('--mouth-debug', action='store_true', help='口の特徴点と開き具合を表示')
    parser.add_argument('--head-offset', type=float, default=0., help='頭の飾りの上下位置（顔幅に対する比率、正で下）')
    parser.add_argument('--preview-file', type=Path, help='確認用の投影画像を0.5秒ごとにローカル保存（任意）')
    args = parser.parse_args()
    if not math.isfinite(args.head_offset) or not -.5 <= args.head_offset <= .5:
        parser.error('--head-offset は -0.5〜0.5 です')
    if args.preview_file and args.preview_file.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
        parser.error('--preview-file は .jpg / .jpeg / .png を指定してください')
    if (args.detect_width != 0 and args.detect_width < 160) or not 0 < args.threshold <= 1:
        parser.error('--detect-width は0または160以上、--threshold は0より大きく1以下です')
    if args.min_face < 40 or not math.isfinite(args.time_limit) or args.time_limit <= 0:
        parser.error('--min-face>=40、--time-limit>0 を指定してください')
    sprites = make_sprites()
    if not MODEL.is_file():
        raise RuntimeError(f'顔検出モデルがありません: {MODEL}')
    detector = FaceDetector(MODEL, args.detect_width, args.threshold)
    lbf = ROOT / 'models' / 'lbfmodel.yaml'
    if not lbf.is_file():
        raise RuntimeError('口検出モデルがありません。python setup_models.py を実行してください。')
    estimator = MouthEstimator(lbf)
    race = CakeRace(min_face=args.min_face, time_limit=args.time_limit, player_count=args.players, sensitivity=args.mouth_sensitivity)
    visuals = GameVisuals()
    sounds = SoundEffects(enabled=not args.no_sound)
    commentator = None
    if args.commentary:
        from commentary import Commentator
        commentator = Commentator()
    game_enabled = not args.mirror_only
    last_game_state = None
    cap = cv2.VideoCapture(args.camera)
    tracker, snow = Tracker(), Snow()
    fullscreen, hud, guides = args.fullscreen, True, False
    head_offset, last_preview = args.head_offset, 0.
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
        print('M: 1人／2人切替 | G: ゲーム切替 | R: 再試合 | SPACE: シャッフル | 1-6: 素材確認 | +/-: 口の感度 | ↑↓: 頭の飾り位置 | D: 位置ガイド | S: 保存 | F: 全画面 | H: 説明 | Q/ESC: 終了', flush=True)
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError('カメラ映像を取得できません。接続や他アプリのカメラ使用を確認してください。')
            frame = cv2.flip(frame, 1)
            now = time.monotonic()
            dt, last = now - last, now
            fps = .9 * fps + .1 / max(dt, .001)
            faces = detector.detect(frame)
            tracker.ttl = 12. if game_enabled and race.state in ('countdown', 'playing', 'paused', 'result') else 1.2
            visible = tracker.update(faces, now)
            ratios = {}
            if game_enabled:
                mouth_tracks = race.mouth_targets(visible, frame.shape[1])
                ratios = estimator.estimate(frame, mouth_tracks)
                race.update(visible, ratios, frame.shape[1], now)
                if race.state != last_game_state or race.events:
                    print(f'GAME {race.state} | bites={[p.hits for p in race.players]} | time={race.elapsed:.2f}', flush=True)
                    last_game_state = race.state
            sounds.update(race, now, active=game_enabled)
            if commentator:
                commentator.update(race, now, active=game_enabled)
            snow.draw(frame, dt, now)
            render(frame, visible, sprites, now, head_offset)
            visuals.draw(frame, race, visible, ratios, now, game_enabled)
            if commentator:
                text(frame, f'AI実況：{commentator.status}', (frame.shape[1]/2, 91), .4)
            display = frame.copy() if guides or args.mouth_debug or (hud and not game_enabled) else frame
            draw_guides(display, visible, estimator.points if args.mouth_debug and game_enabled else {}, ratios, guides)
            if hud and not game_enabled:
                # 頭上の星や帽子を隠さないよう、操作説明は画面下に置く。
                bottom = display.shape[0]
                cv2.rectangle(display, (0, bottom-58), (display.shape[1], bottom), (30, 28, 24), -1)
                text(display, f'クリスマス変身！  {len(visible)}人  毎秒{fps:.0f}コマ  飾り位置 {head_offset:+.2f}',
                     (display.shape[1]/2, bottom-37), .55)
                text(display, '空白：変身  1〜6：素材  ↑↓：位置  G：対戦  S：写真  F：全画面  Q：終了',
                     (display.shape[1]/2, bottom-13), .43)
            if args.preview_file and now - last_preview >= .5:
                write_preview(args.preview_file, display, visible, race, fps, ratios)
                last_preview = now
            cv2.imshow(WINDOW, display)
            key = cv2.waitKeyEx(1)
            if key in (27, ord('q'), ord('Q')):
                break
            if key == 32:
                tracker.shuffle()
            elif key in (ord('r'), ord('R')):
                tracker.shuffle()
                race.reset()
            elif key in (ord('g'), ord('G')):
                game_enabled = not game_enabled
                race.reset()
            elif key in (ord('m'), ord('M')):
                race.set_player_count(2 if race.player_count == 1 else 1)
                game_enabled = True
            elif key in (ord('+'), ord('='), ord('-')):
                level = max(1, min(5, race.sensitivity + (-1 if key == ord('-') else 1)))
                if level != race.sensitivity:
                    race.set_sensitivity(level)
                    print(f'口の感度: {level}/5', flush=True)
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
        sounds.close()
        if commentator:
            commentator.close()
        cv2.destroyAllWindows()

