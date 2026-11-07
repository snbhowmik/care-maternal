"""Unit tests for the schedule engine. No database needed."""

from datetime import date, timedelta
from unittest import TestCase

from care_maternal.utils.schedule import (
    build_items,
    edd,
    gestational_age,
    ga_date,
    item_state,
    load_spec,
    parse_ga,
)

LMP = date(2026, 1, 1)


class ParseGaTests(TestCase):
    def test_weeks_and_days(self):
        self.assertEqual(parse_ga("13+6"), 97)
        self.assertEqual(parse_ga("36"), 252)

    def test_rejects_invalid_days(self):
        with self.assertRaises(ValueError):
            parse_ga("13+7")

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            parse_ga("thirteen")


class DatingTests(TestCase):
    def test_edd_is_lmp_plus_280_days(self):
        self.assertEqual(edd(LMP), LMP + timedelta(days=280))

    def test_gestational_age_on_a_date(self):
        self.assertEqual(gestational_age(LMP, LMP + timedelta(days=97)), (13, 6))


class WindowTests(TestCase):
    def setUp(self):
        self.items = {i["spec_id"]: i for i in build_items(LMP)}

    def test_nt_scan_window_is_11_to_13_6_weeks(self):
        nt = self.items["S-NT"]
        self.assertEqual(nt["due_from"], ga_date(LMP, "11"))
        self.assertEqual(nt["due_to"], ga_date(LMP, "13+6"))

    def test_td2_waits_for_td1(self):
        td2 = self.items["V-TD2"]
        self.assertIsNone(td2["due_from"])
        self.assertIn("Td-1", td2["waiting_on"])

    def test_td_booster_is_a_clinician_decision(self):
        boost = self.items["V-TDBOOST"]
        self.assertIsNone(boost["due_from"])
        self.assertIn("clinician", boost["waiting_on"])

    def test_every_spec_item_is_built_once(self):
        spec = load_spec()
        spec_ids = [i["id"] for b in spec["schedule"] for i in b["items"]]
        self.assertEqual(len(spec_ids), len(set(spec_ids)), "duplicate spec ids")
        self.assertEqual(sorted(spec_ids), sorted(self.items))


class StateTests(TestCase):
    def test_states(self):
        f, t = date(2026, 3, 1), date(2026, 3, 10)
        self.assertEqual(item_state(f, t, None, date(2026, 2, 28)), "upcoming")
        self.assertEqual(item_state(f, t, None, date(2026, 3, 5)), "due")
        self.assertEqual(item_state(f, t, None, date(2026, 3, 11)), "overdue")
        self.assertEqual(item_state(f, t, date(2026, 3, 11), date(2026, 3, 12)), "done")
        self.assertEqual(item_state(None, None, None, date(2026, 3, 5)), "waiting")
