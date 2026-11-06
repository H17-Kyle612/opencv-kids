"""クリスマスカメラの起動、入力、処理順の制御。"""
import argparse
from contextlib import ExitStack
from datetime import datetime
import math
from pathlib import Path
import time

import cv2

from cake_chomp.diagnostics import MouthTrace, draw_debug
from cake_chomp.game import CakeGame
from cake_chomp.rules import DEFAULT_SENSITIVITY, MAX_SENSITIVITY, MIN_FACE_WIDTH
from camera import open_camera
from costume.scene import CostumeScene
from diagnostics import FrameTiming, draw_guides, draw_landmarks, write_preview
from tracking import Tracker
from vision import FaceDetector

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / 'models' / 'face_detection_yunet_2023mar.onnx'
WINDOW = 'クリスマス ぱくぱく対戦'
DEBUG_OFF, DEBUG_DETAILS, DEBUG_LANDMARKS = range(3)


def save(frame):
    folder = ROOT / 'outputs'
    folder.mkdir(exist_ok=True)
    path = folder / f'christmas_{datetime.now():%Y%m%d_%H%M%S_%f}.png'
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f'画像を保存できませんでした: {path}')
    print(f'保存しました: {path}')


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=0, help='カメラ番号（既定: 0）')
    parser.add_argument('--camera-fps', type=int, default=30, help='カメラへ要求するFPS（対応範囲内で設定、既定: 30）')
    parser.add_argument('--detect-width', type=int, default=640, help='顔検出の最大幅（既定: 640、0で入力を縮小しない）')
    parser.add_argument('--threshold', type=float, default=.75, help='顔検出のしきい値（既定: 0.75）')
    parser.add_argument('--fullscreen', action=argparse.BooleanOptionalAction, default=True, help='全画面で起動（既定）。--no-fullscreenでウィンドウ表示')
    parser.add_argument('--no-sound', action='store_true', help='効果音を再生しない')
    parser.add_argument('--commentary', action='store_true', help='Codex App ServerによるAI音声実況を有効にする')
    parser.add_argument('--players', type=int, choices=(1, 2), default=2, help='1: 1人チャレンジ、2: 2人対戦（既定）')
    parser.add_argument('--mirror-only', action='store_true', help='ゲームを自動開始しない')
    parser.add_argument('--min-face', type=int, default=160, help='ゲーム開始に必要な顔幅（既定: 160px、起動後は [ / ] で調整）')
    parser.add_argument('--time-limit', type=float, default=30., help='制限時間（秒、既定: 30）')
    parser.add_argument('--mouth-sensitivity', type=int, choices=range(1, MAX_SENSITIVITY+1), default=DEFAULT_SENSITIVITY, help=f'口の感度（1〜{MAX_SENSITIVITY}、大きいほど小さな開閉で反応。既定: {DEFAULT_SENSITIVITY}）')
    parser.add_argument('--mouth-debug', action='store_true', help='口の特徴点と開き具合を表示')
    parser.add_argument('--head-offset', type=float, default=0., help='頭の飾りの上下位置（顔幅に対する比率、正で下）')
    parser.add_argument('--mouth-trace', type=Path, help='計測用の開度と処理時間をCSVに記録')
    parser.add_argument('--preview-file', type=Path, help='確認用の投影画像を0.5秒ごとにローカル保存（任意）')
    args = parser.parse_args()
    if not math.isfinite(args.head_offset) or not -.5 <= args.head_offset <= .5:
        parser.error('--head-offset は -0.5〜0.5 です')
    if args.preview_file and args.preview_file.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
        parser.error('--preview-file は .jpg / .jpeg / .png を指定してください')
    if (args.detect_width != 0 and args.detect_width < 160) or not 0 < args.threshold <= 1:
        parser.error('--detect-width は0または160以上、--threshold は0より大きく1以下です')
    if not 1 <= args.camera_fps <= 240:
        parser.error('--camera-fps は1〜240です')
    if args.min_face < MIN_FACE_WIDTH or not math.isfinite(args.time_limit) or args.time_limit <= 0:
        parser.error(f'--min-face>={MIN_FACE_WIDTH}、--time-limit>0 を指定してください')
    return args


def set_fullscreen(enabled):
    mode = cv2.WINDOW_FULLSCREEN if enabled else cv2.WINDOW_NORMAL
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, mode)


