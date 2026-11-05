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
        self.context_sequence = 0
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
            self.context_sequence += 1
            self.current = {'sequence':self.context_sequence, 'at':timestamp(), 'context':context}

    def sending(self, packet, params):
        now = time.monotonic()
        with self.lock:
            self.sequence += 1
            entry = {'sequence':self.sequence, 'captured_at':packet['at'], 'sent_at':timestamp(),
                     'queue_ms':round((now-packet['monotonic'])*1000, 1),
                     'context':packet['context'], 'request':{'method':'thread/realtime/appendText', 'params':params},
                     'status':'送信中', 'transport':'app_server'}
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
            if kind in ('audio_waiting', 'audio_stalled', 'audio_playing', 'speech_gap',
                        'audio_track_muted', 'audio_track_unmuted', 'audio_track_ended', 'audio_context'):
                self.audio.append({'received_at':timestamp(), 'browser_at':event.get('at'), 'type':kind, 'gap_ms':event.get('gap_ms'), 'state':event.get('state')})
            if kind in ('speech_started', 'speech_ended'):
                self.audio.append({'received_at':timestamp(), 'browser_at':event.get('at'),
                                   'type':event['type'], 'gap_ms':event.get('gap_ms')})
                self.speaking = event['type'] == 'speech_started'
                if not self.speaking:
                    self.last_end = time.monotonic()
                    self.reaction_at = None
            if isinstance(event.get('metrics'), dict):
                self.browser.update(event['metrics'])

    def can_react(self):
        with self.lock:
            now = time.monotonic()
            return (not self.speaking and now-self.last_end >= .25 and
                    (self.reaction_at is None or now-self.reaction_at >= 6.))

    def should_send(self, context):
        return self.can_react() and (bool(context.get('react')) or context['state'] in ('waiting', 'ready', 'countdown', 'paused'))

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
