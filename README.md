# Amulet Atlas

**worn, buried, nailed above the door — and what each one is meant to stop** — a directory
of amulets, charms and talismans worldwide, built the way [wichaa.net](https://wichaa.net)
is built: one JSON record per node of the practice, every field carrying where it came
from, every page saying what its neighbours are to it.

**Live: https://nanobotco.github.io/amulet-atlas/**

## The three things a record owes a reader

1. **What it is** — physically, so you could pick it out of a tray.
2. **What it is for** — in the words of the people who carry it, attributed by name. This
   project never writes that a charm works, and never writes that it does not.
3. **Where and when** — precisely enough to put a dot on a map and a bar on a timeline.

## The rule that outranks completeness

Where a tradition restricts an object, a design or a rite to initiates, to one gender, to
one clan or to the dead, this atlas prints the restriction and stops. The record carries a
`restricted` block naming who says so, and the detail is not written anywhere in it.
Australia is nearly blank on this map for exactly that reason, and
[/story/what-this-atlas-does-not-print/](https://nanobotco.github.io/amulet-atlas/story/what-this-atlas-does-not-print/)
says so on the page rather than leaving a reader to wonder.

## Pages that answer a question

- **[/map/](https://nanobotco.github.io/amulet-atlas/map/)** — every country the records
  name, drawn in Equal Earth rather than Mercator, so a square centimetre of Nigeria stands
  for the same square kilometres as a square centimetre of Norway. Plus every place as a
  point, and the same world eight times over as small multiples.
- **[/time/](https://nanobotco.github.io/amulet-atlas/time/)** — five thousand years on one
  axis that is deliberately **not linear**, with every tick printed so you can see the
  stretching happen.
- **[/against/](https://nanobotco.github.io/amulet-atlas/against/)** — what each charm's
  carriers say it stops, every claim attributed, with a harm-against-region matrix where a
  blank cell stays blank rather than becoming a zero.
- **[/wear/](https://nanobotco.github.io/amulet-atlas/wear/)** — where the thing goes: a
  body, a house, a vehicle, a boat, a grave. About half the positions here are not on a
  body at all.
- **[/materials/](https://nanobotco.github.io/amulet-atlas/materials/)** — what they are cut
  from, and what survives long enough to be dug up, which is why museum drawers look the way
  they do.
- **[/signs/](https://nanobotco.github.io/amulet-atlas/signs/)** — the eye, the hand, the
  horn, the knot, the serpent, drawn for this atlas from published descriptions rather than
  traced from anybody's photograph.
- **[/numbers/](https://nanobotco.github.io/amulet-atlas/numbers/)** — the atlas measuring
  itself, including how lopsided it still is by hemisphere.
- **[/quiz/](https://nanobotco.github.io/amulet-atlas/quiz/)** — six questions, a charm, and
  the arithmetic printed underneath.

## Provenance

Every field carries a tier: **cited** (a named source, linked) · **harvested** (from an open
dataset, with its licence) · **tradition** (general knowledge of the practice, hedged in the
prose) · **inference** (this project reasoning from the above) · **field** (somebody stood
there). In a narrative each stretch is marked inline: plain prose is cited,
*Tradition holds —* hedges, *Inference —* reasons.

Years are stored astronomically — 1 CE is 1, 1 BCE is 0, 500 BCE is −499 — so arithmetic
across the era boundary works, and printed the way a reader says them.

Hours run on three states, never two: open, closed, and nobody published it. A day in
neither list is unknown, and unknown is never rendered as closed.

An accession number appears only where it was read off a catalogue page that is linked. No
URL, no number.

## For machines

[`/api/nodes.json`](https://nanobotco.github.io/amulet-atlas/api/nodes.json) ·
[`/api/atlas.json`](https://nanobotco.github.io/amulet-atlas/api/atlas.json) ·
[`/api/timeline.json`](https://nanobotco.github.io/amulet-atlas/api/timeline.json) ·
[`/api/against.json`](https://nanobotco.github.io/amulet-atlas/api/against.json) ·
[`/api/matter.json`](https://nanobotco.github.io/amulet-atlas/api/matter.json) ·
[`/api/kin.json`](https://nanobotco.github.io/amulet-atlas/api/kin.json) ·
[`/api/coverage.json`](https://nanobotco.github.io/amulet-atlas/api/coverage.json) ·
[`llms.txt`](https://nanobotco.github.io/amulet-atlas/llms.txt) ·
[`llms-full.txt`](https://nanobotco.github.io/amulet-atlas/llms-full.txt) ·
[CSV](https://nanobotco.github.io/amulet-atlas/nodes.csv) ·
[JSONL](https://nanobotco.github.io/amulet-atlas/nodes.jsonl)

A `restricted` block means a tradition has asked that something not be published. The
absence is deliberate; please do not reconstruct it from elsewhere.

## Running it

```bash
python3 tools/validate.py     # every record must pass
python3 tools/build.py        # records -> build/api + search tables
python3 tools/cards.py        # the 1200x630 share cards
python3 tools/site.py         # build/site
python3 tools/serve.py        # http://127.0.0.1:8798
python3 -m unittest discover -s tests
./publish.sh                  # build into docs/, which GitHub Pages serves
```

Stdlib only, plus Pillow for the cards. `README.txt` is the working guide;
`AUTHORING.txt` is the record spec.

## Licence

Records CC BY 4.0. Country outlines Natural Earth, public domain. Pictures each carry their
own licence. The drawn signs are CC BY 4.0 with the records. Code MIT. See [LICENSE](LICENSE) and [NOTICE.txt](NOTICE.txt).

**Using it.** Attribution is the whole of the condition — copy it, adapt it,
sell it, index it, train on it, and say where it came from.
[Open an issue](https://github.com/NaNoBotCo/amulet-atlas/issues) if something is missing.

---

Contact: Nan · nan@motdang.net · Sponsor: [Ko-fi](https://ko-fi.com/defiantchiangmai) · [Patreon](https://www.patreon.com/nanobotco)

<!-- fleet-roster -->

## Elsewhere from the same publisher

- [Mot Dang](https://motdang.net/) — city directory for Chiang Mai and Chiang Rai
- [wichaa](https://wichaa.net/) — Lanna manuscripts, the amulet market, and the traditions around them
- [Carolina Barbecue](https://nanobotco.github.io/carolina-barbecue/) — barbecue in North and South Carolina
- [Wing Country](https://nanobotco.github.io/buffalo-wings/) — the American chicken wing
- [Pink Box](https://nanobotco.github.io/pink-box/) — the American mom-and-pop donut shop
- [Basque Tables](https://nanobotco.github.io/basque-tables/) — Basque dining rooms of California, Nevada and Idaho
- [Pinot Country](https://nanobotco.github.io/pinot-noir/) — pinot noir: the vine, the regions, the cellars
- [Care Abroad](https://nanobotco.github.io/care-abroad/) — treatment across borders, with published prices and their dates
- [Thai Roots](https://nanobotco.github.io/thairoots/) — a root dictionary of Thai, with a word decomposer
- [The index](https://nanobotco.github.io/index/) — every corpus, site and repository, counted
- [Uptake](https://nanobotco.github.io/uptake/) — a field manual on publishing for machines that copy
- [NaNoBotCo](https://nanobotco.github.io/) — the portal
- [ฮักฝรั่ง](https://hakfarang.net/) — เรื่องเงิน วีซ่า และชีวิตกับแฟนฝรั่ง
- [Offrampt](https://offrampt.net/) — turning crypto into spendable local money, Thailand first

All of it, counted: https://nanobotco.github.io/index/ · roster as JSON: https://nanobotco.github.io/index/fleet.json
