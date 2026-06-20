# pymmtl

A Python front-end for **MMTL** — the Mayo SPPDG *Multilayer Multiconductor
Transmission Line* 2-D quasi-static boundary-element field solver.

`pymmtl` reproduces the user-facing functionality of the original Tcl/Tk **TNT**
application — building cross-sections, running the solver, sweeping parameters,
iterating conductor width to a target impedance, and exporting HSPICE
W-element models — entirely in Python. The proven numerical core is **not**
re-implemented; the vendored C++/Fortran `mmtl_bem` solver (`csrc/`) is invoked
as a subprocess.

```
pymmtl/
  csrc/        vendored C++/Fortran BEM solver (built once with cmake + gfortran)
  examples/    example .xsctn cross-sections
  pymmtl/      the Python package (model, csdl I/O, results parser, solver
               driver, sweep/iterate/rlgc, and the Tkinter GUI under gui/)
  tests/       pytest suite + golden solver outputs
```

## Install / build

```bash
# 1. build the solver binary (needs cmake + gfortran + g++)
python -c "import pymmtl.solver as s; print(s.build())"
#    ...or set $MMTL_BEM to an existing mmtl_bem binary.

# 2. install the package (numpy is the only hard dependency; scipy is optional)
pip install -e .            # add [dev] for pytest + scipy
```

The solver binary is located via, in order: `$MMTL_BEM`, the vendored build at
`csrc/build/src/mmtl_bem`, then `$PATH`.

## Command line

```bash
python -m pymmtl run    examples/example-microstrip-2.xsctn        # Z0/eps_eff/velocity
python -m pymmtl info   examples/coplanar.xsctn
python -m pymmtl sweep  examples/example-microstrip-2.xsctn \
        --param "fr4.thickness=30:70:5" --metric impedance --csv out.csv
python -m pymmtl iterate examples/example-microstrip-2.xsctn c1 50
python -m pymmtl export  examples/example-microstrip-2.xsctn -o model.hspice-w.rlgc
```

## GUI

```bash
python -m pymmtl.gui.app [file.xsctn]
```

A TNT-style window: a title/units bar, "Create New Structure" buttons, a
reorderable layer-stackup list, and a zoomable cross-section drawing. The
**BEM**, **Sweep**, and **Iterate** menus run the solver; **File → Export
HSPICE W-element** writes an RLGC model.

## The `.xsctn` format

Cross-sections use the Tcl-flavored *Cross-Section Description Language*
(`package require csdl`; `set ::Stackup::...` globals; `GroundPlane`,
`DielectricLayer`, `RectangleConductors`, `TrapezoidConductors`,
`CircleConductors`, `RectangleDielectric` commands). `pymmtl.csdl.load` /
`dump` read and write exactly the vocabulary the solver parses.

## Validation

`tests/` builds the C++ solver, captures golden `.result` outputs for every
example, and asserts that the full Python pipeline (`csdl.dump` → `mmtl_bem` →
`results.parse`) reproduces them, that `model.resolve()` matches the solver's
own geometry layout, and that the results parser, sweep, iterate, and RLGC
export behave correctly.

```bash
pytest                       # or: python -m pytest tests
```

## Notes & limitations

* The original TNT "Wavelet Simulators" are **not** included — their source is
  not part of this repository.
* The exact byte layout of the original `.hspice-w.rlgc` file cannot be
  reproduced (the original Tcl writer is absent); `pymmtl` emits the standard
  HSPICE W-element RLGC format, computing R0/Rs from the user-guide equations.
* BEM MMTL is loss-free (ignores dielectric loss tangent); `Go`/`Gd` are zero.
