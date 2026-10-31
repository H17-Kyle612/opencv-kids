from collections import deque
import queue
import unittest
from unittest.mock import Mock
from codex_client import CodexClient
from types import SimpleNamespace
from commentary import Commentator
from commentary_context import MatchStory, game_context
from commentary_debug import CommentaryDebug
import time
import threading
import tempfile
from pathlib import Path
from commentary_settings import CommentarySettings


def race(state='playing'):
    return SimpleNamespace(state=state, player_count=2, time_limit=30., elapsed=10., bites_per_cake=4,
                           players=[SimpleNamespace(track_id=1, hits=8), SimpleNamespace(track_id=2, hits=9)],
                           winners=[1] if state == 'result' else [])


def commentator():
    voice = Commentator.__new__(Commentator)
    voice.refresh_context = threading.Event()
    voice.story = MatchStory()
    voice.debug = CommentaryDebug()
    voice.pending = queue.Queue(maxsize=1)
    voice.last_request = 0.
    voice.previous_state = None
    return voice


class CommentaryTests(unittest.TestCase):
    def test_context_contains_only_game_data(self):
        context = game_context(race('result'))
        self.assertEqual(context, {'mode':'versus','state':'result','remaining_seconds':20.,
                                  'bites':[8,9],'cakes':[2.,2.25],'winners':[2]})

    def test_solo_context_has_no_opponent_or_winner(self):
        game = race('result')
        game.player_count = 1
        game.players = game.players[:1]
        game.winners = []
        context = game_context(game)
        self.assertEqual(context['mode'], 'solo')
        self.assertEqual(context['cakes'], [2.])
        self.assertEqual(context['winners'], [])

    def test_latest_context_replaces_backlog(self):
        voice = commentator()
        voice.update(race(), 100.)
        later = race()
        later.players[0].hits = 16
        voice.update(later, 103.)
        self.assertEqual(voice.pending.qsize(), 1)
        self.assertEqual(voice.pending.get_nowait()['context']['bites'], [16,9])

    def test_idle_state_is_not_sent_repeatedly(self):
        voice = commentator()
        voice.update(race('waiting'), 100.)
        voice.pending.get_nowait()
        voice.update(race('waiting'), 101.)
        self.assertTrue(voice.pending.empty())

    def test_final_and_paused_states_bypass_periodic_interval(self):
        voice = commentator()
        voice.update(race(), 100.)
        voice.update(race('result'), 100.1)
        self.assertEqual(voice.pending.get_nowait()['context']['winners'], [2])
        voice.update(race('paused'), 100.2)
        self.assertEqual(voice.pending.get_nowait()['context']['state'], 'paused')

    def test_speech_cue_does_not_repeat_background_events_or_scores(self):
        context, _ = MatchStory().observe(race(), 100.)
        params = CodexClient.context_params('thread', context)
        self.assertNotIn('"events":', params['text'])
        self.assertNotIn('"bites":', params['text'])
        self.assertIn('未実況の展開だけ', params['text'])

    def test_disabled_game_sends_waiting_without_winner(self):
        self.assertEqual(game_context(race('result'), False)['state'], 'waiting')
        self.assertEqual(game_context(race('result'), False)['winners'], [])


