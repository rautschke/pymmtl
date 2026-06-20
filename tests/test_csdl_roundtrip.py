"""CSDL load/dump round-trip fidelity (no solver required)."""

from pymmtl import csdl
from conftest import example_path


def test_load_roundtrip_stable(example):
    cs = csdl.load(example_path(example))
    cs2 = csdl.loads(csdl.dumps(cs))

    assert len(cs.stack) == len(cs2.stack)
    assert cs.signal_names() == cs2.signal_names()
    assert cs.default_units == cs2.default_units
    assert cs.cseg == cs2.cseg and cs.dseg == cs2.dseg
    assert abs(cs.coupling_length - cs2.coupling_length) <= 1e-15 + 1e-12 * abs(
        cs.coupling_length
    )
    assert abs(cs.rise_time - cs2.rise_time) <= 1e-9

    # element fields survive the round trip
    for a, b in zip(cs.stack, cs2.stack):
        assert a.kind == b.kind
        assert a.name == b.name


def test_unknown_keyword_ignored():
    text = (
        "package require csdl\n"
        'set _title "x"\n'
        "set ::Stackup::defaultLengthUnits \"mils\"\n"
        "SomethingWeird foo -bar 3\n"
        "GroundPlane g\n"
    )
    cs = csdl.loads(text)
    assert [e.kind for e in cs.stack] == ["ground_plane"]
