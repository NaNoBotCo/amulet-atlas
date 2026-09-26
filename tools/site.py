#!/usr/bin/env python3
"""site.py — build/api → build/site: a static site people and bots can both read.

People: a directory front page that shows its own hierarchy, one page per node with its kin
said in both directions, an Equal Earth world map, a deep timeline on a stated non-linear
axis, the signs drawn rather than photographed, large type, high contrast, theme-aware, no
external requests of any kind.

Bots: JSON-LD on every page, robots.txt that ALLOWS everything and says so, sitemap.xml
with lastmod, llms.txt and llms-full.txt, an Atom feed, OpenSearch, CSV + JSONL dumps, and
the whole /api tree.

    python3 tools/site.py
    SITE_URL=https://example.org python3 tools/site.py
"""
from __future__ import annotations

import csv
import html
import json
import os

import fleet
import random
import re
import shutil
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, DATA, IMAGES, ROOT, SEARCH_CORE, TIER_LABEL, TYPES, VENDOR, jload  # noqa: E402
import pages  # noqa: E402
import viz  # noqa: E402
import worldmap  # noqa: E402

SITE = BUILD / "site"
API = BUILD / "api"
CARDS_DIR = ROOT / "cards"
SITE_URL = os.environ.get("SITE_URL", "https://nanobotco.github.io/amulet-atlas").rstrip("/")
SITE_NAME = "Amulet Atlas"
TAGLINE = "worn, buried, nailed above the door — and what each one is meant to stop"
DATA_LICENSE = "https://creativecommons.org/licenses/by/4.0/"
AUTHOR = {"@type": "Person", "name": "NaN", "url": "https://wichaa.net"}

PATH_OF = {"amulet": "amulet", "tradition": "tradition", "motif": "sign", "material": "material",
           "practice": "practice", "place": "place", "person": "person", "org": "org",
           "term": "word", "art": "art", "story": "story"}
DIR_OF = {"amulet": "amulets", "tradition": "traditions", "motif": "signs", "material": "materials",
          "practice": "practices", "place": "places", "person": "people", "org": "organizations",
          "term": "words", "art": "art", "story": "stories"}


def E(x) -> str:
    """html.escape, but a null field is a blank rather than a crash — a field is null here
    when nobody published the thing, which is a state this site prints."""
    return html.escape("" if x is None else str(x))


def clip(text: str, n: int) -> str:
    t = (text or "").strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def rel(depth: int) -> str:
    return "../" * depth


def url_of(r: dict) -> str:
    return f"{PATH_OF[r['type']]}/{r['id']}/"


# The build tables (timeline, atlas, against, matter, places) name a record by its type —
# "motif/<id>/" — and the site files it under PATH_OF, from wherever the page sits.
SEG_PATH = {("word" if k == "term" else k): v for k, v in PATH_OF.items()}


def table_href(url: str, depth: int) -> str:
    seg, _, rest = url.partition("/")
    return f"{rel(depth)}{SEG_PATH.get(seg, seg)}/{rest}index.html"


def time_rows(rows: list, depth: int) -> list:
    return [dict(r, url=table_href(r["url"], depth)) if r.get("url") else r for r in rows]


# Materials with a record of their own. The rest are only counted, on /materials/ (#m-<key>).
MATERIAL_PAGES = {f.stem for f in (DATA / "nodes" / "material").glob("*.json")}


def material_href(key: str) -> str:
    """From a record page, two levels down."""
    return (f"../../material/{key}/index.html" if key in MATERIAL_PAGES
            else f"../../materials/index.html#m-{key}")


def img_src(im: dict, depth: int) -> str:
    return f"{rel(depth)}images/{im['file']}"


def year_label(y) -> str:
    if y is None:
        return "now"
    y = int(y)
    return f"{1 - y} BCE" if y <= 0 else f"{y} CE"


CSS = """
:root{--bg:#f6f3ec;--panel:#fffdf7;--ink:#1d2321;--mute:#6b6a60;--line:#e2ddcf;--carn:#b23a2b;
  --faience:#2b7268;--faience-l:#71b8ab;--gold:#9d7320;--indigo:#31456b;--deep:#1a4b46;
  --focus:#1f5fa8;--chip:#efe9dc;
  /* An atlas letters its plates. Headings take a cut with real serifs so a date reads as a
     date; labels take a narrow sans the way a museum card does; the reading text stays a
     plain humanist sans. All of it is already on the reader's machine. */
  --display:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  --label:"Avenir Next Condensed","HelveticaNeue-CondensedBold","Arial Narrow",Helvetica,sans-serif;
  --body:"Avenir Next",Avenir,"Segoe UI",system-ui,-apple-system,Helvetica,Arial,sans-serif;
  --ui:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#14171a;--panel:#1c2024;--ink:#eef1ee;--mute:#a8ada6;--line:#2e3337;--carn:#e8705c;--faience:#69bdb0;--faience-l:#8fd2c6;--gold:#d7ab55;--indigo:#8fa8d4;--deep:#9fd6cc;--focus:#8ab4f8;--chip:#242a2e}}
:root[data-theme="dark"]{--bg:#14171a;--panel:#1c2024;--ink:#eef1ee;--mute:#a8ada6;--line:#2e3337;--carn:#e8705c;--faience:#69bdb0;--faience-l:#8fd2c6;--gold:#d7ab55;--indigo:#8fa8d4;--deep:#9fd6cc;--focus:#8ab4f8;--chip:#242a2e}
*{box-sizing:border-box}html{font-size:19px;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);line-height:1.62;font-size:1.02rem}
a{color:var(--carn);text-decoration-thickness:.07em;text-underline-offset:.16em}a:hover{color:var(--deep)}
a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:4px}
header.top{border-bottom:1px solid var(--line);padding:.7rem 1rem;max-width:72rem;margin:0 auto;display:flex;gap:.6rem 1.2rem;flex-wrap:wrap;align-items:baseline}
header.top .brand{font-family:var(--display);font-weight:700;font-size:1.12rem;text-decoration:none;color:var(--ink)}header.top .brand b{color:var(--carn)}
nav.crumbs{font-size:.83rem;color:var(--mute);font-family:var(--ui)}nav.crumbs a{text-decoration:none}nav.crumbs a:hover{text-decoration:underline}
main{max-width:72rem;margin:0 auto;padding:1.2rem 1rem 4rem}
h1{font-family:var(--display);font-size:clamp(2rem,4.4vw,2.95rem);line-height:1.1;margin:.5rem 0 .3rem;font-weight:700}
h1 .kind{display:block;font-size:.74rem;color:var(--gold);text-transform:uppercase;letter-spacing:.22em;font-family:var(--label);margin-bottom:.5rem}
h1 .native{display:block;font-size:.5em;color:var(--mute);font-weight:400;margin-top:.25rem}
h2{font-family:var(--display);font-size:1.38rem;margin:1.9rem 0 .5rem;border-bottom:2px solid var(--line);padding-bottom:.25rem;font-weight:700}
h3{font-family:var(--display);font-size:1.08rem;margin:1rem 0 .3rem;font-weight:700}
.said{font-style:italic;color:var(--mute);margin:.2rem 0 .8rem}.lede{font-size:1.13rem;margin:.2rem 0 1rem}.mute{color:var(--mute)}
p{margin:.55rem 0}.prose p{margin:.75rem 0}
.dir{display:grid;grid-template-columns:repeat(auto-fill,minmax(19rem,1fr));gap:1.3rem 2.4rem;align-items:start;margin-top:.8rem}
.dir section{margin:0}.dir h2{margin:.2rem 0 .3rem;border:0;font-size:1.16rem}
.dir h2 a{text-decoration:none;color:var(--ink)}.dir h2 a:hover{color:var(--carn)}
.dir ul{list-style:none;margin:0;padding:0 0 0 .7rem;border-left:2px solid var(--line)}
.dir li{margin:.14rem 0}.dir li.sub{padding-left:.9rem;font-size:.95rem}
.count{color:var(--mute);font-size:.85em;font-family:var(--ui)}
.chip{display:inline-block;background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:.05rem .62rem;font-size:.78rem;margin:.1rem .25rem .1rem 0;color:var(--ink);font-family:var(--ui)}
a.chip{text-decoration:none}a.chip:hover{border-color:var(--carn)}
.tier-cited{border-color:var(--focus)}.tier-harvested{border-color:var(--faience)}.tier-tradition{border-color:var(--gold)}.tier-inference{border-style:dashed}.tier-field{border-color:var(--carn)}
table{border-collapse:collapse;width:100%;margin:.4rem 0 1rem;font-size:.95rem}
th,td{text-align:left;vertical-align:top;padding:.45rem .5rem;border-bottom:1px solid var(--line)}
th{width:26%;color:var(--mute);font-weight:600}
.kin{display:grid;grid-template-columns:repeat(auto-fill,minmax(17rem,1fr));gap:.9rem}
.kin a.card{display:block;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.8rem .95rem;text-decoration:none;color:var(--ink)}
.kin a.card b{display:block;font-size:1.03rem;color:var(--carn);font-family:var(--display);font-weight:700}
.kin a.card small{display:block;font-size:.68rem;color:var(--gold);text-transform:uppercase;letter-spacing:.18em;font-family:var(--label)}
.kin a.card span{display:block;margin-top:.3rem;font-size:.92rem;color:var(--ink)}
.kin a.card:hover b{color:var(--deep)}
figure{margin:0 0 1rem;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.6rem}
figure img{width:100%;height:auto;max-height:32rem;object-fit:contain;border-radius:8px;display:block}
figcaption{font-size:.8rem;color:var(--mute);margin-top:.4rem;font-family:var(--ui)}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(12rem,1fr));gap:.7rem}.gallery figure{margin:0}
.hero{display:grid;grid-template-columns:1fr;gap:.6rem;margin:.6rem 0 1.2rem}
.hero h1{font-size:clamp(2.4rem,6.4vw,4rem);letter-spacing:-.012em;margin-bottom:.1rem}
.hero .sub{font-size:1.16rem;color:var(--mute);font-style:italic;max-width:42rem}
.mapwrap{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:.6rem}
.mapwrap svg{width:100%;height:auto;display:block}
.worldmap .cty.has{cursor:pointer}
.worldmap .cty.has:hover{fill:var(--carn)}
.legend{font-size:.82rem;color:var(--mute);margin:.5rem 0 0;font-family:var(--ui);display:flex;flex-wrap:wrap;gap:.25rem .5rem;align-items:center}
.legend .sw{display:inline-block;width:1.15rem;height:.72rem;border:1px solid var(--line);border-radius:2px}
.legend .lb{margin-right:.5rem}.legend .unit{font-style:italic}
.facts{display:flex;flex-wrap:wrap;gap:.8rem;margin:.7rem 0 1.2rem}
.fact{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.7rem 1rem;min-width:8rem;text-align:center}
.fact .n{display:block;font-family:var(--display);font-size:2rem;font-weight:700;line-height:1}
.fact .l{display:block;font-size:.72rem;color:var(--mute);margin-top:.28rem;font-family:var(--label);text-transform:uppercase;letter-spacing:.11em}
.search{display:flex;gap:.5rem;margin:.6rem 0 1rem}
.search input{flex:1;font:inherit;font-size:1.1rem;padding:.6rem .8rem;border:2px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)}
.search button{font:inherit;padding:.6rem 1rem;border-radius:10px;border:2px solid var(--carn);background:var(--carn);color:#fff;cursor:pointer}
.tierline{font-size:.9rem;color:var(--mute);margin:.2rem 0 .8rem}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(15rem,1fr));gap:1rem;align-items:start}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.9rem}
.card a.t{font-family:var(--display);font-weight:700;text-decoration:none;font-size:1.06rem}
.card p{margin:.3rem 0 0;font-size:.9rem;color:var(--mute)}
.card .thumb{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:9px;margin-bottom:.55rem;display:block;background:var(--chip)}
footer{max-width:72rem;margin:0 auto;padding:1rem;color:var(--mute);font-size:.85rem;border-top:1px solid var(--line);font-family:var(--ui)}
.bots a{margin-right:.7rem}.support{margin:.45rem 0 0}.support a{margin-right:.5rem}.fleet{margin:.6rem 0 0;line-height:1.9}.fleet a{margin-right:.55rem;white-space:nowrap}
.btn{display:inline-block;padding:.55rem 1.05rem;border-radius:999px;background:var(--carn);color:#fff;text-decoration:none;font-weight:700;border:2px solid var(--carn);font-family:var(--label);font-size:.95rem;letter-spacing:.03em}
.btn.ghost{background:transparent;color:var(--ink);border-color:var(--line)}
.btn:hover{color:#fff;filter:brightness(1.08)}.btn.ghost:hover{color:var(--ink);border-color:var(--carn)}
.cta{display:flex;gap:.6rem;flex-wrap:wrap;margin:.9rem 0}
.etym{background:var(--panel);border-left:4px solid var(--gold);border-radius:0 12px 12px 0;padding:.7rem 1rem;margin:.8rem 0}
.restricted{background:var(--panel);border-left:4px solid var(--carn);border-radius:0 12px 12px 0;padding:.8rem 1rem;margin:1rem 0}
.restricted b{font-family:var(--label);text-transform:uppercase;letter-spacing:.14em;font-size:.76rem;color:var(--carn);display:block;margin-bottom:.3rem}
.whenbox{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:.9rem 1rem;margin:.4rem 0 1rem}
.spanline{font-family:var(--display);font-size:1.5rem;margin:.1rem 0 .2rem}
.spanline .liv{color:var(--carn)}
.against{list-style:none;margin:.4rem 0;padding:0;display:grid;gap:.5rem}
.against li{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.6rem .85rem}
.against b{font-family:var(--display)}
.against .who{color:var(--mute);font-size:.88rem;display:block}
.against blockquote{margin:.35rem 0 0;padding-left:.7rem;border-left:3px solid var(--gold);font-style:italic}
.two-up{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem;margin:1.4rem 0}
@media(max-width:760px){.two-up{grid-template-columns:1fr}html{font-size:18px}}
.mults{display:grid;grid-template-columns:repeat(auto-fill,minmax(13rem,1fr));gap:.7rem;margin:.8rem 0}
.mults figure{margin:0;padding:.4rem}.mults svg{width:100%;height:auto;display:block}
.mults figcaption{font-size:.8rem;margin-top:.25rem}.mults .n{color:var(--carn);font-weight:700}
.timechart,.density,.bars,.matrix,.bodymap{width:100%;height:auto;display:block}
.timechart .rl,.bars .rl,.matrix .rl{font:500 11px var(--ui);fill:currentColor}
.timechart .tk,.density .tk{font:600 10px var(--label);fill:currentColor;opacity:.7}
.matrix .cl{font:600 10px var(--ui);fill:currentColor}
.bars .vn{font:700 11px var(--ui);fill:currentColor}
.timechart .trow:hover .rl{fill:var(--carn)}
.glyph{color:var(--ink);vertical-align:middle}
.glyphgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(8.5rem,1fr));gap:.7rem;margin:1rem 0}
.glyphgrid a{display:flex;flex-direction:column;align-items:center;gap:.35rem;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.8rem .5rem;text-decoration:none;color:var(--ink);text-align:center}
.glyphgrid a:hover{border-color:var(--carn);color:var(--carn)}
.glyphgrid .nm{font-family:var(--display);font-size:.96rem}
.glyphgrid .ct{font-size:.74rem;color:var(--mute);font-family:var(--ui)}
.bodymap .spot{cursor:pointer}.bodymap .spot:hover{fill-opacity:1}
.wearlist{display:grid;grid-template-columns:repeat(auto-fill,minmax(16rem,1fr));gap:1rem}
.wearlist section{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.8rem .95rem}
.wearlist h3{margin:.1rem 0 .3rem}
.wearlist ul{margin:.2rem 0 0;padding-left:1.1rem;font-size:.93rem}
.tdot{display:inline-block;width:.55rem;height:.55rem;border-radius:50%;margin-right:.3rem;vertical-align:baseline}
.pl-list{columns:2;column-gap:2.4rem;font-size:.95rem}.pl-list h3{break-after:avoid;margin:.6rem 0 .2rem}
.pl-list ul{margin:0 0 .5rem;padding-left:1rem}@media(max-width:700px){.pl-list{columns:1}}
mark.tier{background:transparent;color:var(--mute);font-style:italic}
.sect{margin:1.3rem 0}
.wander{font-size:.85rem}
.quiz fieldset{border:1px solid var(--line);border-radius:12px;background:var(--panel);margin:0 0 1rem;padding:.8rem 1rem}
.quiz legend{font-family:var(--display);font-weight:700;padding:0 .4rem}
.quiz label{display:block;margin:.28rem 0;cursor:pointer}
@media (prefers-reduced-motion: no-preference){
  .kin a.card,.card,.fact,.glyphgrid a{transition:transform .18s ease,box-shadow .18s ease}
  .kin a.card:hover,.card:hover,.glyphgrid a:hover{transform:translateY(-3px);box-shadow:0 10px 24px rgba(0,0,0,.09)}
  .btn{transition:transform .15s ease}.btn:hover{transform:scale(1.04)}
  .search input{transition:box-shadow .2s}.search input:focus{box-shadow:0 0 0 4px color-mix(in srgb,var(--carn) 22%,transparent)}}
"""

