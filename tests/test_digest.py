import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from digest import CATEGORIES, Dart, DartError, category, collect, holding_detail, save_report
from build_site import build, report_body


def fixture(day='2026-10-06'):
    return {'schema_version': 1, 'date': day, 'generated_at': day + 'T19:00:00+09:00',
            'total_disclosures': 1, 'sections': {CATEGORIES[0]: [
                {'corp_name': '<script>alert(1)</script>', 'stock_code': '000001',
                 'report_nm': '단일판매ㆍ공급계약체결', 'rcept_no': '20261006000001', 'market_cap': None}]},
            'market': {}, 'warnings': ['시장 데이터 미수집']}


class Tests(unittest.TestCase):
    def test_pagination_and_receipt_dedup(self):
        dart = Dart('test')
        first = {'rcept_no': '20261006000001'}
        second = {'rcept_no': '20261006000002'}
        with patch.object(dart, 'get', side_effect=[{'total_page': 2, 'list': [first]},
                                                  {'total_page': 2, 'list': [first, second]}]):
            self.assertEqual(dart.disclosures('20261006'), [first, second])

    def test_missing_page_fails(self):
        dart = Dart('test')
        with patch.object(dart, 'get', side_effect=[{'total_page': 2, 'list': [{'rcept_no': '20261006000001'}]}, {'list': []}]):
            with self.assertRaises(DartError):
                dart.disclosures('20261006')

    def test_api_error_is_not_empty_success(self):
        dart = Dart('SECRET')
        with patch.object(dart.session, 'get') as get, patch('digest.time.sleep'):
            get.return_value.json.return_value = {'status': '020', 'message': 'SECRET'}
            with self.assertRaises(DartError) as error:
                dart.get('list')
            self.assertNotIn('SECRET', str(error.exception))
            get.return_value.json.return_value = {'status': '013'}
            self.assertEqual(dart.get('list')['list'], [])

    def test_classification(self):
        self.assertEqual(category('[기재정정] 단일판매ㆍ공급계약체결'), CATEGORIES[0])
        self.assertEqual(category('주식등의대량보유상황보고서(약식)'), CATEGORIES[1])
        self.assertEqual(category('투자판단관련주요경영사항(임상시험결과)'), CATEGORIES[5])
        self.assertEqual(category('매출액또는손익구조30%이상변동'), CATEGORIES[2])
        self.assertIsNone(category('주주총회소집결의'))

    def test_holding_percentage_points(self):
        detail = holding_detail({'stkrt': '6.81', 'stkrt_irds': '0.13'})
        self.assertEqual(detail['previous'], '6.68')
        self.assertIsNone(holding_detail({'stkrt': '-'})['previous'])

    def test_exact_receipt_holding_match(self):
        dart = Dart('test')
        item = {'corp_name': '테스트', 'corp_code': '00000001', 'report_nm': '대량보유상황보고서(약식)', 'rcept_no': '20261006000001'}
        with patch.object(dart, 'disclosures', return_value=[item]), patch.object(dart, 'get', return_value={
                'list': [{'rcept_no': '20261005000001', 'stkrt': '99'}]}):
            report = collect('2026-10-06', dart, {})
            self.assertIsNone(report['sections'][CATEGORIES[1]][0]['holding'])
            self.assertTrue(report['warnings'])

    def test_archives_rerun_and_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_report(fixture(), root / 'reports')
            save_report(fixture('2026-10-07'), root / 'reports')
            report = fixture()
            report['total_disclosures'] = 7
            save_report(report, root / 'reports')
            self.assertEqual(len(list((root / 'reports').glob('*/report.json'))), 2)
            build(root / 'reports', root / 'site')
            page = (root / 'site/index.html').read_text(encoding='utf-8')
            self.assertIn('<p class="date-title">2026-10-07</p>', page)
            self.assertNotIn('<script>alert(1)</script>', page)
            self.assertIn('&lt;script&gt;', page)
            self.assertTrue((root / 'site/months/2026-10.html').exists())
            self.assertIn('결과 없음으로 판단할 수 없습니다', page)

    def test_protect_complete_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = fixture()
            good['warnings'] = []
            save_report(good, tmp)
            with self.assertRaises(DartError):
                save_report(fixture(), tmp)
            self.assertFalse(json.loads((Path(tmp) / good['date'] / 'report.json').read_text(encoding='utf-8'))['warnings'])

    def test_empty_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(Path(tmp) / 'reports', Path(tmp) / 'site')
            self.assertIn('첫 리포트', (Path(tmp) / 'site/index.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
