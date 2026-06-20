"""Modal dialogs: structure property editors, BEM run, sweep, and iterate."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from pymmtl import model

# field spec per stack-element kind: (label, attribute, type)
#   type: "str" | "float" | "int" | "floatN" (float-or-empty)
STRUCTURE_FIELDS = {
    "ground_plane": [
        ("Name", "name", "str"),
        ("Thickness", "thickness", "floatN"),
    ],
    "dielectric_layer": [
        ("Name", "name", "str"),
        ("Thickness", "thickness", "float"),
        ("Permittivity", "permittivity", "float"),
        ("Loss Tangent", "loss_tangent", "float"),
        ("Permeability", "permeability", "float"),
        ("X Offset", "x_offset", "float"),
        ("Y Offset", "y_offset", "float"),
    ],
    "dielectric_block": [
        ("Name", "name", "str"),
        ("Width", "width", "float"),
        ("Height", "height", "float"),
        ("Permittivity", "permittivity", "float"),
        ("Number", "number", "int"),
        ("Pitch", "pitch", "float"),
        ("X Offset", "x_offset", "float"),
        ("Y Offset", "y_offset", "float"),
    ],
    "rectangle_conductors": [
        ("Name", "name", "str"),
        ("Width", "width", "float"),
        ("Height", "height", "float"),
        ("Pitch", "pitch", "float"),
        ("Conductivity (S/m)", "conductivity", "float"),
        ("Number", "number", "int"),
        ("X Offset", "x_offset", "float"),
        ("Y Offset", "y_offset", "float"),
    ],
    "trapezoid_conductors": [
        ("Name", "name", "str"),
        ("Top Width", "top_width", "float"),
        ("Bottom Width", "bottom_width", "float"),
        ("Height", "height", "float"),
        ("Pitch", "pitch", "float"),
        ("Conductivity (S/m)", "conductivity", "float"),
        ("Number", "number", "int"),
        ("X Offset", "x_offset", "float"),
        ("Y Offset", "y_offset", "float"),
    ],
    "circle_conductors": [
        ("Name", "name", "str"),
        ("Diameter", "diameter", "float"),
        ("Pitch", "pitch", "float"),
        ("Conductivity (S/m)", "conductivity", "float"),
        ("Number", "number", "int"),
        ("X Offset", "x_offset", "float"),
        ("Y Offset", "y_offset", "float"),
    ],
}

_KIND_CLASS = {
    "ground_plane": model.GroundPlane,
    "dielectric_layer": model.DielectricLayer,
    "dielectric_block": model.DielectricBlock,
    "rectangle_conductors": model.RectangleConductors,
    "trapezoid_conductors": model.TrapezoidConductors,
    "circle_conductors": model.CircleConductors,
}

KIND_LABEL = {
    "ground_plane": "Ground Plane",
    "dielectric_layer": "Dielectric Layer",
    "dielectric_block": "Dielectric Block",
    "rectangle_conductors": "Rectangle Conductors",
    "trapezoid_conductors": "Trapezoid Conductors",
    "circle_conductors": "Circular Conductors",
}


def _coerce(value: str, typ: str):
    value = value.strip()
    if typ == "str":
        return value
    if typ == "int":
        return int(float(value)) if value else 1
    if typ == "floatN":
        return float(value) if value else None
    return float(value) if value else 0.0


class _Modal(tk.Toplevel):
    """Base modal dialog: sets ``self.result`` and blocks until closed."""

    def __init__(self, master, title: str):
        super().__init__(master)
        self.title(title)
        self.result = None
        self.transient(master)
        self.resizable(False, False)
        self.body = ttk.Frame(self, padding=10)
        self.body.pack(fill="both", expand=True)

    def _finish(self):
        self.grab_set()
        self.wait_window(self)


class PropertyDialog(_Modal):
    """Add or modify a stack element of a given kind."""

    def __init__(self, master, kind: str, element=None, units_label: str = ""):
        super().__init__(master, KIND_LABEL.get(kind, kind))
        self.kind = kind
        self.element = element
        self._vars: dict[str, tk.StringVar] = {}

        fields = STRUCTURE_FIELDS[kind]
        if units_label:
            ttk.Label(self.body, text=f"Dimensions in {units_label}.",
                      foreground="#666").grid(row=0, column=0, columnspan=2,
                                              sticky="w", pady=(0, 6))
        for i, (label, attr, typ) in enumerate(fields, start=1):
            ttk.Label(self.body, text=label).grid(row=i, column=0, sticky="w",
                                                  padx=(0, 8), pady=2)
            var = tk.StringVar()
            if element is not None:
                val = getattr(element, attr)
                var.set("" if val is None else str(val))
            self._vars[attr] = var
            ttk.Entry(self.body, textvariable=var, width=22).grid(
                row=i, column=1, sticky="ew", pady=2)

        btns = ttk.Frame(self.body)
        btns.grid(row=len(fields) + 1, column=0, columnspan=2, pady=(10, 0),
                  sticky="e")
        action = "Modify" if element is not None else "Add"
        ttk.Button(btns, text=action, command=self._ok).pack(side="left", padx=3)
        if element is not None:
            ttk.Button(btns, text="Delete", command=self._delete).pack(
                side="left", padx=3)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left",
                                                                    padx=3)
        self._finish()

    def _ok(self):
        values = {}
        for label, attr, typ in STRUCTURE_FIELDS[self.kind]:
            try:
                values[attr] = _coerce(self._vars[attr].get(), typ)
            except ValueError:
                messagebox.showerror("Invalid value",
                                        f"'{label}' must be a number.")
                return
        if self.element is None:
            el = _KIND_CLASS[self.kind]()
            for attr, val in values.items():
                setattr(el, attr, val)
            self.result = ("add", el)
        else:
            for attr, val in values.items():
                setattr(self.element, attr, val)
            self.result = ("modify", self.element)
        self.destroy()

    def _delete(self):
        self.result = ("delete", self.element)
        self.destroy()


class RunDialog(_Modal):
    """BEM run controls: coupling length, rise time, segment counts."""

    def __init__(self, master, cs):
        super().__init__(master, "Run BEM MMTL Simulation")
        self.cs = cs
        self._v = {
            "coupling": tk.StringVar(value=str(cs.coupling_length)),
            "risetime": tk.StringVar(value=str(cs.rise_time)),
            "cseg": tk.StringVar(value=str(cs.cseg)),
            "dseg": tk.StringVar(value=str(cs.dseg)),
        }
        rows = [
            ("Coupling Length (m)", "coupling"),
            ("Risetime (ps)", "risetime"),
            ("Conductor Segments", "cseg"),
            ("Dielectric Segments", "dseg"),
        ]
        for i, (label, key) in enumerate(rows):
            ttk.Label(self.body, text=label).grid(row=i, column=0, sticky="w",
                                                  padx=(0, 8), pady=3)
            ttk.Entry(self.body, textvariable=self._v[key], width=16).grid(
                row=i, column=1, pady=3)
        btns = ttk.Frame(self.body)
        btns.grid(row=len(rows), column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Run", command=self._ok).pack(side="left", padx=3)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left",
                                                                    padx=3)
        self._finish()

    def _ok(self):
        try:
            self.result = {
                "coupling_length": float(self._v["coupling"].get()),
                "rise_time": float(self._v["risetime"].get()),
                "cseg": int(float(self._v["cseg"].get())),
                "dseg": int(float(self._v["dseg"].get())),
            }
        except ValueError:
            messagebox.showerror("Invalid value", "Run controls must be numbers.")
            return
        self.destroy()


class IterateDialog(_Modal):
    """Iterate a conductor group's width to a target characteristic impedance."""

    def __init__(self, master, cs):
        super().__init__(master, "Iterate to Target Impedance")
        groups = [el.name for el in cs.conductor_groups()]
        self._group = tk.StringVar(value=groups[0] if groups else "")
        self._index = tk.StringVar(value="0")
        self._target = tk.StringVar(value="50")

        ttk.Label(self.body, text="Conductor Group").grid(row=0, column=0,
                                                           sticky="w", pady=3)
        ttk.Combobox(self.body, textvariable=self._group, values=groups,
                     state="readonly", width=18).grid(row=0, column=1, pady=3)
        ttk.Label(self.body, text="Conductor Index").grid(row=1, column=0,
                                                           sticky="w", pady=3)
        ttk.Entry(self.body, textvariable=self._index, width=20).grid(
            row=1, column=1, pady=3)
        ttk.Label(self.body, text="Target Z0 (ohm)").grid(row=2, column=0,
                                                          sticky="w", pady=3)
        ttk.Entry(self.body, textvariable=self._target, width=20).grid(
            row=2, column=1, pady=3)
        btns = ttk.Frame(self.body)
        btns.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Iterate", command=self._ok).pack(side="left", padx=3)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left",
                                                                    padx=3)
        self._finish()

    def _ok(self):
        try:
            self.result = {
                "group": self._group.get(),
                "conductor_index": int(float(self._index.get())),
                "target": float(self._target.get()),
            }
        except ValueError:
            messagebox.showerror("Invalid value", "Index/target must be numbers.")
            return
        self.destroy()


