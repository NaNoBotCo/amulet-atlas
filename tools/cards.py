#!/usr/bin/env python3
"""cards.py — the picture that shows when a page is shared.

One 1200x630 card per record and per standing page, drawn with Pillow. Masters live in
`cards/` and are copied into the site by site.py, which points og:image at a card ONLY
when its file exists — an og:image that 404s unfurls worse than none at all.

Every card carries the same two things, because they are the two this atlas is for:

    where   the countries the record names, filled on an Equal Earth world at thumbnail
            size — the shape alone tells a reader whether this is one valley or four
            continents before they have read a word
    when    the span, drawn on the same warped axis /time/ uses, so a bar that starts at
            the left edge means the Bronze Age wherever you see it

A place record gets a dot rather than a fill. A record with neither countries nor dates
gets the panel left blank, which is the true statement about it.

    python3 tools/cards.py              # every card that is missing
    python3 tools/cards.py --all        # redraw everything
    python3 tools/cards.py amulet/nazar index map
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, ROOT, jload  # noqa: E402
import worldmap as W  # noqa: E402

CARDS = ROOT / "cards"
API = BUILD / "api"
WIDTH, HEIGHT = 1200, 630
PAD = 62
PANEL_X = 612

INK = (20, 23, 26)
INK_2 = (28, 32, 36)
CREAM = (238, 241, 238)
MUTE = (150, 157, 150)
CARN = (200, 74, 56)
CARN_HI = (232, 112, 92)
FAIENCE = (105, 189, 176)
GOLD = (215, 171, 85)
LINE = (52, 58, 62)
SEA = (24, 28, 32)
LAND = (44, 50, 54)

SERIF = "/System/Library/Fonts/Supplemental/Iowan Old Style.ttc"
SERIF_FALLBACK = "/System/Library/Fonts/Supplemental/Georgia.ttf"
SANS = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
SANS_R = "/System/Library/Fonts/Supplemental/Arial.ttf"

TYPE_LABEL = {"amulet": "AN AMULET", "tradition": "A TRADITION", "motif": "A SIGN",
              "material": "A MATERIAL", "practice": "A PRACTICE", "place": "A PLACE",
              "person": "A PERSON", "org": "A COLLECTION", "term": "A WORD",
              "art": "A PICTURE", "story": "A LONG READ"}
SITE_MARK = "AMULET ATLAS"


def font(path: str, size: int, index: int = 0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except OSError:
        try:
            return ImageFont.truetype(SERIF_FALLBACK, size)
        except OSError:
            return ImageFont.load_default()


def F_TITLE(sz):
    return font(SERIF, sz, index=1)


def F_BODY(sz):
    return font(SERIF, sz, index=0)


def F_SANS(sz):
    return font(SANS, sz)


def F_SANS_R(sz):
    return font(SANS_R, sz)


def fit_text(d, text: str, fnt_for, max_w: int, max_lines: int, start: int, floor: int):
    size = start
    while size >= floor:
        f = fnt_for(size)
        avg = d.textlength("n", font=f) or 1
        cols = max(8, int(max_w / avg * 1.05))
        lines = textwrap.wrap(text, width=cols) or [text]
        if len(lines) <= max_lines and all(d.textlength(x, font=f) <= max_w for x in lines):
            return f, lines
        size -= 3
    f = fnt_for(floor)
    avg = d.textlength("n", font=f) or 1
    cols = max(8, int(max_w / avg * 1.05))
    lines = (textwrap.wrap(text, width=cols) or [text])[:max_lines]
    last = lines[-1]
    while last and d.textlength(last + "…", font=f) > max_w:
        last = last[:-1]
    lines[-1] = last.rstrip(" ,;:—-") + "…"
    return f, lines


def draw_lines(d, x, y, lines, fnt, fill, leading=1.15):
    lh = int(fnt.size * leading)
    for i, line in enumerate(lines):
        d.text((x, y + i * lh), line, font=fnt, fill=fill)
    return y + len(lines) * lh


def tracked(d, x, y, text, fnt, fill, track=3):
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + track
    return x


def base_card(kind: str, title: str, sub: str = "", blurb: str = "", right_note: str = ""):
    im = Image.new("RGB", (WIDTH, HEIGHT), INK)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, WIDTH, 7], fill=CARN)
    d.rectangle([PANEL_X - 26, 0, WIDTH, HEIGHT], fill=INK_2)
    y = PAD + 6
    if kind:
        tracked(d, PAD, y, kind, F_SANS(19), GOLD, 3.4)
        y += 46
    f, lines = fit_text(d, title, F_TITLE, PANEL_X - PAD - 60, 3, 76, 34)
    y = draw_lines(d, PAD, y, lines, f, CREAM, 1.08) + 12
    if sub:
        f2, l2 = fit_text(d, sub, F_BODY, PANEL_X - PAD - 60, 2, 30, 20)
        y = draw_lines(d, PAD, y, l2, f2, FAIENCE) + 10
    if blurb:
        f3, l3 = fit_text(d, blurb, F_BODY, PANEL_X - PAD - 60, 4, 27, 18)
        draw_lines(d, PAD, y, l3, f3, MUTE, 1.3)
    d.line([PAD, HEIGHT - 84, PANEL_X - 70, HEIGHT - 84], fill=LINE, width=2)
    tracked(d, PAD, HEIGHT - 62, SITE_MARK, F_SANS(19), GOLD, 3.4)
    if right_note:
        fr = F_SANS_R(19)
        d.text((WIDTH - PAD - d.textlength(right_note, font=fr), HEIGHT - 62), right_note, font=fr, fill=MUTE)
    return im, d


_GEO = None


def geo():
    global _GEO
    if _GEO is None:
        _GEO = W.load()
    return _GEO


def panel_map(d, isos: set, dot=None, w=520):
    """The right-hand panel: an Equal Earth world with the record's countries filled."""
    fit = W.fit_world(w, pad=2.0)
    ox, oy = PANEL_X + 18, (HEIGHT - fit["h"]) / 2
    d.polygon([(ox + x, oy + y) for x, y in
               [(0, 0), (w, 0), (w, fit["h"]), (0, fit["h"])]], fill=SEA)
    for iso, _name, _path in []:
        pass
    for c in geo()["countries"]:
        fill = CARN if c["iso"] in isos else LAND
        for ring in c["rings"]:
            if len(ring) < 4:
                continue
            if max(p[1] for p in ring) < fit["clip_south"]:
                continue
            pts = [W.project(lon, max(lat, fit["clip_south"]), fit) for lon, lat in ring]
            d.polygon([(ox + x, oy + y) for x, y in pts], fill=fill, outline=SEA)
    if dot:
        x, y = W.project(dot[1], dot[0], fit)
        d.ellipse([ox + x - 11, oy + y - 11, ox + x + 11, oy + y + 11], outline=CARN_HI, width=3)
        d.ellipse([ox + x - 4, oy + y - 4, ox + x + 4, oy + y + 4], fill=CARN_HI)
    return oy + fit["h"]


