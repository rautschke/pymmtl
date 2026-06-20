"""Read and write the ``.xsctn`` Cross-Section Description Language.

``.xsctn`` files are Tcl-flavored scripts (``package require csdl`` then ``set``
statements and geometry commands).  We do not run a Tcl interpreter; we parse
the same line-oriented vocabulary the C++ solver's ``nmmtl_parse_xsctn.cpp``
recognises, and emit files it can read back verbatim.
"""

from __future__ import annotations

import re

from pymmtl import units
from pymmtl.model import (
    CircleConductors,
    CrossSection,
    DielectricBlock,
    DielectricLayer,
    GroundPlane,
    RectangleConductors,
    TrapezoidConductors,
)

# ----------------------------- reading ------------------------------------- #
_SET_RE = re.compile(r'^\s*set\s+(\S+)\s+(.*?)\s*$')


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _join_continuations(text: str) -> list[str]:
    """Collapse Tcl backslash line-continuations into single logical lines."""
    lines: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
        else:
            buf += line
            lines.append(buf)
            buf = ""
    if buf:
        lines.append(buf)
    return lines


def _options(tokens: list[str]) -> dict[str, str]:
    """Parse ``-key value`` pairs from a tokenised geometry command."""
    opts: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-") and i + 1 < len(tokens):
            opts[tok[1:]] = tokens[i + 1]
            i += 2
        else:
            i += 1
    return opts


def loads(text: str) -> CrossSection:
    """Parse ``.xsctn`` text into a :class:`CrossSection`."""
    cs = CrossSection()
    default_units = units.DEFAULT_LENGTH_UNITS

    # First pass: pick up defaultLengthUnits early (dimensions depend on it).
    for line in _join_continuations(text):
        m = _SET_RE.match(line)
        if m and m.group(1) == "::Stackup::defaultLengthUnits":
            default_units = _unquote(m.group(2))
    cs.default_units = default_units

    for line in _join_continuations(text):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("package"):
            continue

        m = _SET_RE.match(line)
        if m:
            key, val = m.group(1), _unquote(m.group(2))
            if key == "_title":
                cs.title = val
            elif key == "::Stackup::couplingLength":
                cs.coupling_length = units.parse_coupling_length_m(val)
            elif key == "::Stackup::riseTime":
                cs.rise_time = units.parse_risetime_ps(val)
            elif key == "::Stackup::frequency":
                cs.frequency = val
            elif key == "::Stackup::defaultLengthUnits":
                cs.default_units = val
            elif key == "CSEG":
                cs.cseg = int(float(val))
            elif key == "DSEG":
                cs.dseg = int(float(val))
            continue

        tokens = stripped.split()
        if not tokens:
            continue
        keyword = tokens[0]
        name = tokens[1] if len(tokens) > 1 and not tokens[1].startswith("-") else ""
        opts = _options(tokens[1:])
        el = _build_element(keyword, name, opts, cs.default_units)
        if el is not None:
            cs.stack.append(el)

    return cs


def load(path) -> CrossSection:
    with open(path, "r") as fh:
        return loads(fh.read())


def _dim(opts: dict, key: str, default_units: str, default=0.0):
    if key not in opts:
        return default
    return units.in_default_units(opts[key], default_units)


def _build_element(keyword: str, name: str, opts: dict, default_units: str):
    if keyword == "GroundPlane":
        thickness = (
            units.in_default_units(opts["thickness"], default_units)
            if "thickness" in opts
            else None
        )
        return GroundPlane(
            name=name,
            thickness=thickness,
            x_offset=_dim(opts, "xOffset", default_units),
            y_offset=_dim(opts, "yOffset", default_units),
        )

    if keyword == "DielectricLayer":
        return DielectricLayer(
            name=name,
            thickness=_dim(opts, "thickness", default_units),
            permittivity=float(opts.get("permittivity", 1.0)),
            loss_tangent=float(opts.get("lossTangent", 0.0)),
            permeability=float(opts.get("permeability", 1.0)),
            x_offset=_dim(opts, "xOffset", default_units),
            y_offset=_dim(opts, "yOffset", default_units),
        )

    if keyword == "RectangleDielectric":
        return DielectricBlock(
            name=name,
            width=_dim(opts, "width", default_units),
            height=_dim(opts, "height", default_units),
            permittivity=float(opts.get("permittivity", 1.0)),
            number=int(float(opts.get("number", 1))),
            pitch=_dim(opts, "pitch", default_units),
            x_offset=_dim(opts, "xOffset", default_units),
            y_offset=_dim(opts, "yOffset", default_units),
        )

    if keyword == "RectangleConductors":
        return RectangleConductors(
            name=name,
            width=_dim(opts, "width", default_units),
            height=_dim(opts, "height", default_units),
            pitch=_dim(opts, "pitch", default_units),
            conductivity=units.parse_conductivity(
                opts.get("conductivity", units.DEFAULT_CONDUCTIVITY)
            ),
            number=int(float(opts.get("number", 1))),
            x_offset=_dim(opts, "xOffset", default_units),
            y_offset=_dim(opts, "yOffset", default_units),
        )

    if keyword == "TrapezoidConductors":
        return TrapezoidConductors(
            name=name,
            top_width=_dim(opts, "topWidth", default_units),
            bottom_width=_dim(opts, "bottomWidth", default_units),
            height=_dim(opts, "height", default_units),
            pitch=_dim(opts, "pitch", default_units),
            conductivity=units.parse_conductivity(
                opts.get("conductivity", units.DEFAULT_CONDUCTIVITY)
            ),
            number=int(float(opts.get("number", 1))),
            x_offset=_dim(opts, "xOffset", default_units),
            y_offset=_dim(opts, "yOffset", default_units),
        )

    if keyword == "CircleConductors":
        return CircleConductors(
            name=name,
            diameter=_dim(opts, "diameter", default_units),
            pitch=_dim(opts, "pitch", default_units),
            conductivity=units.parse_conductivity(
                opts.get("conductivity", units.DEFAULT_CONDUCTIVITY)
            ),
            number=int(float(opts.get("number", 1))),
            x_offset=_dim(opts, "xOffset", default_units),
            y_offset=_dim(opts, "yOffset", default_units),
        )

    return None  # unknown keyword -> ignored, matching the tolerant C++ parser


