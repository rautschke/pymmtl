"""model.resolve() must reproduce the solver's own geometry layout."""

from pymmtl import csdl
from conftest import example_path, golden_stdout, parse_geometry_dump


def _close(a, b, rtol=1e-5, atol=1e-10):
    return abs(a - b) <= atol + rtol * max(abs(a), abs(b))


def test_resolve_matches_solver_dump(example):
    gd, gc = parse_geometry_dump(golden_stdout(example))
    geo = csdl.load(example_path(example)).resolve()

    # dielectrics match as an unordered multiset
    resolved = [(d.x0, d.y0, d.x1, d.y1, d.permittivity) for d in geo.dielectrics]
    assert len(resolved) == len(gd)
    used = [False] * len(gd)
    for r in resolved:
        hit = False
        for i, g in enumerate(gd):
            if not used[i] and all(_close(a, b) for a, b in zip(r, g)):
                used[i] = True
                hit = True
                break
        assert hit, f"unmatched dielectric {r}"

    # conductors match by name
    conductors = {c.name: c for c in geo.conductors if not c.is_ground}
    for name, c in conductors.items():
        assert name in gc, f"{name} missing from solver dump"
        g = gc[name]
        if c.shape == "rectangle":
            gx0, gy0, gx1, gy1, _ = g["hdr"]
            assert _close(c.x0, gx0) and _close(c.y0, gy0)
            assert _close(c.x1, gx1) and _close(c.y1, gy1)
        else:  # polygon: compare point sets (ignore closing duplicate)
            gp = g["pts"][:-1] if g["pts"] and g["pts"][0] == g["pts"][-1] else g["pts"]
            assert len(c.points) == len(gp)
            for ax, ay in c.points:
                assert any(_close(ax, bx) and _close(ay, by) for bx, by in gp), (
                    f"{name} point {(ax, ay)} not in dump"
                )
