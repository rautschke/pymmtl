"""Driver for the compiled C++ ``mmtl_bem`` boundary-element solver.

The numerical core is *not* reimplemented in Python; instead we write a
``.xsctn`` file, invoke the vendored ``mmtl_bem`` binary, and parse its
``.result`` output.  This module locates (and can build) the binary and
orchestrates one solver run.

Solver contract (verified in ``csrc/src/nmmtl.cpp``):
    ``mmtl_bem <basename>``  -- the parser appends ``.xsctn`` to the base name
    and writes ``<basename>.result`` / ``.result_field_plot_data`` / ``.dump``
    next to it.  Conductor/dielectric segment counts come from the ``CSEG`` /
    ``DSEG`` lines in the file (CLI segment args are ignored), so they are
    written into the ``.xsctn``.
"""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pymmtl import csdl, results
from pymmtl.model import CrossSection

_PKG_ROOT = Path(__file__).resolve().parents[1]
_CSRC = _PKG_ROOT / "csrc"
_DEFAULT_BIN = _CSRC / "build" / "src" / "mmtl_bem"


class SolverError(RuntimeError):
    """Raised when the solver binary is missing or exits abnormally."""


@dataclass
class RunOutput:
    results: results.Results
    log: str
    workdir: str
    result_path: str
    field_plot_path: str | None


def find_binary() -> str | None:
    """Locate ``mmtl_bem`` via ``$MMTL_BEM``, the vendored build, then ``$PATH``."""
    env = os.environ.get("MMTL_BEM")
    if env and Path(env).is_file() and os.access(env, os.X_OK):
        return env
    if _DEFAULT_BIN.is_file() and os.access(_DEFAULT_BIN, os.X_OK):
        return str(_DEFAULT_BIN)
    found = shutil.which("mmtl_bem")
    return found


def require_binary() -> str:
    binary = find_binary()
    if binary is None:
        raise SolverError(
            "mmtl_bem solver binary not found. Build it with "
            "`pymmtl.solver.build()` (needs cmake + gfortran), or set $MMTL_BEM."
        )
    return binary


def build(build_type: str = "Release") -> str:
    """Configure and build the vendored C++/Fortran solver; return the path."""
    build_dir = _CSRC / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["cmake", "-S", str(_CSRC), "-B", str(build_dir),
         f"-DCMAKE_BUILD_TYPE={build_type}"],
        check=True,
    )
    subprocess.run(
        ["make", "-C", str(build_dir), "-j", str(os.cpu_count() or 1)],
        check=True,
    )
    if not _DEFAULT_BIN.is_file():
        raise SolverError(f"build completed but {_DEFAULT_BIN} is missing")
    return str(_DEFAULT_BIN)


def run(
    cs: CrossSection,
    *,
    coupling_length: float | None = None,
    rise_time: float | None = None,
    cseg: int | None = None,
    dseg: int | None = None,
    workdir: str | os.PathLike | None = None,
    basename: str = "model",
    timeout: float | None = 600.0,
) -> RunOutput:
    """Run the solver on ``cs`` and return parsed results plus the solver log.

    Optional overrides (coupling length, rise time, segment counts) are applied
    to a copy of ``cs`` before writing, leaving the caller's object untouched.
    """
    binary = require_binary()

    model = copy.deepcopy(cs)
    if coupling_length is not None:
        model.coupling_length = coupling_length
    if rise_time is not None:
        model.rise_time = rise_time
    if cseg is not None:
        model.cseg = cseg
    if dseg is not None:
        model.dseg = dseg

    tmp = None
    if workdir is None:
        tmp = tempfile.mkdtemp(prefix="pymmtl_")
        work = Path(tmp)
    else:
        work = Path(workdir)
        work.mkdir(parents=True, exist_ok=True)

    try:
        base = work / basename
        csdl.dump(model, str(base) + ".xsctn")
        proc = subprocess.run(
            [binary, str(base)],
            cwd=str(work),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result_path = str(base) + ".result"
        if not Path(result_path).is_file():
            raise SolverError(
                f"solver produced no .result (exit {proc.returncode}).\n"
                f"--- stdout ---\n{proc.stdout[-2000:]}\n"
                f"--- stderr ---\n{proc.stderr[-2000:]}"
            )
        res = results.load(result_path)
        res.meta["log"] = proc.stdout
        res.meta["returncode"] = proc.returncode
        field = str(base) + ".result_field_plot_data"
        return RunOutput(
            results=res,
            log=proc.stdout,
            workdir=str(work),
            result_path=result_path,
            field_plot_path=field if Path(field).is_file() else None,
        )
    finally:
        # keep the workdir if the caller supplied one; clean our own temp dir
        if tmp is not None and workdir is None and not os.environ.get("PYMMTL_KEEP"):
            shutil.rmtree(tmp, ignore_errors=True)


def run_file(path: str | os.PathLike, **kwargs) -> RunOutput:
    """Load a ``.xsctn`` file and run the solver on it."""
    return run(csdl.load(path), **kwargs)
