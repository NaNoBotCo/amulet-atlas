"""viz.py — every drawn thing on this site, as inline SVG.

Nothing here reaches for a charting library, a tile server or a font the reader does not
have. An SVG that is text in the page is an SVG a reader can select, a screen reader can
walk and a slow connection still gets.

Four families:
  world_*      Equal Earth maps — choropleth, points, and small multiples
  time_*       the deep timeline, on a stated non-linear axis
  chart_*      bars, strips, matrices
  glyph_*      the drawn signs, and the body/house/road diagram behind /wear/

The glyphs are drawn for this project from published descriptions of the signs, not traced
from any one object, and they go out under the project's own licence.
"""
from __future__ import annotations

import math

import worldmap as W

# Faience, which is the colour most of this material actually is, running to indigo.
RAMP = ["#eef5f3", "#cfe6e0", "#a3d2c8", "#71b8ab", "#46988c", "#2b7268", "#1a4b46"]
CARNELIAN = "#b23a2b"
GOLD = "#bb8b2c"
INK = "#1d2321"
SEA = "#f4f7f7"
LAND = "#e4e9e7"
EDGE = "#c3ccc9"


def E(x) -> str:
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def _bucket(n: int, cuts: list) -> int:
    for i, c in enumerate(cuts):
        if n <= c:
            return i
    return len(cuts)


def nice_cuts(values: list, k: int = 6) -> list:
    """Quantile-ish cuts that do not invent detail a short list cannot carry."""
    vals = sorted(v for v in values if v)
    if not vals:
        return [1]
    if len(vals) <= k:
        return sorted(set(vals))[:-1] or [vals[0]]
    out = []
    for i in range(1, k):
        out.append(vals[int(len(vals) * i / k)])
    return sorted(set(out))


# ----------------------------------------------------------------- world maps