SHARE_CSS = """
.shareme{margin:2.6rem 0 .4rem;padding:1rem 1.1rem;background:var(--panel);border:1px solid var(--line);border-radius:14px}
.shareme b{display:block;font-size:.95rem;margin-bottom:.55rem}
.shareme .row{display:flex;flex-wrap:wrap;gap:.45rem}
.shareme a,.shareme button{font:inherit;font-size:.87rem;font-family:var(--ui);padding:.4rem .85rem;border-radius:999px;
  border:1.5px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:.35rem}
.shareme a:hover,.shareme button:hover{border-color:var(--carn);color:var(--carn)}
.shareme .said{font-size:.85rem;color:var(--mute);margin-left:.4rem}
.shareme .copy{border-color:var(--carn);color:#fff;background:var(--carn)}
.shareme .copy:hover{color:#fff;filter:brightness(1.08)}
"""


def share_row(url: str, title: str) -> str:
    u, t = urllib.parse.quote(url, safe=""), urllib.parse.quote(title)
    links = [("Bluesky", f"https://bsky.app/intent/compose?text={t}%20{u}"),
             ("Mastodon", f"https://mastodonshare.com/?text={t}&url={u}"),
             ("Reddit", f"https://www.reddit.com/submit?url={u}&title={t}"),
             ("WhatsApp", f"https://api.whatsapp.com/send?text={t}%20{u}"),
             ("Email", f"mailto:?subject={t}&body={u}")]
    btns = "".join(f'<a href="{E(href)}" target="_blank" rel="noopener">{E(L(name, "อีเมล") if name == "Email" else name)}</a>'
                   for name, href in links)
    return (f'<section class="shareme" data-url="{E(url)}" data-title="{E(title)}">'
            f'<b>{L("Pass it on", "ส่งต่อ")}</b><div class="row">'
            f'<button type="button" class="copy" data-sh="copy">{L("Copy link", "คัดลอกลิงก์")}</button>'
            f'<button type="button" data-sh="native" hidden>{L("Share…", "แชร์…")}</button>{btns}'
            f'<span class="said" aria-live="polite"></span></div></section>'
            '<script>(function(){var s=document.currentScript.previousElementSibling;'
            'var n=s.querySelector(\'[data-sh="native"]\');if(navigator.share)n.hidden=false;'
            's.addEventListener("click",function(e){var b=e.target.closest("[data-sh]");if(!b)return;'
            'var url=s.dataset.url,title=s.dataset.title,said=s.querySelector(".said");'
            'if(b.dataset.sh==="copy"){(navigator.clipboard?navigator.clipboard.writeText(url):Promise.reject())'
            f'.then(function(){{said.textContent="{L("copied", "คัดลอกแล้ว")}"}},function(){{said.textContent=url}});}}'
            'else if(b.dataset.sh==="native"){navigator.share({title:title,url:url}).catch(function(){})}});})();</script>')


NAV = [("index.html", "Everything"), ("map/index.html", "The map"), ("time/index.html", "The timeline"),
       ("against/index.html", "What it stops"), ("wear/index.html", "Where it goes"),
       ("signs/index.html", "The signs"), ("materials/index.html", "Materials"),
       ("places/index.html", "Places"), ("stories/index.html", "Long reads"),
       ("numbers/index.html", "Numbers"), ("quiz/index.html", "Pick me one"),
       ("search/index.html", "Search"), ("words/index.html", "Words"),
       ("sources/index.html", "Where we got it"), ("coverage/index.html", "Where we stop"),
       ("api/index.json", "API"), ("llms.txt", "llms.txt")]
NAV_TH = {"Everything": "ทั้งหมด", "The map": "แผนที่", "The timeline": "เส้นเวลา", "What it stops": "กันอะไร",
          "Where it goes": "อยู่ตรงไหน", "The signs": "สัญลักษณ์", "Materials": "วัสดุ", "Places": "สถานที่",
          "Long reads": "เรื่องยาว", "Numbers": "ตัวเลข", "Pick me one": "เลือกให้หน่อย", "Search": "ค้นหา",
          "Words": "ถ้อยคำ", "Where we got it": "แหล่งที่มา", "Where we stop": "ขอบเขต"}

# ------------------------------------------------------------------ the Thai edition
# The same pages under /th/, from the same records. A record's Thai lives beside its English
# (names.th, text_th, kin[].as_th); vocabulary labels in data/vocab/th.json. Where a section
# has no Thai yet, the English prints under a one-line Thai note, marked lang="en".
LANG = "en"
TH = jload(DATA / "vocab" / "th.json")
SITE_NAME_TH = "แอตลาสเครื่องราง"
TAGLINE_TH = "สวมใส่ ฝังดิน ตอกไว้เหนือประตู และแต่ละชิ้นมีไว้กันอะไร"
# pages that exist in English only for now; a Thai page links across to them
EN_ONLY = ("map/", "time/", "against/", "wear/", "signs/", "materials/", "numbers/", "quiz/",
           "search/", "sources/", "coverage/")
ROOT_FILES = ("images/", "api/", "vendor/", "cards/", "schema/", "icon.svg", "manifest.webmanifest",
              "opensearch.xml", "feed.xml", "llms.txt", "llms-full.txt", "sitemap.xml", "nodes.")
NO_TH = "ส่วนนี้ยังไม่ได้เขียนเป็นภาษาไทย ด้านล่างเป็นภาษาอังกฤษ"
TIER_TH = {"cited": "อ้างอิง", "harvested": "รวบรวม", "tradition": "ตามคติ", "inference": "ข้อสันนิษฐาน", "field": "ภาคสนาม"}


def L(en: str, th: str) -> str:
    return th if LANG == "th" else en


def th_label(table: str, key, en: str) -> str:
    """A vocabulary label in the page's language."""
    if LANG != "th":
        return en
    v = TH.get(table, {}).get(key)
    return (v.get("name") if isinstance(v, dict) else v) or en


def rname(r: dict) -> str:
    return (r["names"].get("th") if LANG == "th" else "") or r["names"]["name"]


def tblurb(r: dict, n=220) -> str:
    """The blurb in the page's language: the Thai `what`, cut at a space."""
    w = (r.get("text_th") or {}).get("what", "").strip() if LANG == "th" else ""
    if not w:
        return r["blurb"]
    if len(w) <= n:
        return w
    return w[:n].rsplit(" ", 1)[0] + "…"


def ttext(r: dict, key: str) -> str:
    """A text section as HTML in the page's language, with the English fallback marked."""
    if LANG == "th":
        th = (r.get("text_th") or {}).get(key)
        if th:
            return prose(th)
        en = r["text"].get(key)
        return f'<p class="mute no-th">{NO_TH}</p><div lang="en">{prose(en)}</div>' if en else ""
    return prose(r["text"].get(key))


def tf(r: dict, path: str, en) -> str:
    """A short structured field as HTML: its Thai from th_fields on a Thai page, else the English."""
    th = (r.get("th_fields") or {}).get(path) if LANG == "th" else None
    return E(th) if th else en_span(E(en))


def en_span(x: str) -> str:
    """English content on a Thai page, tagged so a screen reader switches voice."""
    return f'<span lang="en">{x}</span>' if LANG == "th" and x else x


def year_th(y) -> str:
    if y is None:
        return "ปัจจุบัน"
    y = int(y)
    return f"ก่อน ค.ศ. {1 - y}" if y <= 0 else f"ค.ศ. {y}"


def span_th(r: dict) -> str:
    dt = r.get("dating") or {}
    if dt.get("from_year") is None and dt.get("to_year") is None:
        return r.get("span") or ""
    a = year_th(dt.get("from_year")) if dt.get("from_year") is not None else ""
    b = "ปัจจุบัน" if dt.get("living") or dt.get("to_year") is None else year_th(dt["to_year"])
    return ("ราว " if dt.get("circa") else "") + (f"{a} – {b}" if a else b)


def tspan(r: dict) -> str:
    return span_th(r) if LANG == "th" else r.get("span") or ""


def localize(html_text: str, path: str) -> str:
    """A page rendered for /th/<path>: links to the site's shared files and to the pages that
    exist in English only climb one level more, out of /th/."""
    def fix(m):
        attr, q, url = m.group(1), m.group(2), m.group(3)
        if re.match(r"^(?:[a-z]+:|#|/|data:)", url):
            return m.group(0)
        bare = re.sub(r"^(?:\.\./)*", "", url)
        if bare.startswith(ROOT_FILES) or bare.startswith(EN_ONLY):
            return f'{attr}={q}../{url}{q}'
        return m.group(0)
    return re.sub(r'\b(href|src)=(["\'])([^"\']*)\2', fix, html_text)


def has_th(path: str) -> bool:
    return not path.startswith(EN_ONLY) and not path.startswith(("api/", "llms"))


