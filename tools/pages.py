"""pages.py — the pages that answer a question rather than list a type.

  /map/       every country the records name, in Equal Earth, plus every place as a point
  /time/      five thousand years on one stated non-linear axis
  /against/   what each charm's carriers say it stops, and who said so
  /wear/      where the thing goes — on a body, a house, a vehicle, a boat, a grave
  /material/  what they are cut from, and what survives
  /signs/     the signs, drawn
  /numbers/   the atlas measuring itself, including where it is thin
  /quiz/      six questions, and the atlas hands you a charm and shows its working

Each takes the shell's page() and the built tables, and returns finished HTML.
"""
from __future__ import annotations

import json

import viz


def _h(recs, t):
    return [r for r in recs if r["type"] == t]


def _url(r, path_of):
    return f"../{path_of[r['type']]}/{r['id']}/index.html"


# ------------------------------------------------------------------------ map

def map_page(page, recs, atlas, places, cov, site_url, E, clip, path_of, **_) -> str:
    counts = {row["iso"]: row["n"] for row in atlas["rows"]}
    links = {row["iso"]: f"#c-{row['iso']}" for row in atlas["rows"]}
    pts = [{"lat": p["lat"], "lon": p["lon"], "name": f'{p["name"]} — {p["city"]}',
            "url": f'../{p["url"]}index.html'} for p in places["places"] if p.get("lat") is not None]
    # Small multiples by region family: the same world, eight times, so the eye compares
    # shapes instead of trying to hold eight colours apart on one sheet.
    fams = [("Worn at the neck", lambda r: "neck" in ((r.get("object") or {}).get("worn") or [])),
            ("Put at a door", lambda r: bool({"door", "lintel", "roof", "wall"} & set((r.get("object") or {}).get("worn") or []))),
            ("Written on", lambda r: bool({"paper", "parchment", "palm-leaf", "ink"} & set((r.get("object") or {}).get("materials") or []))),
            ("Metal", lambda r: bool({"iron", "silver", "gold", "copper", "lead", "brass", "coin"} & set((r.get("object") or {}).get("materials") or []))),
            ("Stone", lambda r: bool({"carnelian", "jade", "agate", "turquoise", "lapis", "jet"} & set((r.get("object") or {}).get("materials") or []))),
            ("Still carried", lambda r: bool((r.get("dating") or {}).get("living"))),
            ("Only archaeological", lambda r: (r.get("dating") or {}).get("to_year") is not None),
            ("Restricted by its tradition", lambda r: bool(r.get("restricted")))]
    groups = []
    for label, test in fams:
        hit = [r for r in recs if test(r)]
        isos = {c for r in hit for c in r.get("countries", []) or []}
        groups.append({"label": label, "n": len(hit), "isos": isos})

    rows = []
    for row in atlas["rows"]:
        items = " · ".join(f'<a href="../{r["url"]}index.html">{E(r["name"])}</a>' for r in row["records"])
        undrawn = "" if row.get("drawable", True) else ' <span class="chip">not on the sheet</span>'
        rows.append(f'<tr id="c-{E(row["iso"])}"><th>{E(row["name"])} <span class="count">({row["n"]})</span>{undrawn}</th>'
                    f'<td>{items}</td></tr>')
    nd = atlas.get("not_drawable") or []
    nd_line = ""
    if nd:
        from common import country_name as _cn
        nd_line = (f'<p class="mute"><b>Named but not filled:</b> '
                   + ", ".join(E(_cn(i)) for i in nd)
                   + f'. {E(atlas.get("not_drawable_note", ""))}</p>')

    body = f"""
<h1><span class="kind">Amulet Atlas</span>The map</h1>
<p class="lede">Drawn in Equal Earth, so a square centimetre of Nigeria stands for the same
square kilometres as a square centimetre of Norway. A Mercator would have inflated the far
north, which is where the least of this material comes from, and shrunk the equator, which
is where the most of it does — the picture would have argued something the records do not.</p>
<div class="mapwrap">{viz.world_choropleth(counts, 1100, "records by country", unit="records", links=links)}</div>
<p class="mute">{E(atlas["reading_an_absence"])}</p>
<h2>Every place, as a point</h2>
<p class="mute">Markets, workshops, shrines, dig sites and the museum rooms where a lot of the
rest of it ended up. Every point was placed by hand from a published address or coordinate —
there is no open dataset of amulet stalls — and each record says how close its point is.</p>
<div class="mapwrap">{viz.world_points(pts, 1100, "places")}</div>
<p><a href="../places/index.html">The places, written up →</a></p>
<h2>The same world, eight times</h2>
<p class="mute">Red is the countries where this atlas has a record of that kind. A blank is a
blank in the atlas, not an absence in the world.</p>
{viz.world_multiples(groups, 250)}
<h2>Which halves of the world</h2>
{viz.hemisphere_bar(cov["world"]["hemispheres"], len(recs), 760)}
<p class="mute">{E(cov["world"]["reading_an_absence"])}</p>
<h2>Country by country</h2>
{nd_line}
<table>{"".join(rows)}</table>
<p class="legend">Outlines from <a href="https://www.naturalearthdata.com/">Natural Earth</a>,
1:110m, public domain. The table behind this page is
<a href="../api/atlas.json">atlas.json</a>.</p>
"""
    return page("The map — Amulet Atlas", body, 1,
                "Every country the records name, drawn in Equal Earth, plus every place as a point.",
                None, f"{site_url}/map/", card="map")


