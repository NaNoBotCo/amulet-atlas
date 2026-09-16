#!/usr/bin/env python3
"""validate.py — every record must pass before anything is built.

Checks, in order:
  1. schema/node.schema.json (structure, enums, patterns)
  2. id == filename; type == folder; ids unique across all types
  3. kin targets and confusable_with targets exist
  4. every source id exists in data/sources/sources.json (record, etymology, provenance)
  5. region keys — WARN only (open list); facet values — WARN only (open list)
  6. every image licence is on the free-to-use allowlist and its file exists
  7. provenance.fields paths point at real fields
  8. banned words in reader-facing text (fleet rule) — ERROR
  9. against[] harms, object.form/materials/worn, holdings[].museum against their vocab
 10. an accession number without the catalogue URL it was read off — ERROR
 11. dating: from_year <= to_year, living implies to_year null, a to_year in the future

Exit 1 on any error. Warnings never fail the build; they are printed.

    python3 tools/validate.py            # all records
    python3 tools/validate.py --strict   # warnings fail too
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import IMAGES, SCHEMA, jload, load_nodes, load_sources, load_vocab, validate_record  # noqa: E402

THIS_YEAR = 2026

# Free-to-use licences. "No known copyright restrictions" is the Flickr Commons and
# Library of Congress rights statement: the holding institution has found no copyright
# and asks only that the item be credited. It is the same status under which the LoC
# material already reaches this project through Wikimedia Commons, so an item that
# carries it ON ITS OWN PAGE (per item, never per collection) is accepted here too.
FREE_LICENSES = re.compile(
    r"^(CC0(\s*1\.0)?|Public domain|PD(-[A-Za-z0-9-]+)?|CC[- ]BY(-SA)?(\s*[1-4]\.[0-9])?|FAL(\s*1\.[0-9])?"
    r"|No known copyright restrictions|NoC-US|United States Government Work)$", re.I)
# Words that never appear in reader-facing copy on any of Nan's sites, and the
# adjudicating words this subject attracts. Every one of them decides, on the reader's
# behalf, whether somebody else's practice is real. That is not this project's sentence
# to write. "Superstition" is a verdict; "a charm sold at the shrine gate" is a fact.
# A quotation in quotation marks is exempt — so quote and attribute instead of asserting.
DRAFT = bool(os.environ.get("BUILD_DRAFT"))
BANNED = re.compile(
    r"\b(superstiti\w+|primitive|savage(ry|s)?|witch[- ]doctors?|mumbo[- ]jumbo"
    r"|hocus[- ]?pocus|trinkets?|knick[- ]?knacks?|exotic(a|ally)?|authentic(ity|ally)?"
    r"|inauthentic|genuine article|the real thing|merely|mere(?= [a-z])|so[- ]called"
    r"|voodoo)\b"
    # "backward" only where it judges a people. A line of script written backwards is a
    # fact about the script.
    r"|\bbackwards?\s+(people|peoples|culture|cultures|society|societies|nation|nations|tribe|tribes|village|villages)\b", re.I)
# The efficacy tell: a sentence that says a charm DOES something, with nobody's name on it.
# Narrow on purpose. "The shape is said to be modelled on an eland horn" is a claim about a
# shape, not about an effect, and "is thought to have hung on the wall" is an archaeologist
# reading a floor plan — neither is the thing the house rule is guarding against. What is
# guarded against is "it is believed to protect against the evil eye", where no one is on
# the hook for the claim. So: a hedging verb, then a verb of effect, and no claimant named
# anywhere in the sentence.
_HEDGE = r"(?:is|are|was|were) (?:believed|said|thought|reputed|supposed|held) to"
_EFFECT = (r"(?:protect|ward|guard|shield|repel|drive|avert|keep|cure|heal|prevent|stop|"
           r"bring|grant|confer|ensure|attract|make \w+ invulnerable)")
UNATTRIBUTED = re.compile(_HEDGE + r"\s+(?:\w+\s+){0,2}" + _EFFECT, re.I)
# Anything in here counts as putting a name to it: a person, a people, a text, or the class
# of people who carry the thing.
ATTRIBUTED = re.compile(
    r"\b(wearers?|carriers?|owners?|users?|buyers?|sellers?|makers?|practitioners?|devotees?|"
    r"parents?|villagers?|informants?|the tradition|the text|the texts|the source|the sources|"
    r"tradition holds|according to|records?|reported|writes|wrote|says|said by|told|"
    r"ethnograph\w+|scholars?|the (?:Church|Talmud|Qur.an|Daozang|Vedas))\b", re.I)


# Proper nouns are exempt: a tradition is named what it is named. These are the only ones —
# "Louisiana Voodoo" is that religion's own English name, and the ban still applies to every
# other use of the two-o spelling.
PROPER_NOUNS = ("Louisiana Voodoo", "Voodoo in popular culture", "White Zombie",
                "London Voodoo", "The Magic Island")


def ban_clean(text: str) -> str:
    """The text a banned-word check should actually look at: quotations removed, because a
    speaker keeps their own words, and the handful of proper nouns removed too."""
    clean = re.sub(r'[\u201c"][^\u201d"]{0,240}[\u201d"]', "X", text or "")
    for noun in PROPER_NOUNS:
        clean = clean.replace(noun, "X")
    return clean


def _get(rec: dict, dotted: str):
    """Dotted path with optional list indices: text.story, kin[3].as, images[0].license."""
    node = rec
    for part in dotted.split("."):
        m = re.match(r"^([A-Za-z_]+)(?:\[(\d+)\])?$", part)
        if not m:
            return None
        key, idx = m.group(1), m.group(2)
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return None
        if idx is not None:
            if isinstance(node, list) and int(idx) < len(node):
                node = node[int(idx)]
            else:
                return None
    return node


def text_fields(rec: dict):
    for k, v in (rec.get("text") or {}).items():
        yield f"text.{k}", v
    for i, k in enumerate(rec.get("kin") or []):
        yield f"kin[{i}].as", k.get("as", "")
    for i, c in enumerate(rec.get("confusable_with") or []):
        yield f"confusable_with[{i}].tell", c.get("tell", "")
    e = rec.get("etymology") or {}
    for k in ("root", "note"):
        if e.get(k):
            yield f"etymology.{k}", e[k]
    for i, sec in enumerate(rec.get("sections") or []):
        yield f"sections[{i}].h", sec.get("h", "")
        yield f"sections[{i}].text", sec.get("text", "")
    for i, tg in enumerate(rec.get("tags") or []):
        yield f"tags[{i}].note", tg.get("note", "")
    h = rec.get("hours") or {}
    for k in ("text", "note", "seasonal"):
        if h.get(k):
            yield f"hours.{k}", h[k]
    for i, rg in enumerate(rec.get("recognitions") or []):
        yield f"recognitions[{i}].what", rg.get("what", "") + " " + rg.get("note", "")


def validate_all(strict=False, quiet=False) -> int:
    schema = jload(SCHEMA)
    recs = load_nodes()
    sources = load_sources()
    regions = {e["key"] for e in load_vocab("regions").get("entries", [])}
    facets = load_vocab("facets").get("facets", {})
    tagkeys = {e["key"] for e in load_vocab("tags").get("entries", [])}
    recog = {e["key"] for e in load_vocab("recognizers").get("entries", [])}
    harms = {e["key"] for e in load_vocab("against").get("entries", [])}
    mats = {e["key"] for e in load_vocab("materials").get("entries", [])}
    forms = {e["key"] for e in load_vocab("forms").get("entries", [])}
    worns = {e["key"] for e in load_vocab("worn").get("entries", [])}
    museums = {e["key"] for e in load_vocab("museums").get("entries", [])}
    countries = set()
    try:
        countries = {c["iso"] for c in jload(Path(__file__).resolve().parent.parent / "data" / "geo" / "world.json")["countries"]}
    except Exception:
        pass
    ids: dict[str, str] = {}
    errors: list[str] = []
    warns: list[str] = []
    for r in recs:
        tag = f"{r.get('type','?')}/{r.get('id','?')}"
        if r.get("id") in ids:
            errors.append(f"{tag}: duplicate id (also {ids[r['id']]})")
        ids[r.get("id", "")] = tag
    for r in recs:
        tag = f"{r['type']}/{r['id']}" if "type" in r and "id" in r else r["_path"]
        for e in validate_record(r, schema):
            errors.append(f"{tag}: {e}")
        if Path(r["_path"]).stem != r.get("id"):
            errors.append(f"{tag}: filename {Path(r['_path']).name} != id")
        if r.get("type") != r["_dir_type"]:
            errors.append(f"{tag}: type {r.get('type')!r} but the file sits in data/nodes/{r['_dir_type']}/")
        for k in r.get("kin", []):
            if k["to"] not in ids:
                # BUILD_DRAFT=1: an unwritten kin target is a warning, so the site can be
                # built while records are still being written. Never set it for a publish.
                (warns if DRAFT else errors).append(f"{tag}: kin target {k['to']} not found")
            if k["to"] == r.get("id"):
                errors.append(f"{tag}: kin points at itself")
        for c in r.get("confusable_with", []):
            if c["id"] not in ids:
                (warns if DRAFT else errors).append(f"{tag}: confusable_with {c['id']} not found")
        for s in r.get("sources", []):
            if s not in sources:
                errors.append(f"{tag}: source {s} not in sources.json")
        prov = r.get("provenance", {})
        for where, p in [("default", prov.get("default", {}))] + list(prov.get("fields", {}).items()):
            if p.get("source") and p["source"] not in sources:
                errors.append(f"{tag}: provenance {where} cites {p['source']} which is not in sources.json")
            if p.get("tier") == "cited" and not p.get("source") and not r.get("sources"):
                warns.append(f"{tag}: provenance {where} is 'cited' but names no source")
        et = r.get("etymology") or {}
        if et.get("source") and et["source"] not in sources:
            errors.append(f"{tag}: etymology cites {et['source']} which is not in sources.json")
        if r.get("type") == "term" and not et.get("root"):
            warns.append(f"{tag}: a word with no etymology.root")
        for reg in r.get("region", []):
            if reg not in regions:
                warns.append(f"{tag}: region {reg} not in regions.json (open list — add it there)")
        for fk, fv in (r.get("facets") or {}).items():
            spec = facets.get(fk)
            if not spec:
                warns.append(f"{tag}: facet {fk} not in facets.json (open list — add it there)")
                continue
            if r["type"] not in spec["types"]:
                warns.append(f"{tag}: facet {fk} is not listed for type {r['type']}")
            vals = fv if isinstance(fv, list) else [fv]
            for v in vals:
                if spec["values"] and v not in spec["values"]:
                    warns.append(f"{tag}: facet {fk}={v!r} not among known values")
        hrs = r.get("hours") or {}
        if hrs:
            if hrs.get("source") and hrs["source"] not in sources:
                errors.append(f"{tag}: hours.source {hrs['source']} not in sources.json")
            both = set(hrs.get("open", [])) & set(hrs.get("closed", []))
            if both:
                errors.append(f"{tag}: hours lists {sorted(both)} as both open and closed")
            if not hrs.get("open") and not hrs.get("closed"):
                warns.append(f"{tag}: hours names no day either way")
        for i, tg in enumerate(r.get("tags", [])):
            if tg["tag"] not in tagkeys:
                errors.append(f"{tag}: tags[{i}] {tg['tag']!r} not in tags.json")
            if tg["source"] not in sources:
                errors.append(f"{tag}: tags[{i}] source {tg['source']} not in sources.json")
            if tg.get("tier") in ("tradition", "inference"):
                errors.append(f"{tag}: tags[{i}] {tg['tag']} cannot be tier {tg['tier']} — ownership and welcome tags are cited, harvested or field")
        for i, rg in enumerate(r.get("recognitions", [])):
            if rg["by"] not in recog:
                errors.append(f"{tag}: recognitions[{i}] by {rg['by']!r} not in recognizers.json")
            if rg["source"] not in sources:
                errors.append(f"{tag}: recognitions[{i}] source {rg['source']} not in sources.json")
        for i, ag in enumerate(r.get("against", [])):
            if ag["harm"] not in harms:
                errors.append(f"{tag}: against[{i}] harm {ag['harm']!r} not in against.json")
            if ag["source"] not in sources:
                errors.append(f"{tag}: against[{i}] source {ag['source']} not in sources.json")
            if ag.get("quote") and not ag.get("who"):
                errors.append(f"{tag}: against[{i}] quotes somebody without naming them in `who`")
        ob = r.get("object") or {}
        if ob.get("source") and ob["source"] not in sources:
            errors.append(f"{tag}: object.source {ob['source']} not in sources.json")
        if ob.get("form") and ob["form"] not in forms:
            warns.append(f"{tag}: object.form {ob['form']!r} not in forms.json (open list — add it there)")
        for m in ob.get("materials", []) or []:
            if m not in mats:
                warns.append(f"{tag}: object.materials {m!r} not in materials.json (open list — add it there)")
        for wv in ob.get("worn", []) or []:
            if wv not in worns:
                warns.append(f"{tag}: object.worn {wv!r} not in worn.json (open list — add it there)")
        if ob.get("length_mm") is not None and not ob.get("source"):
            errors.append(f"{tag}: object.length_mm is a measurement with no source — cite it or drop it")
        for i, h in enumerate(r.get("holdings", [])):
            if h["museum"] not in museums:
                errors.append(f"{tag}: holdings[{i}] museum {h['museum']!r} not in museums.json")
            if h["source"] not in sources:
                errors.append(f"{tag}: holdings[{i}] source {h['source']} not in sources.json")
            if h.get("accession") and not h.get("url"):
                errors.append(f"{tag}: holdings[{i}] carries accession {h['accession']!r} with no catalogue URL — no URL, no accession")
        dt = r.get("dating") or {}
        if dt:
            if dt.get("source") and dt["source"] not in sources:
                errors.append(f"{tag}: dating.source {dt['source']} not in sources.json")
            a, b = dt.get("from_year"), dt.get("to_year")
            if a is not None and b is not None and a > b:
                errors.append(f"{tag}: dating from_year {a} is later than to_year {b}")
            if dt.get("living") and b is not None:
                errors.append(f"{tag}: dating.living is true but to_year is set — a living practice runs to null")
            if b is not None and b > THIS_YEAR:
                errors.append(f"{tag}: dating.to_year {b} is in the future")
            if a is None and b is None and not dt.get("period"):
                warns.append(f"{tag}: dating carries neither years nor a period name")
        elif r.get("type") in ("amulet", "tradition", "motif", "practice"):
            warns.append(f"{tag}: no dating (it will not appear on /time/)")
        for c in r.get("countries", []) or []:
            if countries and c not in countries:
                # Natural Earth at 1:110m has no outline for the small island states and
                # territories. The code is still right and the record should keep it —
                # common.TOO_SMALL_TO_DRAW carries the name and /map/ lists them under the
                # sheet. Anything NOT on that list is a typo.
                from common import TOO_SMALL_TO_DRAW
                if c in TOO_SMALL_TO_DRAW:
                    warns.append(f"{tag}: country {c} is named but too small to draw at 1:110m — keep it; /map/ lists it")
                else:
                    errors.append(f"{tag}: country {c} is not an ISO code this atlas knows — check it")
        if r.get("restricted"):
            if not (r["restricted"].get("who_says") or r["restricted"].get("source")):
                errors.append(f"{tag}: restricted says a tradition limits this, without naming who says so")
        for i, im in enumerate(r.get("images", [])):
            if not FREE_LICENSES.match(im["license"].strip()):
                errors.append(f"{tag}: images[{i}] licence {im['license']!r} is not on the free-to-use allowlist")
            if not (IMAGES / im["file"]).exists():
                warns.append(f"{tag}: images[{i}] file missing: {im['file']}")
        for path in prov.get("fields", {}):
            if _get(r, path) is None:
                warns.append(f"{tag}: provenance.fields.{path} names a field the record does not have")
        for fname, txt in text_fields(r):
            # the proper noun is exempt: an organization is named what it is named
            clean = ban_clean(txt)
            m = BANNED.search(clean)
            if m:
                errors.append(f"{tag}: {fname} uses the banned word {m.group(0)!r}")
            if fname.startswith("text."):
                for sent in re.split(r"(?<=[.!?])\s+", clean):
                    u = UNATTRIBUTED.search(sent)
                    if u and not ATTRIBUTED.search(sent) and not re.search(r"\b[A-Z][a-z]{3,}", sent[2:]):
                        warns.append(f"{tag}: {fname} says {u.group(0)!r} with nobody named — say who says it")
                        break
        if r.get("type") == "place" and not r.get("geo"):
            warns.append(f"{tag}: no geo (map will not show it)")
        if not r.get("sources") and prov.get("default", {}).get("tier") in ("cited", "harvested"):
            warns.append(f"{tag}: tier {prov['default']['tier']} but sources is empty")
    if not quiet:
        for w in warns:
            print("warn ", w)
        for e in errors:
            print("ERROR", e)
        print(f"{len(recs)} records · {len(errors)} errors · {len(warns)} warnings")
    if errors or (strict and warns):
        return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    sys.exit(validate_all(ap.parse_args().strict))
