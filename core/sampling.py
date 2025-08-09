from dataclasses import dataclass
from typing import List, Optional
from qgis.core import QgsGeometry, QgsPointXY

@dataclass
class SamplePoint:
    point: QgsPointXY
    kp: Optional[float]  # measure along line; None for preserved vertices without measure

class GeometrySampler:
    def __init__(self, distance: float, preserve_nodes: bool):
        self.distance = float(distance) if (distance and distance > 0) else 0.0
        self.preserve_nodes = bool(preserve_nodes)

    def _sample_one_line(self, geom: QgsGeometry) -> List[SamplePoint]:
        pts: List[SamplePoint] = []
        length = geom.length()
        if length <= 0:
            p = geom.centroid().asPoint()
            return [SamplePoint(QgsPointXY(p), 0.0)]

        def add_at(m):
            p = geom.interpolate(m).asPoint()
            pts.append(SamplePoint(QgsPointXY(p), m))

        add_at(0.0)
        if self.distance > 0:
            m = self.distance
            while m < length:
                add_at(m); m += self.distance
        add_at(length)

        if self.preserve_nodes:
            seen = {(round(sp.point.x(),6), round(sp.point.y(),6)) for sp in pts}
            for v in geom.vertices():
                key = (round(v.x(),6), round(v.y(),6))
                if key in seen: continue
                pts.append(SamplePoint(QgsPointXY(v), None))

        pts.sort(key=lambda sp: (float('inf') if sp.kp is None else sp.kp,
                                 round(sp.point.x(),6), round(sp.point.y(),6)))
        uniq, seen = [], set()
        for sp in pts:
            key = (round(sp.point.x(),6), round(sp.point.y(),6))
            if key in seen: continue
            seen.add(key); uniq.append(sp)
        return uniq

    def sample_geometry(self, geom: QgsGeometry) -> List[SamplePoint]:
        if geom.isMultipart():
            all_pts: List[SamplePoint] = []
            for part in geom.constParts():
                all_pts.extend(self._sample_one_line(QgsGeometry(part.clone())))
            all_pts.sort(key=lambda sp: (float('inf') if sp.kp is None else sp.kp,
                                         round(sp.point.x(),6), round(sp.point.y(),6)))
            return all_pts
        return self._sample_one_line(geom)