class MatchStoryTests(unittest.TestCase):
    def test_recent_and_previous_pace_use_elapsed_game_time(self):
        story = MatchStory()
        game = race()
        for second in range(7):
            game.elapsed = float(second)
            game.players[0].hits = second if second <= 3 else 3+(second-3)*2
            game.players[1].hits = second
            context, _ = story.observe(game, float(second))
        self.assertEqual(context['recent_bites'], [6,3])
        self.assertEqual(context['bites_per_second'], [2.,1.])
        self.assertEqual(context['previous_bites_per_second'], [1.,1.])

    def test_cake_and_lead_change_trigger_without_waiting_for_regular_reaction(self):
        story = MatchStory()
        game = race()
        game.elapsed = 0.
        game.players[0].hits, game.players[1].hits = 3, 4
        story.observe(game, 0.)
        game.elapsed = 1.5
        game.players[0].hits = 5
        context, _ = story.observe(game, 1.5)
        self.assertTrue(context['react'])
        self.assertIn({'type':'lead_change','leaders':[1]}, context['events'])
        self.assertIn({'type':'cake_finished','player':1,'count':1}, context['events'])

    def test_background_updates_do_not_request_a_speech_every_half_second(self):
        story = MatchStory()
        game = race()
        story.observe(game, 0.)
        context, _ = story.observe(game, .5)
        self.assertFalse(context['react'])
        client = CodexClient.__new__(CodexClient)
        params = client.context_params('thread', context)
        self.assertIn('新しい発話は増やさない', params['text'])

    def test_result_is_background_while_busy_and_does_not_replay_when_idle(self):
        story = MatchStory()
        game = race()
        story.observe(game, 0.)
        game.state = 'result'
        context, _ = story.observe(game, 1., allow_reaction=False)
        self.assertFalse(context['react'])
        self.assertEqual(context['priority'], 'urgent')
        self.assertEqual(context['events'], [{'type':'finish'}])
        context, _ = story.observe(game, 2., allow_reaction=True)
        self.assertFalse(context['react'])
        context, _ = story.observe(game, 3., allow_reaction=True)
        self.assertFalse(context['react'])

    def test_result_while_idle_requests_one_closing_sentence(self):
        story = MatchStory()
        game = race()
        story.observe(game, 0.)
        game.state = 'result'
        context, _ = story.observe(game, 1., allow_reaction=True)
        self.assertTrue(context['react'])
        later, _ = story.observe(game, 2., allow_reaction=True)
        self.assertFalse(later['react'])
        self.assertEqual(later['events'], [])

    def test_restart_clears_old_pace_and_lead_history(self):
        story = MatchStory()
        game = race()
        old, _ = story.observe(game, 10.)
        game.elapsed = 0.
        game.state = 'countdown'
        context, changed = story.observe(game, 11.)
        self.assertTrue(changed)
        self.assertGreater(context['match'], old['match'])
        self.assertNotIn('bites_per_second', context)
        self.assertFalse(context['react'])

    def test_events_are_sent_once_even_when_voice_is_busy(self):
        story = MatchStory()
        game = race()
        story.observe(game, 0.)
        game.players[1].hits = 12
        quiet, _ = story.observe(game, 2., allow_reaction=False)
        self.assertFalse(quiet['react'])
        reaction, _ = story.observe(game, 3., allow_reaction=True)
        self.assertTrue(reaction['react'])
        self.assertIn({'type':'cake_finished','player':2,'count':1}, quiet['events'])
        self.assertIsNotNone(quiet['event_id'])
        self.assertEqual(reaction['events'], [])
        self.assertIsNone(reaction['event_id'])

    def test_sending_interval_is_half_a_second_and_state_changes_are_immediate(self):
        voice = commentator()
        voice.update(race(), 100.)
        voice.pending.get_nowait()
        voice.update(race(), 100.49)
        self.assertTrue(voice.pending.empty())
        voice.update(race(), 100.5)
        self.assertFalse(voice.pending.empty())
        voice.update(race('paused'), 100.51)
        self.assertEqual(voice.pending.get_nowait()['context']['state'], 'paused')


    def test_reversal_through_tie_is_immediate_background_during_speech(self):
        voice = commentator()
        game = race()
        voice.update(game, 100.)
        voice.pending.get_nowait()
        voice.debug.playback({'type':'speech_started'})
        game.players[0].hits = 9
        voice.update(game, 100.5)
        voice.pending.get_nowait()
        game.players[0].hits = 10
        voice.update(game, 100.55)
        latest = voice.pending.get_nowait()['context']
        self.assertEqual(latest['priority'], 'urgent')
        self.assertFalse(latest['react'])
        self.assertEqual(latest['leaders'], [1])

    def test_background_is_observed_while_speaking_without_normal_cue(self):
        voice = commentator()
        game = race()
        voice.update(game, 100.)
        voice.pending.get_nowait()
        voice.debug.playback({'type':'speech_started'})
        game.players[1].hits += 1
        voice.update(game, 100.5)
        packet = voice.debug.context_after(1, timeout=0)
        self.assertEqual(packet['sequence'], 2)
        self.assertEqual(packet['context']['bites'], [8,10])
        self.assertFalse(packet['context']['react'])

    def test_new_event_batches_have_distinct_ids_and_background_is_not_mutated(self):
        voice = commentator()
        game = race()
        voice.update(game, 100.)
        game.players[1].hits = 12
        voice.update(game, 100.5)
        first = voice.debug.snapshot()['current']['context']
        game.players[1].hits = 16
        voice.update(game, 101.)
        second = voice.debug.snapshot()['current']['context']
        self.assertNotEqual(first['event_id'], second['event_id'])
        self.assertEqual(second['events'], [{'type':'cake_finished','player':2,'count':1}])
        self.assertFalse(second['react'])
        self.assertTrue(voice.pending.get_nowait()['context']['react'])

    def test_solo_never_generates_a_leader_reversal(self):
        story = MatchStory()
        game = race()
        game.player_count = 1
        game.players = game.players[:1]
        story.observe(game, 0.)
        game.players[0].hits = 20
        context, _ = story.observe(game, 2., allow_reaction=False)
        self.assertFalse(context['react'])
        self.assertEqual(context['leaders'], [])


