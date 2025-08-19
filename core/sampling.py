from typing import List, Tuple
from qgis.core import QgsGeometry, QgsPointXY

class GeometrySampler:
    def __init__(self, distance: float, preserve_nodes: bool):
        self.distance = float(distance) if (distance and distance > 0) else 0.0
        self.preserve_nodes = bool(preserve_nodes)

    def _vertices_only(self, geom: QgsGeometry) -> List[Tuple[QgsPointXY, float]]:
        pts: List[Tuple[QgsPointXY, float]] = []
        for v in geom.vertices():
            p = QgsPointXY(v)
            kp = geom.lineLocatePoint(QgsGeometry.fromPointXY(p))
            pts.append((p, float(kp)))
        pts.sort(key=lambda t: (round(t[1],6), round(t[0].x(),6), round(t[0].y(),6)))
        uniq, seen = [], set()
        for p,kp in pts:
            key = (round(kp,6), round(p.x(),6), round(p.y(),6))
            if key in seen: continue
            seen.add(key); uniq.append((p,kp))
        return uniq

    def _fixed_step_with_optional_vertices(self, geom: QgsGeometry) -> List[Tuple[QgsPointXY, float]]:
        L = float(geom.length() or 0.0)
        if L == 0:
            p = geom.interpolate(0.0).asPoint()
            return [(QgsPointXY(p), 0.0)]
        s = self.distance if self.distance > 0 else L

        pts: List[Tuple[QgsPointXY, float]] = []
        d = 0.0
        while d < L - 1e-9:
            p = geom.interpolate(d).asPoint()
            kp = geom.lineLocatePoint(QgsGeometry.fromPointXY(QgsPointXY(p)))
            pts.append((QgsPointXY(p), float(kp)))
            d += s
        # endpoint
        p_end = geom.interpolate(L).asPoint()
        kp_end = geom.lineLocatePoint(QgsGeometry.fromPointXY(QgsPointXY(p_end)))
        pts.append((QgsPointXY(p_end), float(kp_end)))

        if self.preserve_nodes:
            for v in geom.vertices():
                p = QgsPointXY(v)
                kp = geom.lineLocatePoint(QgsGeometry.fromPointXY(p))
                pts.append((p, float(kp)))

        pts.sort(key=lambda t: (round(t[1],6), round(t[0].x(),6), round(t[0].y(),6)))
        uniq, seen = [], set()
        for p,kp in pts:
            key = (round(kp,6), round(p.x(),6), round(p.y(),6))
            if key in seen: continue
            seen.add(key); uniq.append((p,kp))
        return uniq

    def sample_geometry_with_kp(self, geom: QgsGeometry) -> List[Tuple[QgsPointXY, float]]:
        if self.distance <= 0:
            return self._vertices_only(geom)
        if geom.isMultipart():
            all_pts: List[Tuple[QgsPointXY, float]] = []
            for part in geom.constParts():
                all_pts.extend(self._fixed_step_with_optional_vertices(QgsGeometry(part.clone())))
            all_pts.sort(key=lambda t: (round(t[1],6), round(t[0].x(),6), round(t[0].y(),6)))
            return all_pts
        return self._fixed_step_with_optional_vertices(geom)