# ----------------------------- writing ------------------------------------- #
def _fmt(value: float) -> str:
    """Format a number compactly (no trailing zeros, no exponent for plain ints)."""
    if value == int(value):
        return str(int(value))
    return repr(value)


def _opt_lines(pairs: list[tuple[str, object]]) -> str:
    body = " \\\n".join(f"\t -{key} {val}" for key, val in pairs)
    return body


def dumps(cs: CrossSection) -> str:
    """Serialise a :class:`CrossSection` to ``.xsctn`` text the solver accepts."""
    out: list[str] = []
    out.append("#----------------------------------")
    out.append("# Written by pymmtl")
    out.append("#----------------------------------")
    out.append("")
    out.append("package require csdl")
    out.append("")
    out.append(f'set _title "{cs.title}"')
    out.append(f'set ::Stackup::couplingLength "{_fmt(cs.coupling_length)}"')
    out.append(f'set ::Stackup::riseTime "{_fmt(cs.rise_time)}"')
    if cs.frequency:
        out.append(f'set ::Stackup::frequency "{cs.frequency}"')
    out.append(f'set ::Stackup::defaultLengthUnits "{cs.default_units}"')
    out.append(f"set CSEG {cs.cseg}")
    out.append(f"set DSEG {cs.dseg}")
    out.append("")

    for el in cs.stack:
        out.append(_dump_element(el))

    return "\n".join(out) + "\n"


def _cond(value: float) -> str:
    return f"{_fmt(value)}siemens/meter"


def _dump_element(el) -> str:
    if el.kind == "ground_plane":
        pairs = []
        if el.thickness is not None:
            pairs.append(("thickness", _fmt(el.thickness)))
        if el.x_offset:
            pairs.append(("xOffset", _fmt(el.x_offset)))
        if el.y_offset:
            pairs.append(("yOffset", _fmt(el.y_offset)))
        if not pairs:
            return f"GroundPlane {el.name}"
        return f"GroundPlane {el.name}  \\\n" + _opt_lines(pairs)

    if el.kind == "dielectric_layer":
        pairs = [
            ("thickness", _fmt(el.thickness)),
            ("lossTangent", _fmt(el.loss_tangent)),
            ("permittivity", _fmt(el.permittivity)),
            ("permeability", _fmt(el.permeability)),
            ("yOffset", _fmt(el.y_offset)),
            ("xOffset", _fmt(el.x_offset)),
        ]
        return f"DielectricLayer {el.name}  \\\n" + _opt_lines(pairs)

    if el.kind == "dielectric_block":
        pairs = [
            ("width", _fmt(el.width)),
            ("height", _fmt(el.height)),
            ("permittivity", _fmt(el.permittivity)),
            ("number", el.number),
            ("pitch", _fmt(el.pitch)),
            ("yOffset", _fmt(el.y_offset)),
            ("xOffset", _fmt(el.x_offset)),
        ]
        return f"RectangleDielectric {el.name}  \\\n" + _opt_lines(pairs)

    if el.kind == "rectangle_conductors":
        pairs = [
            ("width", _fmt(el.width)),
            ("pitch", _fmt(el.pitch)),
            ("conductivity", _cond(el.conductivity)),
            ("height", _fmt(el.height)),
            ("number", el.number),
            ("yOffset", _fmt(el.y_offset)),
            ("xOffset", _fmt(el.x_offset)),
        ]
        return f"RectangleConductors {el.name}  \\\n" + _opt_lines(pairs)

    if el.kind == "trapezoid_conductors":
        pairs = [
            ("topWidth", _fmt(el.top_width)),
            ("bottomWidth", _fmt(el.bottom_width)),
            ("height", _fmt(el.height)),
            ("pitch", _fmt(el.pitch)),
            ("conductivity", _cond(el.conductivity)),
            ("number", el.number),
            ("yOffset", _fmt(el.y_offset)),
            ("xOffset", _fmt(el.x_offset)),
        ]
        return f"TrapezoidConductors {el.name}  \\\n" + _opt_lines(pairs)

    if el.kind == "circle_conductors":
        pairs = [
            ("diameter", _fmt(el.diameter)),
            ("pitch", _fmt(el.pitch)),
            ("conductivity", _cond(el.conductivity)),
            ("number", el.number),
            ("yOffset", _fmt(el.y_offset)),
            ("xOffset", _fmt(el.x_offset)),
        ]
        return f"CircleConductors {el.name}  \\\n" + _opt_lines(pairs)

    raise ValueError(f"unknown element kind {el.kind!r}")


def dump(cs: CrossSection, path) -> None:
    with open(path, "w") as fh:
        fh.write(dumps(cs))