def world_choropleth(counts: dict, width=980, title="", ramp=None, unit="records",
                     links: dict | None = None, ident="map") -> str:
    """counts: {ISO2: n}. Countries with no row are drawn in the blank colour, and the
    legend says what a blank means rather than leaving a reader to guess."""
    ramp = ramp or RAMP
    fit = W.fit_world(width)
    cuts = nice_cuts(list(counts.values()), len(ramp) - 1)
    out = [f'<svg class="worldmap" viewBox="0 0 {width:.0f} {fit["h"]:.0f}" '
           f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{E(title or "world map")}">']
    out.append(f'<path d="{W.outline(fit)}" fill="{SEA}" stroke="{EDGE}" stroke-width=".7"/>')
    for d in W.graticule(fit):
        out.append(f'<path d="{d}" fill="none" stroke="{EDGE}" stroke-width=".4" opacity=".55"/>')
    for iso, name, d in W.land_paths(fit):
        n = counts.get(iso, 0)
        fill = ramp[_bucket(n, cuts)] if n else LAND
        t = f"{name} — {n} {unit}" if n else f"{name} — no record here names it"
        href = (links or {}).get(iso)
        path = (f'<path d="{d}" fill="{fill}" stroke="#fff" stroke-width=".45" '
                f'class="cty{" has" if n else ""}"><title>{E(t)}</title></path>')
        out.append(f'<a href="{E(href)}">{path}</a>' if href else path)
    out.append(f'<path d="{W.equator(fit)}" fill="none" stroke="{INK}" stroke-width=".7" '
               f'stroke-dasharray="6 4" opacity=".45"><title>the equator</title></path>')
    out.append("</svg>")
    return "".join(out) + ramp_legend(cuts, ramp, unit)


def world_points(points: list, width=980, title="", colour=CARNELIAN, r=4.0, ident="pts") -> str:
    """points: [{lat, lon, name, url?, n?, colour?}] — one dot each, drawn over a plain world."""
    fit = W.fit_world(width)
    out = [f'<svg class="worldmap" viewBox="0 0 {width:.0f} {fit["h"]:.0f}" '
           f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{E(title or "world map")}">']
    out.append(f'<path d="{W.outline(fit)}" fill="{SEA}" stroke="{EDGE}" stroke-width=".7"/>')
    for d in W.graticule(fit):
        out.append(f'<path d="{d}" fill="none" stroke="{EDGE}" stroke-width=".4" opacity=".55"/>')
    for iso, name, d in W.land_paths(fit):
        out.append(f'<path d="{d}" fill="{LAND}" stroke="#fff" stroke-width=".45"/>')
    out.append(f'<path d="{W.equator(fit)}" fill="none" stroke="{INK}" stroke-width=".7" '
               f'stroke-dasharray="6 4" opacity=".4"/>')
    for p in sorted(points, key=lambda q: -(q.get("lat") or 0)):
        if p.get("lat") is None or p.get("lon") is None:
            continue
        x, y = W.project(p["lon"], p["lat"], fit)
        rr = r * (1 + 0.28 * math.log(max(1, p.get("n", 1))))
        dot = (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr:.1f}" fill="{p.get("colour", colour)}" '
               f'fill-opacity=".82" stroke="#fff" stroke-width="1"><title>{E(p["name"])}</title></circle>')
        out.append(f'<a href="{E(p["url"])}">{dot}</a>' if p.get("url") else dot)
    out.append("</svg>")
    return "".join(out)


def world_multiples(groups: list, width=236, cols=4) -> str:
    """groups: [{label, n, isos:set}] — a grid of thumbnail worlds, one per harm or per
    material. Small multiples answer a question a single map cannot: not where is the most,
    but where is THIS, and the eye compares the shapes."""
    fit = W.fit_world(width, pad=1.0)
    # Thumbnail geometry: every third point, nothing under two pixels across, coordinates
    # to whole pixels. Twelve copies of the full 1:110m sheet is a megabyte of detail the
    # reader cannot see at this size.
    base = W.land_paths(fit, step=3, min_px=2.0, places=0)
    out = ['<div class="mults">']
    for g in groups:
        isos = set(g["isos"])
        paths = "".join(
            f'<path d="{d}" fill="{CARNELIAN if iso in isos else LAND}" stroke="#fff" stroke-width=".3"/>'
            for iso, _n, d in base)
        out.append(
            f'<figure><svg viewBox="0 0 {width:.0f} {fit["h"]:.0f}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="{E(g["label"])} — {g["n"]}">'
            f'<path d="{W.outline(fit)}" fill="{SEA}" stroke="{EDGE}" stroke-width=".5"/>{paths}</svg>'
            f'<figcaption><b>{E(g["label"])}</b> <span class="n">{g["n"]}</span></figcaption></figure>')
    out.append("</div>")
    return "".join(out)


def locator(lat: float, lon: float, others: list, width=420, span=26.0, label="") -> str:
    """A regional box for one place record, with its neighbours in grey."""
    fit = W.fit_box(lat, lon, span, width)
    out = [f'<svg class="locator" viewBox="0 0 {width:.0f} {fit["h"]:.0f}" '
           f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{E(label or "locator map")}">',
           f'<rect width="{width:.0f}" height="{fit["h"]:.0f}" fill="{SEA}"/>']
    geo = W.load()
    for c in geo["countries"]:
        for ring in c["rings"]:
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            if max(xs) < fit["lon0"] or min(xs) > fit["lon1"] or max(ys) < fit["lat0"] or min(ys) > fit["lat1"]:
                continue
            pts = [W.project(x, y, fit) for x, y in ring]
            out.append('<path d="M' + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) +
                       f'Z" fill="{LAND}" stroke="#fff" stroke-width=".6"/>')
    for o in others:
        x, y = W.project(o["lon"], o["lat"], fit)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{INK}" opacity=".3"><title>{E(o["name"])}</title></circle>')
    x, y = W.project(lon, lat, fit)
    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="none" stroke="{CARNELIAN}" stroke-width="2"/>'
               f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{CARNELIAN}"/>')
    out.append("</svg>")
    return "".join(out)


