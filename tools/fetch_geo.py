"""fetch_geo.py — the outlines every map on this site is drawn from.

Natural Earth, public domain. One file, fetched once into data/geo/ and refreshed only
when it needs refreshing:

  world.json   ne_110m_admin_0_countries — every map on this site, drawn in Equal Earth

1:110m is the right sheet for an atlas whose smallest map is 250 px across and whose
largest is 1100. It is also why a handful of small island states are named by records but
not filled on the map; common.TOO_SMALL_TO_DRAW keeps their names and /map/ lists them.

    python3 tools/fetch_geo.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GEO, jdump  # noqa: E402

BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
CREDIT = "Natural Earth (public domain)"
SITE = "https://www.naturalearthdata.com/"

TOL_WORLD = 0.08


def _perp(p, a, b) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - (x1 + t * dx)) ** 2 + (y - (y1 + t * dy)) ** 2) ** 0.5


def simplify(pts: list, tol: float) -> list:
    """Douglas-Peucker, iterative so a long coastline does not blow the stack."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        far, d = -1, tol
        for k in range(i + 1, j):
            dk = _perp(pts[k], pts[i], pts[j])
            if dk > d:
                far, d = k, dk
        if far > 0:
            keep[far] = True
            stack.append((i, far))
            stack.append((far, j))
    return [p for p, k in zip(pts, keep) if k]


def rings_of(geom: dict) -> list:
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    if geom["type"] == "LineString":
        return [geom["coordinates"]]
    if geom["type"] == "MultiLineString":
        return list(geom["coordinates"])
    return []


def fetch(name: str) -> dict:
    url = BASE + name
    print(f"fetching {url}")
    with urllib.request.urlopen(url, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def thin(ring, tol, dp=3):
    s = simplify([(round(c[0], dp), round(c[1], dp)) for c in ring], tol)
    return [[x, y] for x, y in s]


def do_world() -> None:
    gj = fetch("ne_110m_admin_0_countries.geojson")
    out = []
    for f in gj["features"]:
        p = f["properties"]
        rings = []
        for ring in rings_of(f["geometry"]):
            xs = [c[0] for c in ring]
            ys = [c[1] for c in ring]
            if max(xs) - min(xs) < 0.5 and max(ys) - min(ys) < 0.5:
                continue
            s = thin(ring, TOL_WORLD, 2)
            if len(s) > 3:
                rings.append(s)
        if not rings:
            continue
        out.append({"iso": p.get("ISO_A2_EH") or p.get("ISO_A2") or "", "name": p.get("NAME") or "", "rings": rings})
    out.sort(key=lambda s: s["name"])
    jdump({"source": CREDIT + ", Admin 0 countries, 1:110m", "url": SITE,
           "coords": "[lon, lat], 2 dp, Douglas-Peucker at 0.08°", "countries": out},
          GEO / "world.json", indent=None)
    say("world.json", out, "rings")


def say(fn, out, _k):
    kb = (GEO / fn).stat().st_size / 1024
    print(f"wrote {fn} — {len(out)} shapes, {sum(len(r) for s in out for r in s['rings'])} points, {kb:.0f} KB")


if __name__ == "__main__":
    GEO.mkdir(parents=True, exist_ok=True)
    raise SystemExit(do_world())
