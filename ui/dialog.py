import os, math
from typing import Optional
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QCheckBox, QFileDialog, QMessageBox, QWidget,
    QGroupBox, QGridLayout, QFormLayout, QSizePolicy, QSpacerItem
)
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsWkbTypes, QgsFeatureRequest, QgsFeature, QgsGeometry,
    QgsPointXY, QgsUnitTypes
)
from qgis.gui import QgsMapLayerComboBox
try:
    from qgis.core import QgsMapLayerProxyModel   # QGIS 3.28 LTR 正確位置
except ImportError:
    from qgis.gui import QgsMapLayerProxyModel    # 後備（少數客製環境）

from ..core.sampling import GeometrySampler
from ..core.assembler import AttributeAssembler
from ..core.elevation import ElevationSampler
from ..core.rounding import round_by_distance
from ..core.azimuth import Azimuth
from ..infra.layer_io import CRSGuard
from ..infra.exporter import Exporter, sanitize_name

WGS84 = QgsCoordinateReferenceSystem('EPSG:4326')

class LineNodeProcessorDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("Line Node Processor")
        self.setMinimumSize(800, 560)
        self.setSizeGripEnabled(True)
        self.setStyleSheet("""
        QGroupBox { margin-top: 8px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 2px 4px 6px 4px; font-weight: 600; }
        QLabel { margin: 0px; }
        """)

        # helper: fixed-width labels to avoid crowding
        self.LABEL_W = 120
        def _L(text: str) -> QLabel:
            lab = QLabel(text)
            lab.setFixedWidth(self.LABEL_W)
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return lab
        self._L = _L

        # ---- Root grid (two columns) ----
        root = QGridLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setHorizontalSpacing(12)
        root.setVerticalSpacing(10)

        # ---- Left: Vector (Line) ----
        grpVec = QGroupBox("Vector (Line)")
        frmVec = QFormLayout(grpVec)
        frmVec.setContentsMargins(8, 8, 8, 8)
        frmVec.setHorizontalSpacing(10)
        frmVec.setVerticalSpacing(8)
        frmVec.setRowWrapPolicy(QFormLayout.DontWrapRows)
        frmVec.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.cmbLine = QgsMapLayerComboBox()
        self.cmbLine.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.cmbLine.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cmbLine.setMinimumContentsLength(18)

        row_ext_vec = QHBoxLayout()
        self.chkExtVec = QCheckBox("Use external file")
        self.btnPickVec = QPushButton("Browse…"); self.btnPickVec.setEnabled(False)
        row_ext_vec.addWidget(self.chkExtVec)
        row_ext_vec.addWidget(self.btnPickVec)
        row_ext_vec.addStretch(1)
        row_ext_vec.setSpacing(8)

        self.cmbGroup = QComboBox()
        self.cmbGroup.addItem("(None)", "")

        frmVec.addRow(self._L("Project line:"), self.cmbLine)
        frmVec.addRow(self._L("External:"), self._wrap(row_ext_vec))
        frmVec.addRow(self._L("Group field:"), self.cmbGroup)

        # ---- Right: Raster (DEM) ----
        grpRas = QGroupBox("Elevation (Raster)")
        frmRas = QFormLayout(grpRas)
        frmRas.setContentsMargins(8, 8, 8, 8)
        frmRas.setHorizontalSpacing(10)
        frmRas.setVerticalSpacing(8)
        frmRas.setRowWrapPolicy(QFormLayout.DontWrapRows)
        frmRas.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.cmbRas = QgsMapLayerComboBox()
        self.cmbRas.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.cmbRas.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cmbRas.setMinimumContentsLength(18)

        row_ext_ras = QHBoxLayout()
        self.chkExtRas = QCheckBox("Use external file")
        self.btnPickRas = QPushButton("Browse…"); self.btnPickRas.setEnabled(False)
        row_ext_ras.addWidget(self.chkExtRas)
        row_ext_ras.addWidget(self.btnPickRas)
        row_ext_ras.addStretch(1)
        row_ext_ras.setSpacing(8)

        self.cmbBand = QComboBox()
        self.cmbBand.addItem("1", 1)

        frmRas.addRow(self._L("Project raster:"), self.cmbRas)
        frmRas.addRow(self._L("External:"), self._wrap(row_ext_ras))
        frmRas.addRow(self._L("DEM band:"), self.cmbBand)

        # ---- Bottom: Sampling / Options ----
        grpOpt = QGroupBox("Sampling / Options")
        frmOpt = QFormLayout(grpOpt)
        frmOpt.setContentsMargins(8, 8, 8, 8)
        frmOpt.setHorizontalSpacing(10)
        frmOpt.setVerticalSpacing(8)
        frmOpt.setRowWrapPolicy(QFormLayout.DontWrapRows)
        frmOpt.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.txtDist = QLineEdit()
        self.txtDist.setPlaceholderText("blank ⇒ vertices only")
        self.txtDist.setClearButtonEnabled(True)

        optRow = QHBoxLayout()
        self.chkKeepVerts = QCheckBox("Preserve vertices"); self.chkKeepVerts.setChecked(True)
        self.chkPreserveAttrs = QCheckBox("Keep attributes"); self.chkPreserveAttrs.setChecked(True)
        self.chkWriteSHP = QCheckBox("Write Shapefile"); self.chkWriteSHP.setChecked(True)
        optRow.setSpacing(14)
        optRow.addWidget(self.chkKeepVerts)
        optRow.addWidget(self.chkPreserveAttrs)
        optRow.addWidget(self.chkWriteSHP)
        optRow.addStretch(1)

        outRow = QHBoxLayout()
        self.txtOut = QLineEdit()
        self.btnOut = QPushButton("Browse…")
        outRow.addWidget(self.txtOut)
        outRow.addWidget(self.btnOut)
        outRow.setSpacing(8)

        frmOpt.addRow(self._L("Distance (m):"), self.txtDist)
        frmOpt.addRow(self._L("Options:"), self._wrap(optRow))
        frmOpt.addRow(self._L("Output folder:"), self._wrap(outRow))

        # ---- Buttons ----
        btnRow = QHBoxLayout()
        self.btnRun = QPushButton("Run")
        self.btnClose = QPushButton("Close")
        btnRow.addStretch(1)
        btnRow.addWidget(self.btnRun)
        btnRow.addWidget(self.btnClose)
        btnRow.setSpacing(10)

        # ---- place widgets to root grid ----
        root.addWidget(grpVec, 0, 0)
        root.addWidget(grpRas, 0, 1)
        root.addWidget(grpOpt, 1, 0, 1, 2)
        root.addLayout(btnRow, 2, 0, 1, 2)
        root.setColumnStretch(0, 1)
        root.setColumnStretch(1, 1)

        # Signals
        self.chkExtVec.toggled.connect(self.on_toggle_ext_vec)
        self.chkExtRas.toggled.connect(self.on_toggle_ext_ras)
        self.btnPickVec.clicked.connect(self.pick_vec)
        self.btnPickRas.clicked.connect(self.pick_ras)
        self.btnOut.clicked.connect(self.pick_out)
        self.btnRun.clicked.connect(self.run_now)
        self.btnClose.clicked.connect(self.close)

        self.cmbLine.layerChanged.connect(self.on_line_layer_changed)
        self.cmbRas.layerChanged.connect(self.on_raster_layer_changed)

        # Project layer change listeners → update dependent combos
        QgsProject.instance().layersAdded.connect(self.on_project_layers_changed)
        QgsProject.instance().layersRemoved.connect(self.on_project_layers_changed)
        QgsProject.instance().layerWasAdded.connect(self.on_project_layers_changed)

        # Initial populate
        self.on_line_layer_changed(self.cmbLine.currentLayer())
        self.on_raster_layer_changed(self.cmbRas.currentLayer())

    # ---- helper to embed QLayout into QFormLayout ----
    def _wrap(self, layout):
        w = QWidget()
        w.setLayout(layout)
        return w

    # ----- project layer changes -----
    def on_project_layers_changed(self, *args, **kwargs):
        if not self.chkExtVec.isChecked():
            self.on_line_layer_changed(self.cmbLine.currentLayer())
        if not self.chkExtRas.isChecked():
            self.on_raster_layer_changed(self.cmbRas.currentLayer())

    # ----- vector layer change => update group dropdown -----
    def on_line_layer_changed(self, layer):
        self.cmbGroup.blockSignals(True)
        self.cmbGroup.clear(); self.cmbGroup.addItem("(None)", "")
        lyr = None
        if self.chkExtVec.isChecked():
            path = self.btnPickVec.property("path")
            if path:
                lyr = QgsVectorLayer(path, os.path.basename(path), "ogr")
        else:
            lyr = layer
        if isinstance(lyr, QgsVectorLayer) and lyr.isValid():
            for f in lyr.fields():
                self.cmbGroup.addItem(f.name(), f.name())
        self.cmbGroup.blockSignals(False)

    # ----- raster layer change => update band dropdown -----
    def on_raster_layer_changed(self, layer):
        self.cmbBand.blockSignals(True)
        self.cmbBand.clear()
        band_count = 0
        rlyr = None
        if self.chkExtRas.isChecked():
            path = self.btnPickRas.property("path")
            if path:
                rlyr = QgsRasterLayer(path, os.path.basename(path))
        else:
            rlyr = layer
        if isinstance(rlyr, QgsRasterLayer) and rlyr.isValid():
            try:
                band_count = rlyr.bandCount()
            except Exception:
                band_count = 1
        if band_count <= 0:
            band_count = 1
        for b in range(1, band_count+1):
            self.cmbBand.addItem(str(b), b)
        self.cmbBand.blockSignals(False)

    # ----- toggle external/project inputs -----
    def on_toggle_ext_vec(self, on):
        self.btnPickVec.setEnabled(on)
        self.cmbLine.setEnabled(not on)
        self.on_line_layer_changed(self.cmbLine.currentLayer())

    def on_toggle_ext_ras(self, on):
        self.btnPickRas.setEnabled(on)
        self.cmbRas.setEnabled(not on)
        self.on_raster_layer_changed(self.cmbRas.currentLayer())

    # ----- pick files -----
    def pick_vec(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select vector file", "",
            "Vector files (*.gpkg *.shp *.geojson *.json *.gml *.dxf);;All files (*)")
        if path:
            self.btnPickVec.setProperty("path", path)
            self.btnPickVec.setText(os.path.basename(path))
            self.on_line_layer_changed(self.cmbLine.currentLayer())

    def pick_ras(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select raster file", "",
            "Raster files (*.tif *.tiff *.img);;All files (*)")
        if path:
            self.btnPickRas.setProperty("path", path)
            self.btnPickRas.setText(os.path.basename(path))
            self.on_raster_layer_changed(self.cmbRas.currentLayer())

    def pick_out(self):
        path = QFileDialog.getExistingDirectory(self, "Select output folder", "")
        if path:
            self.txtOut.setText(path)

    # ----- load layers according to selection -----
    def _load_vector(self):
        if self.chkExtVec.isChecked():
            path = self.btnPickVec.property("path")
            if not path: return None
            v = QgsVectorLayer(path, os.path.basename(path), "ogr")
            return v if (v and v.isValid() and v.geometryType()==QgsWkbTypes.LineGeometry) else None
        else:
            lyr = self.cmbLine.currentLayer()
            return lyr if (isinstance(lyr, QgsVectorLayer) and lyr.geometryType()==QgsWkbTypes.LineGeometry) else None

    def _load_raster(self):
        if self.chkExtRas.isChecked():
            path = self.btnPickRas.property("path")
            if not path: return None
            r = QgsRasterLayer(path, os.path.basename(path))
            return r if (r and r.isValid()) else None
        else:
            lyr = self.cmbRas.currentLayer()
            return lyr if isinstance(lyr, QgsRasterLayer) else None

    # ----- run with new 3D rules -----
    def run_now(self):
        vlyr = self._load_vector()
        if not vlyr or vlyr.geometryType() != QgsWkbTypes.LineGeometry:
            QMessageBox.critical(self, "Error", "Please select a valid LINE vector layer (project or external).")
            return

        out_dir = self.txtOut.text().strip()
        if not out_dir:
            QMessageBox.critical(self, "Error", "Please select an output folder.")
            return

        dist_txt = self.txtDist.text().strip()
        if dist_txt == "":
            distance = 0.0
            keep_vertices = True   # vertices only
            dist_label = "verts"
        else:
            try:
                distance = float(dist_txt)
            except:
                QMessageBox.critical(self, "Error", "Distance must be a number or left blank.")
                return
            if distance < 0:
                QMessageBox.critical(self, "Error", "Distance must be >= 0.")
                return
            keep_vertices = self.chkKeepVerts.isChecked()
            dist_label = (str(int(distance)) if abs(distance - int(distance)) < 1e-9 else str(distance))

        preserve_attrs = self.chkPreserveAttrs.isChecked()
        write_shp = self.chkWriteSHP.isChecked()
        group_field = self.cmbGroup.currentData() or None

        crs = vlyr.crs()
        if CRSGuard.is_geographic(crs) or CRSGuard.map_units_not_meters(crs):
            QMessageBox.critical(self, "Error", "Input layer must be projected in meters (not geographic).")
            return

        rlyr = self._load_raster()
        band = int(self.cmbBand.currentData() or 1)
        if rlyr:
            if CRSGuard.is_geographic(rlyr.crs()) or CRSGuard.map_units_not_meters(rlyr.crs()):
                QMessageBox.critical(self, "Error", "Elevation raster must be projected in meters.")
                return

        try:
            os.makedirs(out_dir, exist_ok=True)
            from qgis.core import QgsCoordinateTransform, QgsProject
            xform_to_wgs84 = QgsCoordinateTransform(crs, WGS84, QgsProject.instance())
            xform_to_raster = None
            if rlyr and rlyr.crs() != crs:
                xform_to_raster = QgsCoordinateTransform(crs, rlyr.crs(), QgsProject.instance())

            elev_sampler = ElevationSampler(rlyr, xform_to_raster, band=band)
            sampler = GeometrySampler(distance, keep_vertices)
            assembler = AttributeAssembler(xform_to_wgs84, preserve_attrs)
            exporter = Exporter(out_dir, write_shp)

            from collections import defaultdict
            group_rows = defaultdict(list)
            group_pts  = defaultdict(list)

            def round_policy(val):
                return round_by_distance(val, distance)

            has_dem = bool(rlyr)

            total = vlyr.featureCount() or 0
            req = QgsFeatureRequest()
            for i, feat in enumerate(vlyr.getFeatures(req)):
                if i % 50 == 0:
                    self.iface.mainWindow().statusBar().showMessage(f"Processing {i}/{total}…")

                geom = feat.geometry()
                if not geom or geom.isEmpty():
                    continue
                if vlyr.wkbType() and vlyr.geometryType() != QgsWkbTypes.LineGeometry:
                    continue

                if group_field and group_field in feat.fields().names():
                    gval = str(feat[group_field])
                else:
                    gval = f"feat_{feat.id()}"
                safe = sanitize_name(gval)

                parts = [geom] if not geom.isMultipart() else [QgsGeometry(p.clone()) for p in geom.constParts()]
                for part in parts:
                    # sample points with KP (lineLocatePoint)
                    samples = sampler.sample_geometry_with_kp(part)

                    prev_xy = None
                    prev_elev = None
                    total_3d = 0.0 if has_dem else None

                    for xy, kp in samples:
                        elev = elev_sampler.sample(xy) if has_dem else None

                        d2d = None; d3d = None
                        if prev_xy is not None:
                            dx = xy.x() - prev_xy.x()
                            dy = xy.y() - prev_xy.y()
                            d2d = (dx*dx + dy*dy) ** 0.5

                            if has_dem:
                                # 若任一端 elevation 缺值 ⇒ 用 2D 代替該段 3D；否則真 3D
                                if (prev_elev is None) or (elev is None):
                                    d3d = d2d
                                else:
                                    dz = elev - prev_elev
                                    d3d = (d2d*d2d + dz*dz) ** 0.5

                        az = Azimuth.compute(prev_xy, xy)

                        d2d_r = round_policy(d2d) if d2d is not None else None
                        d3d_r = round_policy(d3d) if d3d is not None else None

                        # 保障 3D >= 2D
                        if has_dem and d2d_r is not None and d3d_r is not None and d3d_r < d2d_r:
                            d3d_r = d2d_r

                        # 累積 3D：只有 DEM 時才累積；缺值段已等同 2D
                        if has_dem and d3d_r is not None:
                            total_3d = (total_3d or 0.0) + d3d_r

                        row = assembler.assemble_row(
                            xy=xy,
                            elev=elev if has_dem else None,
                            d2d=d2d_r,
                            d3d=d3d_r if has_dem else None,
                            azimuth=az,
                            kp=round_policy(kp) if kp is not None else None,
                            total3d=round_policy(total_3d) if (has_dem and total_3d) else None,
                            feature=feat, group_field=group_field, group_value=gval
                        )
                        group_rows[safe].append(row)
                        group_pts[safe].append((xy, row))

                        prev_xy = xy
                        prev_elev = elev if has_dem else None

            # write outputs
            for g, rows in group_rows.items():
                exporter.write_csv(g, rows, dist_label)
                exporter.write_point_shp(g, group_pts[g], rows, crs, dist_label)

            QMessageBox.information(self, "Done", f"Export finished to:\n{out_dir}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Processing failed:\n{e}")
