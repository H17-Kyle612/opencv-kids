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
6. **4口で1ホール。制限時間内により多く食べた方が勝ち**です。個数に上限はありません。

小さめの口の開閉でも反応するよう、開くしきい値を調整しています。
開く・閉じるのしきい値は分けていますが、継続時間や前回の加点からの間隔制限は設けていません。
各フレームで検出した開閉1往復を1口として数えます。開けっぱなし・閉じっぱなしでは連続加点しません。
制限時間は30秒。残り時間が0になると終了し、食べた量が多い方の勝ちです。
ホールの端数も1口=1/4個として判定し、同じ量なら引き分けです。
カウントダウン中は得点になりません。

対戦中に顔や口の特徴点を見失った場合は、**両者の計測と得点を一時停止**します。
2人が安定して戻ったら3秒のカウントダウン後に再開し、10秒以上戻らない場合は待機へ戻ります。
プレイヤーは開始時の2人に割り当てます。これは位置による追跡であり、個人を識別する顔照合ではありません。
顔の交差や長い遮蔽で割り当てが不安定になった場合は、Rキーで再試合してください。

## HUD・結果・演出

- プレイヤー別の色枠、食べたホール数、口数、全体進捗、口の開き具合のメーター
- 対戦タイム、カウントダウン、一時停止表示
- 勝敗、食べたホール数と端数・口数、1秒あたりの口数
- 食べるたびにケーキが弾んで回転し、クリーム・金色の粒・光の輪と大きな文字が出現
- ホール1ホール完食時の強い粒子演出、勝利時の花火と紙吹雪

画面の案内は日本語で統一し、**BIZ UDPゴシック（太字）**を使用しています。
文字画像を事前生成して同梱し、実行中はOpenCVで合成します。ゲーム実行時の追加依存はありません。
フォントとSIL Open Font Licenseは `assets/fonts/` に保存しています。

## 効果音

macOSでは、カウントダウン・開始・1口ごと・1ホール完食・残り3秒・終了に効果音が鳴ります。
プレイヤーごとに音程を変え、同時に食べた場合は重ねた音を使います。
短いWAVを事前に読み込み、macOS標準のAudioToolboxで非同期再生するため、ゲーム処理を止めません。
`--no-sound` で無効にできます。音量はmacOSの設定に従います。

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

# 制限時間（個数の上限はありません）
python christmas_camera.py --time-limit 60

# 検出を軽くする。小さい顔は検出しにくくなります
python christmas_camera.py --detect-width 640

# 頭の飾りを上へ移動（顔幅に対する比率。正で下、負で上）
python christmas_camera.py --head-offset -0.05

