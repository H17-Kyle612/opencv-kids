"""変身素材の組み合わせと抽選。"""

HEADS = ('santa', 'antlers', 'star', 'gift', 'cross', 'none')
LOOKS = (('santa', 'none', 'beard'), ('antlers', 'red', 'none'),
         ('star', 'none', 'none'), ('gift', 'red', 'none'),
         ('cross', 'none', 'none'), ('none', 'none', 'wreath'))
NOSES = ('red', 'none')


def random_outfit(rng):
    # 頭の素材は一つずつ。鼻と顔周りは独立して抽選。
    head = rng.choice(HEADS)
    nose = rng.choice(NOSES)
    surround = rng.choice(('beard', 'wreath', 'none'))
    if head == 'none' and nose == 'none' and surround == 'none':
        head = 'santa'
    return head, nose, surround
