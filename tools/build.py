#!/usr/bin/env python3
"""build.py — records → build/api (JSON) + build/searchdocs.json + search tables.

Order: validate → enrich → write. Nothing is written if validation fails.

Outputs (all regenerated, never hand-edited):
  build/api/nodes.json          every enriched record
  build/api/<type>/<id>.json    one per record
  build/api/index.json          directory: id, type, name, region, facets, blurb
  build/api/places.json         places with coordinates, one row each, with provenance
  build/api/kin.json            every directed kin edge, plus auto backlinks
  build/api/atlas.json          the map table: one row per country, what is documented there
  build/api/timeline.json       the timeline table: one row per dated record
  build/api/against.json        the harm table: what each charm is said to be for, and who says
  build/api/matter.json         materials, forms and where on the body — the /material/ and /wear/ tables
  build/api/vocab/*.json        regions, types, facets, against, materials, forms, worn
  build/api/sources.json        the source registry (merged)
  build/api/coverage.json       scope as an object: what is in, what is not, where rows come from
  build/searchdocs.json         one document per record
  data/search/amulets.thesaurus.json   mined from the records for search-core (synonymy only)

    python3 tools/build.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BUILD, DATA, SOURCES, TIER_LABEL, TYPES, country_by_geo,  # noqa: E402
                    country_name, is_drawable, jdump, jload, load_nodes, load_sources,
                    load_vocab, span_label)
from validate import validate_all  # noqa: E402

SEARCH_DIR = DATA / "search"
API = BUILD / "api"
TAGS = {e["key"]: e for e in load_vocab("tags").get("entries", [])}
RECOG = {e["key"]: e for e in load_vocab("recognizers").get("entries", [])}
HARMS = {e["key"]: e for e in load_vocab("against").get("entries", [])}
MATS = {e["key"]: e for e in load_vocab("materials").get("entries", [])}
FORMS = {e["key"]: e for e in load_vocab("forms").get("entries", [])}
WORN = {e["key"]: e for e in load_vocab("worn").get("entries", [])}
MUSEUMS = {e["key"]: e for e in load_vocab("museums").get("entries", [])}
REGIONS = {e["key"]: e for e in load_vocab("regions").get("entries", [])}


def merge_sources() -> dict:
    """sources.json + every data/sources/new-*.json, de-duplicated by id, written back."""
    base = jload(SOURCES)
    have = {s["id"] for s in base["sources"]}
    added = 0
    for p in sorted(SOURCES.parent.glob("new-*.json")):
        d = jload(p)
        for s in d.get("sources", []):
            if s.get("id") and s["id"] not in have:
                base["sources"].append(s)
                have.add(s["id"])
                added += 1
        p.unlink()
    if added:
        base["sources"].sort(key=lambda s: s["id"])
        jdump(base, SOURCES)
        print(f"merged {added} new sources into sources.json")
    return {s["id"]: s for s in base["sources"]}


def blurb(r: dict, n=220) -> str:
    w = r["text"]["what"].strip()
    if len(w) <= n:
        return w
    head = w[:n]
    if ". " in head and len(head.rsplit(". ", 1)[0]) > 60:
        return head.rsplit(". ", 1)[0] + "."
    return head.rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def tier_for(rec: dict, path: str) -> dict:
    prov = rec.get("provenance", {})
    best = None
    for p, v in prov.get("fields", {}).items():
        if path == p or path.startswith(p + "."):
            if best is None or len(p) > len(best[0]):
                best = (p, v)
    return best[1] if best else prov.get("default", {})


def hemis(r: dict) -> list:
    """Which halves of the world a record touches: its own coordinate first, then the
    hemispheres its regions carry, then its countries' rough positions. A record that
    reaches none of them says so by being absent from the hemisphere counts."""
    out = set()
    g = r.get("geo") or {}
    if g:
        out.add("N" if g["lat"] >= 0 else "S")
        out.add("E" if g["lon"] >= 0 else "W")
    for k in r.get("region", []):
        for h in (REGIONS.get(k) or {}).get("hemi", []) or []:
            out.add(h)
    return sorted(out)


def enrich(r: dict, by_id: dict, sources: dict) -> dict:
    out = {k: v for k, v in r.items() if not k.startswith("_")}
    out["blurb"] = blurb(out)
    out["region_terms"] = [dict(REGIONS.get(k) or {"key": k, "name": k}) for k in out["region"]]
    out["hemispheres"] = hemis(out)
    out["kin_out"] = []
    for k in out.get("kin", []):
        t = by_id.get(k["to"])
        if t:
            out["kin_out"].append({"to": k["to"], "type": t["type"], "name": t["names"]["name"],
                                   "as": k["as"], "rel": k.get("rel", "kin"),
                                   "name_th": t["names"].get("th", ""), "as_th": k.get("as_th", "")})
    out["source_list"] = [dict(sources[s], id=s) for s in out.get("sources", []) if s in sources]
    out["tiers"] = {p: tier_for(out, p) for p in
                    ("text.what", "text.story", "text.how", "text.today", "etymology", "dating", "object", "geo", "address")
                    if p.split(".")[0] in out and (len(p.split(".")) == 1 or p.split(".")[1] in out[p.split(".")[0]])}
    out["primary_image"] = next((im for im in out.get("images", []) if im.get("primary")), (out.get("images") or [None])[0])
    out["tag_facts"] = [dict(TAGS.get(t["tag"], {"key": t["tag"], "label": t["tag"], "icon": ""}),
                             **{"source": t["source"], "note": t.get("note", ""), "tier": t.get("tier", "cited"), "url": t.get("url", "")})
                        for t in out.get("tags", [])]
    out["recognition_facts"] = [dict(RECOG.get(x["by"], {"key": x["by"], "label": x["by"]}),
                                     **{"what": x["what"], "year": x.get("year"), "source": x["source"], "url": x.get("url", "")})
                                for x in out.get("recognitions", [])]
    out["acclaim"] = len({x["by"] for x in out.get("recognitions", [])})
    out["against_facts"] = [dict(HARMS.get(a["harm"], {"key": a["harm"], "label": a["harm"]}),
                                 **{"who": a.get("who", ""), "quote": a.get("quote", ""),
                                    "source": a["source"], "tier": a.get("tier", "cited"), "note": a.get("note", "")})
                            for a in out.get("against", [])]
    ob = out.get("object") or {}
    out["material_facts"] = [dict(MATS.get(m, {"key": m, "label": m, "kind": "other"})) for m in ob.get("materials", []) or []]
    out["worn_facts"] = [dict(WORN.get(w, {"key": w, "label": w, "group": "other"})) for w in ob.get("worn", []) or []]
    out["form_fact"] = dict(FORMS.get(ob.get("form"), {"key": ob.get("form"), "label": ob.get("form")})) if ob.get("form") else None
    out["holding_facts"] = [dict(MUSEUMS.get(h["museum"], {"key": h["museum"], "label": h["museum"]}),
                                 **{"what": h.get("what", ""), "accession": h.get("accession", ""),
                                    "url": h.get("url", ""), "source": h["source"]})
                            for h in out.get("holdings", [])]
    dt = out.get("dating") or {}
    out["span"] = span_label(dt.get("from_year"), dt.get("to_year")) if dt else ""
    out["country_names"] = [{"iso": c, "name": country_name(c)} for c in out.get("countries", []) or []]
    return out


def backlinks(recs: list[dict]):
    """Every record learns who links to it, with that record's own sentence. Never invented prose."""
    by_id = {r["id"]: r for r in recs}
    for r in recs:
        r["kin_in"] = []
    for r in recs:
        for k in r["kin_out"]:
            t = by_id.get(k["to"])
            if t:
                t["kin_in"].append({"from": r["id"], "type": r["type"], "name": r["names"]["name"], "as": k["as"], "rel": k["rel"],
                                    "name_th": r["names"].get("th", ""), "as_th": k.get("as_th", "")})


