"""Unit constants and value parsing for MMTL cross-sections.

The ``.xsctn`` format stores geometric dimensions in a chosen *default length
unit* (mils/microns/inches/meters), conductivity in siemens/meter, coupling
length in meters, and rise time in picoseconds.  The C++ parser
(``nmmtl_parse_xsctn.cpp``) converts everything to SI internally; these helpers
mirror the constants it uses (``nmmtl.h``).
"""

from __future__ import annotations

import math
import re

# --- length units -> meters (nmmtl.h: MILS_TO_METERS, INCHES_TO_METERS, ...) ---
LENGTH_UNITS: dict[str, float] = {
    "mils": 2.54e-5,
    "microns": 1.0e-6,
    "inches": 2.54e-2,
    "meters": 1.0,
}
DEFAULT_LENGTH_UNITS = "mils"

# --- physical constants (nmmtl.h) ---
SPEED_OF_LIGHT = 2.99792458e8                      # m/s
MU0 = 4.0e-7 * math.pi                             # H/m
EPSILON0 = 1.0 / (MU0 * SPEED_OF_LIGHT * SPEED_OF_LIGHT)
DEFAULT_CONDUCTIVITY = 5.8e7                        # S/m (copper)
DEFAULT_GND_THICKNESS_M = 2.54e-5                  # DEFAULT_GND_THICK

# leading signed float (optionally in scientific notation)
_NUM_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def split_number_unit(value: str | float | int) -> tuple[float, str]:
    """Split ``'12mils'`` / ``'3e+07siemens/meter'`` into ``(12.0, 'mils')``.

    A bare number returns an empty suffix.
    """
    if isinstance(value, (int, float)):
        return float(value), ""
    s = str(value).strip().strip('"').strip()
    m = _NUM_RE.match(s)
    if not m:
        raise ValueError(f"cannot parse a number from {value!r}")
    return float(m.group(0)), s[m.end():].strip()


def to_meters(value: str | float | int, default_units: str) -> float:
    """Convert a dimension to meters.

    Strings may carry an explicit length-unit suffix; otherwise ``default_units``
    applies.  Bare numbers are interpreted in ``default_units``.
    """
    num, suffix = split_number_unit(value)
    unit = suffix if suffix in LENGTH_UNITS else default_units
    return num * LENGTH_UNITS[unit]


def in_default_units(value: str | float | int, default_units: str) -> float:
    """Return the numeric value expressed in ``default_units``.

    Used when loading so the model stores dimensions in the file's default unit
    (matching how the GUI edits and how ``.xsctn`` files are written back).
    """
    num, suffix = split_number_unit(value)
    if suffix in LENGTH_UNITS and suffix != default_units:
        return num * LENGTH_UNITS[suffix] / LENGTH_UNITS[default_units]
    return num


def parse_conductivity(value: str | float | int) -> float:
    """Parse a conductivity field (``'3e+07siemens/meter'``, ``'5.0e7S/m'``,
    ``'3e+07'``) into S/m.  The unit is always siemens/meter."""
    num, _ = split_number_unit(value)
    return num


def parse_coupling_length_m(value: str | float | int) -> float:
    """Coupling length; bare numbers are meters (parser default)."""
    num, suffix = split_number_unit(value)
    if suffix in LENGTH_UNITS:
        return num * LENGTH_UNITS[suffix]
    return num  # meters


def parse_risetime_ps(value: str | float | int) -> float:
    """Rise time; bare numbers are picoseconds (parser default)."""
    num, suffix = split_number_unit(value)
    s = suffix.lower()
    if s in ("ps", ""):
        return num
    if s == "ns":
        return num * 1e3
    if s in ("us", "µs"):
        return num * 1e6
    if s == "ms":
        return num * 1e9
    if s == "s":
        return num * 1e12
    return num