# ----------------------------------------------------------------------- time

ERA_COLOUR = {"prehistoric": "#1a4b46", "ancient": "#2b7268", "classical": "#46988c",
              "medieval": "#9d7320", "early-modern": "#c08a2e", "modern": "#b23a2b",
              "living": "#b23a2b"}


def time_page(page, recs, timeline, by_id, site_url, E, year_label, **_) -> str:
    rows = sorted(timeline["rows"], key=lambda r: (r["from_year"] if r["from_year"] is not None else 9999))

    def colour(r):
        rec = by_id.get(r["id"]) or {}
        era = (rec.get("facets") or {}).get("era")
        return ERA_COLOUR.get(era, "#2b7268")

    methods: dict = {}
    for r in rows:
        methods[r["method"]] = methods.get(r["method"], 0) + 1
    mrows = sorted(({"label": k or "unstated", "n": v} for k, v in methods.items()),
                   key=lambda x: -x["n"])
    living = [r for r in rows if r["living"]]
    ended = [r for r in rows if not r["living"] and r["to_year"] is not None]
    undated = timeline.get("undated", [])
    undated_links = " · ".join(
        f'<a href="../{ {"term": "word"}.get(by_id[i]["type"], by_id[i]["type"]) }/{E(i)}/index.html">{E(by_id[i]["names"]["name"])}</a>'
        for i in undated if i in by_id)

    body = f"""
<h1><span class="kind">Amulet Atlas</span>The timeline</h1>
<p class="lede">{len(rows)} records with a date on them, from the oldest to the one somebody
bought this morning. <b>The axis is not linear</b>, and the ticks say so: five thousand years
at one scale would give the last two centuries about a millimetre, and the last two centuries
are where a third of these records live. Every tick is printed so you can see the stretching
happen.</p>
<div class="mapwrap">{viz.time_density(rows, 1100)}</div>
<p class="mute">That curve is the shape of <i>this atlas</i>, not of the past. It rises at 1800
because the written record rises at 1800.</p>
<div class="facts">
  <div class="fact"><span class="n">{len(living)}</span><span class="l">still carried</span></div>
  <div class="fact"><span class="n">{len(ended)}</span><span class="l">no longer</span></div>
  <div class="fact"><span class="n">{len(undated)}</span><span class="l">undated here</span></div>
</div>
<h2>Every dated record</h2>
<p class="mute">A bar with an open circle at its right-hand end is something people still carry.
A dotted bar is a date somebody reasoned to rather than dug up. Colour is the era the record
files itself under.</p>
<div class="mapwrap">{viz.time_chart(rows, 1100, 15.5, 200, colour)}</div>
<h2>How these dates are known</h2>
{viz.bars(mrows, 760, " records", 28, 210)}
<p class="mute">An excavated date and an ethnographer's date are not the same kind of fact, and
the atlas keeps them apart rather than averaging them into a number.
<a href="../story/dating-a-charm/index.html">The long version →</a></p>
<h2>Undated, and why that matters</h2>
<p class="mute">{E(timeline["note"])}</p>
<p>{undated_links or "<span class='mute'>Nothing in this build is undated.</span>"}</p>
<p class="legend">Years are stored astronomically — 1 CE is 1, 1 BCE is 0, 500 BCE is −499 — so
that arithmetic across the era boundary works, and printed the way a reader says them. The
table behind this page is <a href="../api/timeline.json">timeline.json</a>.</p>
"""
    return page("The timeline — Amulet Atlas", body, 1,
                "Five thousand years of amulet on one stated non-linear axis.",
                None, f"{site_url}/time/", card="time")