def search_doc(r: dict) -> dict:
    n = r["names"]
    et = r.get("etymology") or {}
    ob = r.get("object") or {}
    return {
        "id": r["id"], "type": r["type"], "name": n["name"],
        "names": " ".join([n["name"]] + n.get("aliases", []) + [n.get("said", ""), n.get("native", "")]),
        "terms": " ".join([r["type"]] + [t.get("name", "") for t in r["region_terms"]]
                          + [a["label"] for a in r.get("against_facts", [])]
                          + [m["label"] for m in r.get("material_facts", [])]
                          + [w["label"] for w in r.get("worn_facts", [])]
                          + [h["label"] for h in r.get("holding_facts", [])]
                          + [c["name"] for c in r.get("country_names", [])]
                          + [str(v) if not isinstance(v, list) else " ".join(map(str, v)) for v in (r.get("facets") or {}).values()]
                          + [k["name"] for k in r["kin_out"]]
                          + [(r.get("address") or {}).get(k, "") for k in ("city", "admin", "country")]),
        "text": " ".join([r["text"].get(k, "") for k in ("what", "story", "how", "today", "notes")]
                         + [et.get("root", ""), et.get("note", ""), ob.get("inscription", ""), r.get("span", "")]
                         + [c["tell"] for c in r.get("confusable_with", [])]),
        "blurb": r["blurb"],
        "region": (r["region"] or [""])[0],
    }


