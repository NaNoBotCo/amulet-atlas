"""worldmap.py — one projection, shared by every map on this site.

An atlas of charms from every hemisphere cannot be drawn on a Mercator. Mercator
inflates the far north, which is where the least of this material comes from, and
shrinks the equator, which is where the most of it does — so the picture would argue
something the records do not.

Every world map here is drawn in **Equal Earth** (Šavrič, Patterson and Jenny, 2018):
equal-area, so a square centimetre of Nigeria and a square centimetre of Norway stand
for the same square kilometres, and pseudocylindrical, so it still reads as a map
rather than a puzzle. Regional maps drop to a plate carrée box scaled by cos(latitude),
which is honest enough over a few hundred kilometres and keeps north straight up.

    fit = fit_world(width=980)
    x, y = project(lon, lat, fit)
    for iso, d in land_paths(fit): ...

Antarctica is drawn and then left unlabelled: no amulet record points at it, and the
blank is the true statement.
"""
from __future__ import annotations

import math
from common import GEO, jload

A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2


def _equal_earth(lon: float, lat: float) -> tuple[float, float]:
    lam, phi = math.radians(lon), math.radians(lat)
    th = math.asin(max(-1.0, min(1.0, M * math.sin(phi))))
    t2 = th * th
    t6 = t2 * t2 * t2
    x = lam * math.cos(th) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = th * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


# The projection's own extent, measured once rather than quoted from memory.
_X0, _ = _equal_earth(-180, 0)
_X1, _ = _equal_earth(180, 0)
_, _Y0 = _equal_earth(0, 90)
_, _Y1 = _equal_earth(0, -90)


def fit_world(width: float = 980, pad: float = 2.0, clip_south: float = -60.0) -> dict:
    """Scale and offsets for a full-world Equal Earth frame `width` px across.

    clip_south cuts the empty Antarctic band; pass -90 to keep it."""
    _, ytop = _equal_earth(0, 90)
    _, ybot = _equal_earth(0, clip_south)
    k = (width - 2 * pad) / (_X1 - _X0)
    height = (ytop - ybot) * k + 2 * pad
    return {"k": k, "pad": pad, "w": width, "h": height,
            "x0": _X0, "ytop": ytop, "clip_south": clip_south, "kind": "equal-earth"}


def project(lon: float, lat: float, fit: dict) -> tuple[float, float]:
    if fit.get("kind") == "box":
        x = fit["pad"] + (lon - fit["lon0"]) * fit["kx"]
        y = fit["pad"] + (fit["lat1"] - lat) * fit["ky"]
        return x, y
    x, y = _equal_earth(lon, lat)
    return (fit["pad"] + (x - fit["x0"]) * fit["k"],
            fit["pad"] + (fit["ytop"] - y) * fit["k"])


def fit_box(lat: float, lon: float, span_deg: float, width: float = 430, pad: float = 2.0) -> dict:
    """A plate carrée window `span_deg` wide centred on a point, with longitude squeezed
    by cos(lat) so a locator map of Kyoto is not stretched sideways."""
    cos = max(0.2, math.cos(math.radians(lat)))
    lon0, lon1 = lon - span_deg / 2, lon + span_deg / 2
    hspan = span_deg * cos * 0.72
    lat0, lat1 = lat - hspan / 2, lat + hspan / 2
    kx = (width - 2 * pad) / (lon1 - lon0)
    ky = kx / cos
    return {"kind": "box", "pad": pad, "w": width, "h": (lat1 - lat0) * ky + 2 * pad,
            "lon0": lon0, "lon1": lon1, "lat0": lat0, "lat1": lat1, "kx": kx, "ky": ky}


def load() -> dict:
    return jload(GEO / "world.json")


def land_paths(fit: dict, geo: dict | None = None, min_ring: int = 4,
               step: int = 1, min_px: float = 0.0, places: int = 1):
    """[(iso, name, 'M… Z'), …] — one path per country, rings joined.

    `step` keeps every Nth point and `min_px` drops a ring whose projected bounding box is
    smaller than that many pixels across. Both exist for the thumbnail maps on /map/ and
    /against/: a 1:110m coastline drawn at 250 px wide carries detail nobody can see and
    weighs a megabyte across twelve copies. The first and last point of a ring are always
    kept, so nothing opens up."""
    geo = geo or load()
    south = fit.get("clip_south", -90)
    out = []
    for c in geo["countries"]:
        parts = []
        for ring in c["rings"]:
            if len(ring) < min_ring:
                continue
            if max(p[1] for p in ring) < south:
                continue
            pts = [project(lon, max(lat, south), fit) for lon, lat in ring]
            if min_px:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if max(xs) - min(xs) < min_px and max(ys) - min(ys) < min_px:
                    continue
            if step > 1 and len(pts) > step * 3:
                pts = pts[::step] + [pts[-1]]
            parts.append("M" + "L".join(f"{x:.{places}f},{y:.{places}f}" for x, y in pts) + "Z")
        if parts:
            out.append((c["iso"], c["name"], "".join(parts)))
    return out


def graticule(fit: dict, step_lon: int = 30, step_lat: int = 30) -> list:
    """Meridians and parallels as path strings — the reminder that the sheet is curved."""
    out = []
    south = int(fit.get("clip_south", -90))
    for lon in range(-180, 181, step_lon):
        pts = [project(lon, lat, fit) for lat in range(south, 91, 2)]
        out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts))
    for lat in range(-60 if south <= -60 else south, 91, step_lat):
        pts = [project(lon, lat, fit) for lat in range(-180, 181, 2)]
        out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts))
    return out


def equator(fit: dict) -> str:
    pts = [project(lon, 0, fit) for lon in range(-180, 181, 2)]
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def outline(fit: dict) -> str:
    """The frame of the projected world — the shape the sheet actually is."""
    south = fit.get("clip_south", -90)
    pts = [project(180, lat, fit) for lat in range(90, int(south) - 1, -2)]
    pts += [project(lon, south, fit) for lon in range(180, -181, -4)]
    pts += [project(-180, lat, fit) for lat in range(int(south), 91, 2)]
    pts += [project(lon, 90, fit) for lon in range(-180, 181, 4)]
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"
