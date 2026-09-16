#!/usr/bin/env python3
"""fetch_wiki.py — the verification corpus a drafting agent reads before it writes.

Plain-text copies of the Wikipedia articles this set cites, one file per article, each
carrying its title, URL and fetch date at the top. An agent reads these first and reaches
for the live web only when a fact is not in them.

    python3 tools/fetch_wiki.py <out-dir>

MediaWiki caps a full-text extract at one article per request, so this walks them one at
a time with a pause. Sixty-odd articles take about a minute.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://en.wikipedia.org/w/api.php"
UA = {"User-Agent": "amulet-atlas-build/0.1 (https://wichaa.net; nan@motdang.net) python-urllib"}

TITLES = """Amulet|Talisman|Apotropaic magic|Evil eye|Nazar (amulet)|Hamsa|Charm (object)|
Scarab (artifact)|Eye of Horus|Ankh|Djed|Tyet|Bes|Taweret|Heart scarab|Faience|Egyptian faience|Carnelian|
Cippi of Horus|Ancient Egyptian funerary practices|Lamashtu|Pazuzu|Incantation bowl|Ketef Hinnom|
Mesopotamian myths|Gorgoneion|Medusa|Fascinus|Bulla (amulet)|Lunula (amulet)|Magical gem|Curse tablet|
Byzantine amulets|Mezuzah|Tefillin|Kabbalah|Practical Kabbalah|Red string (Kabbalah)|Ta'wiz|Talismanic shirt|
Islamic amulets|Ayat al-Kursi|Hand of Fatima|Martenitsa|Mărțișor|Mjölnir|Thor's hammer|Adder stone|
Rowan|Witch bottle|Horseshoe|Cimaruta|Cornicello|Four-leaf clover|Rabbit's foot|Caul|Corn dolly|
Saint Brigid's cross|Hex sign|Concealed shoes|Saint Christopher|Miraculous Medal|Scapular|Agnus Dei (sacramental)|
Sacramental|Ex-voto|Votive offering|Rudraksha|Nazar battu|Navaratna|Yantra|Kavacha|Gau (amulet)|
Prayer flag|Dzi bead|Tibetan Buddhism|Fu (character)|Taoist talisman|Numismatic charm|Bagua|
Bujeok|Dol hareubang|Omamori|Ofuda|Omikuji|Maneki-neko|Daruma doll|Teru teru bōzu|Senninbari|Ema (Shinto)|
Ongon|Shamanism in Siberia|Thai Buddha amulet|Takrut|Palad khik|Sak Yant|Jimat|Anting-anting|Kris|
Milagro (votive)|Ojo de venado|Azabache|Figa (amulet)|Ekeko|Alasitas|Dreamcatcher|Hei-tiki|Hei matau|
Pounamu|Inuit religion|Tupilaq|Gris-gris (talisman)|Nkisi|Nkisi nkondi|Akua'ba|Agadez Cross|Cowrie shell|
Shell money|Ethiopian magic scroll|Coptic Christianity|Tattoo|Amulet MS 248|Challenge coin|Worry stone|
Crystal healing|Lucky charm|Luck|Good luck charm|Abracadabra|Sator Square|Magic square|Swastika|
Swastika (Germanic Iron Age)|Solomon's seal|Seal of Solomon|Hexagram|Cross|Crescent|Serpent (symbolism)|
Snake worship|Amber|Jade|Jade use in Mesoamerica|Turquoise|Lapis lazuli|Jet (gemstone)|Coral|
Iron|Cold iron|Silver|Amulet (Egypt)|W. M. Flinders Petrie|E. A. Wallis Budge|Pitt Rivers Museum|
British Museum|Metropolitan Museum of Art|Wellcome Collection|Museum of New Zealand Te Papa Tongarewa|
Musée du quai Branly – Jacques Chirac|Native American Graves Protection and Repatriation Act|
Australian Institute of Aboriginal and Torres Strait Islander Studies|Secret sacred|
Grand Bazaar, Istanbul|Khan el-Khalili|Quiapo Church|Mercado de Sonora|Witches' Market|
Akodessewa Fetish Market|Fushimi Inari-taisha|Sensō-ji|Insa-dong|Monastiraki|Via San Gregorio Armeno|
Barkhor|Thamel|Vodou|Haitian Vodou|West African Vodun|Fetishism|Juju|Mojo (African-American culture)|
Phylactery|Periapt|Mascot|Ward (law)|Alan Dundes|Frederick Thomas Elworthy|Edward Lovett|
Folklore of the United Kingdom|Apotropaic marks|Ancient Egyptian amulets"""


def main(out_dir: str) -> int:
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    titles = [t.strip() for t in TITLES.replace("\n", "").split("|") if t.strip()]
    got, missing, pages = [], [], []
    for t in titles:
        q = {"action": "query", "prop": "extracts|info", "explaintext": 1, "format": "json",
             "redirects": 1, "inprop": "url", "titles": t}
        req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers=UA)
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:  # noqa: BLE001
            missing.append(f"{t} ({e})")
            continue
        for pid, pg in d["query"]["pages"].items():
            if int(pid) < 0 or not pg.get("extract"):
                missing.append(pg.get("title") or t)
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", pg["title"].lower()).strip("-")
            (out / f"{slug}.txt").write_text(
                f"TITLE: {pg['title']}\nURL: {pg['fullurl']}\nFETCHED: {time.strftime('%Y-%m-%d')}\n\n{pg['extract']}\n",
                encoding="utf-8")
            got.append(pg["title"])
            pages.append((pg["title"], pg["fullurl"], slug))
        time.sleep(0.35)
    # Every fetched article becomes a source id the records may cite, written straight into
    # data/sources/sources.json. An author never invents one: if it is not here, it was not
    # read.
    import datetime
    sp = pathlib.Path(__file__).resolve().parent.parent / "data" / "sources" / "sources.json"
    existing = {}
    if sp.exists():
        existing = {x["id"]: x for x in json.loads(sp.read_text())["sources"]}
    today = datetime.date.today().isoformat()
    for title, url, slug in pages:
        existing.setdefault(f"s:wp-{slug}", {
            "id": f"s:wp-{slug}", "kind": "encyclopedia", "title": title,
            "publisher": "Wikipedia", "url": url, "accessed": today,
            "license": "CC BY-SA 4.0"})
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps({"note": "Every source any record may cite. Wikipedia articles land here from tools/fetch_wiki.py with the date they were read; anything else is added by hand or by an author in data/sources/new-*.json, which build.py merges.", "sources": [existing[k] for k in sorted(existing)]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(got)} fetched into {out} · {len(existing)} source ids · {len(missing)} missing: {missing}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    raise SystemExit(main(sys.argv[1]))