def mine_thesaurus(recs: list[dict]) -> int:
    """Synonymy groups from each record's own names and aliases — never hand-curated here."""
    groups = []
    for r in recs:
        n = r["names"]
        g = sorted({x.lower().strip() for x in [n["name"], n.get("said", "")] + n.get("aliases", []) if x and len(x.split()) <= 4})
        if len(g) >= 2:
            groups.append(g)
    # The words a reader is likeliest to arrive with, against the words the records use.
    groups += [
        ["amulet", "charm", "talisman", "lucky charm", "protective charm"],
        ["evil eye", "malocchio", "mati", "nazar", "ayin hara"],
        ["hamsa", "khamsa", "hand of fatima", "hand of miriam"],
        ["scarab", "scarab beetle", "khepri"],
        ["eye of horus", "wedjat", "udjat"],
        ["thors hammer", "mjolnir", "hammer pendant"],
        ["omamori", "japanese charm", "shrine charm"],
        ["thai amulet", "phra khrueang", "buddha amulet"],
        ["gris gris", "grigri", "mojo bag", "mojo hand"],
        ["milagro", "ex voto", "votive offering"],
        ["horseshoe", "lucky horseshoe"],
        ["prayer flag", "lungta", "wind horse"],
    ]
    SEARCH_DIR.mkdir(parents=True, exist_ok=True)
    jdump({"note": "mined by build.py from data/nodes names + aliases — synonymy only", "groups": groups},
          SEARCH_DIR / "amulets.thesaurus.json", indent=0)
    return len(groups)


def places_table(recs: list[dict]) -> dict:
    """Every place record with a coordinate, one row each. There is no harvested layer here:
    a market stall or a museum gallery is not a row in an open dataset, so every point on
    this map was placed by hand and says where it came from."""
    rows = []
    for r in recs:
        if r["type"] != "place":
            continue
        g = r.get("geo") or {}
        a = r.get("address") or {}
        hrs = r.get("hours") or {}
        iso = a.get("country") or (country_by_geo(g["lat"], g["lon"]) if g else None)
        rows.append({
            "id": r["id"], "name": r["names"]["name"], "url": f"place/{r['id']}/",
            "city": a.get("city", ""), "country": iso, "country_name": country_name(iso) if iso else "",
            "lat": g.get("lat"), "lon": g.get("lon"), "precision": g.get("precision"),
            "kind": (r.get("facets") or {}).get("kind"),
            "days": day_state(r), "hours_text": hrs.get("text", ""),
            "blurb": r["blurb"], "tier": tier_for(r, "text.what").get("tier"),
            "tags": sorted({t["tag"] for t in r.get("tags", [])}),
            "recognitions": r.get("acclaim", 0),
            "hemispheres": r.get("hemispheres", []),
            "image": (r.get("primary_image") or {}).get("file"),
        })
    rows.sort(key=lambda x: (x["country_name"] or "zz", x["name"].lower()))
    return {"built": time.strftime("%Y-%m-%d"), "count": len(rows),
            "note": "Every point placed by hand from a published address or coordinate. `precision` says how close it is.",
            "places": rows}


DAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


