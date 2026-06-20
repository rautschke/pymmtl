"""Iterate a conductor width to hit a target characteristic impedance.

Reproduces TNT's "Iterate" feature: with all other parameters fixed, adjust a
conductor group's width until the characteristic impedance of a chosen signal
line reaches a target value.

The impedance-vs-width relation is monotonic in practice; we bracket a sign
change of ``Z0(width) - target`` and refine with Brent's method (SciPy if
available) or bisection.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from pymmtl import solver
from pymmtl.model import CONDUCTOR_KINDS, CrossSection

# width-like attribute for each conductor kind
_WIDTH_ATTR = {
    "rectangle_conductors": "width",
    "circle_conductors": "diameter",
    "trapezoid_conductors": "bottom_width",
}


@dataclass
class IterateResult:
    width: float
    impedance: float
    iterations: int
    converged: bool
    history: list[tuple[float, float]]


def iterate_width(
    cs: CrossSection,
    group: str,
    target: float,
    *,
    conductor_index: int = 0,
    width_attr: str | None = None,
    bracket: tuple[float, float] | None = None,
    tol: float = 1e-3,
    max_iter: int = 40,
) -> IterateResult:
    """Find the width of ``group`` giving ``target`` ohms on the chosen signal."""
    el = cs.find_group(group)
    if el is None or el.kind not in CONDUCTOR_KINDS:
        raise KeyError(f"{group!r} is not a conductor group")
    attr = width_attr or _WIDTH_ATTR[el.kind]
    signal = cs.signal_name_for(group, conductor_index)

    history: list[tuple[float, float]] = []

    def z0(width: float) -> float:
        model = copy.deepcopy(cs)
        setattr(model.find_group(group), attr, width)
        out = solver.run(model)
        value = out.results.impedance.get(signal, float("nan"))
        history.append((width, value))
        return value

    def f(width: float) -> float:
        return z0(width) - target

    w0 = float(getattr(el, attr)) or 1.0
    lo, hi = bracket if bracket else _auto_bracket(f, w0)

    flo, fhi = f(lo), f(hi)
    if flo == 0.0:
        return IterateResult(lo, target, len(history), True, history)
    if fhi == 0.0:
        return IterateResult(hi, target, len(history), True, history)
    if flo * fhi > 0:
        # no sign change found; return the closer endpoint
        best = lo if abs(flo) < abs(fhi) else hi
        return IterateResult(best, f(best) + target, len(history), False, history)

    width = _solve(f, lo, hi, flo, fhi, tol, max_iter)
    return IterateResult(width, f(width) + target, len(history),
                         True, history)


def _auto_bracket(f, w0: float, grow: float = 1.6, steps: int = 12):
    """Expand a bracket outward from ``w0`` until ``f`` changes sign."""
    lo = w0 / grow
    hi = w0 * grow
    flo, fhi = f(lo), f(hi)
    for _ in range(steps):
        if flo * fhi <= 0:
            return lo, hi
        lo /= grow
        hi *= grow
        flo, fhi = f(lo), f(hi)
    return lo, hi


def _solve(f, lo, hi, flo, fhi, tol, max_iter) -> float:
    try:
        from scipy.optimize import brentq

        return float(brentq(f, lo, hi, xtol=tol * max(abs(lo), abs(hi), 1.0),
                            maxiter=max_iter))
    except Exception:
        pass
    # bisection fallback
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(fmid) <= tol or (hi - lo) <= tol * max(abs(mid), 1.0):
            return mid
        if flo * fmid < 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)
