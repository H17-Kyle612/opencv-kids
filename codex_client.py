"""Codex App Serverのstdio接続。実況専用の一時スレッドを使用する。"""
from collections import deque
import json
import os
import select
import shutil
import subprocess
import tempfile
import time

from commentary_settings import DEFAULT_PROMPT

PROMPT = DEFAULT_PROMPT
# 音声モデルを上書きせず、App Serverの有効な設定・既定値に従う。
REQUESTED_MODEL = None


VOICE_RULES = """Voice delivery: fastest clear Japanese sports-announcer pace, rapid connected articulation, no pauses between clauses, and one short call per update.
観客全体に向けて、日本語の試合実況だけを発話する。このルールは下の演出設定より優先する。選手はプレイヤー番号で呼び、観客に話しかけたり会話調の「〜ね」「〜よ」で締めたりしない。
受領確認、挨拶、前置き、質問、待機の宣言、操作案内、舞台裏の説明は一切発話しない。モデル名、システム、バックエンド、ツール、処理、入力、指示、データの受信・更新・取得には触れない。「続報を待ちます」「確認します」「データでは」のような言葉も禁止。実況できる事実がなければ無言で終える。
最初の試合の事実が届くまで無言。試合状況が届くたびに、それを合図として即座に声を出す。playingは今の見せ場を一声、開始なら「さあ、スタート！」。resultは確定した勝敗か1人の達成だけを一声で叫ぶ。理由や振り返りは加えない。
一息で1〜2秒、15文字程度の短い一声だけ。第一声から、聞き取れる限界の超早口。子音をはっきりつないで、節と節の間をほとんど空けず、語尾まで同じ速度で言い切る。数字の列挙や二文目は省く。
close_race=trueは両者が得点して差が2口以内の接戦。まず接戦を大きな声で叫ぶ。たとえば「接戦だーーーっ！」「並んだ並んだ！まだ伸びる！」。声を跳ね上げ、山場の一語だけ伸ばして、残りは一気に畳みかける。並んだ・逆転したと言うのは実際にそうなった時だけ。例文を毎回繰り返さない。
Backchannel policy: 相づち・聞き返し・受領確認は発話しない。
Interruption policy: 一息の実況を最後まで言い切る。
Delegation policy:
Backend tools: なし。
Generate <|SpawnThinking|> when: 該当なし。
Do not generate <|SpawnThinking|> when: 常に。"""


def session_prompt(style):
    return f'{VOICE_RULES}\n\n演出設定（上の発話ルールの範囲内で適用）\n{style.strip()}'


class CodexClient:
    def __init__(self, on_process=None):
        executable = shutil.which('codex')
        if not executable:
            raise RuntimeError('Codex CLIがありません。実況にはcodex app-serverが必要です。')
        self.folder = tempfile.TemporaryDirectory(prefix='cake-commentary-')
        self.process = subprocess.Popen([executable, 'app-server', '--stdio'], cwd=self.folder.name,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, bufsize=0)
        if on_process:
            on_process(self.process)
        os.set_blocking(self.process.stdout.fileno(), False)
        self.buffer = b''
        self.wire = deque()
        self.events = deque()
        self.sequence = 0
        self.thread_id = None
        try:
            self.rpc('initialize', {'clientInfo': {'name':'cake_chomp_commentary', 'title':'ケーキぱくぱく実況', 'version':'0.1.0'},
                                    'capabilities': {'experimentalApi': True}})
            self.send({'method':'initialized'})
            # 音声モデルはrealtime/startで指定する。通常のCodexモデルでturnは実行しない。
            account = self.rpc('account/read', {'refreshToken': False}).get('account')
            if not account or account.get('type') != 'chatgpt':
                raise RuntimeError('ChatGPTログインが必要です。codex login を実行してください。')
            result = self.rpc('thread/start', {'ephemeral': True, 'cwd':self.folder.name,
                                               'approvalPolicy':'never', 'sandbox':'read-only',
                                               'baseInstructions':PROMPT})
            self.thread_id = result['thread']['id']
        except Exception:
            self.close()
            raise

    def send(self, message):
        self.process.stdin.write((json.dumps(message, ensure_ascii=False)+'\n').encode())
        self.process.stdin.flush()

    def _read(self, timeout):
        deadline = time.monotonic()+timeout
        while not self.wire:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                return None
            if not select.select([self.process.stdout], [], [], remaining)[0]:
                return None
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError('Codex App Serverとの接続が終了しました')
            self.buffer += chunk
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                if line.strip():
                    self.wire.append(json.loads(line))
        return self.wire.popleft()

    def rpc(self, method, params, timeout=20.):
        self.sequence += 1
        number = self.sequence
        self.send({'id':number, 'method':method, 'params':params})
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            message = self._read(max(.01, deadline-time.monotonic()))
            if message is None:
                break
            if message.get('id') == number and 'method' not in message:
                if 'error' in message:
                    raise RuntimeError(f"{method}: {message['error'].get('message', message['error'])}")
                return message['result']
            self.events.append(message)
        raise TimeoutError(f'Codex {method} が時間内に応答しませんでした')

    def start_voice(self, offer, prompt=None, voice='cove'):
        initial = '最初のゲーム状況JSONが届くまで無言。待機について口に出さない。'
        self.rpc('thread/realtime/start', {
            'threadId': self.thread_id, 'outputModality': 'audio',
            'version': 'v3', 'voice': voice,
            'transport': {'type': 'webrtc', 'sdp': offer},
            'includeStartupContext': False, 'clientManagedHandoffs': True,
            'backendReasoningStatus': False, 'delegationAckFiller': False,
            'flushTranscriptTailOnSessionEnd': False,
            'prompt': session_prompt(PROMPT if prompt is None else prompt),
            'initialItems': [{'role':'developer', 'text':initial}],
        })
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            message = self.events.popleft() if self.events else self._read(.1)
            if not message:
                continue
            method, params = message.get('method'), message.get('params', {})
            if method == 'thread/realtime/error':
                raise RuntimeError(params.get('message', '音声接続エラー'))
            if method == 'thread/realtime/sdp':
                return params['sdp']
        raise TimeoutError('GPT-Liveの音声接続が時間内に完了しませんでした')

    @staticmethod
    def context_params(thread_id, context):
        control_fields = {'match', 'event_id', 'priority', 'react'}
        facts = {key: value for key, value in context.items() if key not in control_fields}
        bites = facts['bites']
        if facts['state'] == 'playing' and facts['mode'] == 'versus' and len(bites) == 2:
            facts['close_race'] = min(bites) > 0 and abs(bites[0] - bites[1]) <= 2
        return {'threadId':thread_id, 'role':'user',
                'text':json.dumps(facts, ensure_ascii=False, separators=(',', ':'))}

    def append_context(self, context):
        params = self.context_params(self.thread_id, context)
        self.rpc('thread/realtime/appendText', params, timeout=5)
        return params

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()
        self.folder.cleanup()