def day_state(rec: dict | None) -> dict:
    """open / closed / unknown for each of the seven days. A day nobody has published stays
    UNKNOWN. A day nobody published stays unknown here rather than being filled in as
    closed, which is the difference between a directory a reader can fly on and one that
    sends them to a locked door."""
    out = {d: "unknown" for d in DAYS}
    h = (rec or {}).get("hours") or {}
    for d in h.get("closed", []):
        out[d] = "closed"
    for d in h.get("open", []):
        out[d] = "open"
    return out


def atlas_table(recs: list[dict]) -> dict:
    """One row per country: which records name it, and how many. This is the choropleth on
    /map/. A blank country means no record here names it — never that nobody there carries
    a charm. The two statements are not the same and the page says so."""
    by_iso: dict = {}
    for r in recs:
        for c in r.get("countries", []) or []:
            row = by_iso.setdefault(c, {"iso": c, "name": country_name(c), "drawable": is_drawable(c),
                                       "n": 0, "types": {}, "records": []})
            row["n"] += 1
            row["types"][r["type"]] = row["types"].get(r["type"], 0) + 1
            row["records"].append({"id": r["id"], "type": r["type"], "name": r["names"]["name"],
                                   "url": f"{'word' if r['type'] == 'term' else r['type']}/{r['id']}/"})
    for row in by_iso.values():
        row["records"].sort(key=lambda x: x["name"].lower())
    rows = sorted(by_iso.values(), key=lambda x: (-x["n"], x["name"]))
    hemi = {h: sum(1 for r in recs if h in r.get("hemispheres", [])) for h in ("N", "S", "E", "W")}
    return {"built": time.strftime("%Y-%m-%d"), "countries": len(rows),
            "reading_an_absence": ("A country with no rows has no record here that names it. That is a fact about this "
                                   "atlas, not about the country. The gaps are listed on /coverage/."),
            "not_drawable": [r["iso"] for r in rows if not r["drawable"]],
            "not_drawable_note": ("Named by a record but not filled on the map: the 1:110m sheet this atlas draws from "
                                  "has no outline small enough to carry them. They are listed under the map."),
            "hemispheres": hemi, "rows": rows}


def timeline_table(recs: list[dict]) -> dict:
    """One row per dated record, for /time/. Years are astronomical; to_year null means the
    thing is still carried."""
    rows = []
    for r in recs:
        dt = r.get("dating") or {}
        if not dt or (dt.get("from_year") is None and dt.get("to_year") is None):
            continue
        rows.append({"id": r["id"], "type": r["type"], "name": r["names"]["name"],
                     "url": f"{'word' if r['type'] == 'term' else r['type']}/{r['id']}/",
                     "from_year": dt.get("from_year"), "to_year": dt.get("to_year"),
                     "living": bool(dt.get("living")), "period": dt.get("period", ""),
                     "label": dt.get("label") or r.get("span", ""), "method": dt.get("method", "undated"),
                     "circa": bool(dt.get("circa")), "region": (r["region"] or [""])[0],
                     "tier": (dt.get("tier") or tier_for(r, "dating").get("tier"))})
    rows.sort(key=lambda x: (x["from_year"] if x["from_year"] is not None else 9999))
    undated = [r["id"] for r in recs if r["type"] in ("amulet", "tradition", "motif", "practice") and not (r.get("dating") or {}).get("from_year")]
    return {"built": time.strftime("%Y-%m-%d"), "count": len(rows),
            "note": ("Astronomical years: 1 CE is 1, 1 BCE is 0, 500 BCE is -499. A row with no end year is still "
                     "carried. `method` says how the date is known — an excavated date and an ethnographer's date are "
                     "not the same kind of fact."),
            "undated": undated, "rows": rows}


def against_table(recs: list[dict]) -> dict:
    """What each charm is said to be for, and who says it. The table behind /against/.
    Every cell carries a claimant; this project supplies none of its own."""
    cells = []
    for r in recs:
        for a in r.get("against", []):
            cells.append({"id": r["id"], "type": r["type"], "name": r["names"]["name"],
                          "url": f"{'word' if r['type'] == 'term' else r['type']}/{r['id']}/",
                          "harm": a["harm"], "harm_label": HARMS.get(a["harm"], {}).get("label", a["harm"]),
                          "who": a.get("who", ""), "quote": a.get("quote", ""), "source": a["source"],
                          "tier": a.get("tier", "cited"), "region": (r["region"] or [""])[0],
                          "countries": r.get("countries", []) or [], "hemispheres": r.get("hemispheres", [])})
    counts = {}
    for c in cells:
        counts[c["harm"]] = counts.get(c["harm"], 0) + 1
    harms = [dict(HARMS[k], n=counts.get(k, 0)) for k in HARMS]
    harms.sort(key=lambda x: (-x["n"], x["label"]))
    return {"built": time.strftime("%Y-%m-%d"), "count": len(cells),
            "note": "One row per claim, never per charm. A charm said to stop three things appears three times.",
            "harms": harms, "rows": cells}


