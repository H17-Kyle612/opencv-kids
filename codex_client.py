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

    def start_voice(self, offer, prompt=None, voice='cove', initial_context=None):
        initial = '最新のゲーム状況が届くまで無言で待つ。すでにplayingやresultなら、その状況から実況する。'
        if initial_context:
            initial += '\n現在のゲーム状況：'+json.dumps(initial_context, ensure_ascii=False)
        self.rpc('thread/realtime/start', {
            'threadId': self.thread_id, 'outputModality': 'audio',
            'version': 'v3', 'voice': voice,
            'transport': {'type': 'webrtc', 'sdp': offer},
            'includeStartupContext': False, 'clientManagedHandoffs': True,
            'flushTranscriptTailOnSessionEnd': False,
            'prompt': PROMPT if prompt is None else prompt,
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
        if context.get('priority') == 'urgent':
            direction = ' 急展開です。音声を強制的に切らず、言いかけを短い区切りで収めて、この最新の展開へ移ってください。'
        elif context.get('react'):
            direction = ' この展開への実況の合図です。' if context['state'] != 'result' else ' 確定結果を締めくくる合図です。'
        else:
            direction = ' 参考データの更新。合図済みの実況は取り消さず内容を最新にし、新しい発話は増やさない。'
            if context['state'] in ('waiting', 'ready', 'countdown', 'paused'):
                direction += ' 今は発話を止めて待ってください。'
        return {'threadId':thread_id, 'role':'developer',
                'text':json.dumps(context, ensure_ascii=False, separators=(',', ':'))+direction}

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
