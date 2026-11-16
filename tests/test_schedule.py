from datetime import datetime
import unittest
from unittest.mock import patch
from digest import resolve_report_date, main


class ScheduleDateTests(unittest.TestCase):
    def test_schedule_slots(self):
        cases = {
            '2026-10-08T11:00:00Z': '2026-10-08',
            '2026-10-08T17:58:01Z': '2026-10-08',
            '2026-10-09T10:59:59Z': '2026-10-08',
            '2026-10-09T11:00:00Z': '2026-10-09',
            '2027-01-01T02:00:00+09:00': '2026-12-31',
            '2026-03-01T02:00:00+09:00': '2026-02-27',
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

    def test_friday_delays_through_weekend(self):
        for anchor in ['2026-11-14T02:58:00+09:00',
                       '2026-11-14T22:00:00+09:00',
                       '2026-11-15T22:00:00+09:00',
                       '2026-11-16T19:59:59+09:00']:
            with self.subTest(anchor=anchor):
                self.assertEqual(str(resolve_report_date(None, anchor)), '2026-11-13')
        self.assertEqual(str(resolve_report_date(None, '2026-11-16T20:00:00+09:00')), '2026-11-16')

    def test_weekend_skips_all_collection_and_storage(self):
        for day in ['2026-11-14', '2026-11-15']:
            with self.subTest(day=day), patch('sys.argv', ['digest.py', '--date', day]), \
                    patch('digest.Dart') as dart, patch('digest.market_data') as market, \
                    patch('digest.save_report') as save:
                self.assertEqual(main(), 0)
                dart.assert_not_called()
                market.assert_not_called()
                save.assert_not_called()

    def test_delayed_friday_is_collected_and_saved(self):
        with patch('sys.argv', ['digest.py', '--scheduled-run-created-at',
                   '2026-11-14T22:00:00+09:00']), \
                patch.dict('os.environ', {'DART_API_KEY': 'test'}), \
                patch('digest.Dart'), patch('digest.market_data', return_value={}) as market, \
                patch('digest.collect', return_value={'sections': {}, 'warnings': []}) as collect, \
                patch('digest.save_report') as save:
            self.assertEqual(main(), 0)
            market.assert_called_once_with('2026-11-13')
            self.assertEqual(collect.call_args.args[0], '2026-11-13')
            save.assert_called_once()
