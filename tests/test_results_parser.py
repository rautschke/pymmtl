"""Results parser against captured golden .result files (no solver required)."""

import math

from pymmtl import results
from conftest import golden_result


def test_parse_all_goldens(example):
    res = results.load(golden_result(example))
    assert res.n >= 1
    # square matrices sized to the signal count
    for M in (res.C, res.L, res.Rdc):
        assert M is not None
        assert M.shape == (res.n, res.n)
    # every signal has a characteristic impedance entry
    assert set(res.impedance) == set(res.names)


def test_coplanar_values():
    res = results.load(golden_result("coplanar"))
    assert res.names == ["condR0"]
    assert math.isclose(res.impedance["condR0"], 31.5124, rel_tol=1e-4)
    assert math.isclose(res.eps_eff["condR0"], 9.34747, rel_tol=1e-4)
    assert math.isclose(res.C[0, 0], 3.2362695e-10, rel_tol=1e-5)


def test_microstrip2_odd_even_and_crosstalk():
    res = results.load(golden_result("example-microstrip-2"))
    assert set(res.names) == {"c1R0", "c1R1"}
    odd, even = res.odd_even["impedance"]
    assert math.isclose(odd, 53.7377, rel_tol=1e-4)
    assert math.isclose(even, 166.45, rel_tol=1e-4)
    # one crosstalk pair (upper triangle only)
    assert ("c1R1", "c1R0") in res.fxt
    ratio, db = res.bxt[("c1R1", "c1R0")]
    assert math.isclose(ratio, 2.73999e-05, rel_tol=1e-3)


def test_asymmetry_present_for_multiconductor():
    res = results.load(golden_result("example-microstrip-5"))
    assert "inductance" in res.asymmetry
    assert "capacitance" in res.asymmetry
