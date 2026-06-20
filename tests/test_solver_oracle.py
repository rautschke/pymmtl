"""Full Python pipeline (csdl.dump -> mmtl_bem -> parse) vs golden results.

Requires the compiled solver; skipped otherwise.
"""

import pytest

from pymmtl import results, solver
from conftest import example_path, golden_result, num_eq

pytestmark = pytest.mark.skipif(
    solver.find_binary() is None,
    reason="mmtl_bem not built (run pymmtl.solver.build())",
)


def test_pipeline_reproduces_golden(example):
    gold = results.load(golden_result(example))
    fresh = solver.run_file(example_path(example)).results

    assert set(gold.names) == set(fresh.names)
    gi = {n: i for i, n in enumerate(gold.names)}
    fi = {n: i for i, n in enumerate(fresh.names)}

    for attr in ("C", "L", "Rdc"):
        GM = getattr(gold, attr)
        FM = getattr(fresh, attr)
        if GM is None:
            continue
        for a in gold.names:
            for b in gold.names:
                assert num_eq(GM[gi[a], gi[b]], FM[fi[a], fi[b]]), (
                    f"{attr}[{a},{b}]"
                )

    for attr in ("impedance", "eps_eff", "velocity", "delay"):
        gd = getattr(gold, attr)
        fd = getattr(fresh, attr)
        for n in gd:
            assert num_eq(gd[n], fd.get(n, float("nan"))), f"{attr}[{n}]"

    for key, (gr, _gdb) in gold.fxt.items():
        assert num_eq(gr, fresh.fxt.get(key, (float("nan"),))[0], rtol=1e-3)
