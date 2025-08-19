from qgis.core import QgsCoordinateReferenceSystem, QgsUnitTypes
class CRSGuard:
    @staticmethod
    def is_geographic(crs: 'QgsCoordinateReferenceSystem') -> bool:
        return crs.isGeographic()
    @staticmethod
    def map_units_not_meters(crs: 'QgsCoordinateReferenceSystem') -> bool:
        return crs.mapUnits() != QgsUnitTypes.DistanceMeters
