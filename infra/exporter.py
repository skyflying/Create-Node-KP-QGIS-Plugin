import os, re, csv, datetime
from typing import List, Tuple, Dict, Any
from qgis.core import (
    QgsFields, QgsField, QgsFeature, QgsWkbTypes, QgsGeometry, QgsPointXY,
    QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsProject
)
from qgis.PyQt.QtCore import QVariant, QDate, QDateTime, QTime

def sanitize_name(name: str) -> str:
    safe = re.sub(r'[^0-9a-zA-Z_]+', '_', str(name).strip())
    return safe or "group"

def qvariant_type_of(value):
    if isinstance(value, (int,)): return QVariant.Int
    if isinstance(value, (float,)): return QVariant.Double
    if isinstance(value, (bool,)): return QVariant.Bool
    if isinstance(value, (datetime.date, QDate)): return QVariant.Date
    if isinstance(value, (datetime.datetime, QDateTime)): return QVariant.DateTime
    if isinstance(value, (datetime.time, QTime)): return QVariant.Time
    return QVariant.String

def to_csv_cell(v):
    if isinstance(v, QDate): return v.toString("yyyy-MM-dd")
    if isinstance(v, QDateTime): return v.toString("yyyy-MM-ddTHH:mm:ss")
    if isinstance(v, QTime): return v.toString("HH:mm:ss")
    if isinstance(v, datetime.date): return v.strftime("%Y-%m-%d")
    if isinstance(v, datetime.datetime): return v.strftime("%Y-%m-%dT%H:%M:%S")
    if isinstance(v, datetime.time): return v.strftime("%H:%M:%S")
    return "" if v is None else str(v)

class Exporter:
    def __init__(self, out_dir: str, write_shp: bool):
        self.out_dir = out_dir
        self.write_shp = write_shp

    def _csv_path(self, group: str, distance_label) -> str:
        return os.path.join(self.out_dir, f"{group}_{distance_label}_node.csv")

    def _shp_path(self, group: str, distance_label) -> str:
        return os.path.join(self.out_dir, f"{group}_{distance_label}_node.shp")

    def write_csv(self, group: str, rows: List[Dict[str, Any]], distance_label):
        if not rows: return
        path = self._csv_path(group, distance_label)
        fieldnames = list(rows[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(fieldnames)
            for r in rows:
                w.writerow([to_csv_cell(r.get(k)) for k in fieldnames])

    def write_point_shp(self, group: str, pts: List[Tuple[QgsPointXY, Dict[str, Any]]],
                        rows: List[Dict[str, Any]], crs: QgsCoordinateReferenceSystem, distance_label):
        if not self.write_shp or not pts: return
        path = self._shp_path(group, distance_label)

        header = list(rows[0].keys())
        fields = QgsFields()
        sample = rows[0]
        for h in header:
            fields.append(QgsField(h, qvariant_type_of(sample.get(h))))

        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "ESRI Shapefile"
        opts.fileEncoding = "UTF-8"
        opts.layerName = f"{group}_{distance_label}_node"

        writer = QgsVectorFileWriter.create(
            path, fields, QgsWkbTypes.Point, crs, QgsProject.instance().transformContext(), opts
        )
        del writer  # ensure file exists

        writer = QgsVectorFileWriter(path, "UTF-8", fields, QgsWkbTypes.Point, crs, "ESRI Shapefile")
        if writer.hasError() != QgsVectorFileWriter.NoError:
            return

        for (pt, row) in pts:
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(pt))
            attrs = []
            for h in header:
                v = row.get(h)
                if isinstance(v, str) and len(v) > 254: v = v[:254]
                attrs.append(v)
            feat.setAttributes(attrs)
            writer.addFeature(feat)

        del writer
