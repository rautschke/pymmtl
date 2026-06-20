"""Headless command-line interface: ``python -m pymmtl <command>``."""

from __future__ import annotations

import argparse
import sys

from pymmtl import csdl, solver


def _print_results(res, header: str = "") -> None:
    if header:
        print(header)
    print(f"  signals: {', '.join(res.names) or '(none)'}")
    for name in res.names:
        z = res.impedance.get(name, float("nan"))
        e = res.eps_eff.get(name, float("nan"))
        v = res.velocity.get(name, float("nan"))
        print(f"    {name:12s} Z0={z:10.4g} ohm   eps_eff={e:8.4g}   v={v:.4g} m/s")
    if "impedance" in res.odd_even:
        odd, even = res.odd_even["impedance"]
        print(f"  odd/even impedance: {odd:.4g} / {even:.4g} ohm")
    for k, v in res.asymmetry.items():
        print(f"  asymmetry ({k}): {v[0]:.4g}% max")


def cmd_run(args: argparse.Namespace) -> int:
    cs = csdl.load(args.file)
    out = solver.run(
        cs,
        coupling_length=args.coupling,
        rise_time=args.risetime,
        cseg=args.cseg,
        dseg=args.dseg,
    )
    if args.log:
        print(out.log)
    _print_results(out.results, header=f"MMTL results for {args.file}:")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    cs = csdl.load(args.file)
    print(f"title: {cs.title}")
    print(f"units: {cs.default_units}   coupling={cs.coupling_length} m   "
          f"risetime={cs.rise_time} ps   CSEG={cs.cseg} DSEG={cs.dseg}")
    print(f"signals: {', '.join(cs.signal_names()) or '(none)'}")
    for el in cs.stack:
        print(f"  {el.kind:22s} {el.name}")
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    from pymmtl import sweep

    cs = csdl.load(args.file)
    specs = [sweep.parse_spec(s) for s in args.param]
    table = sweep.run_sweep(cs, specs, output=args.metric)
    sweep.write_csv(table, args.csv)
    print(f"ran {len(table.rows)} simulations -> {args.csv}")
    return 0


def cmd_iterate(args: argparse.Namespace) -> int:
    from pymmtl import iterate

    cs = csdl.load(args.file)
    result = iterate.iterate_width(
        cs, args.group, args.target, conductor_index=args.index
    )
    print(f"width = {result.width:.6g} {cs.default_units} -> "
          f"Z0 = {result.impedance:.4f} ohm (target {args.target}) "
          f"in {result.iterations} iterations")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from pymmtl import rlgc

    cs = csdl.load(args.file)
    out = solver.run(cs)
    text = rlgc.hspice_w_element(cs, out.results)
    if args.output:
        with open(args.output, "w") as fh:
            fh.write(text)
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pymmtl", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run the BEM solver on a cross-section")
    r.add_argument("file")
    r.add_argument("--coupling", type=float, default=None, help="coupling length (m)")
    r.add_argument("--risetime", type=float, default=None, help="rise time (ps)")
    r.add_argument("--cseg", type=int, default=None, help="conductor segments")
    r.add_argument("--dseg", type=int, default=None, help="dielectric segments")
    r.add_argument("--log", action="store_true", help="print the solver log")
    r.set_defaults(func=cmd_run)

    i = sub.add_parser("info", help="summarise a cross-section file")
    i.add_argument("file")
    i.set_defaults(func=cmd_info)

    s = sub.add_parser("sweep", help="sweep parameters and write a CSV")
    s.add_argument("file")
    s.add_argument("--param", action="append", required=True,
                   help="spec 'group.field=start:stop:n' (repeatable)")
    s.add_argument("--metric", default="impedance",
                   help="result metric to record (impedance|eps_eff|velocity|delay)")
    s.add_argument("--csv", default="sweep.csv")
    s.set_defaults(func=cmd_sweep)

    it = sub.add_parser("iterate", help="iterate conductor width to a target Z0")
    it.add_argument("file")
    it.add_argument("group", help="conductor group name (e.g. c1)")
    it.add_argument("target", type=float, help="target characteristic impedance (ohm)")
    it.add_argument("--index", type=int, default=0, help="conductor index within group")
    it.set_defaults(func=cmd_iterate)

    e = sub.add_parser("export", help="export an HSPICE W-element model")
    e.add_argument("file")
    e.add_argument("-o", "--output", default=None, help="output .hspice-w.rlgc path")
    e.set_defaults(func=cmd_export)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # surface solver/parse errors cleanly
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