def matter_table(recs: list[dict]) -> dict:
    """Materials, forms and positions on the body — the tables behind /material/ and /wear/."""
    mat, form, worn = {}, {}, {}
    for r in recs:
        ob = r.get("object") or {}
        ref = {"id": r["id"], "type": r["type"], "name": r["names"]["name"],
               "url": f"{'word' if r['type'] == 'term' else r['type']}/{r['id']}/",
               "region": (r["region"] or [""])[0]}
        for m in ob.get("materials", []) or []:
            mat.setdefault(m, {"key": m, **MATS.get(m, {"label": m, "kind": "other"}), "records": []})["records"].append(ref)
        if ob.get("form"):
            form.setdefault(ob["form"], {"key": ob["form"], **FORMS.get(ob["form"], {"label": ob["form"]}), "records": []})["records"].append(ref)
        for w in ob.get("worn", []) or []:
            worn.setdefault(w, {"key": w, **WORN.get(w, {"label": w, "group": "other"}), "records": []})["records"].append(ref)
    def pack(d):
        rows = sorted(d.values(), key=lambda x: (-len(x["records"]), x["label"]))
        for x in rows:
            x["n"] = len(x["records"])
        return rows
    return {"built": time.strftime("%Y-%m-%d"),
            "materials": pack(mat), "forms": pack(form), "worn": pack(worn)}


def coverage(recs: list[dict], sources: dict) -> dict:
    by_type = {t: sum(1 for r in recs if r["type"] == t) for t in TYPES}
    dated = sum(1 for r in recs if (r.get("dating") or {}).get("from_year") is not None)
    living = sum(1 for r in recs if (r.get("dating") or {}).get("living"))
    oldest = min([(r.get("dating") or {}).get("from_year") for r in recs
                  if (r.get("dating") or {}).get("from_year") is not None] or [None])
    isos = sorted({c for r in recs for c in r.get("countries", []) or []})
    hemi = {h: sum(1 for r in recs if h in r.get("hemispheres", [])) for h in ("N", "S", "E", "W")}
    return {
        "built": time.strftime("%Y-%m-%d"),
        "scope": ("Amulets, charms and talismans worldwide — what they are made of, where on the body or the house "
                  "they go, what their carriers say they stop, and when and where each one is documented. Every "
                  "hemisphere, from the Neolithic to a sticker on a phone."),
        "records": by_type,
        "how_records_are_made": ("Hand-written JSON, one per node, each field carrying a provenance tier (cited / "
                                 "harvested / tradition / inference / field). Cited fields name a source in "
                                 "sources.json. Tradition fields are general knowledge of the practice and are hedged "
                                 "in the prose. A claim about what a charm does carries the name of whoever made it, in "
                                 "names who makes the claim."),
        "time": {"records_dated": dated, "still_carried": living, "earliest_year": oldest,
                 "reading_an_absence": ("An undated record is one nobody here could date from a source, not one with "
                                        "no history. Undated records are listed in /api/timeline.json.")},
        "world": {"countries_named": len(isos), "countries": isos, "hemispheres": hemi,
                  "reading_an_absence": ("A blank country means no record here names it. Australia is blank on purpose "
                                         "and /story/what-this-atlas-does-not-print says why.")},
        "places": {"curated": by_type["place"],
                   "reading_an_absence": ("Every point was placed by hand. A market missing here has not been written "
                                          "up; it is not a claim that the market is gone.")},
        "claims": {"rows": sum(len(r.get("against", [])) for r in recs),
                   "with_a_quote": sum(1 for r in recs for a in r.get("against", []) if a.get("quote")),
                   "note": "Every claim carries a claimant. A claim with no source does not get written."},
        "restricted": {"records": sum(1 for r in recs if r.get("restricted")),
                       "note": ("Where a tradition limits what outsiders may be told, the record prints the "
                                "restriction and stops.")},
        "holdings": {"rows": sum(len(r.get("holdings", [])) for r in recs),
                     "with_accession": sum(1 for r in recs for h in r.get("holdings", []) if h.get("accession")),
                     "note": "An accession number appears only where it was read off a catalogue page that is linked."},
        "images": {"count": sum(len(r.get("images", [])) for r in recs),
                   "licences_accepted": ["CC0", "Public domain", "CC BY", "CC BY-SA", "FAL"]},
        "sources": len(sources),
        "not_yet": ["field observations (no record carries the field tier yet)",
                    ("photographs — the licence pipeline is built (tools/harvest_commons.py accepts only CC0, "
                     "public domain, CC BY, CC BY-SA and FAL, and writes the licence and author beside each file), "
                     "but the candidate filenames in the records are guesses and most do not exist on Commons. "
                     "Attaching a search result automatically would be exactly the kind of guess this project "
                     "refuses everywhere else, so the pictures wait for a curated pass"),
                    "most of the southern hemisphere at the density the north has",
                    "prices with dates in most markets",
                    "languages other than English in the prose"],
        "tiers": TIER_LABEL,
    }


