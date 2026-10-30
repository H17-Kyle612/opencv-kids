"""ゲーム用の短い効果音を合成する。外部の音源素材は使わない。"""
from pathlib import Path
import wave
import numpy as np

RATE = 44100
FOLDER = Path(__file__).resolve().parents[1]/'assets'/'sounds'


def tone(frequency, duration, volume=.35):
    t = np.arange(round(RATE*duration))/RATE
    envelope = np.minimum(1., t/.006)*np.exp(-t/max(duration*.35, .01))
    return volume*envelope*(np.sin(2*np.pi*frequency*t)+.25*np.sin(4*np.pi*frequency*t))


def write(name, samples):
    with wave.open(str(FOLDER/f'{name}.wav'), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes((np.clip(samples, -1, 1)*32767).astype('<i2').tobytes())


def main():
    FOLDER.mkdir(parents=True, exist_ok=True)
    t = np.arange(round(RATE*.09))/RATE
    envelope = np.sin(np.pi*t/.09)**2*np.exp(-t*18)
    for name, frequency in (('bite1', 840), ('bite2', 640)):
        phase = 2*np.pi*(frequency*t-1800*t*t)
        write(name, .5*envelope*(np.sin(phase)+.2*np.sin(2*phase)))
    write('bite_both', tone(840, .09, .23)+tone(640, .09, .23))
    write('tick', tone(1046, .08, .28))
    for name, notes, duration in (
        ('start', (523, 659, 784, 1046), .09),
        ('cake', (1046, 1318, 1568), .07),
        ('finish', (523, 659, 784, 1046, 1318, 1568), .12),
    ):
        write(name, np.concatenate([tone(f, duration, .28) for f in notes]))
    print(FOLDER)


if __name__ == '__main__':
    main()
