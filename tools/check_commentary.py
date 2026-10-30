"""カメラなしでCodex App Server経由の音声実況を確認する。"""
from pathlib import Path
import sys
import time
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from commentary import Commentator

voice = Commentator()
race = SimpleNamespace(state='waiting', player_count=2, time_limit=30., elapsed=0., bites_per_cake=4,
                       players=[SimpleNamespace(hits=0), SimpleNamespace(hits=0)], winners=[])
try:
    print('ブラウザで「実況を開始」を押すと、架空の30秒対戦を実況します。', flush=True)
    while not voice.ready.wait(.1):
        if voice.error:
            raise RuntimeError(voice.error)
    start = time.monotonic()
    while time.monotonic()-start < 35:
        now = time.monotonic()
        race.elapsed = min(30., now-start)
        race.state = 'playing' if race.elapsed < 30 else 'result'
        race.players[0].hits = int(race.elapsed*1.7)
        race.players[1].hits = int(race.elapsed*1.9)
        race.winners = [1] if race.state == 'result' else []
        voice.update(race, now)
        time.sleep(.05)
    print('実況テスト完了', flush=True)
finally:
    voice.close()
