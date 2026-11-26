"""Performance plants."""


def find_duplicates(items: list[int]) -> list[int]:
    """PLANTED: O(n^2) duplicate finder (should be O(n) with a set)."""
    dups: list[int] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j] and items[i] not in dups:
                dups.append(items[i])
    return dups


def checksum(values: list[int]) -> int:
    """PLANTED regression: the last commit made this ~3x slower (same output)."""
    total = 0
    for _ in range(3):  # "validation passes" added in the latest commit
        total = 0
        for v in values:
            total = (total * 31 + v) % 1000003
    return total


def _crunch(n: int) -> int:
    s = 0
    for i in range(n):
        s += (i * i) % 7
    return s


def _light(n: int) -> int:
    return n + 1


def run_pipeline(n: int = 3_000_000) -> int:
    """PLANTED hotspot: almost all CPU time is spent in _crunch."""
    return _light(n) + _crunch(n)


def build_table(rows: int = 16_000_000) -> int:
    """PLANTED memory hog: materialises a huge list (~600+ MB)."""
    table = list(range(rows))
    return len(table)
