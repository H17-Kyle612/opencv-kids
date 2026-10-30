# みんなのクリスマス変身カメラ & ケーキぱくぱく対戦

カメラに映った全員がクリスマスの姿に変身し、2人が十分な大きさで映ると
口の開閉でケーキを食べる対戦ゲームが始まります。
映像の取得・顔検出・口の特徴点推定・描画はOpenCVで処理します。
MediaPipeやdlibは使用していません。

## 起動（セットアップ済みの場合）

プロジェクトのフォルダで実行します。

```sh
source .venv/bin/activate
python christmas_camera.py --fullscreen
```

ゲームを自動開始せず、変身ミラーとして起動する場合：

```sh
python christmas_camera.py --fullscreen --mirror-only
```

## 初回セットアップ（macOS / Homebrew）

```sh
brew update
brew install python
git clone https://github.com/H17-Kyle612/opencv-kids.git
cd opencv-kids
"$(brew --prefix)/bin/python3" -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python setup_models.py
python christmas_camera.py --fullscreen
```

開発時の環境は Homebrew Python 3.15.2 / OpenCV 4.14.0 / NumPy 2.5.4 です。
既存環境から更新する場合、`opencv-python` と `opencv-contrib-python` は共存させません。

```sh
source .venv/bin/activate
python -m pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python-headless
python -m pip install --force-reinstall -r requirements-lock.txt
python setup_models.py
```

初回は実行元アプリのカメラ権限を許可してください。
映らない場合は「システム設定 → プライバシーとセキュリティ → カメラ」を確認します。

## ゲームのルール

1. 画面の左と右に1人ずつ入り、カメラを正面から見ます。
2. 両者の顔幅が160px以上で、口の特徴点を推定できる状態が1.5秒続くと準備完了です。
3. 準備中は口を閉じます。この間の値を、各プレイヤーの閉じた口の基準にします。
4. **3・2・1** のカウントダウン後にスタートします。
5. **閉じる → 開く → 閉じる** の1往復を1口と数えます。開けっぱなしでは増えません。
6. **4口で1ホール、3ホール（12口）を先に完食した方が勝ち**です。

口を開く・閉じる状態には短い継続時間と別々のしきい値を設け、瞬間的な揺れを抑えています。
制限時間は90秒。時間切れは口数が多い方の勝ち、同点や同じフレームの完食は引き分けです。
カウントダウン中は得点になりません。

対戦中に顔や口の特徴点を見失った場合は、**両者の計測と得点を一時停止**します。
2人が安定して戻ったら3秒のカウントダウン後に再開し、10秒以上戻らない場合は待機へ戻ります。
プレイヤーは開始時の2人に割り当てます。これは位置による追跡であり、個人を識別する顔照合ではありません。
顔の交差や長い遮蔽で割り当てが不安定になった場合は、Rキーで再試合してください。

## HUD・結果・演出

- プレイヤー別の色枠、食べたホール数、口数、全体進捗、口の開き具合のメーター
- 対戦タイム、カウントダウン、一時停止表示
- 勝敗、完食タイム、食べたホール数・口数、1秒あたりの口数
- 食べるたびにケーキが弾んで回転し、クリーム・金色の粒・光の輪と大きな文字が出現
- ホール完食時の強い粒子演出、勝利時の花火と紙吹雪

HUDはOpenCV標準フォントで描くため、画面内の案内は英語です。

## 操作

カメラウィンドウを選択して操作してください。

| キー | 操作 |
|---|---|
| G | ゲーム / 変身ミラーを切り替え |
| R | 再試合・ゲームをリセットし、変身をシャッフル |
| Space | 全員の変身をシャッフル |
| S | 雪・変身・ゲームHUDを含む写真を `outputs/` に保存 |
| F | 全画面切り替え |
| H | 変身ミラーの操作説明を表示・非表示 |
| 1〜6 | 全員の素材を指定（サンタ・トナカイ・星・箱・十字架・リース） |
| ↑ / ↓ | 頭の飾りの上下位置を微調整 |
| D | 顔の枠と5つの特徴点のガイド |
| Q / Esc | 終了 |

## 変身素材