def ramp_legend(cuts: list, ramp: list, unit: str) -> str:
    cells = [f'<span class="sw" style="background:{LAND}"></span><span class="lb">none here</span>']
    lo = 1
    for i, c in enumerate(cuts):
        cells.append(f'<span class="sw" style="background:{ramp[i]}"></span>'
                     f'<span class="lb">{lo if lo == c else f"{lo}–{c}"}</span>')
        lo = c + 1
    cells.append(f'<span class="sw" style="background:{ramp[len(cuts)]}"></span><span class="lb">{lo}+</span>')
    return f'<p class="legend">{"".join(cells)}<span class="unit">{E(unit)}</span></p>'


# ------------------------------------------------------------------- the timeline

# The axis is NOT linear, and the page says so. Five thousand years of amulet at one
# scale gives the last two centuries about a millimetre, and the last two centuries are
# where half these records live. So the axis is piecewise: anchors in years, mapped to
# fractions of the width, and every anchor gets a printed tick so a reader can see the
# stretching happen rather than be fooled by it.
ANCHORS = [(-11000, 0.00), (-3000, 0.14), (-1000, 0.28), (0, 0.40), (500, 0.48),
           (1000, 0.56), (1500, 0.66), (1800, 0.76), (1900, 0.84), (1950, 0.90),
           (2000, 0.96), (2026, 1.00)]


RIGHT = 14.0   # the gutter the axis stops in, so a living bar's open circle is not clipped


def year_x(y: float, w: float, pad: float = 0.0) -> float:
    """Year to x, on the piecewise axis above. The left margin `pad` is where the row
    labels live; the axis runs from there to the right gutter."""
    y = max(ANCHORS[0][0], min(ANCHORS[-1][0], y))
    span = w - pad - RIGHT
    for (y0, f0), (y1, f1) in zip(ANCHORS, ANCHORS[1:]):
        if y0 <= y <= y1:
            t = 0 if y1 == y0 else (y - y0) / (y1 - y0)
            return pad + (f0 + t * (f1 - f0)) * span
    return pad + span


def year_label(y) -> str:
    if y is None:
        return "now"
    y = int(y)
    return f"{1 - y} BCE" if y <= 0 else f"{y} CE"


def time_axis(w=980, pad=120.0, h=26.0, y=0.0, min_gap=52.0) -> str:
    """Every anchor gets a tick. A label is dropped where it would print on top of its
    neighbour — the tick stays, so the stretching is still visible, and the last anchor
    always keeps its label because that is the one a reader reads first."""
    out = [f'<g class="taxis" transform="translate(0,{y:.0f})">']
    out.append(f'<line x1="{pad:.0f}" y1="{h:.0f}" x2="{w - RIGHT:.0f}" y2="{h:.0f}" stroke="currentColor" stroke-width=".8" opacity=".55"/>')
    xs = [(yr, year_x(yr, w, pad)) for yr, _f in ANCHORS]
    keep = set()
    last = -1e9
    for yr, x in xs[:-1]:
        if x - last >= min_gap:
            keep.add(yr)
            last = x
    if xs[-1][1] - last < min_gap and keep:
        keep.discard(max(keep, key=lambda k: dict(xs)[k]))
    keep.add(xs[-1][0])
    for yr, x in xs:
        out.append(f'<line x1="{x:.1f}" y1="{h - 5:.0f}" x2="{x:.1f}" y2="{h:.0f}" stroke="currentColor" stroke-width=".8" opacity=".55"/>')
        if yr in keep:
            anchor = "start" if x <= pad + 2 else ("end" if x >= w - RIGHT - 2 else "middle")
            out.append(f'<text class="tk" x="{x:.1f}" y="{h - 9:.0f}" text-anchor="{anchor}">{E(year_label(yr))}</text>')
    out.append("</g>")
    return "".join(out)