def main():
    args = parse_args()
    if not MODEL.is_file():
        raise RuntimeError(f'顔検出モデルがありません: {MODEL}')
    detector = FaceDetector(MODEL, args.detect_width, args.threshold)
    tracker = Tracker()
    costume = CostumeScene(args.head_offset)
    fullscreen, guides, debug = args.fullscreen, False, DEBUG_OFF
    timing = FrameTiming()
    last_preview = 0.

    with ExitStack() as resources:
        game = CakeGame(args.min_face, args.time_limit, args.players, args.mouth_sensitivity,
                        enabled=not args.mirror_only, sound=not args.no_sound)
        resources.callback(game.close)
        commentator = None
        if args.commentary:
            from commentary import Commentator
            commentator = Commentator()
            resources.callback(commentator.close)
        camera = resources.enter_context(open_camera(args.camera, args.camera_fps))
        trace = MouthTrace(args.mouth_trace) if args.mouth_trace else None
        if trace:
            resources.callback(trace.close)
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        resources.callback(cv2.destroyAllWindows)
        cv2.resizeWindow(WINDOW, 1280, 720)
        if fullscreen:
            set_fullscreen(True)
        last = time.monotonic()
        print('M: 1人／2人切替 | G: ゲーム切替 | R: 再試合 | SPACE: シャッフル | 1-6: 素材確認 | +/-: 口の感度 | ↑↓: 頭の飾り位置 | @: 詳細・ランドマーク切替 | [ / ]: 開始の顔幅 | D: 位置ガイド | S: 保存 | F: 全画面 | H: 説明 | Q/ESC: 終了', flush=True)
        while True:
            started = time.perf_counter()
            ok, frame = camera.read()
            timing.capture_ms = (time.perf_counter() - started) * 1000
            timing.camera_fps = camera.fps
            if not ok or frame is None:
                raise RuntimeError('カメラ映像を取得できません。接続や他アプリのカメラ使用を確認してください。')
            frame = cv2.flip(frame, 1)
            now = time.monotonic()
            dt, last = now - last, now
            timing.fps = .9 * timing.fps + .1 / max(dt, .001)

            started = time.perf_counter()
            tracker.ttl = game.tracking_ttl
            visible = tracker.update(detector.detect(frame), now)
            timing.face_ms = (time.perf_counter() - started) * 1000
            costume.update(tracker.tracks.keys())
            ratios, timing.mouth_ms = game.update(frame, visible, now, inspect=debug != DEBUG_OFF)
            if commentator:
                commentator.update(game.race, now, active=game.enabled)
            started = time.perf_counter()
            display = frame
            if debug == DEBUG_LANDMARKS:
                draw_landmarks(frame, visible, game.mouth.points)
            else:
                costume.draw(frame, visible, now, dt=dt, winner_id=game.winner_id)
                game.draw(frame, now)
                details = debug == DEBUG_DETAILS
                if details or guides or args.mouth_debug or (costume.show_help and not game.enabled):
                    display = frame.copy()
                points = game.mouth.points if details or args.mouth_debug else {}
                draw_guides(display, visible, points, ratios, guides or details,
                            labels=not details, face_widths=details)
                if details:
                    draw_debug(display, game.race, ratios, game.mouth.errors, timing, args.detect_width)
                if not game.enabled:
                    costume.draw_help(display, len(visible), timing.fps)
            timing.render_ms = (time.perf_counter() - started) * 1000
            if args.preview_file and now - last_preview >= .5:
                write_preview(args.preview_file, display, visible, game.race, timing.fps, ratios)
                last_preview = now

            started = time.perf_counter()
            cv2.imshow(WINDOW, display)
            key = cv2.waitKeyEx(1)
            timing.display_ms = (time.perf_counter() - started) * 1000
            if trace:
                trace.write(game.race, ratios, now, timing)
            if key in (27, ord('q'), ord('Q')) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key < 0:
                continue
            costume.handle_key(key)
            game.handle_key(key, frame.shape[1])
            if key in (ord('@'), ord('＠')):
                debug = (debug + 1) % 3
            elif key in (ord('d'), ord('D')):
                guides = not guides
            elif key in (ord('s'), ord('S')):
                save(frame)
            elif key in (ord('f'), ord('F')):
                fullscreen = not fullscreen
                set_fullscreen(fullscreen)
