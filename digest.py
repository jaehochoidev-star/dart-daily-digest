"""Collect one KST calendar day's disclosures; archive only complete DART lists."""
import argparse
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

KST = ZoneInfo('Asia/Seoul')
CATEGORIES = ['수주/계약', '지분 변동 — 약식보고', '실적 변동', '자본 변동', 'M&A/투자', '기타 주요경영사항']


def category(title):
    title = re.sub(r'\s+', '', title)
    if '단일판매' in title or '공급계약' in title:
        return CATEGORIES[0]
    if '대량보유' in title and '약식' in title:
        return CATEGORIES[1]
    if any(x in title for x in ['매출액또는손익', '영업실적', '잠정실적', '손익구조']):
        return CATEGORIES[2]
    if any(x in title for x in ['유상증자', '무상증자', '감자결정', '자기주식', '전환사채', '신주인수권부사채', '교환사채']):
        return CATEGORIES[3]
    if any(x in title for x in ['합병', '분할', '타법인주식', '영업양수', '영업양도', '주식교환', '주식이전']):
        return CATEGORIES[4]
    if any(x in title for x in ['투자판단관련', '주요경영사항']):
        return CATEGORIES[5]
    return None


class DartError(RuntimeError):
    pass


class Dart:
    def __init__(self, key):
        self.key = key
        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))

    def get(self, endpoint, **params):
        time.sleep(0.15)
        try:
            response = self.session.get(f'https://opendart.fss.or.kr/api/{endpoint}.json',
                                        params={'crtfc_key': self.key, **params}, timeout=(10, 40))
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            # Never expose a requests exception: its URL contains the API key.
            raise DartError('DART 통신 실패. 잠시 후 다시 실행하세요.') from None
        if data.get('status') == '013':
            return {'list': [], 'total_page': 0}
        if data.get('status') != '000':
            raise DartError('DART 응답 오류. 인증키·사용량·서비스 상태를 확인하세요.')
        return data

    def disclosures(self, day):
        rows = {}
        page = 1
        while True:
            data = self.get('list', bgn_de=day, end_de=day, page_no=page,
                            page_count=100, last_reprt_at='N', sort='date', sort_mth='asc')
            items = data.get('list', [])
            if not items and page > 1:
                raise DartError('DART 페이지가 누락되어 기록을 저장하지 않았습니다.')
            for item in items:
                if not re.fullmatch(r'\d{14}', item.get('rcept_no', '')):
                    raise DartError('DART 접수번호 형식 오류')
                rows[item['rcept_no']] = item
            if page >= int(data.get('total_page', 0)):
                return list(rows.values())
            page += 1


def holding_detail(item):
    current = item.get('stkrt', '')
    change = item.get('stkrt_irds', '')
    previous = None
    try:
        previous = str(Decimal(current.replace(',', '')) - Decimal(change.replace(',', '')))
    except (InvalidOperation, AttributeError):
        pass
    return {'reporter': item.get('repror', ''), 'current': current,
            'previous': previous, 'reason': item.get('report_resn', '')}


def market_data(day):
    # Isolate third-party network calls so an unresponsive provider cannot hang the report.
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'market.json'
        try:
            subprocess.run([sys.executable, str(Path(__file__).with_name('market.py')),
                            day, str(target)], check=True, timeout=240,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return json.loads(target.read_text(encoding='utf-8'))
        except (subprocess.SubprocessError, OSError, ValueError):
            return {'caps': {}, 'gainers': [], 'investors': {},
                    'warnings': ['시장 데이터 수집 실패: 시가총액·순매수·급등 종목을 확인할 수 없습니다.']}


def collect(day, dart, market):
    all_rows = dart.disclosures(day.replace('-', ''))
    sections = {name: [] for name in CATEGORIES}
    warnings = list(market.get('warnings', []))
    holdings = {}
    for item in all_rows:
        group = category(item['report_nm'])
        if not group:
            continue
        row = {k: item.get(k, '') for k in ['corp_name', 'corp_code', 'stock_code', 'report_nm', 'rcept_no', 'flr_nm']}
        row['market_cap'] = market.get('caps', {}).get(row['stock_code'])
        if group == CATEGORIES[1]:
            code = row['corp_code']
            if code not in holdings:
                try:
                    holdings[code] = {x['rcept_no']: x for x in dart.get('majorstock', corp_code=code).get('list', [])}
                except DartError:
                    holdings[code] = {}
            detail = holdings[code].get(row['rcept_no'])
            row['holding'] = holding_detail(detail) if detail else None
            if not detail:
                warnings.append(f"{row['corp_name']}: 약식보고 상세 미수집. 원문을 확인하세요.")
        sections[group].append(row)
    for rows in sections.values():
        rows.sort(key=lambda x: (-(x['market_cap'] or 0), x['corp_name'], x['rcept_no']))
    return {'schema_version': 1, 'date': day, 'generated_at': datetime.now(KST).isoformat(),
            'total_disclosures': len(all_rows), 'sections': sections,
            'market': market, 'warnings': list(dict.fromkeys(warnings))}


def save_report(report, root):
    day = date.fromisoformat(report['date']).isoformat()
    dest = Path(root) / day / 'report.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        previous = json.loads(dest.read_text(encoding='utf-8'))
        # A partial rerun must not replace a previously complete day's report.
        if not previous.get('warnings') and report.get('warnings'):
            raise DartError('기존 정상 기록을 보호했습니다. 일부 데이터 수집 실패 후 다시 실행하세요.')
    temp = dest.with_suffix('.tmp')
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(dest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=datetime.now(KST).date().isoformat())
    parser.add_argument('--reports', default='reports')
    args = parser.parse_args()
    try:
        day = date.fromisoformat(args.date)
        if day > datetime.now(KST).date():
            raise ValueError('미래 날짜는 조회할 수 없습니다.')
        key = os.environ.get('DART_API_KEY', '').strip()
        if not key:
            raise DartError('DART_API_KEY 환경변수 또는 GitHub Actions Secret을 설정하세요.')
        report = collect(day.isoformat(), Dart(key), market_data(day.isoformat()))
        save_report(report, args.reports)
        print(f"{day}: 주요 공시 {sum(map(len, report['sections'].values()))}건 저장")
        if report['warnings']:
            print('::warning::일부 보조 데이터 미수집. 웹페이지의 수집 상태를 확인하세요.')
    except (ValueError, DartError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
