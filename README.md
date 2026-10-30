# みんなのクリスマス変身カメラ

OpenCVだけで、カメラに映った複数人の顔を検出し、一人ずつランダムに変身させます。
カメラ映像は鏡のように左右反転し、大小の雪がゆっくり降ります。

## 初回セットアップ（macOS / Homebrew）

```sh
brew update
brew install python
git clone https://github.com/H17-Kyle612/opencv-kids.git
cd opencv-kids
"$(brew --prefix)/bin/python3" -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
```

顔検出モデルは同梱しています。

## 実行

```sh
cd opencv-kids
source .venv/bin/activate
python christmas_camera.py
```

全画面で起動する場合：

```sh
python christmas_camera.py --fullscreen
```

仮想環境を有効にせず、直接起動することもできます。

```sh
.venv/bin/python christmas_camera.py
```

## 操作

起動したカメラウィンドウを選んで操作してください。

| キー | 操作 |
|---|---|
| Space / R | 全員の変身をシャッフル |
| S | 雪と変身を含む写真を `outputs/` に保存（操作説明は写りません） |
| F | 全画面表示の切り替え |
| H | 操作説明の表示切り替え |
| Q / Esc | 終了 |

自動保存・動画録画・外部送信は行いません。実行時のインターネット接続は不要です。
写真は日時を含む異なる名前で保存します。

## ランダム変身のルール

- 頭：サンタ帽、トナカイのツノ、光る星、プレゼント箱、なし
- 鼻：赤鼻、ニンジン鼻、なし
- 顔周り：サンタのひげ、クリスマスリース、なし
- 各部位を独立して抽選します。同じ部位には一つだけ付け、全て「なし」にはしません。
- リースは顔を囲み、プレゼント箱は頭に載り、星は頭の上で明滅します。
- 検出された全ての顔に適用します。素材はOpenCVの図形描画で作成しています。
- 初登場時に抽選し、位置による追跡中は同じ変身を保ちます。
- 最後に検出してから1.2秒以内なら近くで再検出した顔に変身を引き継ぎます。見失った位置には描画しません。
- 個人を特定する顔照合は行いません。顔が交差したり隠れたりすると変身が入れ替わる場合があります。

## カメラ・人数に合わせた調整

```sh
# 別のカメラを使う
python christmas_camera.py --camera 1

# 検出を軽くする（小さく映る顔は検出しにくくなります）
python christmas_camera.py --detect-width 640

# 遠くの小さな顔にも処理画素数を確保する（処理負荷は増えます）
python christmas_camera.py --detect-width 1280

# 検出しきい値を下げる（誤検出も増える可能性があります）
python christmas_camera.py --threshold 0.65
```

既定では1280×720のカメラ入力を要求し、幅960以下に縮小して毎フレーム検出します。
実際の入力解像度はカメラが対応する設定になります。
人数によるアプリ側の表示上限は設けていませんが、同時人数・検出精度・速度は実際の画角、
顔の画素数、照明、遮蔽、PC性能に左右されます。現場で確認してください。
帽子やツノを置く余白のため、頭の上までゆとりを持って映してください。

初回はmacOSからカメラ権限を求められる場合があります。
映らない場合は「システム設定 → プライバシーとセキュリティ → カメラ」で
実行元アプリ（TerminalやCodexなど）の許可を確認してください。

## カメラなしで確認

```sh
python christmas_camera.py --demo
python -m unittest discover -s tests -v
```

`--demo` は架空の顔6人と全種類の素材を組み合わせた画像を `outputs/` に保存します。
テストでは複数顔の追跡、短時間の見失い、素材の画面端処理、雪の描画を確認します。
実際のカメラでの精度・速度を保証するテストではありません。

## 環境

セットアップに使用したPython：Homebrew Python 3.15.2。
依存関係は `requirements-lock.txt` に記録しています。
このプログラムは `opencv-python` と `numpy` を使用します。MediaPipeやdlibは不要です。

環境を作り直す場合：

```sh
brew update
brew install python
brew upgrade python
cd opencv-kids
"$(brew --prefix)/bin/python3" -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
```

既存の `.venv` を異なるPythonで作り直す場合は、必要なファイルがないことを確認し、
`.venv` のみを削除してから作成してください。
将来Pythonのメジャー・マイナーバージョンが変わった場合は、依存パッケージの対応確認が必要です。

## 顔検出モデルとライセンス

OpenCV 4.x対応のYuNet `face_detection_yunet_2023mar.onnx` を同梱しています。

- 配布元：https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- モデル取得元：https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
- SHA-256：`8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
- ライセンス：`models/LICENSE-YuNet.txt`（MIT）

## フォルダ

- `christmas_camera.py`：クリスマス変身カメラ
- `models/`：顔検出モデルとライセンス
- `tests/`：追跡・描画のテスト
- `assets/`：追加素材の保存場所
- `outputs/`：写真、プレビュー、最初の教材の出力
- `lessons/01_draw_face.py`：最初に準備した図形描画の教材
- `.venv/`：専用Python環境
