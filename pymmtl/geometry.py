"""Per-conductor cross-sectional geometry (area and circumference).

Used by the HSPICE W-element export to compute DC and skin-effect resistance,
mirroring ``nmmtl_dc_resistance.cpp`` (rectangle ``w*h``, circle ``pi*r^2``,
polygon via the shoelace formula).
"""

from __future__ import annotations

import math

from pymmtl.model import ResolvedConductor


def conductor_area(c: ResolvedConductor) -> float:
    """Cross-sectional area in m^2."""
    if c.shape == "rectangle":
        return abs((c.x1 - c.x0) * (c.y1 - c.y0))
    if c.shape == "circle":
        return math.pi * c.radius * c.radius
    return _polygon_area(c.points)


def conductor_circumference(c: ResolvedConductor) -> float:
    """Perimeter in m."""
    if c.shape == "rectangle":
        return 2.0 * (abs(c.x1 - c.x0) + abs(c.y1 - c.y0))
    if c.shape == "circle":
        return 2.0 * math.pi * c.radius
    return _polygon_perimeter(c.points)


def _polygon_area(points: list[tuple[float, float]]) -> float:
    n = len(points)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return abs(s) * 0.5


def _polygon_perimeter(points: list[tuple[float, float]]) -> float:
    n = len(points)
    if n < 2:
        return 0.0
    p = 0.0
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        p += math.hypot(x1 - x0, y1 - y0)
    return p