# -------------------------------------------------------------------- against

def against_page(page, recs, against, by_id, site_url, E, **_) -> str:
    harms = [h for h in against["harms"] if h["n"]]
    rows = against["rows"]
    regions: dict = {}
    for c in rows:
        regions.setdefault(c["region"] or "unplaced", 0)
        regions[c["region"] or "unplaced"] += 1
    top_regions = [r for r, _n in sorted(regions.items(), key=lambda kv: -kv[1])[:14]]

    def cell(h, reg):
        n = sum(1 for c in rows if c["harm"] == h["key"] and (c["region"] or "unplaced") == reg["key"])
        return n, f'{h["label"]} × {reg["label"]} — {n}'

    mat = viz.matrix([{"label": h["label"], "key": h["key"]} for h in harms[:18]],
                     [{"label": r.replace("-", " ").title(), "key": r} for r in top_regions],
                     cell, 1100, 210, 130)

    groups = []
    for h in harms[:12]:
        isos = {i for c in rows if c["harm"] == h["key"] for i in c["countries"]}
        groups.append({"label": h["label"], "n": h["n"], "isos": isos})

    blocks = []
    for h in harms:
        items = []
        for c in rows:
            if c["harm"] != h["key"]:
                continue
            who = f'<span class="who">said by {E(c["who"])}</span>' if c.get("who") else \
                  '<span class="who">no claimant named in the source</span>'
            q = f'<blockquote>{E(c["quote"])}</blockquote>' if c.get("quote") else ""
            items.append(f'<li><b><a href="../{c["url"]}index.html">{E(c["name"])}</a></b> '
                         f'{viz.tier_dot(c["tier"])}{who}{q}</li>')
        gloss = f'<p class="mute">{E(h.get("gloss", ""))}</p>' if h.get("gloss") else ""
        blocks.append(f'<h3 id="h-{E(h["key"])}">{E(h["label"])} <span class="count">({h["n"]})</span></h3>'
                      f'{gloss}<ul class="against">{"".join(items)}</ul>')

    body = f"""
<h1><span class="kind">Amulet Atlas</span>What it stops</h1>
<p class="lede">{against["count"]} claims, each one belonging to somebody. This project does not
record who said it and link the source. Whether a charm works is not a question this
page answers. {E(against["note"])}</p>
{viz.bars([{"label": h["label"], "n": h["n"]} for h in harms], 1100, " claims", 29, 270)}
<h2>Harm against region</h2>
<p class="mute">A blank cell is a blank — no record here makes that claim in that region. It is
not a zero dressed up as a finding.</p>
<div class="mapwrap">{mat}</div>
<h2>Where each worry is documented</h2>
{viz.world_multiples(groups, 250)}
<h2>Every claim, by what it answers</h2>
{"".join(blocks)}
<p class="legend">Dot colour is the provenance tier of the claim: a named source, general
knowledge of the practice, or this project's own reasoning. The table behind this page is
<a href="../api/against.json">against.json</a>.</p>
"""
    return page("What it stops — Amulet Atlas", body, 1,
                "Every claim about what a charm does, attributed to whoever made it.",
                None, f"{site_url}/against/", card="against")


# ----------------------------------------------------------------------- wear

