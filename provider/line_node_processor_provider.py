from qgis.core import QgsProcessingProvider
from ..algorithms.line_node_processor_algo import LineNodeProcessorAlgorithm

class LineNodeProcessorProvider(QgsProcessingProvider):
    def id(self):
        return "line_node_processor"

    def name(self):
        return "Line Node Processor"

    def longName(self):
        return self.name()

    def loadAlgorithms(self):
        self.addAlgorithm(LineNodeProcessorAlgorithm())
