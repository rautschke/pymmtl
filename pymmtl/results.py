"""Parser for the solver's ``<base>.result`` output file.

Extracts the per-unit-length matrices and derived transmission-line parameters
written by ``nmmtl_output_*.cpp``: electrostatic induction (capacitance) ``C``,
inductance ``L``, DC resistance ``Rdc``, characteristic impedance, effective
dielectric constant, propagation velocity/delay (with odd/even for 2-conductor
lines), and forward/backward crosstalk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

# B( ::a , ::b )=  value   /  L(...)=  /  Rdc(...)=
_MATRIX_RE = re.compile(
    r"^(B|L|Rdc)\(\s*::(\S+)\s*,\s*::(\S+)\s*\)=\s*(\S+)"
)
# FXT( ::a , ::b )= ratio =  db dB
_XTALK_RE = re.compile(
    r"^(FXT|BXT)\(\s*::(\S+)\s*,\s*::(\S+)\s*\)=\s*(\S+)\s*=\s*(\S+)\s*dB"
)
_PERLINE_RE = re.compile(r"For Signal Line\s+::(\S+)=\s*(\S+)")
_ODD_RE = re.compile(r"^\s*odd=\s*(\S+)")
_EVEN_RE = re.compile(r"^\s*even=\s*(\S+)")
_ASYM_RE = re.compile(r"([0-9.]+)%\s*\(max\),\s*([0-9.]+)%\s*\(average\)")


@dataclass
class Results:
    names: list[str] = field(default_factory=list)          # signal order
    C: np.ndarray | None = None                              # F/m  (B matrix)
    L: np.ndarray | None = None                              # H/m
    Rdc: np.ndarray | None = None                            # ohm/m
    impedance: dict[str, float] = field(default_factory=dict)
    eps_eff: dict[str, float] = field(default_factory=dict)
    velocity: dict[str, float] = field(default_factory=dict)
    delay: dict[str, float] = field(default_factory=dict)
    odd_even: dict[str, tuple[float, float]] = field(default_factory=dict)
    fxt: dict[tuple[str, str], tuple[float, float]] = field(default_factory=dict)
    bxt: dict[tuple[str, str], tuple[float, float]] = field(default_factory=dict)
    asymmetry: dict[str, tuple[float, float]] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    raw: str = ""

    @property
    def n(self) -> int:
        return len(self.names)


def _float(token: str) -> float:
    t = token.strip().lower()
    if t in ("infinite", "inf", "+inf"):
        return float("inf")
    if t == "-inf":
        return float("-inf")
    try:
        return float(token)
    except ValueError:
        return float("nan")


def loads(text: str) -> Results:
    res = Results(raw=text)
    cmatrix: dict[tuple[str, str], float] = {}
    lmatrix: dict[tuple[str, str], float] = {}
    rmatrix: dict[tuple[str, str], float] = {}
    order: list[str] = []  # first-seen signal order

    section = None  # which per-line scalar dict to fill

    for line in text.splitlines():
        s = line.strip()

        # --- header / meta ---
        if s.startswith("Number of Signal Lines"):
            res.meta["num_signals"] = int(s.split("=")[1])
        elif s.startswith("Number of Ground Planes"):
            res.meta["num_ground_planes"] = int(s.split("=")[1])
        elif s.startswith("Number of Ground Wires"):
            res.meta["num_ground_wires"] = int(s.split("=")[1])
        elif s.startswith("Coupling Length"):
            res.meta["coupling_length"] = _float(s.split("=")[1].split()[0])
        elif s.startswith("Rise Time"):
            res.meta["rise_time"] = _float(s.split("=")[1].split()[0])
        elif s.startswith("Contour (conductor) segments"):
            res.meta["cseg"] = int(s.split("=")[1])
        elif s.startswith("Ground Plane/Dielectric segments"):
            res.meta["dseg"] = int(s.split("=")[1])

        # --- section switches for per-line scalars ---
        if s.startswith("Characteristic Impedance Odd/Even"):
            section = ("odd_even", "impedance")
            continue
        if s.startswith("Characteristic Impedance"):
            section = ("scalar", res.impedance)
            continue
        if s.startswith("Effective Dielectric Constant"):
            section = ("scalar", res.eps_eff)
            continue
        if s.startswith("Propagation Velocity Odd/Even"):
            section = ("odd_even", "velocity")
            continue
        if s.startswith("Propagation Velocity"):
            section = ("scalar", res.velocity)
            continue
        if s.startswith("Propagation Delay Odd/Even"):
            section = ("odd_even", "delay")
            continue
        if s.startswith("Propagation Delay"):
            section = ("scalar", res.delay)
            continue

        # --- matrices ---
        m = _MATRIX_RE.match(s)
        if m:
            tag, a, b, val = m.group(1), m.group(2), m.group(3), _float(m.group(4))
            for nm in (a, b):
                if nm not in order:
                    order.append(nm)
            target = {"B": cmatrix, "L": lmatrix, "Rdc": rmatrix}[tag]
            target[(a, b)] = val
            continue

        # --- crosstalk ---
        m = _XTALK_RE.match(s)
        if m:
            tag, a, b, ratio, db = m.groups()
            entry = (_float(ratio), _float(db) if db not in ("infinite", "-inf") else float("-inf"))
            (res.fxt if tag == "FXT" else res.bxt)[(a, b)] = entry
            continue

        # --- per-line scalars / odd-even ---
        if section is not None:
            mo = _ODD_RE.match(line)
            if mo and section[0] == "odd_even":
                key = section[1]
                prev = res.odd_even.get(key, (float("nan"), float("nan")))
                res.odd_even[key] = (_float(mo.group(1)), prev[1])
                continue
            me = _EVEN_RE.match(line)
            if me and section[0] == "odd_even":
                key = section[1]
                prev = res.odd_even.get(key, (float("nan"), float("nan")))
                res.odd_even[key] = (prev[0], _float(me.group(1)))
                continue
            mp = _PERLINE_RE.search(line)
            if mp and section[0] == "scalar":
                section[1][mp.group(1)] = _float(mp.group(2))
                continue

    # asymmetry ratios are context-sensitive (heading then value) ----------
    _parse_asymmetry(text, res)

    # establish signal order: prefer impedance per-line order, else matrix order
    if res.impedance:
        res.names = list(res.impedance.keys())
    else:
        res.names = order
    # ensure all matrix names are represented
    for nm in order:
        if nm not in res.names:
            res.names.append(nm)

    res.C = _assemble(cmatrix, res.names)
    res.L = _assemble(lmatrix, res.names)
    res.Rdc = _assemble(rmatrix, res.names)
    return res


def _parse_asymmetry(text: str, res: Results) -> None:
    context = None
    for line in text.splitlines():
        if "Asymmetry ratio for inductance" in line:
            context = "inductance"
        elif "Asymmetry ratio for electrostatic" in line:
            context = "capacitance"
        else:
            m = _ASYM_RE.search(line)
            if m and context:
                res.asymmetry[context] = (_float(m.group(1)), _float(m.group(2)))
                context = None


def _assemble(entries: dict[tuple[str, str], float], names: list[str]):
    if not entries:
        return None
    n = len(names)
    idx = {nm: i for i, nm in enumerate(names)}
    mat = np.full((n, n), np.nan)
    for (a, b), val in entries.items():
        if a in idx and b in idx:
            mat[idx[a], idx[b]] = val
    return mat


def load(path) -> Results:
    with open(path, "r") as fh:
        return loads(fh.read())
