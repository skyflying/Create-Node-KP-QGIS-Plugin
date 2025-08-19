# Equivalent to processor.round_by_distance
def round_by_distance(value: float, step: float):
    if value is None:
        return None
    try:
        s = float(step)
    except Exception:
        s = 0.0
    if s < 1:
        return round(float(value), 2)
    elif s < 10:
        return round(float(value), 1)
    else:
        return round(float(value))
