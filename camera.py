"""撮影を表示処理から分離し、古い映像を溜めず最新の1枚だけを渡す。"""
import threading
import time


class LatestCamera:
    def __init__(self, capture):
        self.capture = capture
        self.condition = threading.Condition()
        self.stopped = threading.Event()
        self.frame = None
        self.sequence = 0
        self.read_sequence = 0
        self.failed = False
        self.fps = 0.
        self.worker = threading.Thread(target=self._capture, daemon=True, name='camera-capture')
        self.worker.start()

    def _capture(self):
        previous = None
        try:
            while not self.stopped.is_set():
                ok, frame = self.capture.read()
                if not ok or frame is None:
                    break
                now = time.monotonic()
                if previous is not None:
                    self.fps = .9*self.fps + .1/max(now-previous, .001)
                previous = now
                with self.condition:
                    self.frame = frame
                    self.sequence += 1
                    self.condition.notify_all()
        finally:
            self.capture.release()
            with self.condition:
                self.failed = True
                self.condition.notify_all()

    def read(self):
        with self.condition:
            self.condition.wait_for(lambda: self.sequence>self.read_sequence or self.failed or self.stopped.is_set(), timeout=2.)
            if self.sequence == self.read_sequence or self.stopped.is_set():
                return False, None
            self.read_sequence = self.sequence
            return True, self.frame

    def close(self):
        self.stopped.set()
        with self.condition:
            self.condition.notify_all()
        self.worker.join(timeout=2.)
