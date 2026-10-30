from collections import deque
import queue
import unittest
from unittest.mock import Mock
from codex_client import CodexClient
from types import SimpleNamespace
from commentary import Commentator, game_context


def race(state='playing'):
    return SimpleNamespace(state=state, time_limit=30., elapsed=10., bites_per_cake=4,
                           players=[SimpleNamespace(hits=8), SimpleNamespace(hits=9)],
                           winners=[1] if state == 'result' else [])


def commentator():
    voice = Commentator.__new__(Commentator)
    voice.pending = queue.Queue(maxsize=1)
    voice.last_request = 0.
    voice.previous_state = None
    return voice


class CommentaryTests(unittest.TestCase):
    def test_context_contains_only_game_data(self):
        context = game_context(race('result'))
        self.assertEqual(context, {'state':'result','remaining_seconds':20.,
                                  'bites':[8,9],'cakes':[2.,2.25],'winners':[2]})

    def test_latest_context_replaces_backlog(self):
        voice = commentator()
        voice.update(race(), 100.)
        later = race()
        later.players[0].hits = 16
        voice.update(later, 103.)
        self.assertEqual(voice.pending.qsize(), 1)
        self.assertEqual(voice.pending.get_nowait()['bites'], [16,9])

    def test_final_and_paused_states_bypass_periodic_interval(self):
        voice = commentator()
        voice.update(race(), 100.)
        voice.update(race('result'), 100.1)
        self.assertEqual(voice.pending.get_nowait()['winners'], [2])
        voice.update(race('paused'), 100.2)
        self.assertEqual(voice.pending.get_nowait()['state'], 'paused')

    def test_disabled_game_sends_waiting_without_winner(self):
        self.assertEqual(game_context(race('result'), False)['state'], 'waiting')
        self.assertEqual(game_context(race('result'), False)['winners'], [])


class AppServerVoiceTests(unittest.TestCase):
    def client(self, event):
        client = CodexClient.__new__(CodexClient)
        client.thread_id = 'test-thread'
        client.rpc = Mock(return_value={})
        client.events = deque([event])
        return client

    def test_live_model_uses_app_server_webrtc(self):
        client = self.client({'method':'thread/realtime/sdp', 'params':{'sdp':'answer'}})
        self.assertEqual(client.start_voice('offer'), 'answer')
        method, params = client.rpc.call_args.args
        self.assertEqual(method, 'thread/realtime/start')
        self.assertEqual(params['model'], 'gpt-live-1')
        self.assertEqual(params['transport'], {'type':'webrtc','sdp':'offer'})
        self.assertFalse(params['includeStartupContext'])

    def test_voice_error_is_reported_without_model_fallback(self):
        client = self.client({'method':'thread/realtime/error','params':{'message':'unavailable'}})
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            client.start_voice('offer')
        self.assertEqual(client.rpc.call_count, 1)

    def test_game_updates_stay_in_realtime_session(self):
        client = self.client({})
        client.append_context(game_context(race()))
        self.assertEqual(client.rpc.call_args.args[0], 'thread/realtime/appendText')
        self.assertIn('remaining_seconds', client.rpc.call_args.args[1]['text'])


if __name__ == '__main__':
    unittest.main()