def page(title: str, body: str, depth: int, desc: str = "", jsonld: list | None = None,
         canonical: str = "", extra_head: str = "", og_image: str = "", alt_json: str = "",
         og_alt: str = "", og_type: str = "website", card: str = "", share_title: str = "") -> str:
    r = rel(depth)
    th = LANG == "th"
    if card and (CARDS_DIR / f"{card}.jpg").exists():
        og_image = f"{SITE_URL}/cards/{card}.jpg"
    path = canonical[len(SITE_URL) + 1:] if canonical.startswith(SITE_URL + "/") else ""
    if th and canonical:
        canonical = f"{SITE_URL}/th/{path}"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(o, ensure_ascii=False)}</script>' for o in (jsonld or []))
    if th:
        nav = " · ".join(f'<a href="{r}{h}"{"" if has_th(h) else " lang=en"}>{E(NAV_TH.get(lab, lab))}'
                         f'{"" if has_th(h) or h.startswith(("api/", "llms")) else "<sup> EN</sup>"}</a>' for h, lab in NAV)
    else:
        nav = " · ".join(f'<a href="{r}{h}">{E(lab)}</a>' for h, lab in NAV)
    both = canonical and has_th(path)
    if both:
        other = (f'<a href="{r}../{path}index.html" lang="en" hreflang="en">English</a>' if th
                 else f'<a href="{r}th/{path}index.html" lang="th" hreflang="th">ไทย</a>')
        nav += " · " + other
    alts = (f'<link rel="alternate" hreflang="en" href="{SITE_URL}/{path}"><link rel="alternate" hreflang="th" href="{SITE_URL}/th/{path}">'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/{path}">') if both else ""
    og = ""
    if og_image:
        og = (f'<meta property="og:image" content="{E(og_image)}"><meta property="og:image:width" content="1200">'
              f'<meta property="og:image:height" content="630"><meta property="og:image:type" content="image/jpeg">'
              f'<meta property="og:image:alt" content="{E(og_alt or title)}"><meta name="twitter:card" content="summary_large_image">'
              f'<meta name="twitter:image" content="{E(og_image)}"><meta name="twitter:title" content="{E(title)}">'
              f'<meta name="twitter:description" content="{E(desc[:200])}">')
    if th:
        foot = (f'<p>บันทึกเผยแพร่ภายใต้ <a href="{DATA_LICENSE}">CC BY 4.0</a> เส้นเขตแดนประเทศจาก '
                f'<a href="https://www.naturalearthdata.com/">Natural Earth</a> เป็นสมบัติสาธารณะ ภาพแต่ละภาพมีสัญญาอนุญาตของตัวเองกำกับไว้ข้างภาพ '
                f'ช่องข้อมูลบอกที่มาของตัวเอง และที่ใดที่สายความเชื่อขอไม่ให้เผยแพร่ แอตลาสนี้พิมพ์คำขอนั้นแทน</p>\n'
                f'{fleet.row_html("amulet-atlas", label="เว็บอื่นของผู้จัดทำ")}\n'
                f'{fleet.support_html(self_id="amulet-atlas")}\n'
                f'{fleet.maker_html(lang="th")}')
    else:
        foot = (f'<p>Records licensed <a href="{DATA_LICENSE}">CC BY 4.0</a>. Country outlines from <a href="https://www.naturalearthdata.com/">Natural Earth</a>, public domain. Pictures carry their own licences, stated beside each one. Every field says where it came from — and where a tradition asks that something not be published, this atlas prints the ask instead.</p>\n'
                f'{fleet.row_html("amulet-atlas")}\n'
                f'{fleet.support_html(self_id="amulet-atlas")}\n'
                f'{fleet.maker_html()}')
    brand = "แอตลาส<b>เครื่องราง</b>" if th else "Amulet <b>Atlas</b>"
    out = f"""<!doctype html>
<html lang="{LANG}" translate="no" class="notranslate">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc[:300])}">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1">
<meta name="color-scheme" content="light dark">
<meta property="og:site_name" content="{E(SITE_NAME_TH if th else SITE_NAME)}"><meta property="og:locale" content="{"th_TH" if th else "en_US"}">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc[:200])}"><meta property="og:type" content="{E(og_type)}">
{og}
{f'<link rel="canonical" href="{E(canonical)}">' if canonical else ''}{alts}
{f'<link rel="alternate" type="application/json" href="{E(alt_json)}">' if alt_json else ''}
<link rel="manifest" href="{r}manifest.webmanifest">
<meta name="theme-color" content="#b23a2b">
<link rel="icon" href="{r}icon.svg" type="image/svg+xml">
<link rel="search" type="application/opensearchdescription+xml" title="{E(SITE_NAME)}" href="{r}opensearch.xml">
<link rel="alternate" type="application/atom+xml" title="{E(SITE_NAME)} updates" href="{r}feed.xml">
{extra_head}
<style>{CSS}{SHARE_CSS}{TH_CSS}</style>
{ld}
<meta name="google" content="notranslate">
<meta name="robots" content="notranslate">
<script>if(/[.]translate[.]goog$/.test(location.hostname))location.replace("https://"+location.hostname.slice(0,-15).replace(/--/g,"~").replace(/-/g,".").replace(/~/g,"-")+location.pathname+location.search.replace(/([?&])_x_tr_[^&]*/g,"$1").replace(/[?&]+$/,"").replace(/[?]&+/,"?")+location.hash)</script>
</head>
<body>
<a class="skip" href="#main">{L("Skip to the record", "ข้ามไปที่เนื้อหา")}</a>
<header class="top"><a class="brand" href="{r}index.html">{brand}</a>
<nav class="crumbs">{nav} · <a class="wander" href="{r}wander.html" title="{L("a record at random", "สุ่มหนึ่งบันทึก")}">🎲 {L("Wander", "สุ่มอ่าน")}</a></nav></header>
<main id="main">
{body}
{share_row(canonical, share_title or title) if canonical else ""}
</main>
<script>document.addEventListener("keydown",function(e){{if(e.key==="r"&&!e.metaKey&&!e.ctrlKey&&!e.altKey&&!/input|textarea/i.test(e.target.tagName))location.href="{r}wander.html"}});</script>
<footer>
<div class="bots">{L("For the machines", "สำหรับเครื่อง")}: <a href="{r}api/nodes.json">nodes.json</a> <a href="{r}api/atlas.json">atlas.json</a> <a href="{r}api/timeline.json">timeline.json</a> <a href="{r}api/against.json">against.json</a> <a href="{r}api/kin.json">kin.json</a> <a href="{r}nodes.jsonl">nodes.jsonl</a> <a href="{r}nodes.csv">nodes.csv</a> <a href="{r}llms-full.txt">llms-full.txt</a> <a href="{r}sitemap.xml">sitemap.xml</a> <a href="{r}feed.xml">feed.xml</a> <a href="{r}api/coverage.json">coverage</a> <a href="{r}api/sources.json">sources</a></div>
{foot}
</footer>
</body>
</html>
"""
    return localize(out, path) if th else out


TH_CSS = """
.skip{position:absolute;left:-9999px;top:0;z-index:9;background:var(--ink);color:var(--bg);padding:.5rem .9rem}
.skip:focus{left:8px;top:8px}
:lang(th){letter-spacing:0!important;text-transform:none!important}
html:lang(th) body{line-height:1.8;font-family:"Sukhumvit Set","Thonburi","Noto Sans Thai","Leelawadee UI",var(--body)}
html:lang(th) :is(h1,h2,h3,.brand,.kin a.card b,.card a.t,.glyphgrid .nm){font-family:"Sukhumvit Set","Thonburi","Noto Sans Thai",var(--display);line-height:1.35}
html:lang(th) h1{text-wrap:balance}
.no-th{font-size:.85rem;border-left:3px solid var(--gold);padding-left:.6rem}
nav.crumbs sup{font-size:.62em;color:var(--mute)}
"""


# ------------------------------------------------------------------ helpers

def tier_chip(t: dict) -> str:
    tier = (t or {}).get("tier")
    if not tier:
        return ""
    return f'<span class="chip tier-{E(tier)}" title="{E(TIER_LABEL.get(tier, tier))}">{E(L(tier, TIER_TH.get(tier, tier)))}</span>'


def marks(text: str) -> str:
    """The inline provenance marks an author writes: *Tradition holds —* and *Inference —*, and their Thai."""
    return re.sub(r"\*(Tradition holds —|Tradition —|Inference —|Field —|ตามคติที่เล่าสืบกันมา —|ตามคติ —|ข้อสันนิษฐาน —|จากภาคสนาม —)\*",
                  lambda m: f'<mark class="tier">{E(m.group(1))}</mark>', text or "")


def prose(text: str) -> str:
    if not text:
        return ""
    out = []
    for para in str(text).split("\n\n"):
        p = marks(E(para).replace("\n", "<br>"))
        p = re.sub(r"&lt;mark class=&quot;tier&quot;&gt;", "<mark class=\"tier\">", p)
        out.append(f"<p>{p}</p>")
    return f'<div class="prose">{"".join(out)}</div>'


def name_link(r: dict, depth: int) -> str:
    return f'<a href="{rel(depth)}{url_of(r)}index.html">{E(rname(r))}</a>'


def group_key(r: dict, key: str):
    if not key:
        return None
    node = r
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    if isinstance(node, list):
        return node[0] if node else None
    return node


def group_head(g) -> str:
    return th_label("groups", g, str(g).replace("-", " ").title())


def directory_sections(recs: list[dict], types: dict, depth: int, limit: int | None = None) -> str:
    """The 1997 move, and still the right one: show the hierarchy on the page, with a count
    beside every term, so a reader can see the shape of the thing before clicking anything."""
    out = []
    for t in types["entries"]:
        rs = [r for r in recs if r["type"] == t["key"]]
        if not rs:
            continue
        groups: dict = {}
        for r in rs:
            groups.setdefault(group_key(r, t.get("group_by")) or "", []).append(r)
        items = []
        shown = 0
        for g in sorted(groups, key=lambda g: (g == "", str(g))):
            rows = sorted(groups[g], key=lambda r: rname(r).lower())
            if g:
                items.append(f'<li><b>{E(group_head(g))}</b> <span class="count">({len(rows)})</span></li>')
            for r in rows:
                if limit and shown >= limit:
                    break
                items.append(f'<li class="sub">{name_link(r, depth)}</li>' if g else f'<li>{name_link(r, depth)}</li>')
                shown += 1
        more = ""
        if limit and len(rs) > shown:
            more = f'<li class="sub"><a href="{rel(depth)}{DIR_OF[t["key"]]}/index.html">{L(f"all {len(rs)}", f"ทั้งหมด {len(rs)}")} →</a></li>'
        tv = TH["types"].get(t["key"], {}) if LANG == "th" else {}
        out.append(f'<section><h2><a href="{rel(depth)}{DIR_OF[t["key"]]}/index.html">{E(tv.get("name") or t["name"])}</a> '
                   f'<span class="count">({len(rs)})</span></h2><p class="mute" style="font-size:.88rem;margin:.1rem 0 .4rem">{E(tv.get("blurb") or t["blurb"])}</p>'
                   f'<ul>{"".join(items)}{more}</ul></section>')
    return f'<div class="dir">{"".join(out)}</div>'


def node_jsonld(r: dict) -> list:
    dt = r.get("dating") or {}
    base = {
        "@context": "https://schema.org",
        "@type": "Place" if r["type"] == "place" else ("Person" if r["type"] == "person" else
                 ("Organization" if r["type"] == "org" else ("Article" if r["type"] in ("story", "art") else "DefinedTerm"))),
        "name": r["names"]["name"],
        "url": f"{SITE_URL}/{url_of(r)}",
        "description": r["blurb"],
        "identifier": r["id"],
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_URL},
    }
    if LANG == "th":
        base.update({"url": f"{SITE_URL}/th/{url_of(r)}", "inLanguage": "th", "name": rname(r), "description": tblurb(r)})
    if r["names"].get("aliases"):
        base["alternateName"] = r["names"]["aliases"]
    if r["type"] not in ("place", "person", "org", "story", "art"):
        base["inDefinedTermSet"] = {"@type": "DefinedTermSet", "name": f"{SITE_NAME} — {DIR_OF[r['type']].title()}",
                                    "url": f"{SITE_URL}/{DIR_OF[r['type']]}/"}
    if r.get("geo"):
        base["geo"] = {"@type": "GeoCoordinates", "latitude": r["geo"]["lat"], "longitude": r["geo"]["lon"]}
    if r.get("address"):
        a = r["address"]
        base["address"] = {"@type": "PostalAddress", "addressLocality": a.get("city", ""),
                           "addressRegion": a.get("admin", ""), "addressCountry": a.get("country", "")}
    if r["type"] in ("story", "art"):
        base["author"] = AUTHOR
        base["datePublished"] = r["updated"]
        base["headline"] = r["names"]["name"]
    if dt.get("period"):
        base["temporalCoverage"] = r.get("span") or dt["period"]
    out = [base]
    out.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": SITE_URL},
        {"@type": "ListItem", "position": 2, "name": DIR_OF[r["type"]].title(), "item": f"{SITE_URL}/{DIR_OF[r['type']]}/"},
        {"@type": "ListItem", "position": 3, "name": r["names"]["name"], "item": f"{SITE_URL}/{url_of(r)}"}]})
    return out