def time_chart(rows: list, w=980, rowh=15.0, pad=170.0, colour_by=None, max_rows=None) -> str:
    """rows: [{name, url, from_year, to_year, living, method, label}] — one bar each.

    A bar that runs to the right edge with an open arrow is something still carried. A
    dotted bar is a date somebody inferred rather than dug up."""
    rows = [r for r in rows if r.get("from_year") is not None or r.get("to_year") is not None]
    rows = rows[:max_rows] if max_rows else rows
    top = 44.0
    h = top + len(rows) * rowh + 34
    out = [f'<svg class="timechart" viewBox="0 0 {w:.0f} {h:.0f}" xmlns="http://www.w3.org/2000/svg" '
           f'role="img" aria-label="when each charm is attested">']
    out.append(time_axis(w, pad, 30, 0))
    for yr, _f in ANCHORS:
        x = year_x(yr, w, pad)
        out.append(f'<line x1="{x:.1f}" y1="{top - 8:.0f}" x2="{x:.1f}" y2="{h - 26:.0f}" '
                   f'stroke="currentColor" stroke-width=".5" opacity=".18"/>')
    x0 = year_x(0, w, pad)
    out.append(f'<line x1="{x0:.1f}" y1="{top - 12:.0f}" x2="{x0:.1f}" y2="{h - 26:.0f}" '
               f'stroke="currentColor" stroke-width=".9" opacity=".45"><title>the era boundary</title></line>')
    for i, r in enumerate(rows):
        y = top + i * rowh
        a = r.get("from_year")
        b = r.get("to_year")
        xa = year_x(a if a is not None else b, w, pad)
        xb = year_x(b if b is not None else 2026, w, pad)
        col = (colour_by or (lambda _r: CARNELIAN))(r)
        dash = ' stroke-dasharray="3 3"' if r.get("method") in ("inference", "undated", "art-historical") else ""
        bar = (f'<line x1="{xa:.1f}" y1="{y:.1f}" x2="{max(xb, xa + 2):.1f}" y2="{y:.1f}" '
               f'stroke="{col}" stroke-width="5" stroke-linecap="round" opacity=".88"{dash}/>')
        if r.get("living") or b is None:
            bar += (f'<circle cx="{max(xb, xa + 2):.1f}" cy="{y:.1f}" r="3.6" fill="#fff" '
                    f'stroke="{col}" stroke-width="2"/>')
        lbl = (f'<text class="rl" x="{pad - 8:.0f}" y="{y + 3.4:.1f}" text-anchor="end">{E(r["name"])}</text>')
        tip = f'<title>{E(r["name"])} — {E(r.get("label") or "")}</title>'
        g = f'<g class="trow">{tip}{lbl}{bar}</g>'
        out.append(f'<a href="{E(r["url"])}">{g}</a>' if r.get("url") else g)
    out.append(time_axis(w, pad, 22, h - 26))
    out.append("</svg>")
    return "".join(out)


def time_density(rows: list, w=980, h=92.0, pad=120.0) -> str:
    """How many things in this atlas are in use in a given century — the shape of the
    record set, not of the past. A rise at 1800 is a rise in what got written down."""
    cents = list(range(-11000, 2100, 100))
    counts = []
    for c in cents:
        n = 0
        for r in rows:
            a = r.get("from_year")
            b = r.get("to_year") if r.get("to_year") is not None else 2026
            if a is None:
                continue
            if a <= c + 99 and b >= c:
                n += 1
        counts.append(n)
    top = max(counts) or 1
    pts = []
    for c, n in zip(cents, counts):
        pts.append((year_x(c, w, pad), h - 20 - (n / top) * (h - 34)))
    d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = d + f"L{pts[-1][0]:.1f},{h - 20:.1f}L{pts[0][0]:.1f},{h - 20:.1f}Z"
    return (f'<svg class="density" viewBox="0 0 {w:.0f} {h:.0f}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="how many of these records are in use, century by century">'
            f'<path d="{area}" fill="{RAMP[2]}" opacity=".8"/>'
            f'<path d="{d}" fill="none" stroke="{RAMP[5]}" stroke-width="1.6"/>'
            f'<text class="tk" x="{pad:.0f}" y="12">records in use, by century — peak {top}</text>'
            f'{time_axis(w, pad, h - 6, 0)}</svg>')


# ----------------------------------------------------------------------- charts

