import queue
import threading
import unittest
from camera import LatestCamera

class Capture:
    def __init__(self):
        self.inputs=queue.Queue()
        self.reading=threading.Event()
        self.released=False
        self.count=0
    def read(self):
        self.count+=1
        if self.count==3:self.reading.set()
        return self.inputs.get(timeout=1)
    def release(self):self.released=True

class CameraTests(unittest.TestCase):
    def test_slow_consumer_gets_latest_frame_without_a_backlog(self):
        capture=Capture();capture.inputs.put((True,'old'));capture.inputs.put((True,'latest'))
        camera=LatestCamera(capture)
        self.assertTrue(capture.reading.wait(timeout=1))
        self.assertEqual(camera.read(),(True,'latest'))
        capture.inputs.put((False,None));camera.close()
        self.assertTrue(capture.released)
        self.assertFalse(camera.worker.is_alive())
    def test_capture_failure_wakes_reader(self):
        capture=Capture();capture.inputs.put((False,None));camera=LatestCamera(capture)
        self.assertEqual(camera.read(),(False,None));camera.close();self.assertTrue(capture.released)
