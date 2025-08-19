from typing import Optional, Any
from qgis.core import QgsRasterLayer, QgsPointXY

class ElevationSampler:
    def __init__(self, raster: Optional[QgsRasterLayer], xform_to_raster, band: int = 1):
        self.raster = raster
        self.provider = raster.dataProvider() if raster else None
        self.xform = xform_to_raster
        self.band = int(band or 1)
        try:
            self.nodata = self.provider.sourceNoDataValue(self.band) if self.provider else None
        except Exception:
            self.nodata = None

    def _norm(self, res: Any):
        ok = True; val = None
        if isinstance(res, tuple) and len(res)==2 and isinstance(res[0], (bool,int)):
            ok = bool(res[0]); val = res[1]
        else:
            val = res
        if not ok: return None
        if isinstance(val, (list, tuple)) and val:
            val = val[0]
        try:
            v = float(val)
        except Exception:
            return None
        if v != v: return None  # NaN
        if self.nodata is not None and v == self.nodata:
            return None
        return v

    def sample(self, xy: QgsPointXY):
        if not self.provider: return None
        try:
            pt = self.xform.transform(xy) if self.xform else xy
            return self._norm(self.provider.sample(pt, self.band))
        except Exception:
            return None