class DebugTests(unittest.TestCase):
    def test_reaction_waits_for_audio_and_speech_completion(self):
        debug = CommentaryDebug()
        self.assertTrue(debug.can_react())
        context = {'react':True}
        debug.sending({'context':context,'at':'capture','monotonic':time.monotonic()}, {})
        self.assertFalse(debug.can_react())
        self.assertFalse(debug.should_send({'state':'playing','react':False}))
        self.assertTrue(debug.should_send({'state':'paused','react':False}))
        debug.playback({'type':'speech_started'})
        self.assertFalse(debug.should_send({'state':'playing','react':False}))
        self.assertFalse(debug.should_send({'state':'playing','react':True,'priority':'urgent'}))
        self.assertFalse(debug.should_send({'state':'result','react':True,'priority':'urgent'}))
        self.assertFalse(debug.should_send({'state':'result','react':False}))
        self.assertFalse(debug.can_react())
        debug.playback({'type':'speech_ended'})
        self.assertFalse(debug.can_react())
        debug.last_end -= 1.
        self.assertTrue(debug.can_react())

    def test_audio_gap_does_not_end_speech_and_keeps_diagnostic_details(self):
        debug = CommentaryDebug()
        debug.playback({'type':'speech_started'})
        debug.playback({'type':'speech_gap','gap_ms':500})
        state = debug.snapshot()
        self.assertTrue(state['speaking'])
        self.assertEqual(state['audio'][-1]['gap_ms'], 500)
        self.assertFalse(debug.can_react())
        debug.playback({'type':'audio_track_muted'})
        self.assertEqual(debug.snapshot()['audio'][-1]['type'], 'audio_track_muted')

    def test_debug_records_exact_sent_payload_and_bounds_history(self):
        debug = CommentaryDebug()
        context = game_context(race())
        params = CodexClient.context_params('thread', context)
        for i in range(40):
            entry, started = debug.sending({'context':context, 'at':'capture', 'monotonic':time.monotonic()}, params)
            debug.acknowledge(entry, started)
        state = debug.snapshot()
        self.assertEqual(len(state['sent']), 30)
        self.assertEqual(state['sent'][-1]['request']['params'], params)
        self.assertEqual(state['sent'][-1]['status'], 'App Server受付済み')
        debug.playback({'type':'speech_started','at':'browser-time'})
        self.assertEqual(debug.snapshot()['audio'][-1]['browser_at'], 'browser-time')


class SettingsTests(unittest.TestCase):
    def test_prompt_and_voice_persist_without_changing_default_template(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'settings.json'
            settings = CommentarySettings(path)
            original = settings.snapshot()
            result = settings.save('ウィットを効かせて実況。', 'miko', ['cove','miko'])
            self.assertEqual(result['revision'], original['revision']+1)
            self.assertEqual(CommentarySettings(path).snapshot(), result)

    def test_invalid_settings_do_not_overwrite_saved_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = CommentarySettings(Path(folder)/'settings.json')
            original = settings.snapshot()
            for prompt, voice in [('', 'cove'), ('x'*12001,'cove'), ('声を変える','unknown')]:
                with self.assertRaises(ValueError):
                    settings.save(prompt,voice,['cove'])
                self.assertEqual(settings.snapshot(), original)

    def test_reconnecting_refreshes_narration_without_resetting_game(self):
        voice = commentator()
        game = race()
        voice.update(game,100.)
        voice.pending.get_nowait()
        voice.refresh_context.set()
        voice.update(game,100.1)
        self.assertEqual(voice.pending.get_nowait()['context']['bites'], [8,9])
        self.assertEqual(game.elapsed,10.)
        self.assertEqual(game.state,'playing')


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
        self.assertNotIn('model', params)
        self.assertEqual(params['transport'], {'type':'webrtc','sdp':'offer'})
        self.assertFalse(params['includeStartupContext'])

    def test_browser_prompt_and_selected_voice_are_passed_to_app_server(self):
        client = self.client({'method':'thread/realtime/sdp','params':{'sdp':'answer'}})
        client.start_voice('offer',prompt='ケーキにちなんだ洒落を交えて実況。',voice='miko',initial_context={'state':'playing','bites':[12]})
        params = client.rpc.call_args.args[1]
        self.assertEqual(params['prompt'],'ケーキにちなんだ洒落を交えて実況。')
        self.assertEqual(params['voice'],'miko')
        self.assertIn('playing', params['initialItems'][0]['text'])
        self.assertNotIn('model', params)

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
