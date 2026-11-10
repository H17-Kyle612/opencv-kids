"""Codex App Serverのstdio接続。実況専用の一時スレッドを使用する。"""
from collections import deque
from contextlib import ExitStack
import json
from queue import Empty, SimpleQueue
import shutil
import subprocess
import tempfile
import threading
import time

from commentary_context import finish_phrase
from commentary_settings import DEFAULT_PROMPT, session_prompt

PROMPT = DEFAULT_PROMPT

REQUESTED_MODEL = None


class CodexClient:
    def __init__(self, on_process=None):
        executable = shutil.which('codex.exe') or shutil.which('codex')
        if not executable:
            raise RuntimeError('Codex CLIがありません。実況にはcodex app-serverが必要です。')
        self.folder = tempfile.TemporaryDirectory(prefix='cake-commentary-')
        with ExitStack() as startup:
            startup.callback(self.folder.cleanup)
            self.process = subprocess.Popen([executable, 'app-server', '--stdio'], cwd=self.folder.name,
                                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL)
            self.reader = None
            startup.callback(self._close_process)
            if on_process:
                on_process(self.process)
            self.wire = SimpleQueue()
            self.reader = threading.Thread(target=self._read_stdout, daemon=True, name='codex-stdout')
            self.reader.start()
            self.events = deque()
            self.sequence = 0
            self.thread_id = None
            self.rpc('initialize', {'clientInfo': {'name':'cake_chomp_commentary', 'title':'ケーキぱくぱく実況', 'version':'0.1.0'},
                                    'capabilities': {'experimentalApi': True}})
            self.send({'method':'initialized'})

            account = self.rpc('account/read', {'refreshToken': False}).get('account')
            if not account or account.get('type') != 'chatgpt':
                raise RuntimeError('ChatGPTログインが必要です。codex login を実行してください。')
            result = self.rpc('thread/start', {'ephemeral': True, 'cwd':self.folder.name,
                                               'approvalPolicy':'never', 'sandbox':'read-only',
                                               'baseInstructions':PROMPT})
            self.thread_id = result['thread']['id']
            startup.pop_all()

    def send(self, message):
        self.process.stdin.write((json.dumps(message, ensure_ascii=False)+'\n').encode())
        self.process.stdin.flush()

    def _read_stdout(self):

        try:
            with self.process.stdout as stream:
                for line in stream:
                    if line.strip():
                        self.wire.put(line)
        finally:
            self.wire.put(None)

    def _read(self, timeout):
        try:
            line = self.wire.get(timeout=timeout)
        except Empty:
            return None
        if line is None:
            raise RuntimeError('Codex App Serverとの接続が終了しました')
        return json.loads(line)

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
        initial = '最初の実況の合図が届くまで無言。'
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
        fixed_line = None
        if context['state'] == 'result':
            fixed_line = finish_phrase(context)
        elif context['state'] == 'playing' and {'type': 'start'} in context.get('events', ()):
            fixed_line = 'さあ始まりました！'

        if fixed_line is not None:
            text = f'固定台詞だけを日本語の早口で一字一句そのまま言って、無言で終える。\n「{fixed_line}」'
        else:
            control_fields = {'match', 'event_id', 'priority', 'react'}
            facts = {key: value for key, value in context.items() if key not in control_fields}
            bites = facts['bites']
            if facts['state'] == 'playing' and facts['mode'] == 'versus' and len(bites) == 2:
                facts['close_race'] = min(bites) > 0 and abs(bites[0] - bites[1]) <= 2
            if facts.get('recent_window_seconds', 0) >= 1:
                facts['good_pace_players'] = [
                    i for i, pace in enumerate(facts.get('bites_per_second', ()), 1) if pace >= 1.5
                ]
            cue = ('日本語の超早口で、今の見せ場を10文字前後の叫び一つで実況。'
                   'ケーキは「個」、食べた回数と点差は「口」。言い切ったら止まる。\n')
            text = cue + json.dumps(
                facts, ensure_ascii=False, separators=(',', ':'))
        return {'threadId':thread_id, 'role':'user', 'text':text}

    def append_context(self, params):
        self.rpc('thread/realtime/appendText', params, timeout=5)

    def _close_process(self):
        self.process.stdin.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        if self.reader is None:
            self.process.stdout.close()
        elif self.reader.ident is not None:
            self.reader.join(timeout=1.)
        else:
            self.process.stdout.close()

    def close(self):
        try:
            self._close_process()
        finally:
            self.folder.cleanup()
