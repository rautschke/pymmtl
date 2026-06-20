"""2-D cross-section drawing on a Tk canvas (zoomable)."""

from __future__ import annotations

import tkinter as tk

from pymmtl.model import CrossSection

_DIELECTRIC_FILL = "#cde6c0"
_DIELECTRIC_OUTLINE = "#5a8f4a"
_SIGNAL_FILL = "#f2d33a"
_SIGNAL_OUTLINE = "#9a8200"
_GROUND_FILL = "#9aa0a6"
_GROUND_OUTLINE = "#5f6368"
_PLANE_FILL = "#7a7f85"


class CrossSectionCanvas(tk.Canvas):
    """Draws a :class:`CrossSection`'s resolved geometry, fit-to-window with zoom."""

    def __init__(self, master, **kw):
        kw.setdefault("background", "white")
        kw.setdefault("highlightthickness", 0)
        super().__init__(master, **kw)
        self._cs: CrossSection | None = None
        self._zoom = 1.0
        self._fit_scale = 1.0
        self._offset = (0.0, 0.0)
        self.bind("<Configure>", lambda e: self.redraw())

    # -- public API -------------------------------------------------------- #
    def set_cross_section(self, cs: CrossSection) -> None:
        self._cs = cs
        self.zoom_fit()

    def zoom_in(self) -> None:
        self._zoom *= 1.25
        self.redraw()

    def zoom_out(self) -> None:
        self._zoom /= 1.25
        self.redraw()

    def zoom_fit(self) -> None:
        self._zoom = 1.0
        self.redraw()

    # -- drawing ----------------------------------------------------------- #
    def redraw(self) -> None:
        self.delete("all")
        if self._cs is None:
            return
        geo = self._cs.resolve()
        x0, y0, x1, y1 = geo.bounds
        if x1 <= x0 or y1 <= y0:
            self.create_text(10, 10, anchor="nw", fill="#888",
                             text="(empty cross-section)")
            return

        w = max(self.winfo_width(), 50)
        h = max(self.winfo_height(), 50)
        pad = 40
        sx = (w - 2 * pad) / (x1 - x0)
        sy = (h - 2 * pad) / (y1 - y0)
        self._fit_scale = min(sx, sy)
        scale = self._fit_scale * self._zoom
        # center
        cx = 0.5 * (x0 + x1)
        cy = 0.5 * (y0 + y1)
        self._offset = (w / 2 - cx * scale, h / 2 + cy * scale)
        self._scale = scale

        # dielectrics (drawn first, behind conductors)
        for d in geo.dielectrics:
            self._rect(d.x0, d.y0, d.x1, d.y1, _DIELECTRIC_FILL,
                       _DIELECTRIC_OUTLINE)
            lx, ly = self._pt(d.x0, 0.5 * (d.y0 + d.y1))
            self.create_text(
                lx + 6, ly, anchor="w", fill="#3a5d30",
                text=f"eps={d.permittivity:g}",
                font=("TkDefaultFont", 8),
            )

        # ground planes
        for gp in geo.ground_planes:
            self._rect(gp.x0, gp.y0, gp.x1, gp.y1, _PLANE_FILL, _GROUND_OUTLINE)

        # conductors
        for c in geo.conductors:
            fill = _GROUND_FILL if c.is_ground else _SIGNAL_FILL
            outline = _GROUND_OUTLINE if c.is_ground else _SIGNAL_OUTLINE
            if c.shape == "rectangle":
                self._rect(c.x0, c.y0, c.x1, c.y1, fill, outline)
            elif c.shape == "circle":
                self._oval(c.cx, c.cy, c.radius, fill, outline)
            else:
                self._poly(c.points, fill, outline)
            if c.name and not c.is_ground:
                self.create_text(
                    *self._pt(0.5 * (c.x0 + c.x1), 0.5 * (c.y0 + c.y1)),
                    text=c.name, font=("TkDefaultFont", 7),
                )

        # title
        self.create_text(w / 2, 12, text=self._cs.title, font=("TkDefaultFont", 9, "bold"))

    # -- coordinate transform --------------------------------------------- #
    def _pt(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self._offset
        return (ox + x * self._scale, oy - y * self._scale)

    def _rect(self, x0, y0, x1, y1, fill, outline):
        ax, ay = self._pt(x0, y0)
        bx, by = self._pt(x1, y1)
        self.create_rectangle(ax, ay, bx, by, fill=fill, outline=outline)

    def _oval(self, cx, cy, r, fill, outline):
        ax, ay = self._pt(cx - r, cy + r)
        bx, by = self._pt(cx + r, cy - r)
        self.create_oval(ax, ay, bx, by, fill=fill, outline=outline)

    def _poly(self, points, fill, outline):
        flat = []
        for x, y in points:
            px, py = self._pt(x, y)
            flat += [px, py]
        self.create_polygon(*flat, fill=fill, outline=outline)