def wear_page(page, matter, recs, site_url, E, **_) -> str:
    worn = matter["worn"]
    have = {w["key"]: w["n"] for w in worn}
    groups: dict = {}
    for w in worn:
        groups.setdefault(w.get("group", "other"), []).append(w)
    order = ["body", "carried", "placed", "taken", "other"]
    label = {"body": "On the body", "carried": "Carried, out of sight",
             "placed": "Put somewhere and left", "taken": "Taken into the body", "other": "Elsewhere"}
    secs = []
    for g in order:
        if g not in groups:
            continue
        cards = []
        for w in sorted(groups[g], key=lambda x: -x["n"]):
            items = "".join(f'<li><a href="../{r["url"]}index.html">{E(r["name"])}</a></li>'
                            for r in sorted(w["records"], key=lambda x: x["name"].lower()))
            note = f'<p class="mute" style="font-size:.86rem">{E(w.get("note", ""))}</p>' if w.get("note") else ""
            cards.append(f'<section id="w-{E(w["key"])}"><h3>{E(w["label"])} '
                         f'<span class="count">({w["n"]})</span></h3>{note}<ul>{items}</ul></section>')
        secs.append(f'<h2>{E(label[g])}</h2><div class="wearlist">{"".join(cards)}</div>')

    forms = matter["forms"]
    body = f"""
<h1><span class="kind">Amulet Atlas</span>Where it goes</h1>
<p class="lede">Half the meaning of a charm is its position. The same shape at the throat, in a
pocket, over a door and in a grave is doing four different things, and the traditions say so
themselves. Only about half the positions in this atlas are on a body at all.</p>
<div class="mapwrap">{viz.body_diagram(have, 900)}</div>
<p class="mute">Dot size is how many records this atlas has for that position. Click one to jump
to its list.</p>
{"".join(secs)}
<h2>And what shape it takes</h2>
{viz.bars([{"label": f["label"], "n": f["n"]} for f in forms[:22]], 900, "", 27, 210)}
<p class="legend">Positions come from <a href="../api/vocab/worn.json">worn.json</a>; the counts
come from the records themselves, in <a href="../api/matter.json">matter.json</a>. The figure,
the house, the car and the boat are drawn for this atlas.</p>
"""
    return page("Where it goes — Amulet Atlas", body, 1,
                "On a body, on a house, in a vehicle, on a boat, in a grave.",
                None, f"{site_url}/wear/", card="wear")


# ------------------------------------------------------------------ materials

def material_page(page, matter, recs, by_id, site_url, E, **_) -> str:
    mats = matter["materials"]
    kinds: dict = {}
    for m in mats:
        kinds.setdefault(m.get("kind", "other"), []).append(m)
    kind_label = {"stone": "Stone", "organic": "Once alive", "fired": "Out of a kiln",
                  "metal": "Metal", "written": "Written on", "textile": "Thread and cloth",
                  "plant": "Plant", "mineral": "Mineral", "modern": "Made this century",
                  "other": "Other"}
    secs = []
    for k in ("stone", "metal", "fired", "organic", "written", "textile", "plant", "mineral", "modern", "other"):
        if k not in kinds:
            continue
        cards = []
        for m in sorted(kinds[k], key=lambda x: -x["n"]):
            items = "".join(f'<li><a href="../{r["url"]}index.html">{E(r["name"])}</a></li>'
                            for r in sorted(m["records"], key=lambda x: x["name"].lower()))
            page_link = (f'<a href="../material/{E(m["key"])}/index.html">written up →</a>'
                         if any(r["id"] == m["key"] and r["type"] == "material" for r in recs) else "")
            cards.append(f'<section id="m-{E(m["key"])}"><h3>{E(m["label"])} '
                         f'<span class="count">({m["n"]})</span></h3><ul>{items}</ul>'
                         f'<p style="font-size:.86rem">{page_link}</p></section>')
        secs.append(f'<h2>{E(kind_label[k])}</h2><div class="wearlist">{"".join(cards)}</div>')

    surviving = {"faience", "carnelian", "jade", "agate", "turquoise", "lapis", "jet", "glass",
                 "gold", "silver", "copper", "iron", "lead", "bone", "tooth", "shell", "cowrie",
                 "amber", "coral", "terracotta"}
    perishing = {"paper", "parchment", "palm-leaf", "cloth", "thread", "knot", "wood", "seed",
                 "herb", "hair", "skin", "salt", "earth", "ink", "leather"}
    surv = sum(m["n"] for m in mats if m["key"] in surviving)
    per = sum(m["n"] for m in mats if m["key"] in perishing)

    body = f"""
<h1><span class="kind">Amulet Atlas</span>Materials</h1>
<p class="lede">What a charm is cut from is half of what it claims. Red carnelian for blood,
cold iron against what walks at night, a bead of glass that costs nothing and can be replaced,
a strip of paper that will not last a winter. This page counts what the records are made of.</p>
{viz.bars([{"label": m["label"], "n": m["n"]} for m in mats[:24]], 1000, "", 28, 230)}
<h2>What survives, and what the drawer therefore holds</h2>
<div class="facts">
  <div class="fact"><span class="n">{surv}</span><span class="l">in a material that lasts</span></div>
  <div class="fact"><span class="n">{per}</span><span class="l">in one that does not</span></div>
</div>
<p class="mute">Stone, fired quartz paste and metal come out of the ground legible after four
thousand years. Paper, cloth, thread, herb, hair and salt do not. A museum tray of ancient
amulets is a record of what lasts, and this atlas's own ancient section inherits that bias —
which is why the modern records lean the other way and why the two should not be read as one
continuous series.</p>
{"".join(secs)}
<p class="legend">Material keys come from <a href="../api/vocab/materials.json">materials.json</a>;
the counts come from the records, in <a href="../api/matter.json">matter.json</a>.</p>
"""
    return page("Materials — Amulet Atlas", body, 1,
                "Carnelian, iron, amber, coral, paper, hair, salt — and what survives.",
                None, f"{site_url}/materials/", card="materials")


