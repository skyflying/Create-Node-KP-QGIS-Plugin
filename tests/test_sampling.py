import unittest
from qgis.core import QgsGeometry, QgsPointXY
from line_node_processor.core.sampling import GeometrySampler

class TestGeometrySampler(unittest.TestCase):
    def test_sample_distance(self):
        line = QgsGeometry.fromPolylineXY([QgsPointXY(0,0), QgsPointXY(10,0)])
        sampler = GeometrySampler(5.0, False)
        pts = sampler.sample_geometry(line)
        self.assertTrue(len(pts) >= 3)