def bars(rows: list, w=760, unit="", rowh=26, left=200, colour=None) -> str:
    """rows: [{label, n, url?}] — a plain horizontal bar chart with the number printed."""
    top = max([r["n"] for r in rows] or [1])
    h = len(rows) * rowh + 8
    out = [f'<svg class="bars" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img">']
    for i, r in enumerate(rows):
        y = i * rowh + 4
        bw = (w - left - 56) * (r["n"] / top)
        col = colour(r) if colour else RAMP[4]
        out.append(f'<text class="rl" x="{left - 8}" y="{y + 15}" text-anchor="end">{E(r["label"])}</text>'
                   f'<rect x="{left}" y="{y + 4}" width="{bw:.1f}" height="{rowh - 11}" fill="{col}" rx="2"/>'
                   f'<text class="vn" x="{left + bw + 6:.1f}" y="{y + 15}">{r["n"]}{E(unit)}</text>')
    out.append("</svg>")
    return "".join(out)


def matrix(rows: list, cols: list, cell, w=860, rowlab=170, collab=110) -> str:
    """A grid: rows x cols, `cell(row, col)` returning (n, title). Empty cells stay empty —
    a blank is a blank, never a zero dressed as a finding."""
    cw = max(16, (w - rowlab - 8) / max(1, len(cols)))
    ch = 22
    h = collab + len(rows) * ch + 8
    vals = []
    for r in rows:
        for c in cols:
            n, _ = cell(r, c)
            if n:
                vals.append(n)
    cuts = nice_cuts(vals, len(RAMP) - 1)
    out = [f'<svg class="matrix" viewBox="0 0 {w:.0f} {h:.0f}" xmlns="http://www.w3.org/2000/svg" role="img">']
    for j, c in enumerate(cols):
        x = rowlab + j * cw + cw / 2
        out.append(f'<text class="cl" transform="translate({x:.1f},{collab - 6}) rotate(-58)">{E(c["label"])}</text>')
    for i, r in enumerate(rows):
        y = collab + i * ch
        out.append(f'<text class="rl" x="{rowlab - 8}" y="{y + 15}" text-anchor="end">{E(r["label"])}</text>')
        for j, c in enumerate(cols):
            n, title = cell(r, c)
            x = rowlab + j * cw
            fill = RAMP[_bucket(n, cuts)] if n else "none"
            out.append(f'<rect x="{x:.1f}" y="{y + 2}" width="{cw - 2:.1f}" height="{ch - 4}" '
                       f'fill="{fill}" stroke="{EDGE}" stroke-width=".4" rx="1.5">'
                       f'<title>{E(title)}</title></rect>')
    out.append("</svg>")
    return "".join(out)


def hemisphere_bar(h: dict, total: int, w=560) -> str:
    """Four bars: north, south, east, west. The point of the page is that a reader can see
    at a glance how lopsided the atlas still is."""
    names = [("N", "Northern"), ("S", "Southern"), ("E", "Eastern"), ("W", "Western")]
    rows = [{"label": lab, "n": h.get(k, 0)} for k, lab in names]
    return bars(rows, w=w, unit=f" of {total}", rowh=28, left=90,
                colour=lambda r: CARNELIAN if r["label"] in ("Southern", "Western") else RAMP[4])


# ------------------------------------------------------------------- the signs

