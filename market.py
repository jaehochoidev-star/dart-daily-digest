"""Optional KRX data through pykrx. Missing data is never reported as zero results."""
from datetime import date
import json
import os
from pathlib import Path
import sys


def collect(day):
    result = {'caps': {}, 'gainers': [], 'investors': {}, 'warnings': [],
              'gainers_status': 'unavailable', 'date': day}
    if date.fromisoformat(day).weekday() >= 5:
        result['gainers_status'] = 'closed'
        result['warnings'].append('주말: 시장 데이터 집계 대상이 아닙니다.')
        return result
    if not (os.environ.get('KRX_ID') and os.environ.get('KRX_PW')):
        result['warnings'].append('KRX 로그인 미설정: 시가총액·순매수·급등 종목을 수집하려면 Actions Secrets에 KRX_ID와 KRX_PW를 등록하세요.')
        return result
    from pykrx import stock
    stamp = day.replace('-', '')
    for market in ['KOSPI', 'KOSDAQ']:
        try:
            frame = stock.get_market_cap_by_ticker(stamp, market=market)
            if frame.empty or not (frame['시가총액'] > 0).any():
                raise ValueError('empty')
            result['caps'].update({str(ticker): int(row['시가총액']) for ticker, row in frame.iterrows()})
        except Exception:
            result['warnings'].append(f'{market} 시가총액 미수집 (휴장 또는 제공처 오류).')
    gainers = []
    gainers_ok = True
    for market in ['KOSPI', 'KOSDAQ']:
        try:
            frame = stock.get_market_ohlcv_by_ticker(stamp, market=market, alternative=False)
            if frame.empty or not (frame['거래량'] > 0).any():
                raise ValueError('empty')
            for ticker, row in frame[frame['등락률'] >= 5].iterrows():
                gainers.append({'name': stock.get_market_ticker_name(ticker) or str(ticker),
                                'ticker': str(ticker), 'market': market, 'change': float(row['등락률']),
                                'close': int(row['종가']), 'value': int(row['거래대금'])})
        except Exception:
            gainers_ok = False
            result['warnings'].append(f'{market} 급등 종목 미수집 (휴장 또는 제공처 오류).')
    result['gainers'] = sorted(gainers, key=lambda x: -x['change'])
    result['gainers_status'] = 'ok' if gainers_ok else 'partial' if gainers else 'unavailable'
    for investor in ['외국인', '기관합계', '개인']:
        rows = []
        ok = True
        for market in ['KOSPI', 'KOSDAQ']:
            try:
                frame = stock.get_market_net_purchases_of_equities(stamp, stamp, market, investor)
                if frame.empty:
                    raise ValueError('empty')
                rows.extend({'name': str(row['종목명']), 'ticker': str(ticker), 'market': market,
                             'value': int(row['순매수거래대금'])} for ticker, row in frame.iterrows()
                            if row['순매수거래대금'] > 0)
            except Exception:
                ok = False
                result['warnings'].append(f'{market} {investor} 순매수 미수집 (휴장 또는 제공처 오류).')
        result['investors'][investor] = {'status': 'ok' if ok else 'partial' if rows else 'unavailable',
                                         'rows': sorted(rows, key=lambda x: -x['value'])[:10]}
    return result


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(json.dumps(collect(sys.argv[1]), ensure_ascii=False, allow_nan=False), encoding='utf-8')
