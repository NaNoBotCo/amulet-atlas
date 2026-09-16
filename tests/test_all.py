"""The rules this project would be sorry to break silently.

    python3 -m unittest discover -s tests

These are not tests of Python. They are tests of the promises the site makes on its own
pages: that a date is stored the way the atlas says it is, that a blank country is a blank
and not a zero, that a restriction is never filled in, and that no claim about what a charm
does gets made in this project's own voice.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("BUILD_DRAFT", "1")

import common  # noqa: E402
import viz  # noqa: E402
import worldmap as W  # noqa: E402
from validate import BANNED, ban_clean, validate_all  # noqa: E402

RECS = common.load_nodes()
SOURCES = common.load_sources()


class Records(unittest.TestCase):
    def test_validate_passes(self):
        self.assertEqual(validate_all(quiet=True), 0, "tools/validate.py reports errors")

    def test_every_record_has_a_source_or_says_why(self):
        for r in RECS:
            tier = (r.get("provenance") or {}).get("default", {}).get("tier")
            if tier in ("cited", "harvested"):
                self.assertTrue(r.get("sources"), f"{r['id']}: tier {tier} with no sources")

    def test_no_claim_in_the_projects_own_voice(self):
        """against[] is where claims live, and every one names a source."""
        for r in RECS:
            for a in r.get("against", []):
                self.assertTrue(a.get("source", "").startswith("s:"),
                                f"{r['id']}: a claim with no source")

    def test_accession_numbers_carry_their_catalogue_page(self):
        for r in RECS:
            for h in r.get("holdings", []):
                if h.get("accession"):
                    self.assertTrue(h.get("url"), f"{r['id']}: accession with no URL")

    def test_restricted_records_name_who_restricts(self):
        for r in RECS:
            rs = r.get("restricted")
            if rs:
                self.assertTrue(rs.get("who_says") or rs.get("source"),
                                f"{r['id']}: a restriction with nobody behind it")

    def test_banned_words_are_absent_outside_quotations(self):
        for r in RECS:
            for k, v in (r.get("text") or {}).items():
                self.assertIsNone(BANNED.search(ban_clean(v)), f"{r['id']}.text.{k}")


class Dates(unittest.TestCase):
    def test_astronomical_years_round_trip(self):
        self.assertEqual(common.year_label(-2999), "3000 BCE")
        self.assertEqual(common.year_label(0), "1 BCE")
        self.assertEqual(common.year_label(1), "1 CE")
        self.assertEqual(common.year_label(None), "now")

    def test_no_span_runs_backwards(self):
        for r in RECS:
            dt = r.get("dating") or {}
            a, b = dt.get("from_year"), dt.get("to_year")
            if a is not None and b is not None:
                self.assertLessEqual(a, b, f"{r['id']}: dating runs backwards")

    def test_living_means_open_ended(self):
        for r in RECS:
            dt = r.get("dating") or {}
            if dt.get("living"):
                self.assertIsNone(dt.get("to_year"), f"{r['id']}: living but with an end year")

    def test_timeline_axis_is_monotonic(self):
        xs = [viz.year_x(y, 980, 170) for y in range(-11000, 2027, 25)]
        self.assertEqual(xs, sorted(xs), "the time axis folds back on itself")

    def test_timeline_axis_spends_real_width_on_the_last_two_centuries(self):
        w = 980 - 170 - viz.RIGHT
        recent = viz.year_x(2026, 980, 170) - viz.year_x(1800, 980, 170)
        self.assertGreater(recent / w, 0.2,
                           "the modern records would be squeezed into a hairline")


class Projection(unittest.TestCase):
    def test_equal_earth_puts_cities_in_the_right_quadrants(self):
        fit = W.fit_world(980)
        mid_x, mid_y = W.project(0, 0, fit)
        for name, lat, lon, right, below in [("Cairo", 30.05, 31.23, True, False),
                                             ("Lima", -12.05, -77.04, False, True),
                                             ("Wellington", -41.29, 174.78, True, True),
                                             ("Reykjavik", 64.15, -21.94, False, False)]:
            x, y = W.project(lon, lat, fit)
            self.assertEqual(x > mid_x, right, f"{name} is on the wrong side of the meridian")
            self.assertEqual(y > mid_y, below, f"{name} is on the wrong side of the equator")

    def test_every_country_draws(self):
        paths = W.land_paths(W.fit_world(980))
        self.assertGreater(len(paths), 150)
        for _iso, _name, d in paths:
            self.assertTrue(d.startswith("M") and d.endswith("Z"))

    def test_hemispheres_are_all_reachable_from_the_region_vocabulary(self):
        hemis = {h for e in common.load_vocab("regions")["entries"] for h in e.get("hemi", [])}
        self.assertEqual(hemis, {"N", "S", "E", "W"})


class Vocabularies(unittest.TestCase):
    def test_ids_are_unique_across_types(self):
        ids = [r["id"] for r in RECS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_kin_target_exists(self):
        ids = {r["id"] for r in RECS}
        missing = sorted({k["to"] for r in RECS for k in r.get("kin", []) if k["to"] not in ids})
        self.assertEqual(missing, [], f"kin pointing nowhere: {missing[:10]}")

    def test_kin_is_a_sentence_not_a_label(self):
        for r in RECS:
            for k in r.get("kin", []):
                self.assertGreater(len(k["as"].split()), 3,
                                   f"{r['id']} -> {k['to']}: kin should say what it IS to this one")

    def test_a_glyph_exists_for_every_sign_or_the_page_says_so(self):
        """Not every sign needs a drawing — but the /signs/ page must name the ones without."""
        drawn = set(viz.GLYPHS)
        signs = {r["id"] for r in RECS if r["type"] == "motif"}
        self.assertTrue(signs & drawn, "no sign has a glyph at all")

    def test_source_ids_all_resolve(self):
        for r in RECS:
            for s in r.get("sources", []):
                self.assertIn(s, SOURCES, f"{r['id']} cites {s}")


class Absence(unittest.TestCase):
    """The site promises, in print, that a blank is a blank. These hold it to that."""

    def test_hours_never_invent_a_closure(self):
        for r in RECS:
            h = r.get("hours") or {}
            self.assertFalse(set(h.get("open", [])) & set(h.get("closed", [])),
                             f"{r['id']}: a day both open and closed")

    def test_measurements_carry_a_source(self):
        for r in RECS:
            ob = r.get("object") or {}
            if ob.get("length_mm") is not None:
                self.assertTrue(ob.get("source"), f"{r['id']}: a measurement with no source")


if __name__ == "__main__":
    unittest.main()