def kin_card(k: dict, key: str, depth: int) -> str:
    name = (k.get("name_th") if LANG == "th" else "") or k["name"]
    said = E(k.get("as_th")) if LANG == "th" and k.get("as_th") else en_span(E(k["as"]))
    return (f'<a class="card" href="{rel(depth)}{PATH_OF[k["type"]]}/{E(k[key])}/index.html">'
            f'<small>{E(th_label("rels", k["rel"], k["rel"]))}</small><b>{E(name)}</b><span>{said}</span></a>')


def kin_block(r: dict, by_id: dict, depth: int) -> str:
    out = []
    if r.get("kin_out"):
        cards = "".join(kin_card(k, "to", depth) for k in r["kin_out"])
        out.append(f'<h2>{L("What this is near", "สิ่งที่อยู่ใกล้กัน")}</h2><div class="kin">{cards}</div>')
    if r.get("kin_in"):
        cards = "".join(kin_card(k, "from", depth) for k in r["kin_in"])
        out.append(f'<h2>{L("What names this one", "สิ่งที่กล่าวถึงเรื่องนี้")}</h2><p class="mute" style="font-size:.9rem">'
                   f'{L("Each in its own words, ", "แต่ละรายการใช้ถ้อยคำของตัวเอง ")}'
                   f'{L("from its own page.", "จากหน้าของตัวเอง")}</p><div class="kin">{cards}</div>')
    return "".join(out)


def against_block(r: dict) -> str:
    if not r.get("against_facts"):
        return ""
    items = []
    for i, a in enumerate(r["against_facts"]):
        q = f'<blockquote>{tf(r, f"against.{i}.quote", a["quote"])}</blockquote>' if a.get("quote") else ""
        who = f'<span class="who">{L("said by", "กล่าวโดย")} {tf(r, f"against.{i}.who", a["who"])}</span>' if a.get("who") else \
              f'<span class="who">{L("no claimant named in the source", "แหล่งที่มาไม่ได้ระบุผู้กล่าว")}</span>'
        gloss = f' <span class="mute">— {E(a["gloss"])}</span>' if a.get("gloss") and LANG == "en" else ""
        note = f'<span class="who">{tf(r, f"against.{i}.note", a["note"])}</span>' if a.get("note") else ""
        items.append(f'<li><b>{E(th_label("against", a["key"], a["label"]))}</b>{gloss} {tier_chip({"tier": a.get("tier")})}{who}{note}{q}</li>')
    return (f'<h2>{L("What its carriers say it stops", "ผู้พกบอกว่ามันกันอะไร")}</h2>'
            f'<p class="mute" style="font-size:.9rem">'
            + L('Reported, attributed, not tested here. Each row below is somebody\'s claim, with their name on it.',
                'รายงานตามที่มีผู้กล่าว ระบุชื่อผู้กล่าว และไม่ได้ทดสอบที่นี่ แถวด้านล่างคือคำกล่าวของแต่ละคน พร้อมชื่อของเขา')
            + f'</p><ul class="against">{"".join(items)}</ul>')


def object_block(r: dict) -> str:
    ob = r.get("object") or {}
    if not ob:
        return ""
    rows = []
    if r.get("form_fact"):
        rows.append((L("Form", "รูปแบบ"), E(th_label("forms", r["form_fact"]["key"], r["form_fact"]["label"]))))
    if r.get("material_facts"):
        rows.append((L("Made of", "ทำจาก"), " · ".join(
            f'<a href="{E(material_href(m["key"]))}">{E(th_label("materials", m["key"], m["label"]))}</a>' for m in r["material_facts"])))
    if r.get("worn_facts"):
        rows.append((L("Goes", "อยู่ที่"), " · ".join(f'<a href="../../wear/index.html#w-{E(w["key"])}">{E(th_label("worn", w["key"], w["label"]))}</a>'
                                                     for w in r["worn_facts"])))
    if ob.get("made_by"):
        rows.append((L("Made by", "ผู้ทำ"), tf(r, "object.made_by", ob["made_by"])))
    if ob.get("inscription"):
        rows.append((L("It says", "จารึกว่า"), tf(r, "object.inscription", ob["inscription"]) + (f' <span class="mute">({E(ob["script"])})</span>' if ob.get("script") else "")))
    if ob.get("count"):
        rows.append((L("Counted", "จำนวน"), E(ob["count"])))
    if ob.get("length_mm"):
        rows.append((L("Length", "ความยาว"), f'{E(ob["length_mm"])} {L("mm", "มม.")}'))
    if ob.get("colour"):
        rows.append((L("Colour", "สี"), tf(r, "object.colour", " · ".join(ob["colour"]))))
    if ob.get("single_use") is not None:
        rows.append((L("Retired", "ปลดระวาง"), (L("yes — it is replaced rather than kept", "ใช่ — เปลี่ยนใหม่แทนการเก็บไว้") if ob["single_use"]
                                              else L("no — it is kept", "ไม่ — เก็บไว้"))))
    if ob.get("note"):
        rows.append((L("Note", "หมายเหตุ"), tf(r, "object.note", ob["note"])))
    if not rows:
        return ""
    body = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
    return f'<h2>{L("The thing itself", "ตัววัตถุ")}</h2><table>{body}</table>'


METHOD = {"excavated": ("excavated — dug up in a dated context", "ขุดค้น — พบในชั้นดินที่ระบุอายุได้"),
          "inscribed": ("inscribed — the object carries its own date", "จารึก — ตัววัตถุมีวันที่ของตัวเอง"),
          "textual": ("textual — a dated text describes it", "เอกสาร — มีตำราที่ระบุปีบรรยายถึง"),
          "ethnographic": ("ethnographic — somebody recorded it being used, on a date", "ชาติพันธุ์วรรณนา — มีผู้บันทึกการใช้ไว้พร้อมวันที่"),
          "art-historical": ("art-historical — dated by style", "ประวัติศาสตร์ศิลป์ — กำหนดอายุจากรูปแบบ"),
          "dated-object": ("a dated example survives", "มีชิ้นที่ระบุปีหลงเหลืออยู่"),
          "undated": ("nobody here could date it", "ที่นี่ยังไม่มีใครระบุอายุได้")}


def dating_block(r: dict) -> str:
    dt = r.get("dating") or {}
    if not dt:
        return ""
    span = (span_th(r) if LANG == "th" else "") or dt.get("label") or r.get("span") or ""
    liv = f' <span class="liv">{L("still carried", "ยังใช้อยู่")}</span>' if dt.get("living") else ""
    rows = []
    if dt.get("period"):
        rows.append((L("Period", "ยุค"), tf(r, "dating.period", dt["period"])))
    if dt.get("method"):
        m = METHOD.get(dt["method"])
        rows.append((L("How the date is known", "รู้อายุได้อย่างไร"), E(L(m[0], m[1]) if m else dt["method"])))
    if dt.get("note"):
        rows.append((L("Note", "หมายเหตุ"), tf(r, "dating.note", dt["note"])))
    tbl = f'<table>{"".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)}</table>' if rows else ""
    foot = L('Years are stored astronomically — 1 CE is 1, 1 BCE is 0, 500 BCE is −499 — and printed the way a reader says them. '
             '<a href="../../story/dating-a-charm/index.html">How these dates are made.</a>',
             'ปีเก็บไว้แบบดาราศาสตร์ — ค.ศ. 1 คือ 1, ก่อน ค.ศ. 1 คือ 0, ก่อน ค.ศ. 500 คือ −499 — และพิมพ์ออกมาแบบที่ผู้อ่านพูดกัน '
             '<a href="../../story/dating-a-charm/index.html">วันที่เหล่านี้ได้มาอย่างไร</a>')
    return (f'<h2>{L("When", "เมื่อไร")}</h2><p class="spanline">{E(span)}{liv} {tier_chip({"tier": dt.get("tier")})}</p>{tbl}'
            f'<p class="mute" style="font-size:.88rem">{foot}</p>')


def holdings_block(r: dict) -> str:
    if not r.get("holding_facts"):
        return ""
    rows = []
    for i, h in enumerate(r["holding_facts"]):
        acc = f' <span class="mute">acc. {E(h["accession"])}</span>' if h.get("accession") else ""
        what = f' — {tf(r, f"holdings.{i}.what", h["what"])}' if h.get("what") else ""
        lab = f'<a href="{E(h["url"])}">{E(h["label"])}</a>' if h.get("url") else E(h["label"])
        rows.append(f"<li>{lab}{what}{acc}</li>")
    return (f'<h2>{L("Where you can see one", "ชมได้ที่ไหน")}</h2><ul>{"".join(rows)}</ul>'
            f'<p class="mute" style="font-size:.88rem">'
            + L('An accession number appears here only where it was read off a catalogue page that is linked. No link, no number.',
                'เลขทะเบียนวัตถุปรากฏที่นี่เฉพาะเมื่ออ่านมาจากหน้าแค็ตตาล็อกที่มีลิงก์ ไม่มีลิงก์ ไม่มีเลข')
            + '</p>')


def restricted_block(r: dict) -> str:
    rs = r.get("restricted")
    if not rs:
        return ""
    who = f' <span class="mute">— {E(rs["who_says"])}</span>' if rs.get("who_says") else ""
    src = f' <a href="{E(rs["url"])}">{L("source", "ที่มา")}</a>' if rs.get("url") else ""
    return (f'<div class="restricted"><b>{L("This one is not fully ours to publish", "เรื่องนี้ไม่ใช่ของเราที่จะเผยแพร่ได้ทั้งหมด")}</b>'
            f'<p>{tf(r, "restricted.note", rs["note"])}{who}{src}</p>'
            f'<p class="mute" style="font-size:.9rem">{L("The atlas prints the restriction and stops. ", "แอตลาสพิมพ์ข้อจำกัดนี้ไว้แล้วหยุดเพียงเท่านี้ ")}'
            f'<a href="../../story/what-this-atlas-does-not-print/index.html">{L("Why.", "ทำไม")}</a></p></div>')


def sources_block(r: dict) -> str:
    if not r.get("source_list"):
        return ""
    items = []
    for s in r["source_list"]:
        title = E(s.get("title") or s["id"])
        pub = f' <span class="mute">— {E(s["publisher"])}</span>' if s.get("publisher") else ""
        acc = f' <span class="mute">{L("read", "อ่านเมื่อ")} {E(s["accessed"])}</span>' if s.get("accessed") else ""
        link = f'<a href="{E(s["url"])}">{title}</a>' if s.get("url") else title
        items.append(f"<li>{link}{pub}{acc}</li>")
    return f'<h2>{L("Where this came from", "ที่มา")}</h2><ul lang="en">{"".join(items)}</ul>' if LANG == "th" else \
        f'<h2>Where this came from</h2><ul>{"".join(items)}</ul>'


DAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
DAY_NAME = {"Mo": "Monday", "Tu": "Tuesday", "We": "Wednesday", "Th": "Thursday",
            "Fr": "Friday", "Sa": "Saturday", "Su": "Sunday"}
DAY_TH = {"Mo": ("จ", "วันจันทร์"), "Tu": ("อ", "วันอังคาร"), "We": ("พ", "วันพุธ"), "Th": ("พฤ", "วันพฤหัสบดี"),
          "Fr": ("ศ", "วันศุกร์"), "Sa": ("ส", "วันเสาร์"), "Su": ("อา", "วันอาทิตย์")}
STATE_TH = {"open": "เปิด", "closed": "ปิด", "unknown": "ไม่ทราบ"}


def hours_block(r: dict) -> str:
    h = r.get("hours") or {}
    th = LANG == "th"
    if not h:
        return (f'<div class="whenbox"><b>{L("Opening days", "วันเปิด")}</b><p class="mute">'
                + L('Nobody has published days this project could read. That is not the same as closed.',
                    'ยังไม่มีใครเผยแพร่วันเปิดที่โครงการนี้อ่านได้ ซึ่งไม่ได้แปลว่าปิด')
                + '</p></div>')
    op, cl = set(h.get("open", [])), set(h.get("closed", []))
    cells = []
    for d in DAYS:
        state = "open" if d in op else ("closed" if d in cl else "unknown")
        col = {"open": "var(--faience)", "closed": "var(--line)", "unknown": "transparent"}[state]
        if th:
            cells.append(f'<span class="chip" style="background:{col}" title="{DAY_TH[d][1]} — {STATE_TH[state]}">{DAY_TH[d][0]}</span>')
        else:
            cells.append(f'<span class="chip" style="background:{col}" title="{DAY_NAME[d]} — {state}">{d}</span>')
    txt = f'<p class="hrs">{tf(r, "hours.text", h["text"])}</p>' if h.get("text") else ""
    chk = f' <span class="mute">{L("checked", "ตรวจเมื่อ")} {E(h["checked"])}</span>' if h.get("checked") else ""
    return (f'<div class="whenbox"><b>{L("Opening days", "วันเปิด")}</b><p>{"".join(cells)}</p>{txt}'
            f'<p class="mute" style="font-size:.86rem">'
            + L('Filled = open, outlined = closed, blank = nobody published it. A blank stays a blank.',
                'ทึบ = เปิด ขอบ = ปิด ว่าง = ไม่มีใครเผยแพร่ ช่องว่างคงเป็นช่องว่าง')
            + f'{chk}</p></div>')


