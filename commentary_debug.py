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
        self.context_changed = threading.Condition(self.lock)
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
        with self.context_changed:
            self.context_sequence += 1
            self.current = {'sequence':self.context_sequence, 'at':timestamp(), 'context':context}
            self.context_changed.notify_all()

    def context_after(self, sequence, timeout=1.):
        with self.context_changed:
            self.context_changed.wait_for(lambda: self.context_sequence != sequence, timeout)
            return self.current

    def background_sent(self, report):
        # ブラウザで実際に送った背景情報を、音声指示とは別の経路として記録する。
        if not isinstance(report, dict) or not isinstance(report.get('payload'), dict):
            return
        payload = report['payload']
        if payload.get('type') != 'session.context.append' or payload.get('channel') != 'commentary':
            return
        try:
            context = report['context']
            captured = report['captured_at']
            sent = report['sent_at']
            delay = max(0., (datetime.fromisoformat(sent)-datetime.fromisoformat(captured)).total_seconds()*1000)
        except (KeyError, TypeError, ValueError):
            return
        with self.lock:
            self.sequence += 1
            self.sent.append({'sequence':self.sequence, 'captured_at':captured, 'sent_at':sent,
                              'queue_ms':round(delay, 1), 'context':context, 'transport':'webrtc_background',
                              'request':{'method':'session.context.append','params':payload},
                              'status':'WebRTC送信済み（個別の受理対応は未確認）'})

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
        reports = event.get('background_sent', [])
        if isinstance(reports, list):
            for report in reports[-8:]:
                self.background_sent(report)
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
                self.browser.update(event['metrics'])

    def can_react(self):
        with self.lock:
            now = time.monotonic()
            return (not self.speaking and now-self.last_end >= .25 and
                    (self.reaction_at is None or now-self.reaction_at >= 6.))

    def should_send(self, context):
        # 背景はWebRTCで常時更新。RPCでは発話の合図と明示的な停止だけを送る。
        return context['state'] in ('waiting', 'ready', 'countdown', 'paused') or (bool(context.get('react')) and self.can_react())

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
