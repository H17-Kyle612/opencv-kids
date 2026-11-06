"""口の推定から採点、ゲーム表示、効果音までを接続する。"""
from pathlib import Path
import time

from .audio import SoundEffects
from .mouth import MouthEstimator
from .rules import MAX_SENSITIVITY, MIN_FACE_WIDTH, CakeRace
from .visuals import GameVisuals

MODEL = Path(__file__).resolve().parents[1] / 'models' / 'lbfmodel.yaml'


class CakeGame:
    def __init__(self, min_face, time_limit, player_count, sensitivity, *, enabled=True, sound=True):
        if not MODEL.is_file():
            raise RuntimeError('口検出モデルがありません。python setup_models.py を実行してください。')
        self.race = CakeRace(min_face, time_limit, player_count, sensitivity)
        self.mouth = MouthEstimator(MODEL)
        self.visuals = GameVisuals()
        self.sounds = SoundEffects(enabled=sound)
        self.enabled = enabled
        self.last_state = None

    @property
    def tracking_ttl(self):
        return 12. if self.enabled and self.race.state in ('countdown', 'playing', 'paused', 'result') else 1.2

    @property
    def winner_id(self):
        return self.race.winner_track_id if self.enabled else None

    def update(self, frame, tracks, now, *, inspect=False):
        width = frame.shape[1]
        players = self.race.mouth_targets(tracks, width) if self.enabled else []
        targets = players
        if inspect and not targets:
            targets = sorted(tracks, key=lambda track: track.face[2], reverse=True)[:self.race.player_count]
        started = time.perf_counter()
        ratios = self.mouth.estimate(frame, targets)
        mouth_ms = (time.perf_counter() - started) * 1000
        if self.enabled:
            self.race.update(tracks, ratios if players else {}, width, now)
            if self.race.state != self.last_state or self.race.events:
                print(f'GAME {self.race.state} | bites={[p.hits for p in self.race.players]} | time={self.race.elapsed:.2f}', flush=True)
                self.last_state = self.race.state
        self.sounds.update(self.race, now, active=self.enabled)
        return ratios, mouth_ms

    def draw(self, frame, now):
        if self.enabled:
            self.visuals.draw(frame, self.race, now)

    def handle_key(self, key, width):
        race = self.race
        if key in (ord('r'), ord('R')):
            race.reset()
        elif key in (ord('g'), ord('G')):
            self.enabled = not self.enabled
            race.reset()
        elif key in (ord('m'), ord('M')):
            race.set_player_count(2 if race.player_count == 1 else 1)
            self.enabled = True
        elif key in (ord('+'), ord('='), ord('-')):
            step = -1 if key == ord('-') else 1
            level = max(1, min(MAX_SENSITIVITY, race.sensitivity + step))
            if level != race.sensitivity:
                race.set_sensitivity(level)
                print(f'口の感度: {level}/{MAX_SENSITIVITY}', flush=True)
        elif key in (ord('['), ord(']')):
            step = -10 if key == ord('[') else 10
            race.min_face = max(MIN_FACE_WIDTH, min(width, race.min_face + step))
            print(f'ゲーム開始の顔幅: {race.min_face}px', flush=True)

    def close(self):
        self.sounds.close()
