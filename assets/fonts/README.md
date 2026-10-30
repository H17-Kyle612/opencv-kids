# 日本語フォント

- 書体：BIZ UDPゴシック 太字（BIZ UDPGothic Bold）
- 配布元：https://github.com/google/fonts/tree/main/ofl/bizudpgothic
- ライセンス：SIL Open Font License 1.1（同梱の `OFL.txt`）

`BIZUDPGothic-Bold.ttf` が原本です。
`japanese.png` と `japanese.json` は、このアプリで使う文字を事前生成した画像と配置情報です。
実行中はOpenCVで読み込み・合成します。Pillowは実行時には使用しません。

UIの文言を変更した開発者は、プロジェクト直下で更新してください。

```sh
uv run --with pillow tools/build_font.py
```
