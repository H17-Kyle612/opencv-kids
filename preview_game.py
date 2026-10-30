"""カメラを使わず、ゲーム画面と演出の確認画像・動画を作る。"""
from pathlib import Path
import cv2
import numpy as np
from cake_game import CakeRace, Player
from tracking import Track
from accessories import make_sprites, render
from game_visuals import GameVisuals


def background():
    frame = np.full((720, 1280, 3), (46, 30, 25), np.uint8)
    tracks = []
    for i, x in enumerate((320, 960)):
        y = 270
        cv2.ellipse(frame, (x, y), (76, 95), 0, 0, 360, (175, 215, 245), -1, cv2.LINE_AA)
        for ex in (x-27, x+27):
            cv2.circle(frame, (ex, y-22), 7, (40, 40, 40), -1, cv2.LINE_AA)
        cv2.ellipse(frame, (x, y+25), (25, 16), 0, 0, 180, (40, 40, 40), 3, cv2.LINE_AA)
        face = np.array([x-76, y-95, 152, 190, x-27, y-22, x+27, y-22,
                         x, y, x-25, y+25, x+25, y+25, .99], np.float32)
        tracks.append(Track(i+1, face, ('star' if i == 0 else 'santa', 'none', 'none'), 0))
    return frame, tracks


def main():
    folder = Path(__file__).resolve().parent / 'outputs'
    folder.mkdir(exist_ok=True)
    visuals, sprites = GameVisuals(), make_sprites()
    race = CakeRace()
    race.players = [Player(1, hits=5), Player(2, hits=7)]
    snapshots = []
    for state in ('countdown', 'playing', 'result'):
        frame, tracks = background()
        race.state = state
        race.countdown_since = 0.
        race.elapsed = race.time_limit if state == 'result' else (0. if state == 'countdown' else 12.6)
        race.winners = [0]
        race.reason = '時間終了！'
        if state == 'result':
            race.players[0].hits = 19
        render(frame, tracks, sprites, 1.2)
        visuals.draw(frame, race, tracks, {1:.025, 2:.3}, 1.2)
        path = folder / f'game_{state}.png'
        cv2.imwrite(str(path), frame)
        snapshots.append(cv2.resize(frame, (640, 360)))
        print(path)
    cv2.imwrite(str(folder/'game_preview.png'), np.concatenate(snapshots, axis=0))
    writer = cv2.VideoWriter(str(folder/'cake_chomp_demo.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), 24, (1280, 720))
    if not writer.isOpened():
        raise RuntimeError('確認動画を作成できませんでした')
    race.reset()
    race.state = 'playing'
    race.players = [Player(1), Player(2)]
    visuals = GameVisuals()
    try:
        for i in range(144):
            now = i/24
            frame, tracks = background()
            race.elapsed = now
            race.events = []
            if i in (12, 28, 44, 60, 78, 96, 114, 130):
                player = race.players[0]
                player.hits += 1
                player.last_bite = now
                race.events.append(0)
            if i in (20, 50, 85, 120):
                race.players[1].hits += 1
                race.players[1].last_bite = now
                race.events.append(1)
            render(frame, tracks, sprites, now)
            visuals.draw(frame, race, tracks, {1:.2, 2:.1}, now)
            writer.write(frame)
    finally:
        writer.release()
    print(folder/'cake_chomp_demo.mp4')


if __name__ == '__main__':
    main()
