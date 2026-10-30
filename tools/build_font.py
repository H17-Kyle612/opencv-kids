"""開発時だけ使用。BIZ UDPゴシックから必要な文字の画像を生成する。
実行例: uv run --no-project --with pillow tools/build_font.py
Pillowはこのツール専用で、ゲーム実行時には不要。
"""
import ast
import json
from pathlib import Path
import string
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'assets'/'fonts'
SIZE, CELL, COLUMNS = 96, 128, 16


def main():
    characters = set(string.printable.strip())
    for path in ROOT.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                characters.update(c for c in node.value if c.isprintable() or c == '\u3000')
    font = ImageFont.truetype(str(FOLDER/'BIZUDPGothic-Bold.ttf'), SIZE)
    characters = sorted(characters)
    atlas = Image.new('L', (CELL*COLUMNS, CELL*((len(characters)+COLUMNS-1)//COLUMNS)))
    draw = ImageDraw.Draw(atlas)
    glyphs = {}
    for i, char in enumerate(characters):
        left, top, right, bottom = font.getbbox(char, anchor='ls')
        w, h = right-left, bottom-top
        x, y = (i%COLUMNS)*CELL+2, (i//COLUMNS)*CELL+2
        if w+4 > CELL or h+4 > CELL:
            raise ValueError(f'文字がセルからはみ出します: {char}')
        draw.text((x-left, y-top), char, font=font, fill=255, anchor='ls')
        glyphs[char] = {'rect': [x, y, w, h], 'offset': [left, top], 'advance': font.getlength(char)}
    atlas.save(FOLDER/'japanese.png')
    (FOLDER/'japanese.json').write_text(json.dumps({'font':'BIZ UDPGothic Bold', 'size': SIZE, 'glyphs':glyphs}, ensure_ascii=False))
    print(f'{len(characters)}文字を生成しました: {FOLDER}')


if __name__ == '__main__':
    main()
