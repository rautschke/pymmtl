"""Parameter sweeps over a cross-section.

Reproduces TNT's "Sweep Simulation": vary one or more parameters across ranges,
run the solver for the Cartesian product of values, and collect a table of
results that can be exported to CSV.
"""

from __future__ import annotations

import copy
import csv as _csv
import itertools
from dataclasses import dataclass, field

from pymmtl import solver
from pymmtl.model import CrossSection

# CSDL/option field name -> dataclass attribute on a stack element
_FIELD_ALIASES = {
    "width": "width",
    "height": "height",
    "thickness": "thickness",
    "permittivity": "permittivity",
    "lossTangent": "loss_tangent",
    "permeability": "permeability",
    "pitch": "pitch",
    "number": "number",
    "conductivity": "conductivity",
    "diameter": "diameter",
    "topWidth": "top_width",
    "bottomWidth": "bottom_width",
    "xOffset": "x_offset",
    "yOffset": "y_offset",
}

# global parameters addressable as "<keyword>"
_GLOBAL_ALIASES = {
    "coupling": "coupling_length",
    "couplingLength": "coupling_length",
    "risetime": "rise_time",
    "riseTime": "rise_time",
    "cseg": "cseg",
    "CSEG": "cseg",
    "dseg": "dseg",
    "DSEG": "dseg",
}

_METRICS = {
    "impedance": "impedance",
    "eps_eff": "eps_eff",
    "velocity": "velocity",
    "delay": "delay",
}


@dataclass
class SweepSpec:
    """One swept parameter and its value range."""

    target: str | None  # group name, or None for a global parameter
    field: str          # attribute name (already resolved to dataclass attr)
    label: str          # human label for the CSV column
    values: list[float]

    def apply(self, cs: CrossSection, value: float) -> None:
        if self.target is None:
            setattr(cs, self.field, value)
        else:
            el = cs.find_group(self.target)
            if el is None:
                raise KeyError(f"no stack element named {self.target!r}")
            setattr(el, self.field, value)


def parse_spec(spec: str) -> SweepSpec:
    """Parse ``'group.field=start:stop:n'`` or ``'global=start:stop:n'``.

    ``start:stop:n`` yields ``n`` linearly spaced values (inclusive). A bare
    comma list ``'=a,b,c'`` is also accepted.
    """
    lhs, _, rhs = spec.partition("=")
    if not rhs:
        raise ValueError(f"sweep spec needs '=values': {spec!r}")
    lhs = lhs.strip()

    if "." in lhs:
        target, fld = lhs.split(".", 1)
        if fld not in _FIELD_ALIASES:
            raise ValueError(f"unknown field {fld!r} in {spec!r}")
        attr = _FIELD_ALIASES[fld]
        label = f"{target}.{fld}"
    else:
        if lhs not in _GLOBAL_ALIASES:
            raise ValueError(f"unknown global parameter {lhs!r} in {spec!r}")
        target = None
        attr = _GLOBAL_ALIASES[lhs]
        label = lhs

    values = _parse_values(rhs.strip())
    return SweepSpec(target=target, field=attr, label=label, values=values)


def _parse_values(rhs: str) -> list[float]:
    if ":" in rhs:
        parts = rhs.split(":")
        if len(parts) != 3:
            raise ValueError(f"range must be start:stop:n, got {rhs!r}")
        start, stop, n = float(parts[0]), float(parts[1]), int(float(parts[2]))
        if n <= 1:
            return [start]
        step = (stop - start) / (n - 1)
        return [start + i * step for i in range(n)]
    return [float(x) for x in rhs.split(",") if x.strip()]


@dataclass
class SweepTable:
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)


def run_sweep(
    cs: CrossSection,
    specs: list[SweepSpec],
    *,
    output: str = "impedance",
    progress=None,
) -> SweepTable:
    """Run the Cartesian product of ``specs`` and tabulate ``output`` per signal."""
    if output not in _METRICS:
        raise ValueError(f"unknown metric {output!r}; choose from {list(_METRICS)}")
    metric_attr = _METRICS[output]

    signal_names = cs.signal_names()
    param_cols = [s.label for s in specs]
    value_cols = [f"{output}:{nm}" for nm in signal_names]
    table = SweepTable(columns=param_cols + value_cols)

    combos = list(itertools.product(*[s.values for s in specs]))
    for i, combo in enumerate(combos):
        model = copy.deepcopy(cs)
        for spec, value in zip(specs, combo):
            spec.apply(model, value)
        out = solver.run(model)
        metric = getattr(out.results, metric_attr)
        row = {spec.label: value for spec, value in zip(specs, combo)}
        for nm in signal_names:
            row[f"{output}:{nm}"] = metric.get(nm, float("nan"))
        table.rows.append(row)
        if progress is not None:
            progress(i + 1, len(combos), row)
    return table


def write_csv(table: SweepTable, path) -> None:
    with open(path, "w", newline="") as fh:
        writer = _csv.DictWriter(fh, fieldnames=table.columns)
        writer.writeheader()
        for row in table.rows:
            writer.writerow(row)