# ---------------------------------------------------------------------- signs

def signs_page(page, recs, by_id, site_url, E, clip, **_) -> str:
    motifs = sorted(_h(recs, "motif"), key=lambda r: r["names"]["name"].lower())
    trads = sorted(_h(recs, "tradition"), key=lambda r: r["names"]["name"].lower())
    grid = []
    for r in motifs:
        g = viz.glyph(r["id"], 62) or viz.glyph("eye", 62)
        grid.append(f'<a href="../sign/{E(r["id"])}/index.html">{g}'
                    f'<span class="nm">{E(r["names"]["name"])}</span>'
                    f'<span class="ct">{E(r.get("span") or "")}</span></a>')

    kin_of: dict = {}
    for r in recs:
        for k in r.get("kin_out", []):
            kin_of.setdefault(r["id"], set()).add(k["to"])
            kin_of.setdefault(k["to"], set()).add(r["id"])

    def cell(m, t):
        n = 1 if t["key"] in kin_of.get(m["key"], set()) else 0
        return n, f'{m["label"]} × {t["label"]} — {"linked" if n else "no link in this atlas"}'

    mat = ""
    if motifs and trads:
        mat = viz.matrix([{"label": r["names"]["name"], "key": r["id"]} for r in motifs],
                         [{"label": r["names"]["name"], "key": r["id"]} for r in trads],
                         cell, 1100, 190, 150)

    unglyphed = [r["names"]["name"] for r in motifs if not viz.GLYPHS.get(r["id"])]
    body = f"""
<h1><span class="kind">Amulet Atlas</span>The signs</h1>
<p class="lede">An eye, a hand, a horn, a knot, a serpent. These are the marks that turn up in
places that never met, and the interesting question is always which of those is transmission,
which is two peoples arriving at the same shape, and which is nobody knowing. Each record says
which, case by case, or says it is unknown.</p>
<p class="mute">Every glyph below is drawn for this atlas from published descriptions of the
sign. None is traced from a photograph of any one object — an atlas of signs that copied its
signs would be an atlas of somebody else's drawings. They go out under the project's licence.
{"Signs with no glyph yet: " + E(", ".join(unglyphed)) + "." if unglyphed else ""}</p>
<div class="glyphgrid">{"".join(grid)}</div>
<h2>Which traditions this atlas links each sign to</h2>
<p class="mute">A filled cell means a record on one side names the other in its own words. It is
a map of the links this atlas has drawn, which is not the same as a map of the world's signs —
a blank may mean nobody here has written the link yet.</p>
<div class="mapwrap">{mat}</div>
<p><a href="../story/the-eye-everywhere/index.html">The eye across four continents →</a> ·
<a href="../story/the-swastika-problem/index.html">The one sign that needs its own page →</a></p>
<p class="legend">Kin edges behind the grid are in <a href="../api/kin.json">kin.json</a>.</p>
"""
    return page("The signs — Amulet Atlas", body, 1,
                "The marks that cross traditions — an eye, a hand, a horn, a knot — drawn.",
                None, f"{site_url}/signs/", card="signs")


# -------------------------------------------------------------------- numbers

