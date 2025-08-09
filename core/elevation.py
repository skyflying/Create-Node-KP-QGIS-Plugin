import math
from typing import Optional, Tuple, Any
from qgis.core import QgsRasterLayer, QgsPointXY

class ElevationSampler:
    def __init__(self, raster: Optional[QgsRasterLayer], xform_to_raster, band: int = 1):
        self.raster = raster
        self.provider = raster.dataProvider() if raster else None
        self.xform = xform_to_raster
        self.band = band
        try:
            self.nodata = self.provider.sourceNoDataValue(self.band) if self.provider else None
        except Exception:
            self.nodata = None

    def _parse_value(self, res: Any):
        # 支援多種回傳型態
        ok = True
        val = None
        if isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], (bool, int)):
            ok = bool(res[0]); val = res[1]
        else:
            val = res
        if not ok:
            return None
        if isinstance(val, (list, tuple)) and len(val) > 0:
            val = val[0]
        try:
            v = float(val)
        except Exception:
            return None
        if v != v:  # NaN
            return None
        if self.nodata is not None and v == self.nodata:
            return None
        return v

    def sample(self, xy: QgsPointXY):
        if not self.provider:
            return None
        try:
            pt = self.xform.transform(xy) if self.xform else xy
            res = self.provider.sample(pt, self.band)
            return self._parse_value(res)
        except Exception:
            return None
