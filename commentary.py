"""ゲーム状況をCodex App Serverへ渡し、WebRTCでGPT-Liveの声を再生する。"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import queue
import secrets
import time
import threading
import webbrowser
from codex_client import CodexClient, REQUESTED_MODEL
from commentary_settings import CommentarySettings, DEFAULT_PROMPT, DEFAULT_VOICE
from commentary_context import MatchStory, leaders
from commentary_debug import CommentaryDebug, timestamp

ROOT = Path(__file__).resolve().parent


def latest(target, value):
    try:
        older = target.get_nowait()
        old, new = older['context'], value['context']
        if old.get('react') and (old['match'], old['state']) == (new['match'], new['state']):
            new['react'] = True
            if old.get('priority') == 'urgent' and old.get('leaders') == new.get('leaders'):
                new['priority'] = 'urgent'
    except queue.Empty:
        pass
    target.put_nowait(value)



class Commentator:
    def __init__(self):
        self.settings = CommentarySettings()
        self.active_settings = None
        self.voices = []
        self.refresh_context = threading.Event()
        self.story = MatchStory()
        self.debug = CommentaryDebug()
        self.last_transcript_at = 0.
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
                elif path == 'context-events':
                    self.send_response(200)
                    self.send_header('Content-Type','text/event-stream; charset=utf-8')
                    self.send_header('Cache-Control','no-store')
                    self.end_headers()
                    sequence = 0
                    try:
                        while not owner.stopped.is_set():
                            packet = owner.debug.context_after(sequence)
                            if packet and packet['sequence'] != sequence:
                                sequence = packet['sequence']
                                wire = 'data: '+json.dumps(packet, ensure_ascii=False)+'\n\n'
                            else:
                                wire = ': keepalive\n\n'
                            self.wfile.write(wire.encode())
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                elif path == 'state':
                    self.respond({'transcript':owner.transcript, 'error':owner.error,
                                  'debug':owner.debug.snapshot(), 'active_settings':owner.active_settings})
                elif path == 'prompt':
                    self.respond({'requested_model':REQUESTED_MODEL, 'actual_model':None, 'saved':owner.settings.snapshot(),
                                  'active':owner.active_settings, 'default_prompt':DEFAULT_PROMPT,
                                  'default_voice':DEFAULT_VOICE})
                elif path == 'voices':
                    reply = queue.Queue(maxsize=1)
                    try:
                        owner.commands.put_nowait(('voices', None, reply))
                        result = reply.get(timeout=30)
                        self.respond(result, 500 if 'error' in result else 200)
                    except (queue.Empty, queue.Full):
                        self.respond({'error':'声の一覧を取得できませんでした'}, 503)
                elif path == 'context.js':
                    self.respond((ROOT/'voice_context.js').read_bytes(), content_type='text/javascript; charset=utf-8')
                elif path == 'player.js':
                    self.respond((ROOT/'voice_player.js').read_bytes(), content_type='text/javascript; charset=utf-8')
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
                    if not isinstance(body, dict):
                        raise ValueError('設定の形式が不正です')
                    if action == 'settings':
                        value = owner.settings.save(body.get('prompt'), body.get('voice'), owner.voices)
                        return self.respond({'saved':value})
                    if action == 'playback':
                        owner.debug.playback(body)
                        return self.respond({})
                    if action == 'ready':
                        owner.refresh_context.set()
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
                if action == 'voices':
                    try:
                        if client is None:
                            client = CodexClient(on_process=lambda p: setattr(self, 'server_process', p))
                        catalog = client.rpc('thread/realtime/listVoices', {})
                        self.voices = catalog.get('voices', {}).get('v3', [])
                        if not self.voices:
                            raise RuntimeError('App ServerからGPT-Liveの声の候補が返されませんでした')
                        reply.put({'voices':self.voices})
                    except Exception as error:
                        reply.put({'error':str(error)})
                    action = None
                if action:
                    self.ready.clear()
                    if client and (self.active_settings is not None or action == 'stop'):
                        client.close()
                        client = None
                    self.error = ''
                    self.transcript = ''
                    self.debug.reset_voice()
                    self.active_settings = None
                    if action == 'stop':
                        self.status = '開始待ち'
                        reply.put({})
                    else:
                        try:
                            self.status = '接続中'
                            if client is None:
                                client = CodexClient(on_process=lambda p: setattr(self, 'server_process', p))
                            chosen = self.settings.snapshot()
                            self.settings.validate(chosen['prompt'], chosen['voice'], self.voices or None)
                            current = self.debug.snapshot()['current']
                            answer = client.start_voice(offer, prompt=chosen['prompt'], voice=chosen['voice'],
                                                        initial_context=current['context'] if current else None)
                            self.active_settings = chosen
                            self.status = '音声接続待ち'
                            reply.put({'sdp':answer})
                            print('AI実況: Codex App Server / GPT-Live（実モデル名未取得） / WebRTC / ChatGPTログイン', flush=True)
                        except Exception as error:
                            self._failure(error)
                            reply.put({'error':self.error})
                            if client:
                                client.close()
                                client = None
                if client:
                    try:
                        control = self.previous_state in ('waiting', 'ready', 'countdown', 'paused')
                        # 発話中は合図を差し込まない。背景は独立したWebRTC経路で更新する。
                        if self.ready.is_set() and (control or self.debug.can_react()):
                            try:
                                context = self.pending.get_nowait()
                            except queue.Empty:
                                context = None
                            if context:
                                # キューに滞留した途中経過は読み上げず、次の最新更新を待つ。
                                if ((time.monotonic()-context['monotonic'] < 1. or context['context']['state'] != 'playing')
                                        and self.debug.should_send(context['context'])):
                                    params = client.context_params(client.thread_id, context['context'])
                                    entry, started = self.debug.sending(context, params)
                                    try:
                                        client.append_context(context['context'])
                                    except Exception as error:
                                        self.debug.acknowledge(entry, started, error)
                                        raise
                                    self.debug.acknowledge(entry, started)
                        message = client.events.popleft() if client.events else client._read(.05)
                        if message:
                            method, data = message.get('method'), message.get('params', {})
                            if method == 'thread/realtime/transcript/delta' and data.get('role') == 'assistant':
                                moment = time.monotonic()
                                if moment-self.last_transcript_at > 1.:
                                    self.transcript = ''
                                self.transcript = (self.transcript+data.get('delta', ''))[-200:]
                                self.last_transcript_at = moment
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
        # 評価は送信時だけ行い、反応フラグを未送信のフレームで消費しない。
        if self.refresh_context.is_set():
            self.refresh_context.clear()
            self.previous_state = None
            self.story.announced = None
            self.story.last_reaction = -float('inf')
        state = race.state if active else 'waiting'
        changed = state != self.previous_state
        result_pending = state == 'result' and (self.story.announced is None or self.story.announced['state'] != 'result')
        current_leaders = leaders([p.hits for p in race.players]) if state == 'playing' else []
        reversal = (len(current_leaders) == 1 and self.story.decisive_leader is not None
                    and current_leaders[0] != self.story.decisive_leader)
        if changed or reversal or ((state == 'playing' or result_pending) and now-self.last_request >= .5):
            context, _ = self.story.observe(race, now, active, allow_reaction=self.debug.can_react())
            self.debug.observe(context)
            latest(self.pending, {'context':context.copy(), 'monotonic':time.monotonic(), 'at':timestamp()})
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
