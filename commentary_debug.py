"""実況の送信内容と時刻を、メモリ内の有限履歴で確認する。"""
from collections import deque
from datetime import datetime, timezone
import threading
import time


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class CommentaryDebug:
    def __init__(self):
        self.lock = threading.Lock()
        self.sent = deque(maxlen=30)
        self.audio = deque(maxlen=20)
        self.current = None
        self.sequence = 0
        self.browser = {}
        self.reaction_at = None
        self.speaking = False
        self.last_end = -float('inf')

    def observe(self, context):
        with self.lock:
            self.current = {'at':timestamp(), 'context':context}

    def sending(self, packet, params):
        now = time.monotonic()
        with self.lock:
            self.sequence += 1
            entry = {'sequence':self.sequence, 'captured_at':packet['at'], 'sent_at':timestamp(),
                     'queue_ms':round((now-packet['monotonic'])*1000, 1),
                     'context':packet['context'], 'request':{'method':'thread/realtime/appendText', 'params':params},
                     'status':'送信中'}
            self.sent.append(entry)
            if packet['context'].get('react'):
                self.reaction_at = now
        return entry, now

    def acknowledge(self, entry, started, error=None):
        with self.lock:
            entry['ack_ms'] = round((time.monotonic()-started)*1000, 1)
            entry['status'] = str(error) if error else 'App Server受付済み'

    def playback(self, event):
        with self.lock:
            kind = event.get('type')
            if kind in ('audio_waiting', 'audio_stalled', 'audio_playing'):
                self.audio.append({'received_at':timestamp(), 'browser_at':event.get('at'), 'type':kind})
            if kind in ('speech_started', 'speech_ended'):
                self.audio.append({'received_at':timestamp(), 'browser_at':event.get('at'),
                                   'type':event['type']})
                self.speaking = event['type'] == 'speech_started'
                if not self.speaking:
                    self.last_end = time.monotonic()
                    self.reaction_at = None
            if isinstance(event.get('metrics'), dict):
                self.browser = event['metrics']

    def can_react(self):
        with self.lock:
            now = time.monotonic()
            return (not self.speaking and now-self.last_end >= .25 and
                    (self.reaction_at is None or now-self.reaction_at >= 6.))

    def should_send(self, context):
        with self.lock:
            # 待機・一時停止の明示的な停止は優先する。実況中の説明は追加しない。
            if context['state'] in ('waiting', 'ready', 'countdown', 'paused'):
                return True
            if self.speaking:
                return False
            return (context.get('react') or self.reaction_at is None or
                    time.monotonic()-self.reaction_at >= 6.)

    def reset_voice(self):
        with self.lock:
            self.speaking = False
            self.reaction_at = None
            self.last_end = -float('inf')
            self.browser = {}

    def snapshot(self):
        with self.lock:
            return {'current':self.current, 'sent':[dict(e) for e in self.sent],
                    'audio':list(self.audio), 'browser':dict(self.browser),
                    'speaking':self.speaking, 'awaiting_audio':self.reaction_at is not None and not self.speaking}