# 口の特徴点と開き具合を確認
python christmas_camera.py --mouth-debug
```

カメラには1280×720を要求し、顔検出は既定で幅960以下で処理します。
口元の推定は入力を一律に縮小せず、元解像度の顔領域を使用します。
`--detect-width 0` を指定すると顔検出も入力画像を縮小しません。
これは解像度を保持する設定であり、検出精度を保証する設定ではありません。
入力解像度はカメラの対応設定に依存します。
検出した全顔に変身を描き、ゲームの口元推定は対戦候補・対戦者の最大2人に限定します。
精度や速度は照明、顔の向き、距離、遮蔽、PC性能に左右されます。

## 確認画像・テスト

```sh
python preview_game.py
python -m unittest discover -s tests -v
```

`preview_game.py` は架空の顔を使ったゲーム画面と
6秒の演出動画を `outputs/` に作成します。
テストは口の開閉の数え方、開けっぱなし・見失い、2人の開始条件、カウントダウン、個数上限なし、時間切れ後の加点防止、
勝敗・引き分け、一時停止、追跡、画面端の描画を検証します。

開発時に投影と同じ描画結果をローカルで確認する任意オプション：

```sh
python christmas_camera.py --preview-file outputs/live_preview.jpg --mouth-debug
```

0.5秒ごとに確認画像1枚と状態のJSONを上書きします。
通常起動では自動保存・録画・外部送信はしません。写真はSキーを押したときだけ保存します。
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
通常のゲームはモデル・素材をローカルから読み込み、インターネット接続は不要です。AI実況を有効にする場合は接続が必要です。

## 実装の分担

- `christmas_camera.py`：既存コマンドのエントリーポイント
- `main.py`：起動・入力・処理順の制御
- `cake_game.py`：開始条件・口の開閉カウント・時間制・勝敗。推論や描画には依存しません
- `vision.py`：YuNetとFacemark LBFによる推論
- `tracking.py`：顔の短期追跡と変身の割り当て
- `accessories.py`：変身素材の配置・星・雪
- `game_visuals.py`：ゲームHUD・演出
- `graphics.py`：画像合成・日本語文字の共通描画
- `audio.py`：効果音の読み込み・非同期再生
- `diagnostics.py`：明示的に有効にする確認表示・ローカル出力

日本語UIの文言を変更した開発者は、次のコマンドで文字画像を更新します。
Pillowはこの開発用ツールだけが使用し、実行用の `.venv` には不要です。

```sh
uv run --with pillow tools/build_font.py
```

フォント配布元：[Google Fonts / BIZ UDPGothic](https://github.com/google/fonts/tree/main/ofl/bizudpgothic)。

## 入力サイズ・タイル分割・並列化

OpenCV 4.xのYuNetは `setInputSize` で入力画像と同じサイズを指定でき、
アプリ側の縮小を省けます。モデル内部には特徴量を縮小する処理があるため、
これを「無損失の推論」とは扱いません。入力画素数を増やすと計算量・メモリ使用量も増えます。
また、モデルの学習時の顔サイズとの相性があり、元サイズが常に高精度とは限りません。

タイル分割は、全体を縮小すると消える小顔を、各タイル内で大きく扱う場合に有用です。
同じ元解像度のまま分割するだけで、顔の画素数が増えるわけではありません。
境界の顔が切れないように重複領域を設け、座標を戻して検出の重複を除く必要があります。

OpenCV自体の内部並列処理に加えてアプリ側で並列化する場合は、
CPUの取り合い、モデルの独立したインスタンス、同じフレームの結果の同期が必要です。
このアプリには未計測のタイル処理やワーカープールは追加していません。

参考：[YuNet実装](https://github.com/opencv/opencv/blob/4.x/modules/objdetect/src/face_detect.cpp)、
[モデルの説明](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)。


## AI音声実況（feature/ai-commentary）

Codex App Serverの実験的な`thread/realtime/*`を使い、GPT-Liveの声を
WebRTCで再生します。App Serverに渡す要求モデル名は`gpt-live-1`です。通常のテキストモデルによる実況生成やmacOSの読み上げは使用しません。
確認した環境はCodex CLI 0.166.0とChatGPTログインです。
APIキーログインの場合は開始を拒否します。利用可否・上限はアカウント側の制限に従います。

```sh
codex login
.venv/bin/python christmas_camera.py --fullscreen --commentary
```

開いたブラウザで「実況を開始」を一度押し、ページを開いたままゲーム画面に戻ります。
終了はゲームのQキー、実況だけ止める場合はブラウザの「実況を停止」です。
ブラウザが開かない場合はターミナルに表示するlocalhostのURLを開いてください。

送信する情報はゲームの状態・残り時間・両者の口数とケーキ数・確定した勝者です。
顔画像、顔の特徴点、マイク音声は送信しません。WebRTCには無音の入力トラックを送り、
GPT-Liveの音声クロックを維持します。開始・終了などの状態変化は即時、試合中は約0.5秒ごとに
最新の状況を渡します。通信は別スレッドで処理し、未送信の状況は最新1件で置き換えます。
接続エラー時もゲームは続行します。別モデル・APIキー・読み上げへの自動切り替えは行いません。

カメラなしの確認コマンド（架空の30秒対戦）：

```sh
.venv/bin/python tools/check_commentary.py
```

- `codex_client.py`：App ServerのJSON-RPCとGPT-Liveセッション
- `commentary.py`：ゲーム状況の抽出、非同期送信、localhostの再生ページ
- `voice_player.html`：WebRTC音声の再生、日本語UI（BIZ UDPGothic）
- `commentary_prompt.txt`：日本語実況の指示

App Serverの音声機能は実験的で、CLIの更新により変わる可能性があります。
公式資料：[Codex App Server](https://learn.chatgpt.com/docs/app-server)、
[GPT-Live 1](https://developers.openai.com/api/docs/models/gpt-live-1)。
## 1人チャレンジ

1人で30秒間に食べたケーキの数・口数・毎秒の口数を記録するモードです。
個数上限はなく、終了時は勝敗の代わりに自分の結果を表示します。

```sh
.venv/bin/python christmas_camera.py --fullscreen --players 1
```

顔幅160px以上の1人を画面のどこでも検出して開始します。複数の顔が映った場合は
一番大きい顔を選び、開始後はその人を追跡します。途中で顔が消えると一時停止します。
Mキーで1人／2人を切り替えます（進行中の得点と時間はリセット）。Rキーで同じモードを再挑戦します。
既定の起動は2人対戦です。

AI実況付きの1人モードは `--players 1 --commentary` を併用します。実況も1人向けの応援と結果発表になります。


### 実況デバッグと発話の制御

ブラウザで、現在のゲーム状況、実際に送信した本文とJSON-RPCパラメータ、
送信日時・送信待ち・App Server受付時間、最新30件の履歴、実際の固定プロンプトを確認できます。
データはメモリ内だけに保持します。取得した顔画像や特徴点は含みません。
直近約3秒の口数・ペース、その前の区間のペース、おかわり・リード交代・終盤のイベントも渡します。

背景更新は約0.5秒ごとに用意し、実況を促す合図は見せ場を優先します。
発声準備中は背景更新の送信を控え、実況指示が背景指示で打ち消されることを避けます。
この間もゲーム状況は最新1件に更新し、発話が終わったあとに最新情報を送ります。
ブラウザで発声中と検出した間、追加の実況は促しません。反応待ちが6秒を超えた場合は再び合図を許可します。
途中経過が送信待ちに1秒以上滞留した場合は捨て、最新のデータを使います。
プロンプトはスポーツ実況として声の抑揚、驚き、終盤の緊張感、達成の喜びを指示します。

音声ログは受信音声の音量から約0.1秒刻みで検出します。スピーカーの実測や、
特定の送信に対応するモデル生成時間ではありません。背景タブではブラウザのタイマー制限を受けます。
表示するジッターバッファ時間はWebRTC接続開始からの平均です。

- `commentary_context.py`：ゲームの事実・直近の展開・実況するタイミング
- `commentary_debug.py`：有限の送信／音声履歴と、発話が重なることを避ける制御
- `voice_player.js`：WebRTC再生・音声検出・デバッグ表示

1人の実況テストは `python tools/check_commentary.py --players 1`。
結果を確認し続ける場合は `--hold` を追加し、終了はCtrl+Cです。


### ブラウザで実況を調整

「遊びながら実況を調整」でプロンプトを書き換え、声を選び「保存して反映」を押します。
声の候補はApp Serverの`thread/realtime/listVoices`が返すv3の一覧です。
接続中は実況だけを再接続するため数秒間音声が止まります。ゲームの時間・得点はリセットしません。
停止中の保存は、次に「実況を開始」したときに反映されます。
保存した設定と適用中の設定を別々に表示し、実際の送信に使ったプロンプトを確認できます。

設定は`.commentary-settings.json`に保存し、Gitから除外します。
標準の`commentary_prompt.txt`は変更しません。「熱狂・ウィット重視の標準文に戻す」は
入力欄を戻すだけで、「保存して反映」を押すまで適用しません。
発話速度や語調はプロンプトで指定します。音声の再生速度を機械的に上げる処理は行いません。

発話中は、待機・一時停止などの明示的な停止指示を除いて、追加の状況や実況指示を送信しません。
短い息継ぎを終了と誤認しにくくするため、無音の判定は約1秒待ちます。
ブラウザの通信診断は欠落・破棄パケット、直近区間の音声補間（無音補間も別表示）、
往復時間、WebRTCのジッターバッファ、AudioContextの状態、再生待ち・停滞イベントを表示します。
これらの値だけで、モデルの言い直し・ネットワーク・再生負荷のどれが原因かを断定はできません。


### 要求モデル名と実モデル名

ChatGPT Liveの公式ヘルプにはGPT-Live-1.1とGPT-Live-1.1 Quipが記載されています。
Quipはモデルの種類であり、声の名前ではありません。
[ChatGPT Voice公式ヘルプ](https://help.openai.com/ja-jp/articles/20001274-chatgpt-voice)。

CLI 0.166.0のChatGPT認証・WebRTC経路で、`gpt-live-1.1`を要求した接続と日本語応答を確認しました。
ただし、明らかに無効なモデル名でも接続と応答が成功し、`session.started`には実モデル名が返りませんでした。
この結果だけでは、指定が反映されたのか、無効な値が無視または既定値に置換されたのかは区別できません。
したがって、接続成功を特定モデルへの切り替え成功とは扱いません。
ブラウザには要求値と「実モデル名未取得」を分けて表示します。
ChatGPTのChatにおけるモデル提供と、App Server経由でのモデル選択を同じものとは断定しません。
