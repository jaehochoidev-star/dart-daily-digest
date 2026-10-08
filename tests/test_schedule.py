from datetime import datetime
import unittest
from digest import resolve_report_date


class ScheduleDateTests(unittest.TestCase):
    def test_schedule_slots(self):
        cases = {
            '2026-10-08T11:30:00Z': '2026-10-08',
            '2026-10-08T17:58:01Z': '2026-10-08',
            '2026-10-09T11:29:59Z': '2026-10-08',
            '2026-10-09T11:30:00Z': '2026-10-09',
            '2027-01-01T02:00:00+09:00': '2026-12-31',
            '2026-03-01T02:00:00+09:00': '2026-02-28',
        }
        for anchor, expected in cases.items():
            with self.subTest(anchor=anchor):
                self.assertEqual(resolve_report_date(None, anchor).isoformat(), expected)

    def test_rerun_preserves_original_date(self):
        self.assertEqual(str(resolve_report_date(None, '2026-10-08T17:58:01Z',
            datetime.fromisoformat('2026-10-12T22:00:00+09:00'))), '2026-10-08')

    def test_manual_date_wins(self):
        self.assertEqual(str(resolve_report_date('2026-10-06', '2026-10-08T17:58:01Z')), '2026-10-06')

    def test_manual_default_is_today(self):
        self.assertEqual(str(resolve_report_date(now=datetime.fromisoformat(
            '2026-10-09T02:58:00+09:00'))), '2026-10-09')

    def test_naive_anchor_rejected(self):
        with self.assertRaises(ValueError):
            resolve_report_date(None, '2026-10-09T02:58:00')
