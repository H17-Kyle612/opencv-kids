"""既存の起動コマンドを維持するエントリーポイント。"""
import cv2
from main import main

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (RuntimeError, cv2.error) as error:
        raise SystemExit(f'エラー: {error}')
