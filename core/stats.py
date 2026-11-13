"""Two small tests, standard library only."""
from math import comb, sqrt


def wilson(k: int, n: int, z: float = 1.96):
    """95% Wilson interval for a proportion k/n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar(a_right, b_right):
    """Exact two-sided McNemar test on paired right/wrong lists.

    Only items where the two versions disagree count: b = A right & B wrong,
    c = A wrong & B right. Returns (b, c, p).
    """
    b = sum(1 for x, y in zip(a_right, b_right) if x and not y)
    c = sum(1 for x, y in zip(a_right, b_right) if y and not x)
    n = b + c
    if n == 0:
        return b, c, 1.0
    p = 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return b, c, min(1.0, p)
