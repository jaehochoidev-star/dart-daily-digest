"""Build portable static HTML, one permanent page per day and monthly archives."""
import argparse
from collections import defaultdict
from datetime import date
from html import escape
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).parent


def e(value):
    return escape(str(value if value is not None else '—'), quote=True)


def money(value):
    if value is None:
        return '미수집'
    if abs(value) >= 1e12:
        return f'{value / 1e12:,.1f}조'
    return f'{value / 1e8:,.0f}억'


def table(headers, rows):
    if not rows:
        return '<p class="empty">해당 공시 또는 조건에 맞는 종목이 없습니다.</p>'
    return '<div class="table-scroll"><table><thead><tr>' + ''.join(
        f'<th scope="col">{e(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(
        '<tr class="search-row">' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows
    ) + '</tbody></table></div>'


def report_body(report):
    sections = report['sections']
    count = sum(map(len, sections.values()))
    body = f'<div class="eyebrow">DAILY DISCLOSURE BRIEF</div><h1>장 마감 리포트</h1><p class="date-title">{e(report["date"])}</p>'
    if report.get('demo'):
        body += '<div class="notice">화면 확인용 가상 데이터입니다. 실제 공시·시세가 아닙니다.</div>'
    body += f'<div class="summary"><div><span>주요 공시</span><strong>{count}<small>건</small></strong></div><div><span>전체 조회 공시</span><strong>{report["total_disclosures"]}<small>건</small></strong></div><div><span>수집 상태</span><strong class="status">{"일부 미수집" if report.get("warnings") else "수집 완료"}</strong></div></div>'
    body += f'<p class="meta">수집 시각 {e(report["generated_at"])} · 당일 접수 공시 기준 · 시가총액 큰 순</p>'
    if report.get('warnings'):
        body += '<details class="notice" open><summary>수집 상태 안내</summary><ul>' + ''.join(
            f'<li>{e(w)}</li>' for w in report['warnings']) + '</ul></details>'
    body += '<label class="search-label" for="search">이 리포트에서 찾기</label><input id="search" type="search" placeholder="기업명, 공시명, 보고자 검색" autocomplete="off"><p id="search-state" role="status"></p>'
    body += '<nav class="section-links" aria-label="리포트 항목">' + ''.join(
        f'<a href="#section-{i}">{e(name)} <b>{len(rows)}</b></a>' for i, (name, rows) in enumerate(sections.items())) + '</nav>'
    for i, (name, rows) in enumerate(sections.items()):
        body += f'<section id="section-{i}"><h2>{e(name)} <span>{len(rows)}건</span></h2>'
        rendered = []
        is_holding = '약식보고' in name
        for row in rows:
            corp = f'<strong>{e(row["corp_name"])}</strong><small class="ticker">{e(row.get("stock_code", ""))}</small>'
            receipt = row['rcept_no']
            # Receipts are validated again when loading the archive.
            link = f'<a href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}" target="_blank" rel="noopener noreferrer" aria-label="{e(row["corp_name"])} 공시 원문 (새 탭)">원문 ↗</a>'
            cells = [corp, e(row['report_nm'])]
            if is_holding:
                detail = row.get('holding') or {}
                prev, current = detail.get('previous'), detail.get('current')
                change = f'{e(prev)}% → {e(current)}%' if prev is not None else '미수집'
                cells += [e(detail.get('reporter') or row.get('flr_nm')), change, e(detail.get('reason') or '원문 확인')]
            cells += [e(money(row.get('market_cap'))), link]
            rendered.append(cells)
        headers = ['기업명', '공시 내용'] + (['보고자', '지분 변동', '사유'] if is_holding else []) + ['시가총액', '링크']
        body += table(headers, rendered) + '</section>'
    market = report.get('market', {})
    body += '<section><h2>투자자 순매수 <span>KOSPI + KOSDAQ · 상위 10</span></h2><p class="meta">당일 순매수 거래대금 기준 · 양수 종목만 표시</p>'
    for name in ['외국인', '기관합계', '개인']:
        data = market.get('investors', {}).get(name, {})
        body += f'<h3>{name}</h3>'
        if data.get('status') != 'ok':
            body += '<p class="notice">일부 또는 전체 데이터 미수집. 휴장 여부와 제공처 상태를 확인하세요.</p>'
        if data.get('rows') or data.get('status') == 'ok':
            body += table(['기업명', '시장', '순매수 금액'], [
                [e(x['name']), e(x['market']), e(money(x['value']))] for x in data.get('rows', [])])
    body += '</section><section><h2>급등 종목 스캔 <span>당일 +5% 이상</span></h2>'
    status = market.get('gainers_status', 'unavailable')
    if status != 'ok':
        body += '<p class="notice">' + ('주말: 시장 데이터 집계 대상이 아닙니다.' if status == 'closed' else '일부 또는 전체 데이터 미수집. 결과 없음으로 판단할 수 없습니다.') + '</p>'
    if market.get('gainers') or status == 'ok':
        body += table(['기업명', '시장', '종가', '등락률', '거래대금'], [
            [e(x['name']), e(x['market']), f'{x["close"]:,}원', f'<span class="up">+{x["change"]:.2f}%</span>', e(money(x['value']))]
            for x in market.get('gainers', [])])
    return body + '</section>'


