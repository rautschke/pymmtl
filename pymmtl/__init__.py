"""pymmtl - a Python front-end for the MMTL/BEM transmission-line field solver.

This package reproduces the user-facing functionality of the original Tcl/Tk
"TNT" application around the compiled C++ ``mmtl_bem`` boundary-element solver:

* an in-memory cross-section model (:mod:`pymmtl.model`),
* read/write of the ``.xsctn`` Cross-Section Description Language
  (:mod:`pymmtl.csdl`),
* parsing of solver ``.result`` files (:mod:`pymmtl.results`),
* a subprocess driver for the solver (:mod:`pymmtl.solver`),
* parameter sweeps, impedance iteration, and HSPICE W-element export.

The numerical core itself remains the proven C++/Fortran solver, vendored as a
git submodule under ``csrc/`` (built from ``csrc/bem/``) and invoked as a
subprocess.
"""

from pymmtl.model import (
    CrossSection,
    GroundPlane,
    DielectricLayer,
    DielectricBlock,
    RectangleConductors,
    TrapezoidConductors,
    CircleConductors,
)

__all__ = [
    "CrossSection",
    "GroundPlane",
    "DielectricLayer",
    "DielectricBlock",
    "RectangleConductors",
    "TrapezoidConductors",
    "CircleConductors",
]

__version__ = "0.1.0"