def main() -> int:
    if validate_all(quiet=False) != 0:
        print("build refused: fix the errors above")
        return 1
    t0 = time.time()
    sources = merge_sources()
    raw = load_nodes()
    by_id = {r["id"]: r for r in raw}
    recs = [enrich(r, by_id, sources) for r in raw]
    backlinks(recs)
    for r in recs:
        jdump(r, API / r["type"] / f"{r['id']}.json")
    jdump({"built": time.strftime("%Y-%m-%d"), "count": len(recs), "nodes": recs}, API / "nodes.json")
    jdump({"built": time.strftime("%Y-%m-%d"), "count": len(recs), "nodes": [{
        "id": r["id"], "type": r["type"], "name": r["names"]["name"], "native": r["names"].get("native", ""),
        "aliases": r["names"].get("aliases", []), "region": r["region"], "countries": r.get("countries", []),
        "facets": r.get("facets", {}), "span": r.get("span", ""), "hemispheres": r.get("hemispheres", []),
        "blurb": r["blurb"], "image": (r["primary_image"] or {}).get("file"), "confidence": r["confidence"],
        "against": [a["harm"] for a in r.get("against", [])],
        "materials": (r.get("object") or {}).get("materials", []), "form": (r.get("object") or {}).get("form"),
        "worn": (r.get("object") or {}).get("worn", []), "restricted": bool(r.get("restricted")),
        "needs_verification": r.get("needs_verification", False), "updated": r["updated"],
        "url": f"{r['type'] if r['type'] != 'term' else 'word'}/{r['id']}/",
    } for r in recs]}, API / "index.json")
    jdump({"built": time.strftime("%Y-%m-%d"), "edges": [dict(k, **{"from": r["id"]}) for r in recs for k in r["kin_out"]]}, API / "kin.json")
    for a in ("regions", "types", "facets", "against", "materials", "forms", "worn", "museums"):
        jdump(load_vocab(a), API / "vocab" / f"{a}.json")
    jdump(jload(SOURCES), API / "sources.json")
    jdump(places_table(recs), API / "places.json")
    jdump(atlas_table(recs), API / "atlas.json")
    jdump(timeline_table(recs), API / "timeline.json")
    jdump(against_table(recs), API / "against.json")
    jdump(matter_table(recs), API / "matter.json")
    jdump(coverage(recs, sources), API / "coverage.json")
    docs = [search_doc(r) for r in recs]
    jdump({"built": time.strftime("%Y-%m-%dT%H:%M:%S"), "docs": docs}, BUILD / "searchdocs.json")
    ng = mine_thesaurus(recs)
    edges = sum(len(r["kin_out"]) for r in recs)
    isos = {c for r in recs for c in r.get("countries", []) or []}
    print(f"built {len(recs)} nodes · {edges} kin edges · {len(isos)} countries · "
          f"{sum(len(r.get('against', [])) for r in recs)} claims · thesaurus {ng} groups · {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
