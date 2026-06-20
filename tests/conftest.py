"""Shared pytest fixtures and helpers for the pymmtl test suite."""

from __future__ import annotations

import glob
import math
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(ROOT, "examples")
GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")


def example_files() -> list[str]:
    return sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*.xsctn")))


def example_names() -> list[str]:
    return [os.path.basename(f)[:-6] for f in example_files()]


@pytest.fixture(params=example_names())
def example(request) -> str:
    return request.param


def golden_result(name: str) -> str:
    return os.path.join(GOLDEN_DIR, f"{name}.result")


def golden_stdout(name: str) -> str:
    return os.path.join(GOLDEN_DIR, f"{name}.stdout")


def example_path(name: str) -> str:
    return os.path.join(EXAMPLES_DIR, f"{name}.xsctn")


def num_eq(a, b, rtol=1e-4, atol=1e-12) -> bool:
    """NaN-aware approximate equality (the solver legitimately emits NaN)."""
    if a is None and b is None:
        return True
    if (a != a) and (b != b):  # both NaN
        return True
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= atol + rtol * max(abs(a), abs(b))


# --- parse the binary's stdout geometry dump (for layout validation) ------- #
_NUM = r"([-+0-9.eE]+)"
_DIEL_RE = re.compile(
    r"^\s*\(%s,%s\)\s*-\s*\(%s,%s\)\s*permittivity:\s*%s" % (_NUM, _NUM, _NUM, _NUM, _NUM)
)
_COND_RE = re.compile(
    r"^(\S+)\s+\(%s,%s\)\s*-\s*\(%s,%s\)\s*conductivity:\s*%s\s*type:\s*(\S)"
    % (_NUM, _NUM, _NUM, _NUM, _NUM)
)
_PTS_RE = re.compile(r"\(%s,%s\)" % (_NUM, _NUM))


def parse_geometry_dump(path: str):
    """Return (dielectrics, conductors) parsed from a solver stdout dump."""
    diel = []
    cond = {}
    section = None
    last = None
    with open(path) as fh:
        for line in fh.read().splitlines():
            if "---- Dielectrics" in line:
                section = "d"
                continue
            if "---- Conductors" in line:
                section = "c"
                continue
            if "---- GroundWires" in line:
                section = "g"
                continue
            if section == "d":
                m = _DIEL_RE.match(line)
                if m:
                    diel.append(tuple(float(x) for x in m.groups()))
            elif section == "c":
                m = _COND_RE.match(line)
                if m:
                    last = m.group(1)
                    cond[last] = {
                        "type": m.group(7),
                        "hdr": tuple(float(x) for x in m.groups()[1:6]),
                        "pts": [],
                    }
                elif last and line.strip().startswith("("):
                    cond[last]["pts"] = [
                        (float(a), float(b)) for a, b in _PTS_RE.findall(line)
                    ]
    return diel, cond
