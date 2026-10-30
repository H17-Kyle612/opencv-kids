"""OpenCV公式チュートリアルが案内するLBFモデルを取得・照合する。"""
from hashlib import sha256
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / 'models' / 'lbfmodel.yaml'
URL = 'https://raw.githubusercontent.com/kurnianggoro/GSOC2017/252614093b29280c549351971d44d71e63c9197c/data/lbfmodel.yaml'
SHA256 = '70dd8b1657c42d1595d6bd13d97d932877b3bed54a95d3c4733a0f740d1fd66b'


def main():
    if MODEL.is_file() and sha256(MODEL.read_bytes()).hexdigest() == SHA256:
        print('LBFモデル: 確認済み')
        return
    MODEL.parent.mkdir(exist_ok=True)
    temporary = MODEL.with_suffix('.download')
    try:
        print('LBFモデルを取得しています（約54 MB）…', flush=True)
        with urllib.request.urlopen(URL, timeout=120) as response, temporary.open('wb') as output:
            while chunk := response.read(1024*1024):
                output.write(chunk)
        if sha256(temporary.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError('モデルのSHA-256が一致しません。保存を中止しました。')
        temporary.replace(MODEL)
        print(f'取得しました: {MODEL}')
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
