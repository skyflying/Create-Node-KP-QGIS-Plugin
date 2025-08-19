import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from .ui.dialog import LineNodeProcessorDialog

class LineNodeProcessorPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dlg = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'icon.ico')
        self.action = QAction(QIcon(icon_path), "Line Node Processor…", self.iface.mainWindow())
        self.action.triggered.connect(self.run_dialog)
        self.iface.addPluginToMenu("&Line Node Processor", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("&Line Node Processor", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dlg:
            self.dlg.deleteLater()
            self.dlg = None

    def run_dialog(self):
        if not self.dlg:
            self.dlg = LineNodeProcessorDialog(self.iface)
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()