CONF_TH = {"high": "สูง", "medium": "กลาง", "low": "ต่ำ"}


def node_page(r: dict, by_id: dict, places: list) -> str:
    n = r["names"]
    th = LANG == "th"
    title_name = rname(r)
    if th:
        second = [x for x in (n["name"] if n["name"] != title_name else "", n.get("native") if n.get("native") not in (title_name, None) else "") if x]
        native = "".join(f'<span class="native"{" lang=en" if x == n["name"] else ""}>{E(x)}</span>' for x in second)
    else:
        native = f'<span class="native">{E(n["native"])}</span>' if n.get("native") else ""
    said = f'<p class="said">{L("said", "ออกเสียง")} {E(n["said"])}</p>' if n.get("said") else ""
    ali = (f'<p class="mute">{L("also", "ชื่ออื่น")}: {E(" · ".join(n["aliases"]))}</p>') if n.get("aliases") else ""
    one = DIR_OF[r["type"]][:-1] if DIR_OF[r["type"]].endswith("s") else DIR_OF[r["type"]]
    chips = [f'<a class="chip" href="../../{DIR_OF[r["type"]]}/index.html">{E(TH["types"][r["type"]]["one"] if th else one)}</a>']
    for t in r.get("region_terms", []):
        chips.append(f'<span class="chip">{E(th_label("regions", t.get("key"), t.get("name") or t.get("key")))}</span>')
    for c in r.get("country_names", [])[:12]:
        chips.append(f'<a class="chip" href="../../map/index.html#c-{E(c["iso"])}">{E(th_label("countries", c["iso"], c["name"]))}</a>')
    if r.get("confidence") != "high":
        chips.append(f'<span class="chip tier-inference">{L("confidence " + str(r["confidence"]), "ความมั่นใจ " + CONF_TH.get(r["confidence"], str(r["confidence"])))}</span>'
                     if th else f'<span class="chip tier-inference">confidence {E(r["confidence"])}</span>')
    if r.get("needs_verification"):
        chips.append(f'<span class="chip tier-inference">{L("needs checking", "รอตรวจสอบ")}</span>')

    kind = TH["types"][r["type"]]["name"] if th else DIR_OF[r["type"]]
    body = [f'<h1><span class="kind">{E(kind)}</span>{E(title_name)}{native}</h1>{said}{ali}',
            f'<p>{"".join(chips)}</p>']
    if r["type"] == "motif" and viz.GLYPHS.get(r["id"]):
        body.append(f'<p style="color:var(--carn)">{viz.glyph(r["id"], 96)}</p>')
    body.append(restricted_block(r))
    what_th = (r.get("text_th") or {}).get("what") if th else None
    if th and not what_th:
        body.append(f'<p class="mute no-th">{NO_TH}</p><p class="lede" lang="en">{E(r["text"]["what"])}</p> '
                    f'{tier_chip(r.get("tiers", {}).get("text.what", {}))}')
    else:
        body.append(f'<p class="lede">{E(what_th or r["text"]["what"])}</p> {tier_chip(r.get("tiers", {}).get("text.what", {}))}')

    et = r.get("etymology") or {}
    if et.get("root") or et.get("first_attested") or et.get("note"):
        bits = []
        if et.get("root"):
            bits.append(f'<b>{tf(r, "etymology.root", et["root"])}</b>')
        if et.get("first_attested"):
            bits.append(f'{L("First written down", "บันทึกครั้งแรก")}: {tf(r, "etymology.first_attested", et["first_attested"])}' + L(".", ""))
        if et.get("note"):
            bits.append(tf(r, "etymology.note", et["note"]))
        if et.get("folk"):
            bits.append(f'<span class="mute">{L("Folk etymology, labelled as one", "นิรุกติศาสตร์พื้นบ้าน ระบุไว้ว่าเป็นเช่นนั้น")}: {tf(r, "etymology.folk", et["folk"])}</span>')
        body.append(f'<div class="etym"><p>{"<br>".join(bits)} {tier_chip(et)}</p></div>')

    if r.get("primary_image"):
        im = r["primary_image"]
        body.append(f'<figure><img src="{img_src(im, 2)}" alt="{E(im.get("alt") or n["name"])}" loading="lazy">'
                    f'<figcaption>{E(im.get("credit") or im.get("title") or "")} — {E(im.get("license"))}</figcaption></figure>')

    body.append(dating_block(r))
    body.append(object_block(r))
    body.append(against_block(r))

    if r["text"].get("story"):
        body.append(f'<h2>{L("The story", "เรื่องราว")}</h2>{ttext(r, "story")} {tier_chip(r.get("tiers", {}).get("text.story", {}))}')
    if r["text"].get("how"):
        body.append(f'<h2>{L("How it is made and carried", "ทำและพกอย่างไร")}</h2>{ttext(r, "how")} {tier_chip(r.get("tiers", {}).get("text.how", {}))}')
    if r["text"].get("today"):
        body.append(f'<h2>{L("Now", "ปัจจุบัน")}</h2>{ttext(r, "today")} {tier_chip(r.get("tiers", {}).get("text.today", {}))}')
    for i, sec in enumerate(r.get("sections", [])):
        tft = (r.get("th_fields") or {}) if th else {}
        if th and tft.get(f"sections.{i}.text"):
            body.append(f'<div class="sect"><h2>{E(tft.get(f"sections.{i}.h") or sec["h"])}</h2>{prose(tft[f"sections.{i}.text"])}</div>')
        elif th:
            body.append(f'<div class="sect" lang="en"><h2>{E(sec["h"])}</h2>{prose(sec["text"])}</div>')
        else:
            body.append(f'<div class="sect"><h2>{E(sec["h"])}</h2>{prose(sec["text"])}</div>')
    if r["text"].get("notes"):
        body.append(f'<h2>{L("Notes", "หมายเหตุ")}</h2>{ttext(r, "notes")}')

    if r["type"] == "place" and r.get("geo"):
        others = [p for p in places if p.get("lat") is not None and p["id"] != r["id"]]
        body.append(f'<h2>{L("Where", "ที่ตั้ง")}</h2><div class="mapwrap">'
                    + viz.locator(r["geo"]["lat"], r["geo"]["lon"], others, 760, 34, n["name"]) + "</div>")
        a = r.get("address") or {}
        line = ", ".join(x for x in (a.get("street"), a.get("city"), a.get("admin")) if x)
        body.append(f'<p class="mute">{tf(r, "address", line)} · {r["geo"]["lat"]:.4f}, {r["geo"]["lon"]:.4f} '
                    f'<span class="chip">{L("precision", "ความแม่นยำ")}: {E(r["geo"].get("precision") or L("unstated", "ไม่ระบุ"))}</span> '
                    f'{tier_chip(r.get("tiers", {}).get("geo", {}))}</p>')
        if r["geo"].get("source"):
            body.append(f'<p class="mute" style="font-size:.88rem">{tf(r, "geo.source", r["geo"]["source"])}</p>')
        body.append(hours_block(r))

    if r.get("tag_facts"):
        body.append(f'<h2>{L("What is on record about it", "สิ่งที่มีบันทึกไว้")}</h2><ul>' + "".join(
            f'<li><b>{E(t["label"])}</b> — {tf(r, f"tags.{i}.note", t.get("note") or t.get("evidence") or "")} '
            f'{tier_chip({"tier": t.get("tier")})}</li>' for i, t in enumerate(r["tag_facts"])) + "</ul>")
    if r.get("recognition_facts"):
        body.append(f'<h2>{L("Recognised by", "ได้รับการรับรองโดย")}</h2><ul>' + "".join(
            f'<li>{E(x["label"])} — {en_span(E(x["what"]))}{" (" + E(x["year"]) + ")" if x.get("year") else ""}</li>'
            for x in r["recognition_facts"]) + "</ul>")
    body.append(holdings_block(r))

    if r.get("confusable_with"):
        body.append(f'<h2>{L("Not to be confused with", "อย่าสับสนกับ")}</h2><ul>' + "".join(
            f'<li><a href="../../{PATH_OF[by_id[c["id"]]["type"]]}/{E(c["id"])}/index.html">'
            f'{E(rname(by_id[c["id"]]))}</a> — {tf(r, f"confusable_with.{i}.tell", c["tell"])}</li>'
            for i, c in enumerate(r["confusable_with"]) if c["id"] in by_id) + "</ul>")

    body.append(kin_block(r, by_id, 2))
    body.append(sources_block(r))
    if r.get("links"):
        body.append(f'<h2>{L("Elsewhere", "ที่อื่น")}</h2><ul>' + "".join(
            f'<li><a href="{E(l["url"])}">{E(l["label"])}</a></li>' for l in r["links"]) + "</ul>")
    body.append(f'<p class="legend">{L("Record updated", "ปรับปรุงบันทึก")} {E(r["updated"])}{L(".", "")} '
                f'<a href="../../api/{E(r["type"])}/{E(r["id"])}.json">{L("This record as JSON", "บันทึกนี้ในรูปแบบ JSON")}</a>{L(".", "")} '
                + L("Every field carries its own provenance; the tier chips above say which.",
                    "ช่องข้อมูลบอกที่มาของตัวเอง ป้ายระดับด้านบนบอกว่าเป็นระดับใด") + '</p>')
    return page(f'{title_name} — {SITE_NAME_TH if th else SITE_NAME}', "".join(body), 2, tblurb(r), node_jsonld(r),
                f"{SITE_URL}/{url_of(r)}", alt_json=f"{SITE_URL}/api/{r['type']}/{r['id']}.json",
                og_type="article" if r["type"] in ("story", "art") else "website", card=r["id"])


def type_index(t: dict, recs: list[dict], by_id: dict) -> str:
    th = LANG == "th"
    tv = TH["types"].get(t["key"], {}) if th else {}
    rs = sorted([r for r in recs if r["type"] == t["key"]], key=lambda r: rname(r).lower())
    groups: dict = {}
    for r in rs:
        groups.setdefault(group_key(r, t.get("group_by")) or "", []).append(r)
    blocks = []
    for g in sorted(groups, key=lambda g: (g == "", str(g))):
        head = f'<h2>{E(group_head(g))} <span class="count">({len(groups[g])})</span></h2>' if g else \
               (f'<h2>{L("The rest", "อื่น ๆ")} <span class="count">({len(groups[g])})</span></h2>' if len(groups) > 1 else "")
        cards = "".join(
            f'<div class="card"><a class="t" href="../{PATH_OF[r["type"]]}/{E(r["id"])}/index.html">{E(rname(r))}</a>'
            + (f'<p class="mute" style="font-size:.8rem">{E(tspan(r))}</p>' if r.get("span") else "")
            + (f'<p>{E(clip(tblurb(r), 170))}</p></div>' if not th or (r.get("text_th") or {}).get("what")
               else f'<p lang="en">{E(clip(r["blurb"], 170))}</p></div>') for r in groups[g])
        blocks.append(head + f'<div class="cards">{cards}</div>')
    body = (f'<h1><span class="kind">{E(SITE_NAME_TH if th else SITE_NAME)}</span>{E(tv.get("name") or t["name"])}</h1>'
            f'<p class="lede">{E(tv.get("blurb") or t["blurb"])}</p>' + "".join(blocks))
    jl = [{"@context": "https://schema.org", "@type": "ItemList", "name": f"{t['name']} — {SITE_NAME}",
           "url": f"{SITE_URL}/{DIR_OF[t['key']]}/", "numberOfItems": len(rs),
           "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": r["names"]["name"],
                                "url": f"{SITE_URL}/{url_of(r)}"} for i, r in enumerate(rs)]}]
    return page(f'{tv.get("name") or t["name"]} — {SITE_NAME_TH if th else SITE_NAME}', body, 1, tv.get("blurb") or t["blurb"], jl,
                f"{SITE_URL}/{DIR_OF[t['key']]}/", card=DIR_OF[t["key"]])


