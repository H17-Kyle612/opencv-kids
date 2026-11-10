# 効果音

`tools/build_sounds.py` で波形を合成した、このゲーム用の短い効果音です。

- bite1 / bite2：各プレイヤーの1口
- bite_both：同じフレームで2人が食べた場合
- tick：開始カウントダウン、残り3秒
- start：スタート
- cake：1ホール完食
- finish：試合終了

再生にはmacOSのAudioToolboxまたはWindowsの標準音声機能を使用します。
