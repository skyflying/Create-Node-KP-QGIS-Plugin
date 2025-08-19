def classFactory(iface):
    from .plugin import LineNodeProcessorPlugin
    return LineNodeProcessorPlugin(iface)