# Drawn here, from published descriptions of each sign, on a 48x48 box. Not traced from
# any one object: an atlas of signs that copied its signs would be an atlas of somebody
# else's drawings.
GLYPHS = {
    "eye": '<path d="M4 24c8-11 32-11 40 0-8 11-32 11-40 0z"/><circle cx="24" cy="24" r="7"/><circle cx="24" cy="24" r="2.6" class="fill"/>',
    "hand": '<path d="M16 44V22M16 22V10a3 3 0 016 0v10M22 20V7a3 3 0 016 0v13M28 20V10a3 3 0 016 0v14M34 24v-6a3 3 0 015 0v14c0 7-5 12-12 12h-5c-6 0-10-4-10-10"/>',
    "open-palm": '<path d="M13 44V20a3 3 0 016 0M19 20V8a3 3 0 016 0v12M25 20V6a3 3 0 016 0v14M31 22v-8a3 3 0 015 0v16c0 8-5 14-12 14h-4"/>',
    "horn": '<path d="M24 5c7 8 10 18 8 27-1 7-4 11-8 12-4-1-7-5-8-12-2-9 1-19 8-27z"/><path d="M20 11h8"/>',
    "knot": '<path d="M12 18c8-10 16-10 24 0s-8 22-12 22-20-12-12-22z"/><path d="M36 18c-8-10-16-10-24 0"/>',
    "serpent": '<path d="M6 34c6-10 12 6 18-4s12 6 18-4"/><path d="M42 26l-4-3M42 26l-4 3"/><circle cx="7" cy="35" r="1.6" class="fill"/>',
    "scarab-sign": '<ellipse cx="24" cy="27" rx="10" ry="13"/><circle cx="24" cy="11" r="4.5"/><path d="M14 20L5 14M14 28H4M15 35l-8 6M34 20l9-6M34 28h10M33 35l8 6M24 15v25"/>',
    "fish": '<path d="M6 24c8-9 22-9 30 0-8 9-22 9-30 0z"/><path d="M36 24l7-7v14z"/><circle cx="15" cy="22" r="1.6" class="fill"/>',
    "tooth-and-claw": '<path d="M30 6c6 8 8 20 4 30-3 7-8 8-12 6"/><path d="M34 12c-6 2-11 8-13 15"/>',
    "crescent": '<path d="M32 6a20 20 0 100 36A16 16 0 0132 6z"/>',
    "cross": '<path d="M24 5v38M9 19h30"/>',
    "coin-square": '<circle cx="24" cy="24" r="18"/><rect x="17" y="17" width="14" height="14"/>',
    "mirror-sign": '<circle cx="24" cy="19" r="13"/><path d="M24 32v12M18 44h12"/>',
    "red-thread": '<path d="M6 30c6-14 12 14 18 0s12 14 18 0"/>',
    "swastika-sign": '<path d="M24 8v32M8 24h32M24 8h10M40 24V14M24 40H14M8 24v10"/>',
    "magic-square": '<rect x="7" y="7" width="34" height="34"/><path d="M18 7v34M30 7v34M7 18h34M7 30h34"/>',
    "palindrome-word": '<path d="M8 14h32M8 24h32M8 34h32"/><path d="M14 10v28M34 10v28"/>',
    "divine-name": '<path d="M10 34c4-16 10-18 14-6s10 10 14-6"/><path d="M8 40h32"/>',
    "footprint": '<ellipse cx="24" cy="29" rx="9" ry="13"/><circle cx="17" cy="13" r="3"/><circle cx="23" cy="10" r="3"/><circle cx="29" cy="11" r="3"/><circle cx="34" cy="15" r="2.6"/>',
    "key": '<circle cx="14" cy="17" r="8"/><path d="M19 23l20 20M33 37l5 5M37 33l5 5"/>',
    "bell": '<path d="M13 34c0-16 3-24 11-24s11 8 11 24z"/><path d="M8 34h32"/><circle cx="24" cy="39" r="3"/>',
    "spiral": '<path d="M24 24a4 4 0 114 4 8 8 0 11-8-8 12 12 0 1112 12 16 16 0 11-16-16"/>',
    "tree": '<path d="M24 44V22"/><path d="M24 22L12 10M24 22l12-12M24 30l-9-8M24 30l9-8"/>',
    "lion": '<circle cx="24" cy="22" r="11"/><path d="M24 4v6M24 34v6M6 22h6M36 22h6M11 9l4 4M37 9l-4 4M11 35l4-4M37 35l-4-4"/><circle cx="20" cy="20" r="1.5" class="fill"/><circle cx="28" cy="20" r="1.5" class="fill"/>',
    "phallic-sign": '<path d="M10 30c0-5 4-8 10-8h12"/><circle cx="10" cy="34" r="4"/><circle cx="17" cy="35" r="4"/><path d="M32 18l8 4-8 4z"/>',
    "fist": '<path d="M12 22c0-6 5-10 12-10s12 4 12 10v10c0 6-5 10-12 10s-12-4-12-10z"/><path d="M20 22h10M24 12v-4"/>',
}
GLYPH_ORDER = list(GLYPHS)


