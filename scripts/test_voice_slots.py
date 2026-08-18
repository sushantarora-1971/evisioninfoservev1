#!/usr/bin/env python3
"""
Offline tests for the voice agent's slot arithmetic.

No credentials, no network, no database — the calendar is a list of busy blocks
passed straight in. Run it after changing anything in voice_booking.py:

    python scripts/test_voice_slots.py
"""

import os
import sys
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import voice_booking as vb   # noqa: E402

IST = vb.IST

MON = date(2026, 8, 17)      # a Monday
SAT = date(2026, 8, 22)
SUN = date(2026, 8, 23)


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)


class WorkingHours(unittest.TestCase):
    def test_sunday_is_closed(self):
        self.assertIsNone(vb.working_window(SUN))

    def test_saturday_closes_early(self):
        _, closes = vb.working_window(SAT)
        self.assertEqual(closes.hour, vb.SAT_END)

    def test_nothing_offered_after_closing(self):
        starts = vb.free_starts(MON, 30, "any", at(MON, 8), [])
        self.assertTrue(all(s.hour < vb.DAY_END for s in starts))
        self.assertLessEqual(starts[-1] + timedelta(minutes=30), at(MON, vb.DAY_END))


class LeadTime(unittest.TestCase):
    def test_never_offers_something_imminent(self):
        now = at(MON, 10, 5)
        starts = vb.free_starts(MON, 30, "any", now, [])
        self.assertTrue(starts)
        self.assertGreaterEqual(starts[0], now + timedelta(hours=vb.LEAD_TIME_HOURS))

    def test_starts_land_on_the_half_hour(self):
        starts = vb.free_starts(MON, 30, "any", at(MON, 9, 7), [])
        self.assertTrue(all(s.minute in (0, 30) for s in starts))


class Buffers(unittest.TestCase):
    def test_keeps_clear_of_an_existing_meeting(self):
        busy = [(at(MON, 14), at(MON, 15))]
        starts = vb.free_starts(MON, 30, "any", at(MON, 6), busy)
        # 14:30 sits inside the meeting; 15:00 is inside the 15-minute buffer.
        self.assertNotIn(at(MON, 14, 30), starts)
        self.assertNotIn(at(MON, 15), starts)
        self.assertIn(at(MON, 15, 30), starts)

    def test_does_not_end_on_top_of_the_next_meeting(self):
        busy = [(at(MON, 15), at(MON, 16))]
        starts = vb.free_starts(MON, 30, "any", at(MON, 6), busy)
        self.assertNotIn(at(MON, 14, 30), starts)   # would end exactly at 15:00

    def test_longer_meeting_needs_a_longer_gap(self):
        busy = [(at(MON, 11), at(MON, 12)), (at(MON, 13, 15), at(MON, 17))]
        # Buffers leave 12:15–13:00 clear, so a 12:30 start fits a 30-minute
        # meeting exactly and a 45-minute one overruns into the next buffer.
        self.assertIn(at(MON, 12, 30), vb.free_starts(MON, 30, "any", at(MON, 6), busy))
        self.assertNotIn(at(MON, 12, 30), vb.free_starts(MON, 45, "any", at(MON, 6), busy))


class PartOfDay(unittest.TestCase):
    def test_morning_stays_in_the_morning(self):
        starts = vb.free_starts(MON, 30, "morning", at(MON, 5), [])
        self.assertTrue(starts)
        self.assertTrue(all(s.hour < 13 for s in starts))

    def test_afternoon_stays_in_the_afternoon(self):
        starts = vb.free_starts(MON, 30, "afternoon", at(MON, 5), [])
        self.assertTrue(all(13 <= s.hour < 17 for s in starts))


class Spread(unittest.TestCase):
    def test_offers_at_most_three(self):
        _, starts = vb.find_slots(MON, 30, "any", at(MON, 5), [])
        self.assertEqual(len(starts), 3)

    def test_options_are_not_consecutive(self):
        _, starts = vb.find_slots(MON, 30, "any", at(MON, 5), [])
        gaps = [(b - a).total_seconds() / 60 for a, b in zip(starts, starts[1:])]
        self.assertTrue(all(g > vb.GRID_MINUTES for g in gaps), gaps)

    def test_returns_everything_when_only_two_are_open(self):
        busy = [(at(MON, 10), at(MON, 16)), (at(MON, 18), at(MON, 19))]
        _, starts = vb.find_slots(MON, 30, "any", at(MON, 5), busy)
        self.assertEqual(starts, [at(MON, 16, 30), at(MON, 17)])


class RollForward(unittest.TestCase):
    def test_full_day_rolls_to_the_next(self):
        busy = [(at(MON, 0), at(MON, 23, 59))]
        day, starts = vb.find_slots(MON, 30, "any", at(MON, 5), busy)
        self.assertEqual(day, MON + timedelta(days=1))
        self.assertTrue(starts)

    def test_sunday_request_rolls_to_monday(self):
        day, starts = vb.find_slots(SUN, 30, "any", at(SUN, 5), [])
        self.assertEqual(day, SUN + timedelta(days=1))
        self.assertTrue(starts)

    def test_widens_part_of_day_before_changing_the_date(self):
        busy = [(at(MON, 9), at(MON, 13))]          # whole morning gone
        day, starts = vb.find_slots(MON, 30, "morning", at(MON, 5), busy)
        self.assertEqual(day, MON, "should stay on the requested day")
        self.assertTrue(all(s.hour >= 13 for s in starts))

    def test_reports_nothing_when_the_week_is_full(self):
        busy = [(at(MON, 0), at(MON + timedelta(days=6), 23, 59))]
        day, starts = vb.find_slots(MON, 30, "any", at(MON, 5), busy)
        self.assertIsNone(day)
        self.assertEqual(starts, [])


class Offers(unittest.TestCase):
    def test_slot_id_round_trips(self):
        held = vb.hold_slots([at(MON, 15)], 30, "conv-1")
        slot_id, start = held[0]
        offer = vb.take_offer(slot_id)
        self.assertEqual(offer["start"], start)
        self.assertEqual(offer["duration"], 30)

    def test_unknown_slot_id_is_rejected(self):
        self.assertIsNone(vb.take_offer("not-a-real-id"))
        self.assertIsNone(vb.take_offer(""))

    def test_expired_offer_is_rejected(self):
        slot_id, _ = vb.hold_slots([at(MON, 15)], 30)[0]
        vb.OFFERS[slot_id]["expires"] = 0
        self.assertIsNone(vb.take_offer(slot_id))

    def test_ids_are_opaque_not_timestamps(self):
        slot_id, start = vb.hold_slots([at(MON, 15, 30)], 30)[0]
        self.assertNotIn("15", slot_id)
        self.assertNotIn(str(start.year), slot_id)


class Spoken(unittest.TestCase):
    def test_reads_like_a_person(self):
        self.assertEqual(vb.spoken(at(MON, 15, 30)), "Monday 17 August at 3:30 PM")
        self.assertEqual(vb.spoken(at(MON, 10, 0)), "Monday 17 August at 10:00 AM")
        self.assertEqual(vb.spoken(at(MON, 12, 0)), "Monday 17 August at 12:00 PM")


if __name__ == "__main__":
    unittest.main(verbosity=2)
