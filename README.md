# DART Daily — 장 마감 리포트

매일 **한국시간 20:30**에 GitHub Actions로 당일 공시를 수집하고 GitHub Pages에 게시합니다. `dart-financial-monitor`와 같은 날짜별 기록 보관 방식이며, PDF·텔레그램·이메일 발송은 하지 않습니다.

## 한 번만 설정

1. 이 코드를 저장소 기본 브랜치에 업로드합니다.
2. **Settings → Secrets and variables → Actions**에 `DART_API_KEY`를 등록합니다. 기존 `dart-financial-monitor`와 같은 키를 사용할 수 있지만, 저장소 Secret은 자동 공유되지 않으므로 새 저장소에도 등록해야 합니다.
3. **Settings → Pages → Source → GitHub Actions**를 선택합니다.
4. Actions의 저장소 쓰기 권한을 허용합니다. 브랜치 보호가 자동 기록 커밋을 막는 경우 봇 쓰기가 가능하도록 설정해야 합니다.
5. **Actions → DART 장 마감 리포트 → Run workflow**로 첫 실행합니다. `date`를 비우면 한국시간 오늘을 수집합니다.

시가총액·투자자 순매수·급등 종목도 수집하려면 같은 Actions Secrets에 **KRX_ID**, **KRX_PW**를 등록합니다. [KRX 정보데이터시스템](https://data.krx.co.kr)의 로그인 ID·비밀번호이며 DART 키와 별개입니다. 미설정 시 DART 공시만 정상 수집하고 시장 항목에는 로그인 미설정을 표시합니다. pykrx 실행 로그는 출력하지 않으므로 계정 정보가 리포트나 실행 로그에 노출되지 않습니다.

기본 게시 주소: https://jaehochoidev-star.github.io/dart-daily-digest/

## 화면과 이력

- 첫 화면: 가장 최근 날짜 리포트. 날짜별 고정 주소: `days/YYYY-MM-DD.html`.
- 왼쪽 날짜 목록, 월별 페이지, 전체 이력에서 과거 리포트 열람.
- 기업·공시명·보고자 검색, 휴대폰 대응, 원문 바로가기.
- 수주/계약, 약식 지분변동, 실적 변동, 자본 변동, M&A/투자, 기타 주요경영사항.
- 외국인·기관·개인의 순매수 거래대금 상위 10개 및 당일 +5% 이상 상승 종목.
- 원본은 `reports/YYYY-MM-DD/report.json`에 저장하고 Git에 커밋합니다. Pages 아티팩트가 만료되어도 원본 기록은 유지됩니다.
- 같은 날짜 재실행은 해당 날짜만 갱신합니다. 이미 정상 수집된 날을 일부 미수집 결과로 덮어쓰지 않습니다.
- 과거 날짜를 수집해도 최신 화면이 과거로 바뀌지 않습니다.

## 데이터 기준과 실패 처리

공시는 DART의 당일 접수 전체 목록을 모든 페이지에서 수집한 뒤 제목 규칙으로 주요 공시를 분류합니다. 정정공시를 포함하고 동일 접수번호만 중복 제거합니다. 비상장 공시도 포함되므로 시장 데이터가 없는 기업은 시가총액을 `미수집`으로 표시합니다.

약식보고의 보고자·지분·사유는 `majorstock` API 결과를 **동일 접수번호**로 연결합니다. 직전 지분율은 당기 지분율에서 증감 %p를 빼서 계산합니다. 해당 상세가 없으면 다른 공시 값으로 대체하지 않고 원문 확인을 안내합니다.

시장 데이터는 pykrx를 통해 KOSPI·KOSDAQ 당일 데이터를 조회합니다. 제공처 차단·변경·휴장 시 일부 항목을 수집하지 못할 수 있습니다. 당일 데이터가 비어도 ‘급등 종목 없음’으로 표시하지 않습니다. 주말은 시장 집계 제외이며 평일 빈 응답은 휴장인지 오류인지 단정하지 않습니다. 순매수 일부 시장만 수집되면 불완전 순위라고 표시합니다. 시가총액은 당일 값이며 이전 거래일 값으로 대체하지 않습니다.

DART 핵심 목록 조회 실패 시 새 기록이나 사이트를 배포하지 않고 기존 게시본을 유지합니다. 보조 데이터 실패 시 공시 리포트는 보관·배포하되 화면과 Actions 경고에 미수집 상태를 표시합니다. API 요청에는 재시도·제한시간을 적용하고, 시장 수집 전체는 4분으로 제한합니다. 인증키는 브라우저로 전달하지 않습니다.

휴일도 날짜별 기록을 남깁니다. 실행 이후 접수된 공시는 같은 날짜를 재실행하면 반영됩니다. GitHub 예약 실행은 지연될 수 있으며, 비활성 공개 저장소의 스케줄 중지 등은 Actions 설정에서 확인해야 합니다.

## 수동 실행과 재배포

- 과거 날짜 수집: Run workflow → `date`: `2026-10-06`처럼 입력.
- 웹페이지만 재생성: Run workflow → `rebuild_only` 선택. API 키 없이 기존 기록으로 재배포합니다.
- 첫 실행 이전 기록이나 첨부 PDF의 내용은 자동 수입하지 않습니다.
- `site/`는 빌드 결과이므로 Git에서 제외합니다. `reports/`는 보존합니다.

## 로컬 개발

Python 3.11 이상을 사용합니다.

```sh
pip install -r requirements.txt
python -m unittest discover -s tests -v
# DART_API_KEY를 환경변수로 설정한 뒤
python digest.py --date 2026-10-06
python build_site.py
python -m http.server 8000 --directory site
```

브라우저에서 `http://localhost:8000`을 엽니다. 수집 없이 `build_site.py`만 실행하면 첫 실행 안내 화면이 생성됩니다. API 키를 파일이나 소스에 넣지 마세요.

## 참고 문서

- [DART 공시 검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)
- [pykrx](https://github.com/sharebook-kr/pykrx)
- [GitHub Pages Actions 배포](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