def glyph(key: str, size=48, cls="") -> str:
    body = GLYPHS.get(key)
    if not body:
        return ""
    return (f'<svg class="glyph {cls}" viewBox="0 0 48 48" width="{size}" height="{size}" '
            f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            f'<g fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</g></svg>')


# ------------------------------------------------------- where the thing goes

# One figure, one doorway, one vehicle. Positions come from data/vocab/worn.json, and the
# page lights up the ones this atlas actually has records for.
SPOTS = {
    "head": (150, 34), "hair": (166, 40), "ear": (137, 46), "neck": (150, 74),
    "chest": (150, 104), "upper-arm": (110, 108), "wrist": (94, 168), "finger": (88, 190),
    "waist": (150, 158), "ankle": (132, 286), "skin": (186, 130), "sewn-in": (176, 120),
    "pocket": (176, 176), "wallet": (190, 176), "phone": (200, 196),
    "door": (320, 190), "lintel": (320, 128), "roof": (320, 92), "wall": (372, 168),
    "foundation": (320, 250), "hearth": (368, 214), "shop": (372, 128), "cradle": (268, 250),
    "vehicle": (470, 208), "boat": (470, 268), "field": (268, 292), "grave": (400, 292),
    "swallowed": (150, 128), "burnt": (420, 92),
}


def body_diagram(have: dict, width=560) -> str:
    """have: {spot_key: n}. A figure, a house, a car, a boat and a grave — because half the
    positions in this atlas are not on a body at all."""
    h = 330
    fig = f'''
    <g class="fig" fill="none" stroke="currentColor" stroke-width="1.6" opacity=".6">
      <circle cx="150" cy="40" r="20"/>
      <path d="M150 60v96M150 90l-42 62M150 90l42 62M150 156l-20 130M150 156l20 130"/>
      <path d="M108 152l-14 22M192 152l14 22"/>
    </g>
    <g class="house" fill="none" stroke="currentColor" stroke-width="1.6" opacity=".6">
      <path d="M262 132l58-52 58 52"/><path d="M276 132v130h88V132"/>
      <rect x="306" y="190" width="28" height="72"/><rect x="286" y="150" width="20" height="20"/>
      <path d="M262 262h116"/>
    </g>
    <g class="car" fill="none" stroke="currentColor" stroke-width="1.6" opacity=".6">
      <path d="M436 216h68l-8-22h-48zM444 194l8-16h36l10 16"/>
      <circle cx="452" cy="222" r="7"/><circle cx="492" cy="222" r="7"/>
    </g>
    <g class="boat" fill="none" stroke="currentColor" stroke-width="1.6" opacity=".6">
      <path d="M432 272h76l-12 20h-52zM470 272v-30l22 22h-22"/>
    </g>
    <g class="grave" fill="none" stroke="currentColor" stroke-width="1.6" opacity=".6">
      <path d="M388 300v-18a12 12 0 0124 0v18zM380 300h40"/>
    </g>'''
    dots = []
    top = max(have.values() or [1])
    for k, (x, y) in SPOTS.items():
        n = have.get(k, 0)
        if not n:
            continue
        r = 4 + 6 * (n / top) ** 0.6
        dots.append(f'<a href="#w-{k}"><circle class="spot" cx="{x * 0.98:.0f}" cy="{y * 0.98:.0f}" '
                    f'r="{r:.1f}" fill="{CARNELIAN}" fill-opacity=".72" stroke="#fff" stroke-width="1.4">'
                    f'<title>{E(k)} — {n}</title></circle></a>')
    return (f'<svg class="bodymap" viewBox="0 0 540 {h}" width="{width}" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="where amulets go: on a body, on a house, in a vehicle, on a boat, in a grave">'
            f'{fig}{"".join(dots)}</svg>')


def tier_dot(tier: str) -> str:
    col = {"cited": RAMP[5], "harvested": RAMP[3], "tradition": GOLD, "inference": CARNELIAN, "field": INK}
    return f'<span class="tdot" style="background:{col.get(tier, EDGE)}"></span>'