ANCH = [(-11000, 0.0), (-3000, 0.14), (-1000, 0.28), (0, 0.40), (500, 0.48), (1000, 0.56),
        (1500, 0.66), (1800, 0.76), (1900, 0.84), (1950, 0.90), (2000, 0.96), (2026, 1.0)]


def _tx(y, x0, w):
    y = max(-11000, min(2026, y))
    for (a, fa), (b, fb) in zip(ANCH, ANCH[1:]):
        if a <= y <= b:
            t = 0 if b == a else (y - a) / (b - a)
            return x0 + (fa + t * (fb - fa)) * w
    return x0 + w


def panel_time(d, a, b, living: bool, y_at: float):
    """The span, on the same warped axis /time/ uses."""
    x0, w = PANEL_X + 30, 500
    y = min(HEIGHT - 96, y_at + 26)
    d.line([x0, y, x0 + w, y], fill=LINE, width=2)
    for yr, _f in ANCH[::2]:
        x = _tx(yr, x0, w)
        d.line([x, y - 5, x, y + 5], fill=LINE, width=2)
    if a is None and b is None:
        return
    xa = _tx(a if a is not None else b, x0, w)
    xb = _tx(b if b is not None else 2026, x0, w)
    d.line([xa, y - 16, max(xb, xa + 3), y - 16], fill=CARN_HI, width=9)
    if living or b is None:
        d.ellipse([max(xb, xa + 3) - 7, y - 23, max(xb, xa + 3) + 7, y - 9], fill=INK_2, outline=CARN_HI, width=3)
    f = F_SANS_R(17)
    d.text((x0, y + 12), "11000 BCE", font=f, fill=MUTE)
    t = "now"
    d.text((x0 + w - d.textlength(t, font=f), y + 12), t, font=f, fill=MUTE)


def year_label(y):
    if y is None:
        return "now"
    y = int(y)
    return f"{1 - y} BCE" if y <= 0 else f"{y} CE"


def record_card(r: dict) -> Image.Image:
    dt = r.get("dating") or {}
    sub = ""
    if r.get("span"):
        sub = r["span"] + (" · still carried" if dt.get("living") else "")
    elif r.get("region_terms"):
        sub = " · ".join(t.get("name", "") for t in r["region_terms"][:2])
    n = len(r.get("countries") or [])
    right = f"{n} countries" if n > 1 else (r["country_names"][0]["name"] if r.get("country_names") else "")
    im, d = base_card(TYPE_LABEL.get(r["type"], r["type"].upper()), r["names"]["name"], sub, r["blurb"], right)
    g = r.get("geo") or {}
    bottom = panel_map(d, set(r.get("countries") or []),
                       dot=(g["lat"], g["lon"]) if g and r["type"] == "place" else None)
    if dt.get("from_year") is not None or dt.get("to_year") is not None:
        panel_time(d, dt.get("from_year"), dt.get("to_year"), bool(dt.get("living")), bottom)
    return im


