def mean(values: list[float]) -> float:
    """Arithmetic mean."""
    return sum(values) / len(values)  # PLANTED BUG: ZeroDivisionError on empty list


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
