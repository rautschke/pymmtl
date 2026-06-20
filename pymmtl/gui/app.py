"""Main TNT-style application window.

Layout mirrors the original Tcl/Tk TNT: a menu bar; a title field and units
selector; "Create New Structure" buttons; a layer-stackup list; and a zoomable
cross-section drawing.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pymmtl import csdl, iterate as iteratemod, model, rlgc, solver, sweep as sweepmod
from pymmtl import units as unitsmod
from pymmtl.gui import dialogs
from pymmtl.gui.canvas import CrossSectionCanvas
from pymmtl.gui.resultview import ResultWindow, SweepWindow

_NEW_BUTTONS = [
    ("New Ground Plane", "ground_plane"),
    ("New Dielectric Layer", "dielectric_layer"),
    ("New Dielectric Block", "dielectric_block"),
    ("New Rectangle Conductors", "rectangle_conductors"),
    ("New Trapezoid Conductors", "trapezoid_conductors"),
    ("New Circular Conductors", "circle_conductors"),
]


class TNTApp:
    def __init__(self, root: tk.Tk, path: str | None = None):
        self.root = root
        self.root.title("pymmtl - TNT")
        self.root.geometry("640x720")
        self.cs = model.CrossSection(title="Untitled", default_units="mils")
        self.path: str | None = None

        self._build_menu()
        self._build_widgets()

        if path:
            self.open_path(path)
        else:
            self._sync_from_model()

    # ----------------------------------------------------------------- UI -- #
    def _build_menu(self):
        bar = tk.Menu(self.root)

        filem = tk.Menu(bar, tearoff=0)
        filem.add_command(label="New", command=self.file_new)
        filem.add_command(label="Open...", command=self.file_open)
        filem.add_command(label="Save", command=self.file_save)
        filem.add_command(label="Save As...", command=self.file_save_as)
        filem.add_separator()
        filem.add_command(label="Export HSPICE W-element...",
                          command=self.export_hspice)
        filem.add_separator()
        filem.add_command(label="Quit", command=self.root.quit)
        bar.add_cascade(label="File", menu=filem)

        bemm = tk.Menu(bar, tearoff=0)
        bemm.add_command(label="Run BEM MMTL Simulation", command=self.run_bem)
        bar.add_cascade(label="BEM", menu=bemm)

        sweepm = tk.Menu(bar, tearoff=0)
        sweepm.add_command(label="Sweep Simulation", command=self.run_sweep)
        bar.add_cascade(label="Sweep", menu=sweepm)

        iterm = tk.Menu(bar, tearoff=0)
        iterm.add_command(label="Iterate to Target Z0", command=self.run_iterate)
        bar.add_cascade(label="Iterate", menu=iterm)

        helpm = tk.Menu(bar, tearoff=0)
        helpm.add_command(label="About", command=self._about)
        bar.add_cascade(label="Help", menu=helpm)

        self.root.config(menu=bar)

    def _build_widgets(self):
        # top: title + units
        top = ttk.Frame(self.root, padding=(8, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Title").pack(side="left")
        self.title_var = tk.StringVar()
        self.title_var.trace_add("write", lambda *_: self._on_title())
        ttk.Entry(top, textvariable=self.title_var, width=40).pack(
            side="left", padx=6)
        ttk.Label(top, text="Default Units").pack(side="left", padx=(12, 2))
        self.units_var = tk.StringVar()
        units_box = ttk.Combobox(top, textvariable=self.units_var,
                                 state="readonly", width=10,
                                 values=list(unitsmod.LENGTH_UNITS))
        units_box.pack(side="left")
        units_box.bind("<<ComboboxSelected>>", lambda e: self._on_units())

        mid = ttk.Frame(self.root, padding=(8, 0))
        mid.pack(fill="x")

        # left: structure buttons
        left = ttk.LabelFrame(mid, text="Create New Structure", padding=6)
        left.pack(side="left", fill="y")
        for label, kind in _NEW_BUTTONS:
            ttk.Button(left, text=label, width=22,
                       command=lambda k=kind: self.new_structure(k)).pack(
                pady=2, fill="x")

        # right: layer stackup
        right = ttk.LabelFrame(mid, text="Layer Stackup", padding=6)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.stack_list = tk.Listbox(right, height=10)
        self.stack_list.pack(side="left", fill="both", expand=True)
        self.stack_list.bind("<Double-Button-1>", lambda e: self.edit_selected())
        sbar = ttk.Scrollbar(right, orient="vertical",
                             command=self.stack_list.yview)
        self.stack_list.configure(yscrollcommand=sbar.set)
        sbar.pack(side="left", fill="y")
        ctrl = ttk.Frame(right)
        ctrl.pack(side="left", fill="y", padx=(6, 0))
        ttk.Button(ctrl, text="Up", width=6, command=lambda: self.move(-1)).pack(pady=2)
        ttk.Button(ctrl, text="Down", width=6, command=lambda: self.move(1)).pack(pady=2)
        ttk.Button(ctrl, text="Edit", width=6, command=self.edit_selected).pack(pady=2)
        ttk.Button(ctrl, text="Delete", width=6, command=self.delete_selected).pack(pady=2)

        # canvas + zoom
        cf = ttk.Frame(self.root, padding=(8, 6))
        cf.pack(fill="both", expand=True)
        zoom = ttk.Frame(cf)
        zoom.pack(fill="x")
        ttk.Button(zoom, text="Zoom In", command=lambda: self.canvas.zoom_in()).pack(side="left")
        ttk.Button(zoom, text="Zoom Out", command=lambda: self.canvas.zoom_out()).pack(side="left", padx=4)
        ttk.Button(zoom, text="Fit", command=lambda: self.canvas.zoom_fit()).pack(side="left")
        self.canvas = CrossSectionCanvas(cf, height=320)
        self.canvas.pack(fill="both", expand=True, pady=(6, 0))

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status, relief="sunken",
                  anchor="w").pack(fill="x", side="bottom")

    # -------------------------------------------------------- model sync -- #
    def _sync_from_model(self):
        self.title_var.set(self.cs.title)
        self.units_var.set(self.cs.default_units)
        self.refresh()

    def refresh(self):
        """Redraw the stackup list (top-to-bottom) and the canvas."""
        self.stack_list.delete(0, "end")
        for el in reversed(self.cs.stack):  # display top -> bottom
            extra = ""
            if el.kind == "dielectric_layer":
                extra = f"  (eps={el.permittivity:g}, t={el.thickness:g})"
            elif el.kind in model.CONDUCTOR_KINDS:
                extra = f"  (x{el.number})"
            self.stack_list.insert("end",
                                   f"{dialogs.KIND_LABEL[el.kind]}: {el.name}{extra}")
        self.canvas.set_cross_section(self.cs)

    def _selected_index(self) -> int | None:
        sel = self.stack_list.curselection()
        if not sel:
            return None
        # listbox is reversed relative to cs.stack
        return len(self.cs.stack) - 1 - sel[0]

    def _on_title(self):
        self.cs.title = self.title_var.get()

    def _on_units(self):
        self.cs.default_units = self.units_var.get()
        self.canvas.set_cross_section(self.cs)

    # ----------------------------------------------------- structure ops -- #
    def new_structure(self, kind: str):
        dlg = dialogs.PropertyDialog(self.root, kind, units_label=self.cs.default_units)
        if dlg.result and dlg.result[0] == "add":
            self.cs.stack.append(dlg.result[1])
            self.refresh()

    def edit_selected(self):
        idx = self._selected_index()
        if idx is None:
            return
        el = self.cs.stack[idx]
        dlg = dialogs.PropertyDialog(self.root, el.kind, element=el,
                                     units_label=self.cs.default_units)
        if not dlg.result:
            return
        action = dlg.result[0]
        if action == "delete":
            del self.cs.stack[idx]
        self.refresh()

    def delete_selected(self):
        idx = self._selected_index()
        if idx is None:
            return
        del self.cs.stack[idx]
        self.refresh()

    def move(self, direction: int):
        idx = self._selected_index()
        if idx is None:
            return
        new = idx + (-direction)  # display is reversed, so invert
        if 0 <= new < len(self.cs.stack):
            self.cs.stack[idx], self.cs.stack[new] = (
                self.cs.stack[new], self.cs.stack[idx])
            self.refresh()
            # keep selection on the moved item
            self.stack_list.selection_set(len(self.cs.stack) - 1 - new)

    # --------------------------------------------------------- file ops -- #
    def file_new(self):
        self.cs = model.CrossSection(title="Untitled", default_units="mils")
        self.path = None
        self._sync_from_model()
        self.status.set("New cross-section")

    def file_open(self):
        path = filedialog.askopenfilename(filetypes=[("Cross-section", "*.xsctn"),
                                                     ("All files", "*")])
        if path:
            self.open_path(path)

    def open_path(self, path: str):
        try:
            self.cs = csdl.load(path)
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))
            return
        self.path = path
        self._sync_from_model()
        self.status.set(f"Opened {os.path.basename(path)}")

    def file_save(self):
        if not self.path:
            return self.file_save_as()
        csdl.dump(self.cs, self.path)
        self.status.set(f"Saved {os.path.basename(self.path)}")

    def file_save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".xsctn",
                                            filetypes=[("Cross-section", "*.xsctn")])
        if path:
            self.path = path
            self.file_save()

    def export_hspice(self):
        try:
            out = self._run_solver()
        except solver.SolverError as exc:
            messagebox.showerror("Solver error", str(exc))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".hspice-w.rlgc",
            filetypes=[("HSPICE W-element", "*.rlgc"), ("All files", "*")])
        if not path:
            return
        rlgc.write_hspice_w_element(self.cs, out.results, path)
        self.status.set(f"Exported {os.path.basename(path)}")

    # ------------------------------------------------------- simulation -- #
    def _run_solver(self, **overrides) -> solver.RunOutput:
        self.status.set("Running solver...")
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            return solver.run(self.cs, **overrides)
        finally:
            self.root.config(cursor="")
            self.status.set("Ready")

    def run_bem(self):
        dlg = dialogs.RunDialog(self.root, self.cs)
        if not dlg.result:
            return
        # persist run controls into the model (matches TNT)
        self.cs.coupling_length = dlg.result["coupling_length"]
        self.cs.rise_time = dlg.result["rise_time"]
        self.cs.cseg = dlg.result["cseg"]
        self.cs.dseg = dlg.result["dseg"]
        try:
            out = self._run_solver()
        except solver.SolverError as exc:
            messagebox.showerror("Solver error", str(exc))
            return
        ResultWindow(self.root, out.results, out.log,
                     title=f"MMTL Results - {self.cs.title}")

    def run_sweep(self):
        if not self.cs.conductor_groups():
            messagebox.showinfo("Sweep", "Add a conductor first.")
            return
        dlg = dialogs.SweepDialog(self.root, self.cs)
        if not dlg.result:
            return
        specs = dlg.result["specs"]
        metric = dlg.result["metric"]
        total = 1
        for s in specs:
            total *= len(s.values)
        if total > 200 and not messagebox.askyesno(
                "Sweep", f"This will run {total} simulations. Continue?"):
            return
        self.root.config(cursor="watch")

        def progress(i, n, row):
            self.status.set(f"Sweep {i}/{n}")
            self.root.update_idletasks()

        try:
            table = sweepmod.run_sweep(self.cs, specs, output=metric,
                                       progress=progress)
        except Exception as exc:
            messagebox.showerror("Sweep error", str(exc))
            return
        finally:
            self.root.config(cursor="")
            self.status.set("Ready")
        SweepWindow(self.root, table, title=f"Sweep - {self.cs.title}")

    def run_iterate(self):
        if not self.cs.conductor_groups():
            messagebox.showinfo("Iterate", "Add a conductor first.")
            return
        dlg = dialogs.IterateDialog(self.root, self.cs)
        if not dlg.result:
            return
        self.root.config(cursor="watch")
        self.status.set("Iterating...")
        self.root.update_idletasks()
        try:
            res = iteratemod.iterate_width(
                self.cs, dlg.result["group"], dlg.result["target"],
                conductor_index=dlg.result["conductor_index"])
        except Exception as exc:
            messagebox.showerror("Iterate error", str(exc))
            return
        finally:
            self.root.config(cursor="")
            self.status.set("Ready")
        msg = (f"Converged: {res.converged}\n"
               f"Width = {res.width:.6g} {self.cs.default_units}\n"
               f"Z0 = {res.impedance:.4f} ohm (target {dlg.result['target']})\n"
               f"Iterations: {res.iterations}")
        if res.converged and messagebox.askyesno(
                "Iterate", msg + "\n\nApply this width to the model?"):
            el = self.cs.find_group(dlg.result["group"])
            attr = iteratemod._WIDTH_ATTR[el.kind]
            setattr(el, attr, res.width)
            self.refresh()
        else:
            messagebox.showinfo("Iterate result", msg)

    def _about(self):
        messagebox.showinfo(
            "About pymmtl",
            "pymmtl - a Python front-end for the MMTL BEM transmission-line\n"
            "solver. Reimplements the TNT GUI in Tkinter; the numerical core\n"
            "is the vendored C++ mmtl_bem binary.")


def main(argv: list[str] | None = None) -> int:
    import sys

    args = argv if argv is not None else sys.argv[1:]
    path = args[0] if args else None
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    TNTApp(root, path=path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