サンタ帽・ひげ・トナカイのツノ・赤鼻・星・プレゼント箱・十字架・リースの
**8点を画像生成した透過PNG**で用意しています。ニンジン鼻は削除しました。
頭・鼻・顔周りを個別に抽選し、検出した全員に適用します。
星は明るい本体、強い金色の後光、放射状の光芒、8か所のきらめきが動きます。

帽子などは両目、鼻は鼻先、ひげは口、リースは顔の中央を基準に配置します。
頭上の余白が少ない場合は頭の飾りを縮小します。頭の上に余白のある画角が適しています。

画像は `assets/generated/` に格納し、生成に使ったプロンプトは `assets/prompts/` に保存しています。
素材の制作に組み込みの `image_gen` を使用しました。実行時の画像生成やAPI接続は不要です。
ケーキは丸ごと・3/4・1/2・1/4・空の皿の5段階を、それぞれ画像生成しています。

## 調整用の起動オプション

```sh
# 別のカメラ
python christmas_camera.py --camera 1

# ゲーム開始の顔幅を変更（入力画像上のpx）
python christmas_camera.py --min-face 180

# 競うホール数と制限時間
python christmas_camera.py --cakes 2 --time-limit 60

# 検出を軽くする。小さい顔は検出しにくくなります
python christmas_camera.py --detect-width 640

# 頭の飾りを上へ移動（顔幅に対する比率。正で下、負で上）
python christmas_camera.py --head-offset -0.05

# 口の特徴点と開き具合を確認
python christmas_camera.py --mouth-debug
```

カメラには1280×720を要求し、顔検出は既定で幅960以下、口元の推定は幅720以下で処理します。
入力解像度はカメラの対応設定に依存します。
検出した全顔に変身を描き、ゲームの口元推定は対戦候補・対戦者の最大2人に限定します。
精度や速度は照明、顔の向き、距離、遮蔽、PC性能に左右されます。

## 確認画像・テスト

```sh
python christmas_camera.py --demo
python preview_game.py
python -m unittest discover -s tests -v
```

`--demo` は変身素材の組み合わせ画像、`preview_game.py` は架空の顔を使ったゲーム画面と
6秒の演出動画を `outputs/` に作成します。
テストは口の開閉の数え方、ノイズ・見失い、2人の開始条件、カウントダウン、勝敗、
引き分け、一時停止、追跡、画面端の描画を検証します。

開発時に投影と同じ描画結果をローカルで確認する任意オプション：

```sh
python christmas_camera.py --preview-file outputs/live_preview.jpg --mouth-debug
```

0.5秒ごとに確認画像1枚と状態のJSONを上書きします。
通常起動では自動保存・録画・外部送信はしません。写真はSキーを押したときだけ保存します。
`--control-file outputs/live_controls.json` を併用すると、JSONの
`{"look": 3, "head_offset": 0.0}` などを更新して、カメラを開き直さず素材・位置を確認できます。
`look` は0でランダム、1〜6で操作表の各素材です。
`outputs/` はGitの公開対象から除外しています。

## 顔検出・口元推定のモデル

- **YuNet**：OpenCV 4.x対応 `face_detection_yunet_2023mar.onnx` を同梱。
  [配布元](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)、
  MITライセンスは `models/LICENSE-YuNet.txt`。
  SHA-256：`8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
- **Facemark LBF**：OpenCV公式チュートリアルで案内されている68点モデルを
  `python setup_models.py` で取得。約54MBのためGitには含めません。
  [上流の配布元](https://github.com/kurnianggoro/GSOC2017/blob/252614093b29280c549351971d44d71e63c9197c/data/lbfmodel.yaml)、
  [OpenCVの使い方](https://docs.opencv.org/3.4.12/d7/dec/tutorial_facemark_usage.html)。
  取得後にSHA-256 `70dd8b1657c42d1595d6bd13d97d932877b3bed54a95d3c4733a0f740d1fd66b` を照合します。

LBFの内側の唇3組の平均距離を口幅で割り、閉じた状態からの変化を判定しています。
実行時はモデル・素材をローカルから読み込むため、インターネット接続は不要です。
