"""まるや線を組み合わせて、自分だけの顔を描こう。"""

import argparse
from pathlib import Path

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", action="store_true", help="画像をウィンドウに表示する")
    args = parser.parse_args()


    face_color = (80, 220, 255)
    ink = (40, 40, 40)


    canvas = np.full((480, 640, 3), 255, dtype=np.uint8)


    cv2.circle(canvas, (320, 240), 150, face_color, -1)
    cv2.circle(canvas, (265, 205), 18, ink, -1)
    cv2.circle(canvas, (375, 205), 18, ink, -1)
    cv2.ellipse(canvas, (320, 260), (75, 55), 0, 0, 180, ink, 7)

    output = Path(__file__).resolve().parents[1] / "outputs" / "my_face.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), canvas):
        raise RuntimeError(f"画像を保存できませんでした: {output}")
    print(f"できました！ {output}")

    if args.show:
        cv2.imshow("My first OpenCV picture - press any key", canvas)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