def numbers_page(page, recs, atlas, timeline, against, matter, places, cov, site_url, E, year_label, **_) -> str:
    edges = sum(len(r.get("kin_out", [])) for r in recs)
    by_type = [{"label": k, "n": v} for k, v in sorted(cov["records"].items(), key=lambda kv: -kv[1]) if v]
    tiers: dict = {}
    for r in recs:
        t = (r.get("provenance") or {}).get("default", {}).get("tier", "unstated")
        tiers[t] = tiers.get(t, 0) + 1
    tier_rows = [{"label": k, "n": v} for k, v in sorted(tiers.items(), key=lambda kv: -kv[1])]
    top_countries = [{"label": row["name"], "n": row["n"]} for row in atlas["rows"][:20]]
    conf: dict = {}
    for r in recs:
        conf[r["confidence"]] = conf.get(r["confidence"], 0) + 1
    needs = [r for r in recs if r.get("needs_verification")]
    restricted = [r for r in recs if r.get("restricted")]
    quoted = sum(1 for r in recs for a in r.get("against", []) if a.get("quote"))

    body = f"""
<h1><span class="kind">Amulet Atlas</span>Numbers</h1>
<p class="lede">The atlas measuring itself, including the places it is thin. Every number on this
page is computed from the records at build time; none of it is typed in by hand.</p>
<div class="facts">
  <div class="fact"><span class="n">{len(recs)}</span><span class="l">records</span></div>
  <div class="fact"><span class="n">{edges}</span><span class="l">kin links</span></div>
  <div class="fact"><span class="n">{atlas["countries"]}</span><span class="l">countries</span></div>
  <div class="fact"><span class="n">{places["count"]}</span><span class="l">places mapped</span></div>
  <div class="fact"><span class="n">{timeline["count"]}</span><span class="l">dated</span></div>
  <div class="fact"><span class="n">{against["count"]}</span><span class="l">claims</span></div>
  <div class="fact"><span class="n">{quoted}</span><span class="l">with somebody quoted</span></div>
  <div class="fact"><span class="n">{cov["sources"]}</span><span class="l">sources</span></div>
  <div class="fact"><span class="n">{len(restricted)}</span><span class="l">held back on purpose</span></div>
  <div class="fact"><span class="n">{E(year_label(cov["time"]["earliest_year"]))}</span><span class="l">earliest dated</span></div>
</div>
<h2>Records by kind</h2>
{viz.bars(by_type, 860, "", 27, 180)}
<h2>Countries with the most</h2>
{viz.bars(top_countries, 860, "", 27, 210)}
<p class="mute">This is a ranking of <b>this atlas</b>, not of the world. Egypt leads because
Egypt's amulets were buried in a dry climate in enormous numbers and then excavated and
catalogued by people who published in English.</p>
<h2>What each record rests on</h2>
{viz.bars(tier_rows, 700, " records", 27, 170)}
<p class="mute">The record's default tier. Individual fields override it, and the chips on each
page say which. {len(needs)} records carry <i>needs checking</i>, and
{conf.get("medium", 0) + conf.get("low", 0)} say their confidence is not high.</p>
<h2>Where it goes, and what it is made of</h2>
<div class="two-up">
  <div>{viz.bars([{"label": w["label"], "n": w["n"]} for w in matter["worn"][:14]], 520, "", 26, 150)}</div>
  <div>{viz.bars([{"label": m["label"], "n": m["n"]} for m in matter["materials"][:14]], 520, "", 26, 150)}</div>
</div>
<h2>Still thin</h2>
<ul>{"".join(f"<li>{E(x)}</li>" for x in cov["not_yet"])}</ul>
<p class="legend">All of it from <a href="../api/coverage.json">coverage.json</a>,
<a href="../api/atlas.json">atlas.json</a>, <a href="../api/timeline.json">timeline.json</a>,
<a href="../api/against.json">against.json</a> and <a href="../api/matter.json">matter.json</a>.
<a href="../coverage/index.html">Where we stop →</a></p>
"""
    return page("Numbers — Amulet Atlas", body, 1,
                "The atlas measuring itself, including the places it is thin.",
                None, f"{site_url}/numbers/", card="numbers")


# ----------------------------------------------------------------------- quiz

