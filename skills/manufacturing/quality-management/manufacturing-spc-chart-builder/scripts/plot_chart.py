#!/usr/bin/env python3
"""Render a control chart as a standalone SVG (no plotting libraries needed).

Uses the same inputs and calculations as control_limits.py (shared _spc.py). Variables charts get two
panels (X / X-bar and MR / R / S); attribute charts one panel with stepped limits for varying sample sizes.
Points beyond the control limits are drawn in red; --usl/--lsl add specification lines to the main panel
(dashed) for reference only - never use specification limits as control limits.

Usage:
    python plot_chart.py bore.csv --value diameter --subgroup hour --title "OP20 bore" > bore.svg
    python plot_chart.py rejects.csv --defectives rejects --n inspected > p_chart.svg

Exit codes: 0 SVG written, 2 usage or data error.
"""

import argparse
import sys
from html import escape

from _spc import attributes, beyond, choose, read_rows, subgroups, to_float, variables

W, PH, ML, MR, MT = 860, 230, 70, 90, 30


def panel(series, y0, labels, usl=None, lsl=None):
    name, pts, cl, ucl, lcl = series
    n = len(pts)
    ul = ucl if isinstance(ucl, list) else [ucl] * n
    ll = lcl if isinstance(lcl, list) else [lcl] * n
    vals = [v for v in pts if v is not None] + ul + ll + [x for x in (usl, lsl) if x is not None]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    X = lambda i: ML + (W - ML - MR) * (i / max(1, n - 1))
    Y = lambda v: y0 + PH - (v - lo) / (hi - lo) * PH
    out = [f'<text x="{ML}" y="{y0 - 8}" class="t">{escape(name)}</text>',
           f'<rect x="{ML}" y="{y0}" width="{W - ML - MR}" height="{PH}" class="frame"/>']

    def step(limit, cls, label):
        d = " ".join(f"{'M' if i == 0 else 'L'}{X(i - 0.5 if i else 0):.1f},{Y(v):.1f} L{X(min(i + 0.5, n - 1)):.1f},{Y(v):.1f}" for i, v in enumerate(limit))
        out.append(f'<path d="{d}" class="{cls}"/>')
        out.append(f'<text x="{W - MR + 6}" y="{Y(limit[-1]) + 4:.1f}" class="lab">{label} {limit[-1]:.6g}</text>')

    step(ul, "lim", "UCL")
    step(ll, "lim", "LCL")
    out.append(f'<line x1="{ML}" x2="{W - MR}" y1="{Y(cl):.1f}" y2="{Y(cl):.1f}" class="cl"/>')
    out.append(f'<text x="{W - MR + 6}" y="{Y(cl) + 4:.1f}" class="lab">CL {cl:.6g}</text>')
    for v, lab in ((usl, "USL"), (lsl, "LSL")):
        if v is not None:
            out.append(f'<line x1="{ML}" x2="{W - MR}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="spec"/>')
            out.append(f'<text x="{ML + 4}" y="{Y(v) - 4:.1f}" class="lab">{lab} {v:g}</text>')
    path = [f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(pts) if v is not None]
    out.append(f'<polyline points="{" ".join(path)}" class="data"/>')
    bad = set(beyond(series))
    for i, v in enumerate(pts):
        if v is not None:
            out.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.2" class="{"ooc" if i in bad else "pt"}"><title>{escape(labels[i])}: {v:.6g}</title></circle>')
    for i in range(0, n, max(1, n // 12)):
        out.append(f'<text x="{X(i):.1f}" y="{y0 + PH + 14}" class="ax">{escape(labels[i])}</text>')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--value")
    ap.add_argument("--subgroup")
    ap.add_argument("--size", type=int)
    ap.add_argument("--defectives")
    ap.add_argument("--defects")
    ap.add_argument("--n")
    ap.add_argument("--chart", choices=["imr", "xbar-r", "xbar-s", "p", "np", "c", "u"])
    ap.add_argument("--usl", type=float)
    ap.add_argument("--lsl", type=float)
    ap.add_argument("--title", default="Control chart")
    a = ap.parse_args()
    try:
        rows = read_rows(a.csv)
        if a.defectives or a.defects:
            col = a.defectives or a.defects
            if not a.n:
                raise ValueError("attribute charts need --n")
            counts = [to_float(r[col], col) for r in rows]
            sizes = [to_float(r[a.n], a.n) for r in rows]
            chart = a.chart or choose(None, "defectives" if a.defectives else "defects", len(set(sizes)) > 1)
            res, labels = attributes(counts, sizes, chart), [str(i + 1) for i in range(len(rows))]
        elif a.value:
            groups, labels = subgroups(rows, a.value, a.subgroup, a.size)
            chart = a.chart or choose(len(groups[0]))
            res = variables(groups, chart)
        else:
            raise ValueError("give --value or --defectives/--defects with --n")
    except (OSError, KeyError, ValueError, IndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    panels = [res["main"]] + ([res["second"]] if "second" in res else [])
    height = MT + len(panels) * (PH + 50) + 10
    body = []
    for k, s in enumerate(panels):
        body += panel(s, MT + 20 + k * (PH + 50), labels, a.usl if k == 0 else None, a.lsl if k == 0 else None)
    style = (".t{font:600 13px sans-serif;fill:#222}.lab,.ax{font:11px sans-serif;fill:#555}.ax{text-anchor:middle}"
             ".frame{fill:#fff;stroke:#ccc}.lim{fill:none;stroke:#c0392b;stroke-width:1.2}.cl{stroke:#2c7a2c;stroke-width:1.2}"
             ".spec{stroke:#7a5cc0;stroke-dasharray:6 4}.data{fill:none;stroke:#3a6ea5;stroke-width:1.2}"
             ".pt{fill:#3a6ea5}.ooc{fill:#d0021b;stroke:#fff}")
    print(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}">'
          f'<style>{style}</style><text x="{ML}" y="18" class="t">{escape(a.title)} - {chart.upper()}</text>'
          + "".join(body) + "</svg>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
