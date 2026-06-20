"""Windows that display solver results, the solver log, and sweep tables."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

import numpy as np

from pymmtl import sweep as _sweep


def format_results(res) -> str:
    """Human-readable summary of a :class:`pymmtl.results.Results`."""
    lines: list[str] = []
    names = res.names
    lines.append(f"Signal lines: {len(names)}  ({', '.join(names)})")
    meta = res.meta
    if meta:
        lines.append(
            f"coupling={meta.get('coupling_length', '?')} m  "
            f"risetime={meta.get('rise_time', '?')} ps  "
            f"CSEG={meta.get('cseg', '?')}  DSEG={meta.get('dseg', '?')}"
        )
    lines.append("")

    def matrix(title, M, unit):
        if M is None:
            return
        lines.append(f"{title} ({unit}):")
        header = "            " + "".join(f"{n:>15s}" for n in names)
        lines.append(header)
        for i, ni in enumerate(names):
            row = f"{ni:>12s}" + "".join(
                f"{M[i, j]:15.5e}" for j in range(len(names))
            )
            lines.append(row)
        lines.append("")

    matrix("Capacitance C (electrostatic induction)", res.C, "F/m")
    matrix("Inductance L", res.L, "H/m")
    matrix("DC Resistance Rdc", res.Rdc, "ohm/m")

    lines.append("Per signal line:")
    lines.append(f"{'name':>12s}{'Z0 [ohm]':>14s}{'eps_eff':>12s}"
                 f"{'v [m/s]':>16s}{'delay [s/m]':>16s}")
    for n in names:
        lines.append(
            f"{n:>12s}"
            f"{res.impedance.get(n, float('nan')):14.4f}"
            f"{res.eps_eff.get(n, float('nan')):12.4f}"
            f"{res.velocity.get(n, float('nan')):16.5e}"
            f"{res.delay.get(n, float('nan')):16.5e}"
        )
    lines.append("")

    if res.odd_even:
        lines.append("Odd / Even modes:")
        for k, (odd, even) in res.odd_even.items():
            lines.append(f"  {k:>10s}: odd={odd:.5g}   even={even:.5g}")
        lines.append("")

    if res.fxt or res.bxt:
        lines.append("Crosstalk (ratio, dB):")
        for tag, d in (("FXT", res.fxt), ("BXT", res.bxt)):
            for (a, b), (ratio, db) in d.items():
                lines.append(f"  {tag}({a},{b}) = {ratio:.5g}  ({db:.3f} dB)")
        lines.append("")

    if res.asymmetry:
        lines.append("Asymmetry ratios (max / avg %):")
        for k, (mx, avg) in res.asymmetry.items():
            lines.append(f"  {k}: {mx:.4f} / {avg:.4f}")
    return "\n".join(lines)


class ResultWindow(tk.Toplevel):
    """Notebook with a results summary and the raw solver log."""

    def __init__(self, master, res, log: str, title: str = "MMTL Results"):
        super().__init__(master)
        self.title(title)
        self.geometry("780x560")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        summary = _scrolled_text(nb)
        summary.insert("1.0", format_results(res))
        summary.configure(state="disabled")
        nb.add(summary.master, text="Results")

        logbox = _scrolled_text(nb)
        logbox.insert("1.0", log or "(no log captured)")
        logbox.configure(state="disabled")
        nb.add(logbox.master, text="Solver Log")


class SweepWindow(tk.Toplevel):
    """Table of sweep results with CSV export."""

    def __init__(self, master, table, title: str = "Sweep Results"):
        super().__init__(master)
        self.title(title)
        self.geometry("720x420")
        self.table = table

        cols = table.columns
        tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=110, anchor="e")
        for row in table.rows:
            tree.insert("", "end", values=[_fmt(row.get(c)) for c in cols])
        vsb = ttk.Scrollbar(self, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Save CSV...", command=self._save).pack(
            side="right", padx=6, pady=6)

    def _save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            _sweep.write_csv(self.table, path)


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.6g}"
    return v


def _scrolled_text(parent) -> tk.Text:
    frame = ttk.Frame(parent)
    text = tk.Text(frame, wrap="none", font=("TkFixedFont", 9))
    vsb = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
    text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    text.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return text
