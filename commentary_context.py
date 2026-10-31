"""実況用の事実と直近約3秒のペースを、ゲーム状態から取り出す。"""
from collections import deque


def game_context(race, active=True):
    return {'mode': 'solo' if race.player_count == 1 else 'versus',
            'state': race.state if active else 'waiting',
            'remaining_seconds': round(max(0, race.time_limit-race.elapsed), 1),
            'bites': [p.hits for p in race.players],
            'cakes': [p.hits/race.bites_per_cake for p in race.players],
            'winners': [i+1 for i in race.winners] if active and race.state == 'result' else []}


def leaders(bites):
    if len(bites) != 2:
        return []
    best = max(bites)
    return [i+1 for i, hits in enumerate(bites) if hits == best]


class MatchStory:
    def __init__(self):
        self.history = deque()
        self.previous = None
        self.announced = None
        self.match = 0
        self.last_reaction = -float('inf')

    def observe(self, race, now, active=True, allow_reaction=True):
        context = game_context(race, active)
        identity = (context['mode'], tuple(p.track_id for p in race.players))
        previous = self.previous
        reset = (previous is None or identity != previous['identity'] or
                 race.elapsed < previous['elapsed'] or
                 (context['state'] in ('waiting', 'ready') and previous['state'] not in ('waiting', 'ready')))
        if reset:
            self.history.clear()
            self.announced = None
            self.match += 1
            self.last_reaction = -float('inf')
        elapsed, hits = race.elapsed, tuple(context['bites'])
        if context['state'] == 'playing':
            if not self.history or elapsed > self.history[-1][0]:
                self.history.append((elapsed, hits))
            while len(self.history) > 1 and self.history[1][0] <= elapsed-6:
                self.history.popleft()
        context['match'] = self.match
        context['elapsed_seconds'] = round(elapsed, 2)
        context['leaders'] = leaders(hits)
        if self.history:
            def sample(at):
                return next((entry for entry in reversed(self.history) if entry[0] <= at), self.history[0])
            recent = sample(elapsed-3)
            before = sample(elapsed-6)
            span = max(elapsed-recent[0], .01)
            context['recent_window_seconds'] = round(elapsed-recent[0], 2)
            context['recent_bites'] = [max(0, a-b) for a, b in zip(hits, recent[1])]
            context['bites_per_second'] = [round(n/span, 2) for n in context['recent_bites']]
            if recent[0]-before[0] >= 1.:
                context['previous_bites_per_second'] = [round((a-b)/(recent[0]-before[0]), 2)
                                                       for a, b in zip(recent[1], before[1])]
        old = self.announced
        events = []
        changed = previous is None or context['state'] != previous['state'] or reset
        if context['state'] == 'playing':
            if changed:
                events.append({'type': 'start' if elapsed < 1 else 'resume'})
            if old and old['match'] == self.match:
                for i, (a, b) in enumerate(zip(context['cakes'], old['cakes'])):
                    if int(a) > int(b):
                        events.append({'type':'cake_finished', 'player':i+1, 'count':int(a)-int(b)})
                if context['leaders'] and old['leaders'] != context['leaders']:
                    events.append({'type':'lead_change', 'leaders':context['leaders']})
                for seconds in (10, 5):
                    if old['remaining_seconds'] > seconds >= context['remaining_seconds']:
                        events.append({'type':'final_stretch', 'remaining_seconds':seconds})
            # 単発の口数よりも、おかわり・逆転など競技上の展開を優先する。
            react = changed or (now-self.last_reaction >= 1.2 and bool(events)) or now-self.last_reaction >= 3.5
        else:
            react = context['state'] == 'result' and (old is None or old['match'] != self.match or old['state'] != 'result')
            if react:
                events.append({'type':'finish'})
        react = react and allow_reaction
        context['events'] = events
        context['react'] = react
        if react:
            self.announced = context.copy()
            self.last_reaction = now
        self.previous = {'identity':identity, 'elapsed':elapsed, 'state':context['state']}
        return context, changed
