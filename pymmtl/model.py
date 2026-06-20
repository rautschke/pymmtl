"""In-memory cross-section model.

This is the Python replacement for the original Tcl ``csdl`` package: an
ordered "layer stackup" (bottom -> top) of ground planes, dielectric layers,
dielectric blocks, and conductor groups, plus the global simulation parameters.

Dimensions are stored in the cross-section's ``default_units`` (e.g. mils),
exactly as they appear in ``.xsctn`` files, so writing back is loss-free.
:meth:`CrossSection.resolve` converts to SI meters and reproduces the C++
parser's geometry layout (``nmmtl_parse_xsctn.cpp``) for drawing/validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pymmtl import units


# --------------------------------------------------------------------------- #
#  Stack element dataclasses (dimensions in the cross-section's default units) #
# --------------------------------------------------------------------------- #
@dataclass
class GroundPlane:
    name: str = ""
    thickness: float | None = None  # None -> omit (solver uses a default)
    x_offset: float = 0.0
    y_offset: float = 0.0
    kind: str = field(default="ground_plane", init=False)


@dataclass
class DielectricLayer:
    name: str = ""
    thickness: float = 0.0
    permittivity: float = 1.0
    loss_tangent: float = 0.0
    permeability: float = 1.0
    x_offset: float = 0.0
    y_offset: float = 0.0
    kind: str = field(default="dielectric_layer", init=False)


@dataclass
class DielectricBlock:
    """``RectangleDielectric`` - an arbitrary rectangle of dielectric."""

    name: str = ""
    width: float = 0.0
    height: float = 0.0
    permittivity: float = 1.0
    number: int = 1
    pitch: float = 0.0
    x_offset: float = 0.0
    y_offset: float = 0.0
    kind: str = field(default="dielectric_block", init=False)


@dataclass
class RectangleConductors:
    name: str = ""
    width: float = 0.0
    height: float = 0.0
    pitch: float = 0.0
    conductivity: float = units.DEFAULT_CONDUCTIVITY
    number: int = 1
    x_offset: float = 0.0
    y_offset: float = 0.0
    kind: str = field(default="rectangle_conductors", init=False)
    type_letter: str = field(default="R", init=False)


@dataclass
class TrapezoidConductors:
    name: str = ""
    top_width: float = 0.0
    bottom_width: float = 0.0
    height: float = 0.0
    pitch: float = 0.0
    conductivity: float = units.DEFAULT_CONDUCTIVITY
    number: int = 1
    x_offset: float = 0.0
    y_offset: float = 0.0
    kind: str = field(default="trapezoid_conductors", init=False)
    type_letter: str = field(default="T", init=False)


@dataclass
class CircleConductors:
    name: str = ""
    diameter: float = 0.0
    pitch: float = 0.0
    conductivity: float = units.DEFAULT_CONDUCTIVITY
    number: int = 1
    x_offset: float = 0.0
    y_offset: float = 0.0
    kind: str = field(default="circle_conductors", init=False)
    type_letter: str = field(default="C", init=False)


CONDUCTOR_KINDS = (
    "rectangle_conductors",
    "trapezoid_conductors",
    "circle_conductors",
)


def is_ground_group(name: str) -> bool:
    """Conductor groups whose name starts with ``gr`` are ground wires
    (``nmmtl_parse_xsctn.cpp``: ``if (strncmp(name, "gr", 2))``)."""
    return name.startswith("gr")


# --------------------------------------------------------------------------- #
#  Resolved (absolute, SI-meter) geometry for drawing / layout validation     #
# --------------------------------------------------------------------------- #
@dataclass
class ResolvedRect:
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class ResolvedDielectric(ResolvedRect):
    permittivity: float = 1.0


@dataclass
class ResolvedConductor:
    name: str
    shape: str  # "rectangle" | "circle" | "polygon"
    is_ground: bool = False
    conductivity: float = 0.0
    # rectangle / bbox
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    # circle
    cx: float = 0.0
    cy: float = 0.0
    radius: float = 0.0
    # polygon
    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class ResolvedGeometry:
    dielectrics: list[ResolvedDielectric] = field(default_factory=list)
    conductors: list[ResolvedConductor] = field(default_factory=list)
    ground_planes: list[ResolvedRect] = field(default_factory=list)
    total_width: float = 0.0
    bounds: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


# --------------------------------------------------------------------------- #
#  Cross-section                                                              #
# --------------------------------------------------------------------------- #
@dataclass
class CrossSection:
    title: str = ""
    default_units: str = units.DEFAULT_LENGTH_UNITS
    coupling_length: float = 0.0  # meters
    rise_time: float = 0.0        # picoseconds
    frequency: str = ""           # informational (raw string e.g. "1000MHz")
    cseg: int = 10
    dseg: int = 10
    stack: list = field(default_factory=list)  # ordered bottom -> top

    # -- convenience ------------------------------------------------------- #
    def add(self, element) -> "CrossSection":
        self.stack.append(element)
        return self

    def conductor_groups(self):
        """Signal conductor groups (ground groups excluded), in stack order."""
        return [
            el
            for el in self.stack
            if el.kind in CONDUCTOR_KINDS and not is_ground_group(el.name)
        ]

    def signal_names(self) -> list[str]:
        """Auto-generated per-conductor signal names, in definition order, matching
        the solver (``<group><typeletter><global_index>``)."""
        return [name for name, _, _ in self.signal_conductors()]

    def signal_conductors(self):
        """List of ``(signal_name, group_element, local_index)`` in definition order."""
        out = []
        idx = 0
        for el in self.stack:
            if el.kind in CONDUCTOR_KINDS and not is_ground_group(el.name):
                for k in range(max(1, el.number)):
                    out.append((f"{el.name}{el.type_letter}{idx}", el, k))
                    idx += 1
        return out

    def signal_name_for(self, group_name: str, local_index: int = 0) -> str:
        """Signal name for conductor ``local_index`` of the named group."""
        for name, el, k in self.signal_conductors():
            if el.name == group_name and k == local_index:
                return name
        raise KeyError(f"no conductor {group_name}[{local_index}]")

    def find_group(self, name: str):
        """Return the stack element with the given name (or ``None``)."""
        for el in self.stack:
            if el.name == name:
                return el
        return None

    # -- geometry layout --------------------------------------------------- #
    def resolve(self) -> ResolvedGeometry:
        """Reproduce the C++ parser layout in SI meters.

        * dielectric layers stack upward from y=0 (top of the bottom ground plane);
        * conductor groups rest atop the most-recently-defined dielectric layer;
        * planar dielectric layers expand horizontally to ``[-W, 2W]`` where ``W``
          is the rightmost conductor edge (``nmmtl_parse_xsctn.cpp:850-853``).
        """
        u = units.LENGTH_UNITS[self.default_units]
        geo = ResolvedGeometry()

        y = 0.0                 # running top of the stack (meters)
        last_diel_top = 0.0     # top of most recent dielectric layer
        planar_layers: list[ResolvedDielectric] = []  # x to be expanded later
        seen_ground_plane = False

        for el in self.stack:
            if el.kind == "ground_plane":
                t = (
                    units.DEFAULT_GND_THICKNESS_M
                    if el.thickness is None
                    else el.thickness * u
                )
                if not seen_ground_plane:
                    # bottom plane: its top is y=0
                    geo.ground_planes.append(ResolvedRect(0.0, -t, 0.0, 0.0))
                    seen_ground_plane = True
                else:
                    # top plane (stripline): sits on top of the stack
                    geo.ground_planes.append(ResolvedRect(0.0, y, 0.0, y + t))
                continue

            if el.kind == "dielectric_layer":
                y0 = y + el.y_offset * u
                y1 = y0 + el.thickness * u
                d = ResolvedDielectric(0.0, y0, 0.0, y1, el.permittivity)
                planar_layers.append(d)
                geo.dielectrics.append(d)
                last_diel_top = y1
                y = y1
                continue

            if el.kind == "dielectric_block":
                base_y = last_diel_top + el.y_offset * u
                w = el.width * u
                h = el.height * u
                pitch = el.pitch * u
                for k in range(max(1, el.number)):
                    x0 = el.x_offset * u + k * pitch
                    geo.dielectrics.append(
                        ResolvedDielectric(x0, base_y, x0 + w, base_y + h,
                                           el.permittivity)
                    )
                continue

            if el.kind in CONDUCTOR_KINDS:
                base_y = last_diel_top + el.y_offset * u
                pitch = el.pitch * u
                ground = is_ground_group(el.name)
                for k in range(max(1, el.number)):
                    xoff = el.x_offset * u + k * pitch
                    rc = self._resolve_conductor(el, xoff, base_y, u, ground)
                    rc.conductivity = el.conductivity
                    geo.conductors.append(rc)
                continue

        # assign signal names in definition order (global index)
        sidx = 0
        for c in geo.conductors:
            if c.is_ground:
                c.name = ""
            else:
                # group name + type letter already embedded via _resolve_conductor
                c.name = f"{c.name}{sidx}"
                sidx += 1

        # total width = rightmost conductor edge
        total_width = 0.0
        for c in geo.conductors:
            right = c.x1 if c.shape != "circle" else c.cx + c.radius
            total_width = max(total_width, right)
        geo.total_width = total_width

        # expand planar dielectric layers horizontally
        for d in planar_layers:
            if d.x0 == 0.0 and d.x1 == 0.0:
                d.x0 = -total_width
                d.x1 = d.x0 + 3.0 * total_width

        # expand ground planes to span the dielectric x-extent
        if planar_layers:
            xmin = min(d.x0 for d in planar_layers)
            xmax = max(d.x1 for d in planar_layers)
            for gp in geo.ground_planes:
                gp.x0, gp.x1 = xmin, xmax

        geo.bounds = self._compute_bounds(geo)
        return geo

    def _resolve_conductor(self, el, xoff, base_y, u, ground) -> ResolvedConductor:
        # name carries the group label + type letter; index appended later
        label = f"{el.name}{el.type_letter}"
        if el.kind == "rectangle_conductors":
            w = el.width * u
            h = el.height * u
            return ResolvedConductor(
                name=label, shape="rectangle", is_ground=ground,
                x0=xoff, y0=base_y, x1=xoff + w, y1=base_y + h,
            )
        if el.kind == "circle_conductors":
            d = el.diameter * u
            r = d / 2.0
            return ResolvedConductor(
                name=label, shape="circle", is_ground=ground,
                cx=xoff + r, cy=base_y + r, radius=r,
                x0=xoff, y0=base_y, x1=xoff + d, y1=base_y + d,
            )
        # trapezoid -> polygon, centred at cx + max(tw,bw)/2; the wider edge is
        # anchored at the x-offset (nmmtl_parse_xsctn.cpp:734-798).
        bw = el.bottom_width * u
        tw = el.top_width * u
        h = el.height * u
        half = max(tw, bw) / 2.0
        center_x = xoff + half
        ylo, yhi = base_y, base_y + h
        pts = [
            (center_x - bw / 2.0, ylo),  # bottom-left
            (center_x - tw / 2.0, yhi),  # top-left
            (center_x + tw / 2.0, yhi),  # top-right
            (center_x + bw / 2.0, ylo),  # bottom-right
        ]
        return ResolvedConductor(
            name=label, shape="polygon", is_ground=ground,
            x0=center_x - half, y0=ylo, x1=center_x + half, y1=yhi, points=pts,
        )

    @staticmethod
    def _compute_bounds(geo: ResolvedGeometry):
        xs, ys = [], []
        for d in geo.dielectrics:
            xs += [d.x0, d.x1]
            ys += [d.y0, d.y1]
        for gp in geo.ground_planes:
            xs += [gp.x0, gp.x1]
            ys += [gp.y0, gp.y1]
        for c in geo.conductors:
            if c.shape == "circle":
                xs += [c.cx - c.radius, c.cx + c.radius]
                ys += [c.cy - c.radius, c.cy + c.radius]
            elif c.shape == "polygon":
                xs += [p[0] for p in c.points]
                ys += [p[1] for p in c.points]
            else:
                xs += [c.x0, c.x1]
                ys += [c.y0, c.y1]
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))
