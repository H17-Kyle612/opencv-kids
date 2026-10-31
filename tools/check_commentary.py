"""カメラなしでCodex App Server経由の音声実況を確認する。"""
import argparse
from pathlib import Path
import sys
import time
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from commentary import Commentator

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--players', type=int, choices=(1, 2), default=2)
parser.add_argument('--hold', action='store_true', help='結果のあともデバッグ画面を開いておく')
args = parser.parse_args()
voice = Commentator()
race = SimpleNamespace(state='waiting', player_count=args.players, time_limit=30., elapsed=0., bites_per_cake=4,
                       players=[SimpleNamespace(track_id=i+1, hits=0) for i in range(args.players)], winners=[])
try:
    print('ブラウザで「実況を開始」を押すと、架空の30秒ゲームを実況します。', flush=True)
    while not voice.ready.wait(.1):
        if voice.error:
            raise RuntimeError(voice.error)
    start = time.monotonic()
    while args.hold or time.monotonic()-start < 38:
        now = time.monotonic()
        race.elapsed = min(30., now-start)
        race.state = 'playing' if race.elapsed < 30 else 'result'
        t = race.elapsed
        race.players[0].hits = int(min(t,8)*1.2+min(max(t-8,0),8)*.8+max(t-16,0)*2.6)
        if args.players == 2:
            race.players[1].hits = int(min(t,8)*.8+min(max(t-8,0),8)*2.+max(t-16,0)*1.7)
        best = max(p.hits for p in race.players)
        race.winners = [i for i,p in enumerate(race.players) if p.hits == best] if args.players == 2 and race.state == 'result' else []
        voice.update(race, now)
        time.sleep(.05)
    print('実況テスト完了', flush=True)
except KeyboardInterrupt:
    pass
finally:
    voice.close()
