class RoundingPolicy:
    """Round values based on step magnitude."""
    def __init__(self, step: float):
        self.step = float(step) if step else 0.0
        if self.step >= 1000: self.decimals = 1
        elif self.step >= 100: self.decimals = 2
        elif self.step >= 10: self.decimals = 3
        else: self.decimals = 4
    def round(self, value):
        if value is None: return None
        try: return round(float(value), self.decimals)
        except Exception: return value