def front_page(recs: list[dict], by_id: dict, types: dict, atlas: dict, timeline: dict,
               against: dict, cov: dict) -> str:
    if LANG == "th":
        return front_page_th(recs, by_id, types, atlas, timeline, against, cov)
    counts = {row["iso"]: row["n"] for row in atlas["rows"]}
    links = {row["iso"]: f"map/index.html#c-{row['iso']}" for row in atlas["rows"]}
    n_amulet = sum(1 for r in recs if r["type"] == "amulet")
    edges = sum(len(r.get("kin_out", [])) for r in recs)
    oldest = cov["time"].get("earliest_year")
    top_harms = [h for h in against["harms"] if h["n"]][:8]
    living = [r for r in timeline["rows"] if r["living"]]
    body = [f"""
<div class="hero">
  <h1>Amulet Atlas</h1>
  <p class="sub">{E(TAGLINE)}</p>
</div>
<div class="facts">
  <div class="fact"><span class="n">{len(recs)}</span><span class="l">records</span></div>
  <div class="fact"><span class="n">{n_amulet}</span><span class="l">kinds of charm</span></div>
  <div class="fact"><span class="n">{atlas["countries"]}</span><span class="l">countries named</span></div>
  <div class="fact"><span class="n">{edges}</span><span class="l">kin links</span></div>
  <div class="fact"><span class="n">{against["count"]}</span><span class="l">claims, each attributed</span></div>
  <div class="fact"><span class="n">{E(year_label(oldest)) if oldest is not None else "—"}</span><span class="l">earliest dated</span></div>
  <div class="fact"><span class="n">{len(living)}</span><span class="l">still carried</span></div>
  <div class="fact"><span class="n">{cov["sources"]}</span><span class="l">sources</span></div>
</div>
<p class="lede">Every hemisphere, from a bead somebody drilled five thousand years ago to a
sticker on a phone. Each record says what the thing <b>is</b>, what its carriers say it
<b>stops</b> — named, quoted, and never tested here — and <b>where</b> and <b>when</b> it is
documented. Where a tradition asks that something not be published, this atlas prints the ask
instead of the thing.</p>
<div class="cta">
  <a class="btn" href="map/index.html">The map</a>
  <a class="btn ghost" href="time/index.html">Five thousand years, one axis</a>
  <a class="btn ghost" href="against/index.html">What it stops</a>
  <a class="btn ghost" href="wear/index.html">Where it goes</a>
  <a class="btn ghost" href="quiz/index.html">Pick me one</a>
</div>
<h2 id="map">Where the records are</h2>
<div class="mapwrap">{viz.world_choropleth(counts, 1040, "records by country", unit="records", links=links)}</div>
<p class="mute" style="font-size:.9rem">{E(atlas["reading_an_absence"])}
<a href="map/index.html">The map, in full →</a></p>
"""]
    body.append('<h2>The signs</h2><p class="mute">Drawn for this atlas from published '
                'descriptions, not traced from any one object.</p><div class="glyphgrid">')
    for r in sorted([x for x in recs if x["type"] == "motif"], key=lambda x: x["names"]["name"].lower()):
        g = viz.glyph(r["id"], 52)
        if not g:
            continue
        body.append(f'<a href="sign/{E(r["id"])}/index.html">{g}<span class="nm">{E(r["names"]["name"])}</span>'
                    f'<span class="ct">{E(clip(r.get("span") or "", 26))}</span></a>')
    body.append('</div><p><a href="signs/index.html">Every sign →</a></p>')

    if timeline["rows"]:
        body.append(f'<h2>How long each one has been carried</h2>'
                    f'<div class="mapwrap">{viz.time_chart(time_rows(sorted(timeline["rows"], key=lambda r: (r["from_year"] if r["from_year"] is not None else 9999))[:26], 0), 1040)}</div>'
                    f'<p class="mute" style="font-size:.9rem">The oldest twenty-six. The axis is not linear and '
                    f'the ticks say so. <a href="time/index.html">All {timeline["count"]} →</a></p>')

    if top_harms:
        body.append('<h2>What people are actually worried about</h2>'
                    + viz.bars([{"label": h["label"], "n": h["n"]} for h in top_harms], 1040, " claims", 30, 260)
                    + '<p class="mute" style="font-size:.9rem">One row per claim, not per charm. '
                      '<a href="against/index.html">The whole table →</a></p>')

    body.append('<h2>Everything, by kind</h2>')
    body.append(directory_sections(recs, types, 0, limit=14))
    body.append(f'<p class="legend">Records are hand-written JSON, one per node, each field carrying a provenance '
                f'tier. <a href="coverage/index.html">What this atlas does not cover</a> · '
                f'<a href="sources/index.html">every source</a> · <a href="api/nodes.json">the data</a>.</p>')
    jl = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL,
           "description": TAGLINE, "inLanguage": "en", "author": AUTHOR,
           "potentialAction": {"@type": "SearchAction", "target": f"{SITE_URL}/search/?q={{search_term_string}}",
                               "query-input": "required name=search_term_string"}},
          {"@context": "https://schema.org", "@type": "Dataset", "name": f"{SITE_NAME} records",
           "description": cov["scope"], "url": f"{SITE_URL}/api/nodes.json",
           "license": DATA_LICENSE, "creator": AUTHOR, "publisher": fleet.publisher_ld(), "includedInDataCatalog": fleet.catalog_ld(),
           "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE_URL}/api/nodes.json"},
                            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{SITE_URL}/nodes.csv"}]}]
    return page(f"{SITE_NAME} — {TAGLINE}", "".join(body), 0, cov["scope"], jl, SITE_URL + "/", card="index")


def front_page_th(recs: list[dict], by_id: dict, types: dict, atlas: dict, timeline: dict,
                  against: dict, cov: dict) -> str:
    counts = {row["iso"]: row["n"] for row in atlas["rows"]}
    links = {row["iso"]: f"map/index.html#c-{row['iso']}" for row in atlas["rows"]}
    n_amulet = sum(1 for r in recs if r["type"] == "amulet")
    edges = sum(len(r.get("kin_out", [])) for r in recs)
    oldest = cov["time"].get("earliest_year")
    top_harms = [h for h in against["harms"] if h["n"]][:8]
    living = [r for r in timeline["rows"] if r["living"]]
    home = sorted([r for r in recs if "TH" in (r.get("countries") or []) and (r.get("text_th") or {}).get("story")],
                  key=lambda r: (r["type"] != "amulet", rname(r)))
    home_cards = "".join(
        f'<div class="card"><a class="t" href="{url_of(r)}index.html">{E(rname(r))}</a>'
        f'<p class="mute" style="font-size:.8rem">{E(TH["types"][r["type"]]["one"])}</p>'
        f'<p>{E(clip(tblurb(r), 150))}</p></div>' for r in home)
    body = [f"""
<div class="hero">
  <h1>{SITE_NAME_TH}</h1>
  <p class="sub">{E(TAGLINE_TH)}</p>
  <p class="mute" lang="en">Amulet Atlas</p>
</div>
<div class="facts">
  <div class="fact"><span class="n">{len(recs)}</span><span class="l">บันทึก</span></div>
  <div class="fact"><span class="n">{n_amulet}</span><span class="l">ชนิดเครื่องราง</span></div>
  <div class="fact"><span class="n">{atlas["countries"]}</span><span class="l">ประเทศที่ระบุ</span></div>
  <div class="fact"><span class="n">{edges}</span><span class="l">ลิงก์เชื่อมโยง</span></div>
  <div class="fact"><span class="n">{against["count"]}</span><span class="l">คำกล่าว พร้อมชื่อผู้กล่าว</span></div>
  <div class="fact"><span class="n">{E(year_th(oldest)) if oldest is not None else "—"}</span><span class="l">เก่าที่สุดที่ระบุปีได้</span></div>
  <div class="fact"><span class="n">{len(living)}</span><span class="l">ยังใช้อยู่</span></div>
  <div class="fact"><span class="n">{cov["sources"]}</span><span class="l">แหล่งที่มา</span></div>
</div>
<p class="lede">ครอบคลุมทุกซีกโลก ตั้งแต่ลูกปัดที่มีคนเจาะเมื่อห้าพันปีก่อน ไปจนถึงสติกเกอร์บนโทรศัพท์
แต่ละบันทึกบอกว่าสิ่งนั้น<b>คืออะไร</b> ผู้พกบอกว่ามัน<b>กันอะไร</b> — ระบุชื่อ อ้างคำพูด และไม่ได้ทดสอบที่นี่ —
และมีบันทึกไว้<b>ที่ไหน</b>และ<b>เมื่อไร</b> ที่ใดที่สายความเชื่อขอไม่ให้เผยแพร่ แอตลาสนี้พิมพ์คำขอนั้นแทนตัวสิ่งนั้น</p>
<div class="cta">
  <a class="btn" href="#thai">จากเมืองไทย</a>
  <a class="btn ghost" href="map/index.html">แผนที่ (EN)</a>
  <a class="btn ghost" href="time/index.html">ห้าพันปี บนแกนเดียว (EN)</a>
  <a class="btn ghost" href="against/index.html">กันอะไร (EN)</a>
</div>
<h2 id="thai">จากเมืองไทย</h2>
<p class="mute">บันทึกที่เขียนเป็นภาษาไทยครบทั้งเรื่อง</p>
<div class="cards">{home_cards}</div>
<h2 id="map">บันทึกอยู่ที่ไหน</h2>
<div class="mapwrap" lang="en">{viz.world_choropleth(counts, 1040, "records by country", unit="records", links=links)}</div>
<p class="mute" style="font-size:.9rem">ประเทศที่ว่างบนแผนที่หมายความว่ายังไม่มีบันทึกใดระบุถึง ไม่ได้หมายความว่าไม่มีใครที่นั่นพกเครื่องราง
<a href="map/index.html">แผนที่ฉบับเต็ม (EN) →</a></p>
"""]
    body.append('<h2>สัญลักษณ์</h2><p class="mute">วาดขึ้นสำหรับแอตลาสนี้จากคำบรรยายที่ตีพิมพ์ '
                'ไม่ได้ลอกจากวัตถุชิ้นใดชิ้นหนึ่ง</p><div class="glyphgrid">')
    for r in sorted([x for x in recs if x["type"] == "motif"], key=lambda x: rname(x)):
        g = viz.glyph(r["id"], 52)
        if not g:
            continue
        body.append(f'<a href="sign/{E(r["id"])}/index.html">{g}<span class="nm">{E(rname(r))}</span>'
                    f'<span class="ct">{E(clip(span_th(r), 30))}</span></a>')
    body.append('</div>')

    if top_harms:
        body.append('<h2>ผู้คนกังวลเรื่องอะไรกันจริง ๆ</h2>'
                    + viz.bars([{"label": th_label("against", h["key"], h["label"]), "n": h["n"]} for h in top_harms], 1040, " คำกล่าว", 30, 260)
                    + '<p class="mute" style="font-size:.9rem">หนึ่งแถวต่อหนึ่งคำกล่าว ไม่ใช่ต่อเครื่องรางหนึ่งชิ้น '
                      '<a href="against/index.html">ตารางทั้งหมด (EN) →</a></p>')

    body.append('<h2>ทั้งหมด แยกตามประเภท</h2>')
    body.append(directory_sections(recs, types, 0, limit=14))
    body.append('<p class="legend">บันทึกเขียนด้วยมือเป็น JSON หนึ่งไฟล์ต่อหนึ่งเรื่อง ช่องข้อมูลระบุระดับที่มา '
                '<a href="coverage/index.html">สิ่งที่แอตลาสนี้ยังไม่ครอบคลุม (EN)</a> · '
                '<a href="sources/index.html">แหล่งที่มาทั้งหมด (EN)</a> · <a href="api/nodes.json">ข้อมูล</a></p>')
    jl = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME_TH, "alternateName": SITE_NAME,
           "url": SITE_URL + "/th/", "description": TAGLINE_TH, "inLanguage": "th", "author": AUTHOR}]
    return page(f"{SITE_NAME_TH} — {TAGLINE_TH}", "".join(body), 0, TAGLINE_TH, jl, SITE_URL + "/", card="index")


def wander_page(recs: list[dict]) -> str:
    urls = json.dumps([url_of(r) + "index.html" for r in recs])
    body = (L('<h1>Wander</h1><p class="lede">One record at random. Press <b>r</b> anywhere on this site '
              'for another.</p><noscript><p>Pick one: ',
              '<h1>สุ่มอ่าน</h1><p class="lede">สุ่มหนึ่งบันทึก กด <b>r</b> ที่ไหนก็ได้ในเว็บนี้เพื่อสุ่มใหม่</p>'
              '<noscript><p>เลือกหนึ่งเรื่อง: ')
            + " · ".join(f'<a href="{url_of(r)}index.html">{E(rname(r))}</a>' for r in recs[:60])
            + "</p></noscript>"
            f'<script>var U={urls};location.replace(U[Math.floor(Math.random()*U.length)]);</script>')
    return page(L(f"Wander — {SITE_NAME}", f"สุ่มอ่าน — {SITE_NAME_TH}"), body, 0, L("A record at random.", "สุ่มหนึ่งบันทึก"))


def sources_page(sources: dict) -> str:
    rows = sorted(sources["sources"], key=lambda s: (s.get("publisher") or "", s.get("title") or ""))
    by_pub: dict = {}
    for s in rows:
        by_pub.setdefault(s.get("publisher") or "Unattributed", []).append(s)
    out = []
    for pub in sorted(by_pub, key=lambda p: (-len(by_pub[p]), p)):
        items = "".join(
            f'<li>{f"""<a href="{E(s["url"])}">{E(s.get("title") or s["id"])}</a>""" if s.get("url") else E(s.get("title") or s["id"])}'
            f'{f""" <span class="mute">read {E(s["accessed"])}</span>""" if s.get("accessed") else ""}'
            f'{f""" <span class="chip">{E(s["license"])}</span>""" if s.get("license") else ""}</li>'
            for s in by_pub[pub])
        out.append(f'<h3>{E(pub)} <span class="count">({len(by_pub[pub])})</span></h3><ul>{items}</ul>')
    body = (f'<h1><span class="kind">{E(SITE_NAME)}</span>Where we got it</h1>'
            f'<p class="lede">{len(rows)} sources. A record may cite only an id that is on this page. '
            f'An author who reads something new registers it here first, with its real title, publisher, URL and '
            f'the date it was read — which is how this atlas keeps from inventing a citation.</p>'
            f'<div class="pl-list">{"".join(out)}</div>')
    return page(f"Sources — {SITE_NAME}", body, 1, "Every source any record may cite.", None,
                f"{SITE_URL}/sources/", card="sources")


