import unittest
import numpy as np
from vision import mouth_measurement

class MouthGeometryTests(unittest.TestCase):
    def points(self):
        pts=np.zeros((68,2),dtype=np.float32)
        pts[48]=(0,0);pts[54]=(100,0)
        for a,b,x in ((61,67,30),(62,66,50),(63,65,70)):
            pts[a]=(x,0);pts[b]=(x,0)
        return pts
    def test_horizontal_lip_jitter_is_not_an_opening(self):
        pts=self.points();pts[67,0]+=15;pts[66,0]-=10;pts[65,0]+=20
        self.assertEqual(mouth_measurement(pts),(100.,0.))
    def test_one_bad_point_does_not_create_a_bite(self):
        pts=self.points();pts[66,1]=25
        self.assertEqual(mouth_measurement(pts)[1],0.)
    def test_real_opening_survives_a_single_outlier_and_rotation(self):
        pts=self.points();pts[[67,66,65],1]=10;pts[66,1]=60
        self.assertAlmostEqual(mouth_measurement(pts)[1],.1)
        a=.4;rotation=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
        self.assertAlmostEqual(mouth_measurement(pts @ rotation.T + [30,60])[1],.1)
    def test_crossed_points_are_closed(self):
        pts=self.points();pts[[67,66,65],1]=-10
        self.assertEqual(mouth_measurement(pts)[1],0.)
