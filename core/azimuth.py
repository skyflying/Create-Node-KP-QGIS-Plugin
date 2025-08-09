import math
from qgis.core import QgsPointXY
class Azimuth:
    @staticmethod
    def compute(prev: 'QgsPointXY', cur: 'QgsPointXY'):
        if prev is None or cur is None: return None
        dx, dy = cur.x()-prev.x(), cur.y()-prev.y()
        if dx == 0 and dy == 0: return None
        ang = math.degrees(math.atan2(dx, dy))  # 0=N, 90=E
        return ang + 360.0 if ang < 0 else ang
