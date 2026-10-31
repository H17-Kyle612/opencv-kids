"""ブラウザで編集した実況設定をローカルに保存する。"""
import json
from pathlib import Path
import threading

ROOT = Path(__file__).resolve().parent
DEFAULT_PROMPT = (ROOT/'commentary_prompt.txt').read_text()
DEFAULT_VOICE = 'cove'


class CommentarySettings:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else ROOT/'.commentary-settings.json'
        self.lock = threading.Lock()
        self.value = {'prompt':DEFAULT_PROMPT, 'voice':DEFAULT_VOICE, 'revision':0}
        if self.path.is_file():
            value = json.loads(self.path.read_text())
            self.validate(value['prompt'], value['voice'])
            self.value = {'prompt':value['prompt'], 'voice':value['voice'], 'revision':int(value.get('revision', 0))}

    @staticmethod
    def validate(prompt, voice, voices=None):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
            raise ValueError('プロンプトは1〜12000文字で入力してください')
        if not isinstance(voice, str) or not voice or (voices is not None and voice not in voices):
            raise ValueError('App Serverの候補から声を選んでください')

    def snapshot(self):
        with self.lock:
            return dict(self.value)

    def save(self, prompt, voice, voices):
        self.validate(prompt, voice, voices)
        with self.lock:
            value = {'prompt':prompt, 'voice':voice, 'revision':self.value['revision']+1}
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
            temporary.replace(self.path)
            self.value = value
            return dict(value)
