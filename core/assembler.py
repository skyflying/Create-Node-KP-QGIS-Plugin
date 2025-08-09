from typing import Dict, Any, Optional
from qgis.core import QgsPointXY, QgsCoordinateTransform, QgsFeature

class AttributeAssembler:
    def __init__(self, xform_to_wgs84: QgsCoordinateTransform, preserve_attrs: bool):
        self.to_wgs84 = xform_to_wgs84
        self.preserve_attrs = preserve_attrs
    def assemble_row(self, xy: QgsPointXY, elev, d2d, d3d, azimuth, kp, total3d,
                     feature: QgsFeature, group_field: Optional[str], group_value: str) -> Dict[str, Any]:
        ll = self.to_wgs84.transform(xy)
        row = {
            "Longitude": ll.x(), "Latitude": ll.y(),
            "Easting": xy.x(), "Northing": xy.y(),
            "Elevation": elev, "Distance": d2d, "Length_3D": d3d,
            "Azimuth": azimuth, "KP": kp, "Total_3D_Length": total3d,
        }
        if group_field: row[group_field] = group_value
        else: row["Group"] = group_value
        if self.preserve_attrs:
            for f in feature.fields():
                name = f.name()
                if name in row: row[f"attr_{name}"] = feature[name]
                else: row[name] = feature[name]
        return row
