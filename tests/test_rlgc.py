"""HSPICE W-element export. Requires the compiled solver."""

import math

import pytest

from pymmtl import csdl, rlgc, results, solver
from conftest import example_path, golden_result

pytestmark = pytest.mark.skipif(
    solver.find_binary() is None,
    reason="mmtl_bem not built (run pymmtl.solver.build())",
)


def test_ro_matches_solver_rdc():
    """Our R0 = 1/(sigma*Area) must match the solver's own Rdc diagonal."""
    cs = csdl.load(example_path("example-microstrip-2"))
    gold = results.load(golden_result("example-microstrip-2"))
    text = rlgc.hspice_w_element(cs, gold)

    assert text.splitlines()[0].startswith("* HSPICE W-element")
    ro, _rs = rlgc._resistance_terms(cs, gold.names)
    for i, name in enumerate(gold.names):
        assert math.isclose(ro[i], gold.Rdc[i, i], rel_tol=1e-6)


def test_rs_positive_for_finite_conductivity():
    cs = csdl.load(example_path("example-microstrip-2"))
    gold = results.load(golden_result("example-microstrip-2"))
    _ro, rs = rlgc._resistance_terms(cs, gold.names)
    assert all(v > 0 for v in rs)


def test_export_structure():
    cs = csdl.load(example_path("coplanar"))
    out = solver.run(cs)
    text = rlgc.hspice_w_element(cs, out.results)
    # conductor count line then six labelled matrix blocks
    assert "\n1\n" in "\n" + text  # single signal conductor
    for label in ("Lo", "Co", "Ro", "Go", "Rs", "Gd"):
        assert f"* {label}" in text