def coverage_page(cov: dict, atlas: dict) -> str:
    hemi = viz.hemisphere_bar(cov["world"]["hemispheres"], sum(cov["records"].values()), 700)
    rows = "".join(f"<tr><th>{E(k)}</th><td>{E(v)}</td></tr>" for k, v in cov["records"].items())
    gaps = "".join(f"<li>{E(x)}</li>" for x in cov["not_yet"])
    tiers = "".join(f"<tr><th>{E(k)}</th><td>{E(v)}</td></tr>" for k, v in cov["tiers"].items())
    body = f"""
<h1><span class="kind">{E(SITE_NAME)}</span>Where we stop</h1>
<p class="lede">{E(cov["scope"])}</p>
<h2>How lopsided this still is</h2>
{hemi}
<p class="mute">Every record counts once per hemisphere it touches, so the four numbers add to more than the
record count. The northern and eastern bars are long because the written record this atlas reads from is
long there. That is a fact about the sources, not about where people carry charms.</p>
<h2>What is in it</h2>
<table>{rows}</table>
<h2>Time</h2>
<table>
<tr><th>Records with a date</th><td>{cov["time"]["records_dated"]}</td></tr>
<tr><th>Still carried</th><td>{cov["time"]["still_carried"]}</td></tr>
<tr><th>Earliest dated</th><td>{E(year_label(cov["time"]["earliest_year"]))}</td></tr>
<tr><th>Reading an absence</th><td>{E(cov["time"]["reading_an_absence"])}</td></tr>
</table>
<h2>The world</h2>
<table>
<tr><th>Countries named</th><td>{cov["world"]["countries_named"]}</td></tr>
<tr><th>Reading an absence</th><td>{E(cov["world"]["reading_an_absence"])}</td></tr>
</table>
<h2>Claims</h2>
<table>
<tr><th>Claim rows</th><td>{cov["claims"]["rows"]}</td></tr>
<tr><th>With somebody quoted</th><td>{cov["claims"]["with_a_quote"]}</td></tr>
<tr><th>Rule</th><td>{E(cov["claims"]["note"])}</td></tr>
</table>
<h2>Held back on purpose</h2>
<table>
<tr><th>Records with a restriction</th><td>{cov["restricted"]["records"]}</td></tr>
<tr><th>Rule</th><td>{E(cov["restricted"]["note"])}</td></tr>
</table>
<p><a href="../story/what-this-atlas-does-not-print/index.html">The long version of that rule →</a></p>
<h2>Not yet</h2>
<ul>{gaps}</ul>
<h2>What each provenance tier means</h2>
<table>{tiers}</table>
<p class="legend">This page is generated from <a href="../api/coverage.json">coverage.json</a>, which is built from
the records themselves. Nothing on it is typed by hand.</p>
"""
    return page(f"Where we stop — {SITE_NAME}", body, 1, cov["scope"], None,
                f"{SITE_URL}/coverage/", card="coverage")


def search_page(docs: list[dict]) -> str:
    body = f"""
<h1><span class="kind">{E(SITE_NAME)}</span>Search</h1>
<p class="lede">Spell it however you spell it — nazar, nazar boncuğu, evil eye bead. If we had to
stretch to find it, the page says so.</p>
<form class="search" role="search" onsubmit="return false"><input id="q" type="search" placeholder="scarab · hamsa · omamori · iron · the evil eye · Naples…" aria-label="Search" autofocus><button id="go" type="button">Search</button></form>
<p id="tier" class="tierline" aria-live="polite"></p>
<div id="out" class="cards"></div>
<p class="legend" id="how">Runs in your browser over every record: exact → same meaning, other word →
near spellings → partial. The index is in this page and the lookup runs in your browser.</p>
<script src="../vendor/searchcore.js"></script>
<script>
(function(){{
var DOCS={json.dumps(docs, ensure_ascii=False)};
var PATH={json.dumps(PATH_OF)};
var TABLES=null, core=null, index=null, PREP=null;
var byId={{}}; DOCS.forEach(function(d){{byId[d.id]=d}});
var TIER={{exact:"exact match",thesaurus:"same meaning, other word",loose:"near spellings — closest first",partial:"partial matches"}};
function esc(s){{return String(s==null?"":s).replace(/[&<>"]/g,function(c){{return {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]}})}}
function build(){{
  core=new SEARCHCORE.SearchCore(TABLES.groups||[],TABLES.words||[]);
  index=new SEARCHCORE.Index(core);
  PREP={{}};
  DOCS.forEach(function(d){{var f={{name:[d.names,3],terms:[d.terms,2],text:[d.text,1]}};index.add(d,f);PREP[d.id]=core.prepareDoc(f)}});
  index.finalize();
}}
function card(d,tier){{
  return '<div class="card"><a class="t" href="../'+PATH[d.type]+'/'+esc(d.id)+'/index.html">'+esc(d.name)+'</a><p class="mute" style="font-size:.76rem;text-transform:uppercase;letter-spacing:.12em">'+esc(d.type)+(d.region?' · '+esc(d.region):'')+'</p><p>'+esc(d.blurb)+'</p><p><span class="chip">'+esc(TIER[tier]||tier)+'</span></p></div>';
}}
function lexical(q){{
  var an=core.analyze(q,index); var rows=[];
  for(var id in PREP){{var r=core.scoreDoc(an,PREP[id]); if(r) rows.push({{id:id,tier:r.tier,score:r.score,coverage:r.coverage}})}}
  var whole=rows.filter(function(r){{return r.coverage>=1}}); var kept=whole.length?whole:rows;
  kept.sort(function(a,b){{return b.score-a.score}}); return kept.slice(0,36);
}}
function render(rows,worst){{
  var out=document.getElementById("out"), t=document.getElementById("tier");
  if(!rows.length){{out.innerHTML="";t.textContent="Nothing here answers to that yet.";return}}
  t.textContent=(TIER[worst]||worst);
  out.innerHTML=rows.map(function(r){{var d=byId[r.id];return d?card(d,r.tier):''}}).join("");
}}
function run(){{
  var q=document.getElementById("q").value.trim(); if(!q){{render([],null);return}}
  var lex=lexical(q); var worst=null;
  lex.forEach(function(r){{if(worst==null||SEARCHCORE.TIER_ORDER.indexOf(r.tier)>SEARCHCORE.TIER_ORDER.indexOf(worst))worst=r.tier}});
  render(lex,worst||"exact");
}}
fetch("tables.json").then(function(r){{return r.json()}}).then(function(t){{TABLES=t;build();
  var u=new URL(location.href); var q0=u.searchParams.get("q"); if(q0){{document.getElementById("q").value=q0;run()}}
}});
document.getElementById("go").addEventListener("click",run);
document.getElementById("q").addEventListener("keydown",function(e){{if(e.key==="Enter"&&!e.isComposing){{e.preventDefault();run()}}}});
document.getElementById("q").addEventListener("input",function(){{if(index)run()}});
}})();
</script>
"""
    return page(f"Search — {SITE_NAME}", body, 1, "Spell it however you spell it.", None,
                f"{SITE_URL}/search/", card="search")


def manifest() -> str:
    return json.dumps({"name": SITE_NAME, "short_name": "Amulets", "start_url": "./index.html",
                       "display": "standalone", "background_color": "#f6f3ec", "theme_color": "#b23a2b",
                       "description": TAGLINE,
                       "icons": [{"src": "icon.svg", "sizes": "any", "type": "image/svg+xml"}]}, indent=1)


def icon_svg() -> str:
    """An eye in a disc — the one sign this atlas can put on its own door without borrowing
    a living tradition's object to do it."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<rect width="64" height="64" rx="13" fill="#1a4b46"/>'
            '<g fill="none" stroke="#f6f3ec" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M10 32c10-13 34-13 44 0-10 13-34 13-44 0z"/><circle cx="32" cy="32" r="8"/></g>'
            '<circle cx="32" cy="32" r="3.6" fill="#b23a2b"/></svg>')


def llms_txt(recs: list[dict], cov: dict) -> str:
    lines = [f"# {SITE_NAME}", "",
             "> A structured atlas of amulets, charms and talismans worldwide: the objects, the traditions they "
             "belong to, the signs cut into them, the materials, the practices that make and retire them, plus "
             "places, people, organizations and vocabulary. One JSON record per node. Every field carries a "
             "provenance tier (cited / harvested / tradition / inference / field). Records say what their "
             "neighbours are to them, in both directions. Claims about what a charm does are always attributed "
             "to a named claimant and are never asserted or denied by this project.",
             "",
             f"Records are CC BY 4.0 ({DATA_LICENSE}). Country outlines are Natural Earth, public domain. Pictures "
             f"carry their own licences, stated per file. Scope and gaps: {SITE_URL}/api/coverage.json",
             "",
             "Note for machines: where a tradition restricts what may be published, the record carries a "
             "`restricted` block and the detail is absent by design. Absence there is a deliberate editorial act, "
             "not missing data to be filled in from elsewhere.",
             "", "## Data",
             f"- [All records, JSON]({SITE_URL}/api/nodes.json)",
             f"- [Directory index, JSON]({SITE_URL}/api/index.json)",
             f"- [The map table, one row per country]({SITE_URL}/api/atlas.json)",
             f"- [The timeline table, astronomical years]({SITE_URL}/api/timeline.json)",
             f"- [What each charm is said to stop, with claimants]({SITE_URL}/api/against.json)",
             f"- [Materials, forms and where on the body]({SITE_URL}/api/matter.json)",
             f"- [Places]({SITE_URL}/api/places.json) · [Kin edges]({SITE_URL}/api/kin.json)",
             f"- [JSONL]({SITE_URL}/nodes.jsonl) · [CSV]({SITE_URL}/nodes.csv)",
             f"- [Record schema]({SITE_URL}/schema/node.schema.json)",
             f"- [Vocabularies]({SITE_URL}/api/vocab/against.json)",
             f"- [Sources registry]({SITE_URL}/api/sources.json)",
             f"- [Full text of every record]({SITE_URL}/llms-full.txt)",
             f"- [The Thai edition · ฉบับภาษาไทย]({SITE_URL}/th/): the same records under /th/; a record's Thai is in "
             "`names.th`, `text_th` and `kin[].as_th`", ""]
    for t in TYPES:
        rs = sorted([r for r in recs if r["type"] == t], key=lambda r: r["names"]["name"].lower())
        if not rs:
            continue
        lines.append(f"## {DIR_OF[t].title()}")
        for r in rs:
            lines.append(f"- [{r['names']['name']}]({SITE_URL}/{url_of(r)}): {r['blurb']}")
        lines.append("")
    lines += ["## Optional",
              f"- [The world map]({SITE_URL}/map/)", f"- [The timeline]({SITE_URL}/time/)",
              f"- [What it stops]({SITE_URL}/against/)", f"- [Where it goes]({SITE_URL}/wear/)",
              f"- [Search]({SITE_URL}/search/)", f"- [Atom feed]({SITE_URL}/feed.xml)",
              f"- [Sitemap]({SITE_URL}/sitemap.xml)"]
    return "\n".join(lines) + "\n"


def llms_full(recs: list[dict], sources: dict) -> str:
    out = [f"# {SITE_NAME} — every record, flattened\n"]
    for t in TYPES:
        for r in sorted([x for x in recs if x["type"] == t], key=lambda x: x["names"]["name"].lower()):
            n = r["names"]
            out.append(f"## {n['name']} ({t})\nURL: {SITE_URL}/{url_of(r)}\n"
                       f"JSON: {SITE_URL}/api/{t}/{r['id']}.json\nid: {r['id']}")
            if n.get("native"):
                out.append(f"native: {n['native']} ({n.get('script', '')})")
            if n.get("aliases"):
                out.append("aliases: " + " · ".join(n["aliases"]))
            if n.get("said"):
                out.append("said: " + n["said"])
            if r.get("span"):
                out.append(f"when: {r['span']}" + (" (still carried)" if (r.get('dating') or {}).get('living') else ""))
            if r.get("countries"):
                out.append("countries: " + " ".join(r["countries"]))
            et = r.get("etymology") or {}
            if et.get("root"):
                out.append(f"root: {et['root']}")
            ob = r.get("object") or {}
            if ob:
                bits = [f"form={ob.get('form', '')}", "materials=" + ",".join(ob.get("materials", []) or []),
                        "worn=" + ",".join(ob.get("worn", []) or [])]
                out.append("object: " + " ".join(b for b in bits if not b.endswith("=")))
            for a in r.get("against", []):
                out.append(f"against: {a['harm']} — said by {a.get('who', 'unnamed')} [{a['source']}]")
            if r.get("restricted"):
                out.append(f"RESTRICTED: {r['restricted']['note']}")
            for k in ("what", "story", "how", "today", "notes"):
                if r["text"].get(k):
                    out.append(f"{k}: {r['text'][k]}")
            for sec in r.get("sections", []):
                out.append(f"{sec['h']}: {sec['text']}")
            for k in r.get("kin_out", []):
                out.append(f"kin: {k['to']} — {k['as']}")
            if r.get("sources"):
                out.append("sources: " + " ".join(r["sources"]))
            out.append(f"tier: {(r.get('provenance') or {}).get('default', {}).get('tier', '')}"
                       f" · confidence: {r['confidence']} · updated: {r['updated']}\n")
    return "\n".join(out) + "\n"


def sitemap(recs: list[dict], extra: list) -> str:
    today = time.strftime("%Y-%m-%d")
    urls = [(SITE_URL + "/", today, "1.0")]
    for p in extra:
        urls.append((f"{SITE_URL}/{p}/", today, "0.8"))
    for t in TYPES:
        if any(r["type"] == t for r in recs):
            urls.append((f"{SITE_URL}/{DIR_OF[t]}/", today, "0.7"))
    for r in recs:
        urls.append((f"{SITE_URL}/{url_of(r)}", r["updated"], "0.6"))
    urls.append((f"{SITE_URL}/th/", today, "0.9"))
    for t in TYPES:
        if t not in FOLDED and any(r["type"] == t for r in recs):
            urls.append((f"{SITE_URL}/th/{DIR_OF[t]}/", today, "0.6"))
    for r in recs:
        urls.append((f"{SITE_URL}/th/{url_of(r)}", r["updated"], "0.5"))
    body = "".join(f"<url><loc>{E(u)}</loc><lastmod>{E(m)}</lastmod><priority>{p}</priority></url>"
                   for u, m, p in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


def robots() -> str:
    return f"""# Everything here is open on purpose. Crawl it, index it, train on it, quote it.
