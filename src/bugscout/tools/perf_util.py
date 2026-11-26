"""Shared big-O helpers."""
from __future__ import annotations

ORDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"]


def norm_big_o(s: str) -> str:
    s = s.strip().replace(" ", "").replace("**", "^").replace("²", "^2").replace("³", "^3")
    table = {"O(1)": "O(1)", "O(logn)": "O(log n)", "O(n)": "O(n)", "O(nlogn)": "O(n log n)", "O(n^2)": "O(n^2)",
             "O(n^3)": "O(n^3)", "O(2^n)": "O(2^n)"}
    return table.get(s, s)


def big_o_rank(s: str) -> int:
    n = norm_big_o(s)
    return ORDER.index(n) if n in ORDER else -1
