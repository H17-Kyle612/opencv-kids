# クリスマス変身カメラ・ケーキぱくぱく対戦

## セットアップ

GitとPython 3を用意し、リポジトリを取得します。

```sh
git clone https://github.com/H17-Kyle612/opencv-kids.git
cd opencv-kids
```

**macOS**（Pythonがなければ `brew install python`）

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python setup_models.py
```

**Windows**（PowerShell、64ビット版Python 3.13を使用）

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_models.py
```

初回はOSの設定でデスクトップアプリのカメラ使用を許可してください。効果音はOS標準の機能で再生します。

**AI実況を使う場合**は [Codex CLI](https://learn.chatgpt.com/docs/codex/cli#install-codex) をインストールし、`codex login` でChatGPTにログインします。AI実況にはインターネット接続が必要です。

## 起動

| | macOS | Windows（PowerShell） |
|---|---|---|
| 2人対戦 | `.venv/bin/python christmas_camera.py` | `.\.venv\Scripts\python.exe christmas_camera.py` |
| AI実況付きの1人モード | `.venv/bin/python christmas_camera.py --players 1 --commentary` | `.\.venv\Scripts\python.exe christmas_camera.py --players 1 --commentary` |

AI実況を使うときは、開いたブラウザで **「実況を開始」** を押します。ブラウザが開かなければ、ターミナルに表示されたURLを開いてください。

## 起動オプション

| 引数 | 内容 |
|---|---|
| `--players 1` / `--players 2` | 1人チャレンジ / 2人対戦（既定は2人） |
| `--commentary` | GPT-LiveのAI実況を有効にする |
| `--mirror-only` | ゲームを自動開始せず、変身ミラーで起動する |
| `--fullscreen` / `--no-fullscreen` | 全画面（既定） / ウィンドウ表示 |
| `--no-sound` | ゲームの効果音を無効にする |
| `--time-limit 30` | 制限時間（秒、正の値、既定30） |
| `--min-face 160` | ゲーム開始に必要な顔幅（px、40以上、既定160） |
| `--mouth-sensitivity 7` | 口の感度（1〜10、既定7。大きいほど反応しやすい） |
| `--camera 0` | カメラ番号（既定0） |
| `--camera-fps 30` | カメラに要求するFPS（1〜240、既定30） |
| `--detect-width 640` | 顔検出に使う画像の最大幅（px、既定640。0で縮小なし） |
| `--threshold 0.75` | 顔検出のしきい値（0より大きく1以下、既定0.75） |
| `--head-offset 0` | 頭飾りの上下位置（-0.5〜0.5、正で下、既定0） |
| `--mouth-debug` | 唇の特徴点と開度を表示する |
| `--mouth-trace outputs/mouth.csv` | 開度と処理時間をCSVに保存する |
| `--preview-file outputs/preview.jpg` | 表示中の画像を約0.5秒ごとに保存する（JPG / PNG） |
| `--help` | 引数一覧を表示する |

## 操作キー

| キー | 操作 |
|---|---|
| `M` / `G` / `R` | 1人・2人を切り替え / ゲームとミラーを切り替え / 再試合 |
| `+` / `-` | 口の感度を上げる / 下げる |
| `[` / `]` | 次の試合の開始顔幅を10px下げる / 上げる |
| `@` | 詳細デバッグ → ランドマークのみ → 非表示 |
| `D` | 顔の位置ガイドを切り替える |
| `Space` / `1`〜`6` / `↑` `↓` | 衣装を抽選 / 衣装を選ぶ / 頭飾りの高さを調整 |
| `H` / `F` / `S` | ミラーの操作説明 / 全画面切り替え / 写真を保存 |
| `Q` / `Esc` | 終了 |