# The one ask is the one the records themselves make: keep the attribution, and keep the
# provenance tier attached to the claim it belongs to. A cited fact and a hedged one are
# not the same fact.
User-agent: *
Allow: /
Content-Signal: search=yes, ai-input=yes, ai-train=yes
Sitemap: {SITE_URL}/sitemap.xml
"""


def ai_txt(cov: dict) -> str:
    return f"""# {SITE_NAME} — a note for machines reading this site
url: {SITE_URL}
license: CC BY 4.0 for the records ({DATA_LICENSE})
attribution: {SITE_NAME} — {SITE_URL}
structured: {SITE_URL}/api/nodes.json
schema: {SITE_URL}/schema/node.schema.json
coverage: {SITE_URL}/api/coverage.json

How to read this data:
- Every field carries a provenance tier. `cited` names a source; `tradition` is general
  knowledge of the practice and is hedged in the prose; `inference` is this project's own
  reasoning and says so. Do not flatten the three into one confidence.
- Claims about what a charm does belong to named claimants in `against[]`. They are not
  this project's assertions and should not be reported as facts about the world.
- A `restricted` block means a tradition has asked that something not be published. The
  absence is deliberate. Do not reconstruct it from other sources.
- An empty country on the map means no record here names it, not that nobody there carries
  a charm. See {SITE_URL}/api/atlas.json for the exact statement.
"""


def humans_txt(recs: list[dict], cov: dict) -> str:
    return f"""/* {SITE_NAME} */
{TAGLINE}

{len(recs)} records · {cov["world"]["countries_named"]} countries · {cov["sources"]} sources
Built as static files by python3 tools/build.py and tools/site.py. Stdlib only.
Maps drawn in Equal Earth from Natural Earth outlines, public domain.
No trackers, no external requests, no fonts fetched from anywhere.
"""


def opensearch() -> str:
    return (f'<?xml version="1.0"?><OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">'
            f'<ShortName>{E(SITE_NAME)}</ShortName><Description>{E(TAGLINE)}</Description>'
            f'<InputEncoding>UTF-8</InputEncoding>'
            f'<Image width="16" height="16" type="image/svg+xml">{SITE_URL}/icon.svg</Image>'
            f'<Url type="text/html" template="{SITE_URL}/search/?q={{searchTerms}}"/>'
            f'</OpenSearchDescription>')


def feed(recs: list[dict]) -> str:
    rs = sorted(recs, key=lambda r: r["updated"], reverse=True)[:50]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entries = "".join(
        f'<entry><title>{E(r["names"]["name"])}</title><link href="{SITE_URL}/{url_of(r)}"/>'
        f'<id>{SITE_URL}/{url_of(r)}</id><updated>{E(r["updated"])}T00:00:00Z</updated>'
        f'<summary>{E(r["blurb"])}</summary></entry>' for r in rs)
    return (f'<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">'
            f'<title>{E(SITE_NAME)}</title><link href="{SITE_URL}/"/><link rel="self" href="{SITE_URL}/feed.xml"/>'
            f'<id>{SITE_URL}/</id><updated>{now}</updated><author><name>NaN</name></author>{entries}</feed>')


def dumps(recs: list[dict]):
    with open(SITE / "nodes.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    cols = ["id", "type", "name", "native", "aliases", "region", "countries", "from_year", "to_year",
            "living", "period", "form", "materials", "worn", "against", "restricted",
            "confidence", "needs_verification", "updated", "url", "blurb"]
    with open(SITE / "nodes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in recs:
            dt = r.get("dating") or {}
            ob = r.get("object") or {}
            w.writerow([r["id"], r["type"], r["names"]["name"], r["names"].get("native", ""),
                        " · ".join(r["names"].get("aliases", [])), " ".join(r["region"]),
                        " ".join(r.get("countries", []) or []),
                        dt.get("from_year", ""), dt.get("to_year", ""), bool(dt.get("living")),
                        dt.get("period", ""), ob.get("form", ""), " ".join(ob.get("materials", []) or []),
                        " ".join(ob.get("worn", []) or []),
                        " ".join(a["harm"] for a in r.get("against", [])),
                        bool(r.get("restricted")), r["confidence"], r.get("needs_verification", False),
                        r["updated"], f"{SITE_URL}/{url_of(r)}", r["blurb"]])


# ------------------------------------------------------------------ main

# /signs/ and /materials/ are BOTH the type index and the question page: the question page
# already lists every record of its type, so a second thinner index would only split the
# reader's attention. The loop below skips those two types.
QUESTION_PAGES = ("map", "time", "against", "wear", "signs", "materials", "numbers", "quiz")
FOLDED = {"motif", "material"}


def main() -> int:
    if not (API / "nodes.json").exists():
        print("run tools/build.py first")
        return 1
    t0 = time.time()
    recs = jload(API / "nodes.json")["nodes"]
    by_id = {r["id"]: r for r in recs}
    sources = jload(API / "sources.json")
    src_by_id = {s["id"]: s for s in sources["sources"]}
    places = jload(API / "places.json")
    atlas = jload(API / "atlas.json")
    timeline = jload(API / "timeline.json")
    against = jload(API / "against.json")
    matter = jload(API / "matter.json")
    types = jload(API / "vocab" / "types.json")
    cov = jload(API / "coverage.json")

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    shutil.copytree(API, SITE / "api")
    shutil.copytree(ROOT / "schema", SITE / "schema")
    (SITE / "vendor").mkdir()
    core_js = VENDOR / "searchcore.js"
    if not core_js.exists():
        print("vendor/searchcore.js missing — copy it from a sibling project")
        return 1
    shutil.copy(core_js, SITE / "vendor" / "searchcore.js")

    # Pictures: only the files records name, and never at archive size.
    saved = 0
    for r in recs:
        for im in r.get("images", []):
            src = IMAGES / im["file"]
            if not src.exists():
                continue
            dst = SITE / "images" / im["file"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                from PIL import Image as _Im
                with _Im.open(src) as pic:
                    if max(pic.size) > 1600 or src.stat().st_size > 600_000:
                        pic = pic.convert("RGB")
                        pic.thumbnail((1600, 1600), _Im.LANCZOS)
                        pic.save(dst, "JPEG", quality=84, optimize=True, progressive=True)
                        saved += src.stat().st_size - dst.stat().st_size
                        continue
            except Exception:  # noqa: BLE001
                pass
            shutil.copy(src, dst)

    (SITE / "index.html").write_text(front_page(recs, by_id, types, atlas, timeline, against, cov), encoding="utf-8")
    (SITE / "wander.html").write_text(wander_page(recs), encoding="utf-8")
    for t in types["entries"]:
        if t["key"] in FOLDED:
            continue
        d = SITE / DIR_OF[t["key"]]
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(type_index(t, recs, by_id), encoding="utf-8")
    for r in recs:
        d = SITE / url_of(r)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(node_page(r, by_id, places["places"]), encoding="utf-8")

    # the Thai edition: the same front page, directories and records under /th/
    global LANG
    LANG = "th"
    tdir = SITE / "th"
    tdir.mkdir()
    (tdir / "index.html").write_text(front_page(recs, by_id, types, atlas, timeline, against, cov), encoding="utf-8")
    (tdir / "wander.html").write_text(wander_page(recs), encoding="utf-8")
    for t in types["entries"]:
        if t["key"] in FOLDED:
            continue
        d = tdir / DIR_OF[t["key"]]
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(type_index(t, recs, by_id), encoding="utf-8")
    for r in recs:
        d = tdir / url_of(r)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(node_page(r, by_id, places["places"]), encoding="utf-8")
    LANG = "en"

    (SITE / "sources").mkdir(exist_ok=True)
    (SITE / "sources" / "index.html").write_text(sources_page(sources), encoding="utf-8")
    (SITE / "coverage").mkdir(exist_ok=True)
    (SITE / "coverage" / "index.html").write_text(coverage_page(cov, atlas), encoding="utf-8")

    ctx = dict(page=page, recs=recs, by_id=by_id, atlas=atlas, timeline=timeline, against=against,
               matter=matter, places=places, cov=cov, site_url=SITE_URL, E=E, clip=clip,
               path_of=PATH_OF, dir_of=DIR_OF, year_label=year_label, href=table_href, time_rows=time_rows)
    built = {
        "map": pages.map_page(**ctx),
        "time": pages.time_page(**ctx),
        "against": pages.against_page(**ctx),
        "wear": pages.wear_page(**ctx),
        "materials": pages.material_page(**ctx),
        "signs": pages.signs_page(**ctx),
        "numbers": pages.numbers_page(**ctx),
        "quiz": pages.quiz_page(quiz=jload(DATA / "vocab" / "quiz.json"), **ctx),
    }
    for name, html_text in built.items():
        d = SITE / name
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(html_text, encoding="utf-8")

    docs = jload(BUILD / "searchdocs.json")["docs"]
    (SITE / "search").mkdir(exist_ok=True)
    (SITE / "search" / "index.html").write_text(search_page(docs), encoding="utf-8")
    groups = []
    p = DATA / "search" / "amulets.thesaurus.json"
    if p.exists():
        groups += jload(p).get("groups", [])
    (SITE / "search" / "tables.json").write_text(json.dumps({"groups": groups, "words": []}, ensure_ascii=False),
                                                 encoding="utf-8")

    extra = list(QUESTION_PAGES) + ["places", "search", "sources", "coverage"]
    (SITE / "llms.txt").write_text(llms_txt(recs, cov), encoding="utf-8")
    (SITE / "llms-full.txt").write_text(llms_full(recs, src_by_id), encoding="utf-8")
    (SITE / "sitemap.xml").write_text(sitemap(recs, extra), encoding="utf-8")
    (SITE / "robots.txt").write_text(robots(), encoding="utf-8")
    (SITE / "opensearch.xml").write_text(opensearch(), encoding="utf-8")
    (SITE / "feed.xml").write_text(feed(recs), encoding="utf-8")
    (SITE / "manifest.webmanifest").write_text(manifest(), encoding="utf-8")
    (SITE / "humans.txt").write_text(humans_txt(recs, cov), encoding="utf-8")
    fleet.decorate(SITE, "amulet-atlas")
    wk = SITE / ".well-known"
    wk.mkdir(exist_ok=True)
    (wk / "ai.txt").write_text(ai_txt(cov), encoding="utf-8")
    (SITE / "ai.txt").write_text(ai_txt(cov), encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    (SITE / "icon.svg").write_text(icon_svg(), encoding="utf-8")
    if CARDS_DIR.exists() and any(CARDS_DIR.iterdir()):
        shutil.copytree(CARDS_DIR, SITE / "cards")
    dumps(recs)

    n_html = sum(1 for _ in SITE.rglob("*.html"))
    leaks = [p for p in SITE.rglob("*") if p.is_file() and p.suffix in (".html", ".json", ".txt", ".xml", ".csv", ".jsonl")
             and "/Users/" in p.read_text(encoding="utf-8", errors="ignore")]
    if leaks:
        print("REFUSED: host paths in", [str(x.relative_to(SITE)) for x in leaks][:5])
        return 2
    print(f"site: {n_html} pages · {len(recs)} records · {atlas['countries']} countries · "
          f"{places['count']} places · {timeline['count']} dated · {saved/1e6:.0f} MB saved on pictures · "
          f"{SITE} · {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