def shell(title, body, reports, prefix='', selected=''):
    months = sorted({r['date'][:7] for r in reports}, reverse=True)
    links = ''.join(f'<a href="{prefix}months/{m}.html">{m}</a>' for m in months)
    dates = ''.join(f'<a {"aria-current=page" if r["date"] == selected else ""} href="{prefix}days/{r["date"]}.html">{r["date"]}<span>{sum(map(len, r["sections"].values()))}건</span></a>' for r in reports[:60])
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} | DART Daily</title><link rel="stylesheet" href="{prefix}assets/style.css"><script defer src="{prefix}assets/search.js"></script></head><body>
<a class="skip" href="#main">본문 바로가기</a><header><a class="brand" href="{prefix}index.html"><span class="brand-mark">D</span>DART <b>DAILY</b></a><span class="header-note">매일 저녁, 공시를 한눈에</span><a href="{prefix}archive.html">전체 이력 ↗</a></header>
<div class="layout"><aside><p class="eyebrow">REPORT ARCHIVE</p><h2>날짜별 리포트</h2><a class="latest" href="{prefix}index.html">최신 리포트 →</a><nav aria-label="월별 이력" class="months">{links}</nav><nav class="dates" aria-label="최근 60일">{dates}</nav><p class="meta">이전 기록은 월별 이력에서<br>확인할 수 있습니다.</p></aside><main id="main">{body}</main></div>
<footer>출처: <a href="https://opendart.fss.or.kr">금융감독원 DART</a> · KRX (pykrx)<br>공시 제목 기반 자동 분류 · 정정공시 포함 · 미수집 값은 추정하지 않습니다.<br>매일 20:30 KST 실행 예정이며 GitHub Actions 상황에 따라 지연될 수 있습니다.</footer></body></html>'''


def archive_body(reports, title):
    body = f'<div class="eyebrow">REPORT ARCHIVE</div><h1>{e(title)}</h1><p class="meta">날짜를 선택하면 해당일의 리포트로 이동합니다.</p><div class="archive-grid">'
    for report in reports:
        count = sum(map(len, report['sections'].values()))
        body += f'<a class="archive-card" href="../days/{report["date"]}.html"><strong>{report["date"]}</strong><span>주요 공시 {count}건</span><small>{"일부 미수집" if report.get("warnings") else "수집 완료"}</small></a>'
    return body + '</div>'


def build(reports_root, output):
    reports = []
    for path in Path(reports_root).glob('*/report.json'):
        report = json.loads(path.read_text(encoding='utf-8'))
        day = date.fromisoformat(report['date']).isoformat()
        if path.parent.name != day:
            raise ValueError(f'날짜와 경로 불일치: {path}')
        for rows in report['sections'].values():
            for row in rows:
                if not (len(row['rcept_no']) == 14 and row['rcept_no'].isascii() and row['rcept_no'].isdigit()):
                    raise ValueError('잘못된 DART 접수번호')
        reports.append(report)
    reports.sort(key=lambda r: r['date'], reverse=True)
    output = Path(output)
    for part in ['assets', 'days', 'months']:
        (output / part).mkdir(parents=True, exist_ok=True)
    for path in (ROOT / 'assets').iterdir():
        shutil.copyfile(path, output / 'assets' / path.name)
    def write(path, text):
        (output / path).write_text(text, encoding='utf-8')
    groups = defaultdict(list)
    for report in reports:
        day = report['date']
        groups[day[:7]].append(report)
        write(f'days/{day}.html', shell(day, report_body(report), reports, '../', day))
    for month, items in groups.items():
        write(f'months/{month}.html', shell(month, archive_body(items, month + ' 리포트'), reports, '../'))
    archive = archive_body(reports, '전체 리포트 이력').replace('href="../days/', 'href="days/')
    write('archive.html', shell('전체 이력', archive, reports))
    latest = report_body(reports[0]) if reports else '<div class="eyebrow">DART DAILY</div><h1>첫 리포트를 기다리고 있습니다.</h1><p>매일 저녁 8시 30분, 당일 공시를 모아 이곳에 기록합니다.</p><p>운영자는 DART_API_KEY 등록 후 GitHub Actions에서 첫 수집을 실행하세요.</p>'
    write('index.html', shell('장 마감 리포트', latest, reports, selected=reports[0]['date'] if reports else ''))
    write('.nojekyll', '')
    print(f'{len(reports)}일의 정적 웹페이지 생성: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reports', default='reports')
    parser.add_argument('--output', default='site')
    args = parser.parse_args()
    build(args.reports, args.output)
