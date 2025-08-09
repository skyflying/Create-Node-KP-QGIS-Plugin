from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterRasterLayer,
    QgsProcessingParameterField, QgsProcessingParameterDistance, QgsProcessingParameterBoolean,
    QgsProcessingParameterFolderDestination, QgsProcessingOutputFolder,
    QgsProcessingContext, QgsProcessingFeedback, QgsFeatureRequest, QgsCoordinateTransform,
    QgsProject, QgsCoordinateReferenceSystem, QgsWkbTypes
)
from qgis.PyQt.QtCore import QCoreApplication
from typing import Optional, List
import os

from ..core.rounding import RoundingPolicy
from ..core.azimuth import Azimuth
from ..core.sampling import GeometrySampler, SamplePoint
from ..core.elevation import ElevationSampler
from ..core.assembler import AttributeAssembler
from ..infra.layer_io import CRSGuard
from ..infra.exporter import Exporter, sanitize_name

WGS84 = QgsCoordinateReferenceSystem('EPSG:4326')

class LineNodeProcessorAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    ELEVATION = 'ELEVATION'
    GROUP_FIELD = 'GROUP_FIELD'
    DISTANCE = 'DISTANCE'
    KEEP_VERTICES = 'KEEP_VERTICES'
    PRESERVE_ATTRS = 'PRESERVE_ATTRS'
    OUTPUT_DIR = 'OUTPUT_DIR'
    WRITE_SHP = 'WRITE_SHP'

    def tr(self, s): return QCoreApplication.translate('LineNodeProcessorAlgorithm', s)
    def createInstance(self): return LineNodeProcessorAlgorithm()
    def name(self): return 'line_node_processor'
    def displayName(self): return self.tr('Line Node Processor')
    def group(self): return self.tr('Line Tools')
    def groupId(self): return 'line_tools'
    def shortHelpString(self):
        return self.tr('Sample points along line features at a fixed distance (meters). '
                       'Optionally keep original vertices, compute KP/azimuth/2D+3D lengths, '
                       'and sample elevation from a raster. '
                       'Input vector must be in a projected CRS with meter units (geographic CRS is blocked).')

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr('Input line layer'), [QgsProcessing.TypeVectorLine]
        ))
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.ELEVATION, self.tr('Elevation raster (optional)'), optional=True
        ))
        self.addParameter(QgsProcessingParameterField(
            self.GROUP_FIELD, self.tr('Group field (optional)'), parentLayerParameterName=self.INPUT, optional=True
        ))
        self.addParameter(QgsProcessingParameterDistance(
            self.DISTANCE, self.tr('Fixed sampling distance (m)'), defaultValue=10.0,
            parentParameterName=self.INPUT, minValue=0.000001
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.KEEP_VERTICES, self.tr('Preserve original vertices'), defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.PRESERVE_ATTRS, self.tr('Preserve original attributes'), defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.WRITE_SHP, self.tr('Also write point Shapefile per group'), defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.OUTPUT_DIR, self.tr('Output folder')
        ))
        self.addOutput(QgsProcessingOutputFolder(self.OUTPUT_DIR, self.tr('Output folder')))

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if not source:
            raise Exception('Invalid input line layer.')

        crs = source.sourceCrs()
        if CRSGuard.is_geographic(crs):
            raise Exception('Input CRS is geographic. Please reproject to a projected CRS (meters).')
        if CRSGuard.map_units_not_meters(crs):
            raise Exception('Input CRS map units are not meters. Please reproject to a CRS in meters.')

        group_field = self.parameterAsString(parameters, self.GROUP_FIELD, context)
        distance = self.parameterAsDouble(parameters, self.DISTANCE, context)
        keep_vertices = self.parameterAsBool(parameters, self.KEEP_VERTICES, context)
        preserve_attrs = self.parameterAsBool(parameters, self.PRESERVE_ATTRS, context)
        raster = self.parameterAsRasterLayer(parameters, self.ELEVATION, context)
        write_shp = self.parameterAsBool(parameters, self.WRITE_SHP, context)
        out_dir = self.parameterAsFile(parameters, self.OUTPUT_DIR, context)
        if not out_dir:
            raise Exception('Output folder is required.')
        os.makedirs(out_dir, exist_ok=True)

        xform_to_wgs84 = QgsCoordinateTransform(crs, WGS84, QgsProject.instance())
        xform_to_raster = None
        if raster and raster.crs() != crs:
            xform_to_raster = QgsCoordinateTransform(crs, raster.crs(), QgsProject.instance())

        elev_sampler = ElevationSampler(raster, xform_to_raster)
        sampler = GeometrySampler(distance, keep_vertices)
        assembler = AttributeAssembler(xform_to_wgs84, preserve_attrs)
        exporter = Exporter(out_dir, write_shp)
        rounding = RoundingPolicy(distance)

        group_rows = {}
        group_pts = {}

        total = source.featureCount() or 0
        for i, feat in enumerate(source.getFeatures(QgsFeatureRequest())):
            if feedback.isCanceled(): break
            geom = feat.geometry()
            if not geom or geom.isEmpty(): continue
            if QgsWkbTypes.geometryType(geom.wkbType()) != QgsWkbTypes.LineGeometry:
                continue

            if group_field and group_field in feat.fields().names():
                group_val = str(feat[group_field])
            else:
                group_val = f"feat_{feat.id()}"
            safe_group = sanitize_name(group_val)
            group_rows.setdefault(safe_group, [])
            group_pts.setdefault(safe_group, [])

            points: List[SamplePoint] = sampler.sample_geometry(geom)

            prev_xy = None
            prev_elev = None
            total_3d = 0.0

            for sp in points:
                xy = sp.point
                elev = elev_sampler.sample(xy) if elev_sampler else None

                d2d = None
                d3d = None
                if prev_xy is not None:
                    dx = xy.x() - prev_xy.x()
                    dy = xy.y() - prev_xy.y()
                    d2d = (dx*dx + dy*dy) ** 0.5
                    if elev is not None and prev_elev is not None:
                        dz = elev - prev_elev
                        d3d = (d2d*d2d + dz*dz) ** 0.5

                az = Azimuth.compute(prev_xy, xy)

                # 四捨五入（相同精度），並確保 3D >= 2D
                d2d_r = rounding.round(d2d) if d2d is not None else None
                d3d_r = rounding.round(d3d) if d3d is not None else None
                if d2d_r is not None and d3d_r is not None and d3d_r < d2d_r:
                    d3d_r = d2d_r

                if d3d_r is not None:
                    total_3d += d3d_r

                row = assembler.assemble_row(
                    xy=xy, elev=elev, d2d=d2d_r, d3d=d3d_r, azimuth=az,
                    kp=sp.kp, total3d=rounding.round(total_3d) if total_3d else None,
                    feature=feat, group_field=group_field, group_value=group_val
                )
                group_rows[safe_group].append(row)
                group_pts[safe_group].append((xy, row))

                prev_xy = xy
                prev_elev = elev

            if total and (i % 25 == 0):
                feedback.setProgress(100 * (i + 1) / total)

        distance_label = int(distance) if abs(distance - int(distance)) < 1e-9 else distance
        for g, rows in group_rows.items():
            exporter.write_csv(g, rows, distance_label)
            if write_shp:
                exporter.write_point_shp(g, group_pts[g], rows, crs, distance_label)

        return { self.OUTPUT_DIR: out_dir }
