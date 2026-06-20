"""Sweep and iterate behaviour. Requires the compiled solver."""

import math

import pytest

from pymmtl import csdl, iterate, sweep, solver
from conftest import example_path

pytestmark = pytest.mark.skipif(
    solver.find_binary() is None,
    reason="mmtl_bem not built (run pymmtl.solver.build())",
)


def test_parse_spec_range():
    spec = sweep.parse_spec("fr4.thickness=30:70:3")
    assert spec.label == "fr4.thickness"
    assert spec.values == [30.0, 50.0, 70.0]

    g = sweep.parse_spec("couplingLength=0:1:2")
    assert g.target is None and g.field == "coupling_length"


def test_sweep_monotonic_thickness():
    cs = csdl.load(example_path("example-microstrip-2"))
    table = sweep.run_sweep(cs, [sweep.parse_spec("fr4.thickness=30:70:3")],
                            output="impedance")
    assert len(table.rows) == 3
    z = [r["impedance:c1R0"] for r in table.rows]
    # microstrip impedance increases with substrate thickness
    assert z[0] < z[1] < z[2]


def test_iterate_hits_target():
    cs = csdl.load(example_path("example-microstrip-2"))
    res = iterate.iterate_width(cs, "c1", 75.0, conductor_index=0)
    assert res.converged
    assert math.isclose(res.impedance, 75.0, abs_tol=0.5)
