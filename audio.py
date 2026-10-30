"""macOS標準のAudioToolboxで、読み込み済みの短い効果音を非同期再生。"""
import ctypes
from ctypes.util import find_library
import math
from pathlib import Path
import sys


class SoundEffects:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.ids = {}
        self.previous_state = None
        self.previous_tick = None
        if not enabled:
            return
        if sys.platform != 'darwin':
            self.enabled = False
            print('このOSの効果音再生には未対応です。', flush=True)
            return
        self.audio = ctypes.CDLL(find_library('AudioToolbox'))
        core = ctypes.CDLL(find_library('CoreFoundation'))
        core.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool]
        core.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
        core.CFRelease.argtypes = [ctypes.c_void_p]
        self.audio.AudioServicesCreateSystemSoundID.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        self.audio.AudioServicesCreateSystemSoundID.restype = ctypes.c_int32
        self.audio.AudioServicesPlaySystemSound.argtypes = [ctypes.c_uint32]
        self.audio.AudioServicesDisposeSystemSoundID.argtypes = [ctypes.c_uint32]
        try:
            for name in ('bite1', 'bite2', 'bite_both', 'tick', 'start', 'cake', 'finish'):
                path = str(Path(__file__).resolve().parent/'assets'/'sounds'/f'{name}.wav').encode()
                url = core.CFURLCreateFromFileSystemRepresentation(None, path, len(path), False)
                if not url:
                    raise RuntimeError('効果音ファイルのURLを作成できませんでした')
                identifier = ctypes.c_uint32()
                try:
                    status = self.audio.AudioServicesCreateSystemSoundID(url, ctypes.byref(identifier))
                finally:
                    core.CFRelease(url)
                if status:
                    raise RuntimeError(f'効果音を読み込めませんでした: {name} ({status})')
                self.ids[name] = identifier.value
        except Exception:
            self.close()
            raise

    def play(self, name):
        if self.enabled:
            self.audio.AudioServicesPlaySystemSound(self.ids[name])

    def update(self, race, now, active=True):
        tick = None
        if active:
            if race.state == 'countdown':
                tick = ('countdown', race.countdown(now))
            elif race.state == 'playing' and 0 < race.time_limit-race.elapsed <= 3:
                tick = ('ending', math.ceil(race.time_limit-race.elapsed))
            if race.state != self.previous_state:
                if race.state == 'playing':
                    self.play('start')
                elif race.state == 'result':
                    self.play('finish')
            if tick is not None and tick != self.previous_tick:
                self.play('tick')
            if race.events:
                if any(race.players[i].hits % race.bites_per_cake == 0 for i in race.events):
                    self.play('cake')
                else:
                    self.play('bite_both' if len(race.events) == 2 else f'bite{race.events[0]+1}')
        self.previous_state, self.previous_tick = race.state, tick

    def close(self):
        for identifier in self.ids.values():
            self.audio.AudioServicesDisposeSystemSoundID(identifier)
        self.ids.clear()
