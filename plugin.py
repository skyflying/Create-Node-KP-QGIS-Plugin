from qgis.core import QgsApplication
from .provider.line_node_processor_provider import LineNodeProcessorProvider

class LineNodeProcessorPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        self.provider = LineNodeProcessorProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