def quiz_page(page, quiz, recs, site_url, E, path_of, **_) -> str:
    """Six questions and a charm — with the scoring printed, because a quiz that hides its
    arithmetic is asking to be believed rather than read."""
    cands = []
    for r in recs:
        if r["type"] != "amulet":
            continue
        ob = r.get("object") or {}
        toks = set()
        toks |= {a["harm"] for a in r.get("against", [])}
        toks |= set(ob.get("materials", []) or [])
        toks |= set(ob.get("worn", []) or [])
        if ob.get("form"):
            toks.add(ob["form"])
        f = r.get("facets") or {}
        for k in ("era", "status", "restricted", "portable"):
            if f.get(k):
                toks.add(str(f[k]))
        if (r.get("dating") or {}).get("living"):
            toks.add("living")
        for k in r.get("kin_out", []):
            toks.add(k["to"])
        cands.append({"id": r["id"], "name": r["names"]["name"],
                      "url": f'../{path_of[r["type"]]}/{r["id"]}/index.html',
                      "blurb": r["blurb"], "toks": sorted(toks),
                      "living": bool((r.get("dating") or {}).get("living"))})

    qs = []
    for i, q in enumerate(quiz["questions"]):
        opts = "".join(
            f'<label><input type="radio" name="q{i}" value="{j}"> {E(a["t"])}</label>'
            for j, a in enumerate(q["a"]))
        qs.append(f'<fieldset><legend>{i + 1}. {E(q["q"])}</legend>{opts}</fieldset>')

    body = f"""
<h1><span class="kind">Amulet Atlas</span>Pick me one</h1>
<p class="lede">Six questions. The atlas hands you a charm from its own records and then shows
its working — which answers pushed it there, and by how much. It is a lookup, not an oracle,
and the scoring runs in this page.</p>
<form class="quiz" id="qz">{"".join(qs)}
<p><button class="btn" type="button" id="go">Hand me one</button>
<button class="btn ghost" type="button" id="again">Start over</button></p></form>
<div id="out"></div>
<p class="legend">Scoring comes from <a href="../api/vocab/quiz.json">quiz.json</a> and the
records' own fields — what each charm is said to stop, what it is made of, where it goes. No
charm is ranked above another; the number only says how many of your answers it matched.</p>
<script>
(function(){{
var Q={json.dumps(quiz["questions"], ensure_ascii=False)};
var C={json.dumps(cands, ensure_ascii=False)};
function esc(s){{return String(s==null?"":s).replace(/[&<>"]/g,function(c){{return {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]}})}}
function run(){{
  var tally={{}}, picked=[];
  Q.forEach(function(q,i){{
    var el=document.querySelector('input[name="q'+i+'"]:checked'); if(!el) return;
    var a=q.a[+el.value]; picked.push({{q:q.q,a:a.t,adds:a.adds}});
    for(var k in a.adds) tally[k]=(tally[k]||0)+a.adds[k];
  }});
  if(!picked.length){{document.getElementById("out").innerHTML='<p class="mute">Answer at least one.</p>';return}}
  var scored=C.map(function(c){{
    var s=0, why=[];
    c.toks.forEach(function(t){{if(tally[t]){{s+=tally[t];why.push(t+" +"+tally[t])}}}});
    return {{c:c,s:s,why:why}};
  }}).filter(function(x){{return x.s>0}});
  scored.sort(function(a,b){{return b.s-a.s}});
  var out=document.getElementById("out");
  if(!scored.length){{
    out.innerHTML='<h2>Nothing in the atlas matched</h2><p class="mute">That is a real answer, '+
      'not a failure: this atlas covers what it covers, and it says where it stops. '+
      '<a href="../coverage/index.html">Where we stop</a>.</p>';return;
  }}
  var top=scored.slice(0,4);
  out.innerHTML='<h2>What the atlas hands you</h2>'+top.map(function(x,i){{
    return '<div class="card" style="margin-bottom:.8rem"><a class="t" href="'+x.c.url+'">'+esc(x.c.name)+'</a>'+
      (i===0?' <span class="chip">closest match</span>':'')+
      (x.c.living?' <span class="chip">still carried</span>':' <span class="chip">no longer carried</span>')+
      '<p>'+esc(x.c.blurb)+'</p>'+
      '<p class="mute" style="font-size:.82rem">matched on: '+x.why.map(esc).join(" · ")+' = '+x.s+'</p></div>';
  }}).join('')+
  '<h3>What you told it</h3><ul>'+picked.map(function(p){{
    return '<li>'+esc(p.a)+' <span class="mute">→ '+esc(Object.keys(p.adds).join(", "))+'</span></li>'}}).join('')+'</ul>';
  out.scrollIntoView({{behavior:"smooth",block:"start"}});
}}
document.getElementById("go").addEventListener("click",run);
document.getElementById("again").addEventListener("click",function(){{
  document.getElementById("qz").reset();document.getElementById("out").innerHTML=""}});
}})();
</script>
"""
    return page("Pick me one — Amulet Atlas", body, 1,
                "Six questions, and the atlas hands you a charm and shows its working.",
                None, f"{site_url}/quiz/", card="quiz")