STANDING = {
    "index": ("AN ATLAS", "Amulet Atlas",
              "worn, buried, nailed above the door",
              "Every hemisphere, from a bead somebody drilled five thousand years ago to a sticker on a phone."),
    "map": ("THE MAP", "Every country the records name",
            "drawn in Equal Earth, not Mercator",
            "A square centimetre of Nigeria stands for the same square kilometres as a square centimetre of Norway."),
    "time": ("THE TIMELINE", "Five thousand years, one axis",
             "and the axis is not linear",
             "Every tick is printed, so you can see the stretching happen instead of being fooled by it."),
    "against": ("WHAT IT STOPS", "Reported, attributed, never tested",
                "the evil eye, a road, a court date, an exam",
                "Every claim here belongs to somebody, and the page says who."),
    "wear": ("WHERE IT GOES", "At the throat, over the door, in the grave",
             "half the positions are not on a body at all",
             "The same shape at the throat and in a grave is doing two different things, and the traditions say so."),
    "signs": ("THE SIGNS", "An eye, a hand, a horn, a knot",
              "drawn for this atlas, not traced",
              "The marks that turn up in places that never met — and which of those is transmission."),
    "materials": ("MATERIALS", "Carnelian, iron, amber, coral, paper, salt",
                  "what a charm is cut from is half of what it claims",
                  "Stone survives four thousand years. Paper does not. The museum drawer is a record of what lasts."),
    "numbers": ("NUMBERS", "The atlas measuring itself",
                "including the places it is thin",
                "Computed from the records at build time. None of it is typed in by hand."),
    "quiz": ("PICK ME ONE", "Six questions, and a charm",
             "with the arithmetic printed",
             "A lookup, not an oracle. The scoring runs in the page and is printed under the answer."),
    "search": ("SEARCH", "Spell it however you spell it",
               "nazar, nazar boncuğu, evil eye bead",
               "The index is in the page. The lookup runs in your browser."),
    "sources": ("SOURCES", "Where we got it",
                "a record may cite only an id on this page",
                "Which is how this atlas keeps from inventing a citation."),
    "coverage": ("WHERE WE STOP", "What this atlas does not cover",
                 "and which gaps are on purpose",
                 "A blank with a citation beats a full record built on a guess."),
    "places": ("PLACES", "Markets, workshops, shrines, dig sites",
               "and the museum rooms the rest of it ended up in",
               "Every point placed by hand. There is no open dataset of amulet stalls."),
    "amulets": ("AMULETS", "The things themselves", "worn, carried, placed, taken", ""),
    "traditions": ("TRADITIONS", "The practice a charm belongs to", "and who is entitled to make one", ""),
    "practices": ("PRACTICES", "A charm is a verb before it is a noun", "making, charging, wearing, retiring", ""),
    "people": ("PEOPLE", "Who made the categories", "collectors, excavators, the catalogue writers", ""),
    "organizations": ("COLLECTIONS", "Who holds the objects", "and who is asking for them back", ""),
    "words": ("WORDS", "Amulet, talisman, charm, ta'wiz", "and what each one actually says", ""),
    "art": ("PICTURES", "Plates, signs, votive walls", "", ""),
    "stories": ("LONG READS", "The eye across four continents", "and who a charm in a case belongs to", ""),
}


def standing_card(key: str, atlas: dict | None) -> Image.Image:
    kind, title, sub, blurb = STANDING[key]
    im, d = base_card(kind, title, sub, blurb, "")
    isos = {row["iso"] for row in (atlas or {}).get("rows", [])} if key in ("index", "map", "places") else set()
    if key == "index" or key == "map":
        panel_map(d, isos)
    elif key == "time":
        y = panel_map(d, set())
        panel_time(d, -2999, None, True, y - 120)
    else:
        panel_map(d, isos)
    return im


def main(argv) -> int:
    CARDS.mkdir(exist_ok=True)
    if not (API / "nodes.json").exists():
        print("run tools/build.py first")
        return 1
    recs = jload(API / "nodes.json")["nodes"]
    atlas = jload(API / "atlas.json") if (API / "atlas.json").exists() else None
    want = [a for a in argv if not a.startswith("-")]
    force = "--all" in argv
    drawn = 0
    for r in recs:
        key = r["id"]
        if want and key not in want and f'{r["type"]}/{r["id"]}' not in want:
            continue
        out = CARDS / f"{key}.jpg"
        if out.exists() and not force and not want:
            continue
        record_card(r).save(out, "JPEG", quality=86, optimize=True, progressive=True)
        drawn += 1
    for key in STANDING:
        if want and key not in want:
            continue
        out = CARDS / f"{key}.jpg"
        if out.exists() and not force and not want:
            continue
        standing_card(key, atlas).save(out, "JPEG", quality=86, optimize=True, progressive=True)
        drawn += 1
    print(f"cards: {drawn} drawn · {len(list(CARDS.glob('*.jpg')))} in {CARDS}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
