"""ゲーム状況をCodex App Serverへ渡し、WebRTCでGPT-Liveの声を再生する。"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import queue
import secrets
import threading
import webbrowser
from codex_client import CodexClient

ROOT = Path(__file__).resolve().parent


def latest(target, value):
    try:
        target.get_nowait()
    except queue.Empty:
        pass
    target.put_nowait(value)


def game_context(race, active=True):
    return {'state': race.state if active else 'waiting',
            'remaining_seconds': round(max(0, race.time_limit-race.elapsed), 1),
            'bites': [p.hits for p in race.players],
            'cakes': [p.hits/race.bites_per_cake for p in race.players],
            'winners': [i+1 for i in race.winners] if active and race.state == 'result' else []}


class Commentator:
    def __init__(self):
        self.pending = queue.Queue(maxsize=1)
        self.commands = queue.Queue(maxsize=2)
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.status = '開始待ち'
        self.error = ''
        self.transcript = ''
        self.server_process = None
        self.previous_state = None
        self.last_request = -float('inf')
        self.prefix = '/'+secrets.token_urlsafe(24)+'/'
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), self._handler())
        self.url = f'http://127.0.0.1:{self.http.server_port}{self.prefix}'
        self.http_thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.worker = threading.Thread(target=self._run, daemon=True, name='cake-gpt-live')
        self.http_thread.start()
        self.worker.start()
        print(f'GPT-Live実況：ブラウザで「実況を開始」を押してください\n{self.url}', flush=True)
        webbrowser.open(self.url)

    def _handler(self):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, value, code=200, content_type='application/json'):
                payload = json.dumps(value, ensure_ascii=False).encode() if content_type == 'application/json' else value
                self.send_response(code)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(payload)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(payload)

            def allowed(self):
                host = f'127.0.0.1:{owner.http.server_port}'
                origin = self.headers.get('Origin')
                return (self.headers.get('Host') == host and self.path.startswith(owner.prefix)
                        and (origin is None or origin == 'http://'+host))

            def do_GET(self):
                if not self.allowed():
                    return self.respond({'error':'アクセスできません'}, 403)
                path = self.path[len(owner.prefix):]
                if path == '':
                    self.respond((ROOT/'voice_player.html').read_bytes(), content_type='text/html; charset=utf-8')
                elif path == 'font.ttf':
                    self.respond((ROOT/'assets/fonts/BIZUDPGothic-Bold.ttf').read_bytes(), content_type='font/ttf')
                elif path == 'state':
                    self.respond({'transcript':owner.transcript, 'error':owner.error})
                else:
                    self.respond({'error':'ページがありません'}, 404)

            def do_POST(self):
                if not self.allowed() or self.headers.get_content_type() != 'application/json':
                    return self.respond({'error':'アクセスできません'}, 403)
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 65536:
                        raise ValueError('リクエストのサイズが不正です')
                    body = json.loads(self.rfile.read(length))
                    action = self.path[len(owner.prefix):]
                    if action == 'ready':
                        owner.ready.set()
                        owner.status = '準備完了'
                        return self.respond({})
                    if action == 'stop':
                        owner.ready.clear()
                    elif action != 'connect':
                        return self.respond({'error':'操作がありません'}, 404)
                    reply = queue.Queue(maxsize=1)
                    owner.commands.put_nowait((action, body.get('sdp'), reply))
                    result = reply.get(timeout=45)
                    self.respond(result, 500 if 'error' in result else 200)
                except (ValueError, queue.Empty, queue.Full) as error:
                    self.respond({'error':str(error) or '接続が混雑しています'}, 400)
        return Handler

    def _run(self):
        client = None
        try:
            while not self.stopped.is_set():
                try:
                    action, offer, reply = self.commands.get_nowait()
                except queue.Empty:
                    action = None
                if action:
                    self.ready.clear()
                    if client:
                        client.close()
                        client = None
                    self.error = ''
                    self.transcript = ''
                    if action == 'stop':
                        self.status = '開始待ち'
                        reply.put({})
                    else:
                        try:
                            self.status = '接続中'
                            client = CodexClient(on_process=lambda p: setattr(self, 'server_process', p))
                            answer = client.start_voice(offer)
                            self.status = '音声接続待ち'
                            reply.put({'sdp':answer})
                            print('AI実況: Codex App Server / GPT-Live 1 / WebRTC / ChatGPTログイン', flush=True)
                        except Exception as error:
                            self._failure(error)
                            reply.put({'error':self.error})
                            if client:
                                client.close()
                                client = None
                if client:
                    try:
                        if self.ready.is_set():
                            try:
                                context = self.pending.get_nowait()
                            except queue.Empty:
                                context = None
                            if context:
                                client.append_context(context)
                        message = client.events.popleft() if client.events else client._read(.05)
                        if message:
                            method, data = message.get('method'), message.get('params', {})
                            if method == 'thread/realtime/transcript/delta' and data.get('role') == 'assistant':
                                self.transcript = (self.transcript+data.get('delta', ''))[-200:]
                            elif method == 'thread/realtime/transcript/done' and data.get('role') == 'assistant':
                                self.transcript = data.get('text', '')[-300:]
                                print(f'GPT-Live実況: {self.transcript}', flush=True)
                            elif method == 'thread/realtime/error':
                                raise RuntimeError(data.get('message', '音声接続エラー'))
                            elif method == 'thread/realtime/closed':
                                raise RuntimeError('音声接続が終了しました。ブラウザで実況を開始してください。')
                    except Exception as error:
                        if not self.stopped.is_set():
                            self._failure(error)
                        client.close()
                        client = None
                else:
                    self.stopped.wait(.05)
        finally:
            if client:
                client.close()

    def _failure(self, error):
        self.ready.clear()
        self.status = '接続エラー'
        self.error = str(error)
        print(f'AI実況: {error}', flush=True)

    def update(self, race, now, active=True):
        state = race.state if active else 'waiting'
        changed = state != self.previous_state
        if changed or (state == 'playing' and now-self.last_request >= 2.5):
            latest(self.pending, game_context(race, active))
            self.last_request = now
        self.previous_state = state

    def close(self):
        self.stopped.set()
        self.ready.clear()
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
        self.worker.join(timeout=3)
        self.http.shutdown()
        self.http.server_close()
        self.http_thread.join(timeout=1)