# fields that make sense to sweep, per kind
_SWEEPABLE = {
    "dielectric_layer": ["thickness", "permittivity"],
    "dielectric_block": ["width", "height", "permittivity"],
    "rectangle_conductors": ["width", "height", "pitch"],
    "trapezoid_conductors": ["top_width", "bottom_width", "height", "pitch"],
    "circle_conductors": ["diameter", "pitch"],
}
_FIELD_TO_CSDL = {
    "thickness": "thickness", "permittivity": "permittivity", "width": "width",
    "height": "height", "pitch": "pitch", "top_width": "topWidth",
    "bottom_width": "bottomWidth", "diameter": "diameter",
}


class SweepDialog(_Modal):
    """Pick parameters to sweep and their start/stop/iteration ranges."""

    def __init__(self, master, cs):
        super().__init__(master, "Sweep Parameters")
        self.cs = cs
        self.rows = []  # (enabled_var, label, start_var, stop_var, n_var)

        ttk.Label(self.body, text="Select parameters and ranges to sweep:",
                  foreground="#444").grid(row=0, column=0, columnspan=5,
                                          sticky="w", pady=(0, 6))
        hdr = ["", "Parameter", "Start", "End", "# Iter"]
        for c, text in enumerate(hdr):
            ttk.Label(self.body, text=text, font=("TkDefaultFont", 9, "bold")
                      ).grid(row=1, column=c, padx=4, sticky="w")

        candidates = self._candidates()
        for r, (label, current) in enumerate(candidates, start=2):
            en = tk.BooleanVar(value=False)
            start = tk.StringVar(value=str(current))
            stop = tk.StringVar(value=str(current))
            n = tk.StringVar(value="5")
            ttk.Checkbutton(self.body, variable=en).grid(row=r, column=0)
            ttk.Label(self.body, text=label).grid(row=r, column=1, sticky="w",
                                                  padx=4)
            ttk.Entry(self.body, textvariable=start, width=10).grid(row=r, column=2)
            ttk.Entry(self.body, textvariable=stop, width=10).grid(row=r, column=3)
            ttk.Entry(self.body, textvariable=n, width=6).grid(row=r, column=4)
            self.rows.append((en, label, start, stop, n))

        self._metric = tk.StringVar(value="impedance")
        mrow = len(candidates) + 2
        ttk.Label(self.body, text="Metric").grid(row=mrow, column=1, sticky="w",
                                                 padx=4, pady=(8, 0))
        ttk.Combobox(self.body, textvariable=self._metric, state="readonly",
                     values=["impedance", "eps_eff", "velocity", "delay"],
                     width=12).grid(row=mrow, column=2, columnspan=2, sticky="w",
                                    pady=(8, 0))

        btns = ttk.Frame(self.body)
        btns.grid(row=mrow + 1, column=0, columnspan=5, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="OK", command=self._ok).pack(side="left", padx=3)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left",
                                                                    padx=3)
        self._finish()

    def _candidates(self):
        out = [
            ("couplingLength", self.cs.coupling_length),
            ("riseTime", self.cs.rise_time),
            ("CSEG", self.cs.cseg),
            ("DSEG", self.cs.dseg),
        ]
        for el in self.cs.stack:
            for attr in _SWEEPABLE.get(el.kind, []):
                out.append((f"{el.name}.{_FIELD_TO_CSDL[attr]}", getattr(el, attr)))
        return out

    def _ok(self):
        from pymmtl import sweep

        specs = []
        for en, label, start, stop, n in self.rows:
            if not en.get():
                continue
            spec_str = f"{label}={start.get()}:{stop.get()}:{n.get()}"
            try:
                specs.append(sweep.parse_spec(spec_str))
            except (ValueError, KeyError) as exc:
                messagebox.showerror("Invalid sweep", str(exc))
                return
        if not specs:
            messagebox.showinfo("Sweep", "Select at least one parameter.")
            return
        self.result = {"specs": specs, "metric": self._metric.get()}
        self.destroy()
