AMULET ATLAS — the working guide
================================
Amulets, charms and talismans worldwide: what they are made of, where on the body or the
house they go, what their carriers say they stop, and when and where each one is
documented. Every hemisphere, from the Neolithic to a sticker on a phone.

Built the way wichaa.net is built: one JSON record per node of the practice, every field
carrying where it came from, every page saying what its neighbours are to it.

Live: https://nanobotco.github.io/amulet-atlas/


THE THREE THINGS A RECORD OWES A READER
  1. What it IS, physically, so you could pick it out of a tray.
  2. What it is FOR — in the words of the people who carry it, attributed by name. This
     project never writes that a charm works and never writes that it does not.
  3. WHERE and WHEN, precisely enough to put a dot on a map and a bar on a timeline.


THE RULE THAT OUTRANKS COMPLETENESS
Where a tradition restricts an object, a design or a rite to initiates, to one gender, to
one clan or to the dead, this atlas prints the restriction and stops. The `restricted`
block names who says so; the detail is not written anywhere in the record. Australia is
nearly blank on this map for exactly that reason, and /story/what-this-atlas-does-not-print
says so on the page rather than leaving a reader to wonder.


RUNNING IT
  python3 tools/validate.py        every record must pass
  python3 tools/build.py           records -> build/api + the search tables
  python3 tools/cards.py           the 1200x630 share cards (only the missing ones)
  python3 tools/site.py            build/site
  python3 tools/serve.py           http://127.0.0.1:8798
  python3 -m unittest discover -s tests
  ./publish.sh                     build into docs/, which GitHub Pages serves

Or double-click "Amulet Atlas.command" for the numbered menu.
Stdlib only, plus Pillow for the cards.

  BUILD_DRAFT=1 python3 tools/validate.py
turns "kin points at a record nobody has written yet" from an error into a warning, so the
site can be built while a set is still being drafted. Never set it for a publish.


REFRESHING THE INPUTS
  python3 tools/fetch_geo.py             Natural Earth outlines into data/geo/
  python3 tools/fetch_wiki.py <folder>   the verification corpus, and a source id for
                                         every article fetched, straight into
                                         data/sources/sources.json


WHERE THINGS LIVE
  AUTHORING.txt          the record spec, the voice rules, the cast list
  BRIEF.txt              what a drafting agent is handed before it writes
  schema/                node.schema.json — what a record must look like
  data/nodes/<type>/     the records, one JSON file each, filename = id
  data/vocab/            regions, against, materials, forms, worn, museums, tags,
                         recognizers, facets, types, quiz
  data/sources/          sources.json is the only place a citable id exists.
                         An author adds new ones to new-<batch>.json; build.py merges them.
  data/geo/world.json    Natural Earth 1:110m countries
  tools/worldmap.py      the Equal Earth projection every map is drawn in
  tools/viz.py           every drawn thing: maps, the timeline, the charts, the signs
  tools/pages.py         the eight pages that answer a question rather than list a type
  build/site/            the built site
  docs/                  what GitHub Pages serves (written by publish.sh)


THE PAGES THAT ANSWER A QUESTION
  /map/        every country the records name, in Equal Earth, plus every place as a point
  /time/       five thousand years on one axis that is not linear and says so
  /against/    what each charm's carriers say it stops, with the claimant named
  /wear/       where the thing goes — body, house, vehicle, boat, grave
  /materials/  what they are cut from, and what survives to be dug up
  /signs/      the signs, drawn for this atlas rather than traced
  /numbers/    the atlas measuring itself, including where it is thin
  /quiz/       six questions, a charm, and the arithmetic printed


CONVENTIONS THAT WILL BITE YOU IF YOU FORGET THEM
  Years are astronomical: 1 CE is 1, 1 BCE is 0, 500 BCE is -499, 3000 BCE is -2999.
    Stored that way so arithmetic across the era boundary works; printed the other way.
  countries[] is what the map is drawn from. Two you can source beat twelve you guessed.
  dating{} is what the timeline is drawn from. No dating, no bar.
  against[] is what /against/ is drawn from. No source, no row.
  Hours have THREE states: open, closed, and nobody published it. A day in neither list is
    unknown, and unknown is never rendered as closed.
  An accession number with no catalogue URL is a hard error. No URL, no number.
  The banned-word list in tools/validate.py is a hard error. A quotation is exempt, so
    quote and attribute instead of asserting.


FOR MACHINES
  /api/nodes.json  /api/index.json  /api/atlas.json  /api/timeline.json  /api/against.json
  /api/matter.json  /api/places.json  /api/kin.json  /api/coverage.json  /api/sources.json
  llms.txt  llms-full.txt  nodes.csv  nodes.jsonl  sitemap.xml  feed.xml  ai.txt


LICENCE
Records CC BY-SA 4.0. Country outlines Natural Earth, public domain. Pictures each carry
their own licence. The drawn signs are CC BY-SA 4.0 with the records. Code MIT. See LICENSE.

COMMERCIAL LICENCE
If share-alike doesn't fit your use — a corpus, a product, a model — a
commercial licence is available. Open an issue and say what you need:
https://github.com/NaNoBotCo/amulet-atlas/issues
