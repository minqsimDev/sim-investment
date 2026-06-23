"""
네이버 금융 컨센서스 — 한국·미국 종목 목표주가·투자의견·기준일 (단일 소스).

· 한국(.KS/.KQ): m.stock.naver.com/api/stock/{6자리}/integration → consensusInfo + researches(증권사 리포트 수)
· 미국:          ac.stock.naver.com 로 reutersCode 해석(AAPL→AAPL.O) 후
                 api.stock.naver.com/stock/{reutersCode}/integration → consensusInfo
공통 필드: 목표가_평균 · 투자의견(recommMean 1~5) · 기준일(createDate). 한국만 커버리지(리포트수).
yfinance .info 를 대체 — 더 빠르고, '기준일'이 있어 신뢰도(staleness) 판단이 가능하다.

- fetch_naver_targets(tickers): 통합 컨센서스 DataFrame
- fetch_naver_reports(ticker):  한국 종목 최근 증권사 리포트(증권사·제목·날짜)
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

_H = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}
_TIMEOUT = 8
_DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{2}")

_KR_INTEGRATION = "https://m.stock.naver.com/api/stock/{code}/integration"
_US_INTEGRATION = "https://api.stock.naver.com/stock/{rc}/integration"
_AC_URL = "https://ac.stock.naver.com/ac"

_COLS = ["ticker", "목표가_평균", "투자의견", "의견점수", "기준일", "커버리지"]
_reuters_cache: dict[str, str | None] = {}   # 심볼 → reutersCode(또는 None) 프로세스 캐시


def _code(ticker: str) -> str:
    """'005930.KS' → '005930'."""
    return str(ticker).split(".")[0].strip()


def _is_us(ticker: str) -> bool:
    """한국 거래소 접미사(.KS/.KQ)가 없으면 미국으로 본다."""
    return not str(ticker).upper().endswith((".KS", ".KQ"))


def _num(v):
    try:
        s = re.sub(r"[^\d.\-]", "", str(v))
        return float(s) if s not in ("", "-", ".") else None
    except (TypeError, ValueError):
        return None


def _opinion_label(mean) -> str:
    """네이버 recommMean(1~5, 높을수록 매수)을 한글 라벨로."""
    m = _num(mean)
    if m is None:
        return "—"
    if m >= 4.5: return "강력매수"
    if m >= 3.5: return "매수"
    if m >= 2.5: return "보유"
    if m >= 1.5: return "시장하회"
    return "매도"


def _parse_consensus(ci: dict) -> dict:
    """consensusInfo(공통: priceTargetMean·recommMean·createDate) → 공통 필드."""
    ci = ci or {}
    return {
        "목표가_평균": _num(ci.get("priceTargetMean")),
        "투자의견":   _opinion_label(ci.get("recommMean")),
        "의견점수":   _num(ci.get("recommMean")),   # 산점도 Y축(1~5, 높을수록 매수)
        "기준일":     ci.get("createDate"),
    }


def _us_query_variants(symbol: str) -> list[str]:
    """미국 심볼 검색 변형. 'BRK-B'는 네이버 검색에서 안 잡혀 'BRK.B'·'BRKB'도 시도."""
    s = symbol.upper()
    out = [s]
    if "-" in s:
        out += [s.replace("-", "."), s.replace("-", "")]
    return out


def _resolve_us_reuters(symbol: str) -> str | None:
    """미국 심볼 → 네이버 reutersCode(예: AAPL→AAPL.O, ORCL→ORCL.K). 실패 시 None. 캐시."""
    if symbol in _reuters_cache:
        return _reuters_cache[symbol]
    rc = None
    norm = symbol.upper().replace("-", "")
    for q in _us_query_variants(symbol):
        try:
            r = requests.get(_AC_URL, params={"q": q, "target": "stock", "where": "nexearch"},
                             headers=_H, timeout=_TIMEOUT)
            items = (r.json() or {}).get("items") or []
        except Exception:
            items = []
        if not items:
            continue
        # code 가 심볼과 일치하는 항목 우선, 없으면 첫 항목
        pick = next((it for it in items if str(it.get("code", "")).upper().replace("-", "") == norm), items[0])
        rc = pick.get("reutersCode")
        if rc:
            break
    _reuters_cache[symbol] = rc
    return rc


def _fetch_one(ticker: str) -> dict:
    """단건 컨센서스(한/미 자동 분기)."""
    out = dict.fromkeys(_COLS)
    out["ticker"] = ticker
    out["투자의견"] = "—"
    try:
        if _is_us(ticker):
            rc = _resolve_us_reuters(_code(ticker))
            if not rc:
                return out
            j = requests.get(_US_INTEGRATION.format(rc=rc), headers=_H, timeout=_TIMEOUT).json()
            out.update(_parse_consensus(j.get("consensusInfo")))
            # 미국은 네이버가 애널리스트 수를 주지 않음 → 커버리지 None
        else:
            j = requests.get(_KR_INTEGRATION.format(code=_code(ticker)), headers=_H, timeout=_TIMEOUT).json()
            out.update(_parse_consensus(j.get("consensusInfo")))
            res = j.get("researches") or []
            out["커버리지"] = len({x.get("bnm") for x in res if x.get("bnm")}) or None
    except Exception:
        pass
    return out


def fetch_naver_targets(tickers: list[str]) -> pd.DataFrame:
    """통합 컨센서스 — 종목별 목표가 평균·투자의견·기준일·커버리지(KR). 병렬."""
    if not tickers:
        return pd.DataFrame(columns=_COLS)
    with ThreadPoolExecutor(max_workers=min(len(tickers), 10)) as ex:
        rows = [f.result() for f in as_completed({ex.submit(_fetch_one, t): t for t in tickers})]
    rows.sort(key=lambda r: tickers.index(r["ticker"]))
    return pd.DataFrame(rows, columns=_COLS)


def consensus_notes(tickers: list[str]) -> dict[str, str]:
    """종목별 네이버 컨센서스 → '팩트 노트' 문자열(라이브). {ticker: note}.
    DB-우선 경로는 호출부에서 consensus_notes_from_df(load_consensus_targets(...))를 쓴다."""
    return consensus_notes_from_df(fetch_naver_targets(tickers))


def consensus_notes_from_df(df) -> dict[str, str]:
    """컨센서스 DataFrame(fetch_naver_targets/DB 동일 컬럼) → {ticker: 팩트 노트}.

    하드코딩/작문 해설을 대체한다 — 전부 네이버 집계값(투자의견·목표가·커버리지·기준일).
    목표가가 없으면(비주식) 키를 넣지 않아 호출부가 중립 폴백을 쓰게 한다."""
    out: dict[str, str] = {}
    if df is None or df.empty:
        return out
    for _, r in df.iterrows():
        tk = r.get("ticker")
        tgt = r.get("목표가_평균")
        if tk is None or tgt is None or (isinstance(tgt, float) and pd.isna(tgt)):
            continue
        is_kr = str(tk).upper().endswith((".KS", ".KQ"))
        parts = []
        op = r.get("투자의견")
        if op and op != "—":
            parts.append(f"투자의견 {op}")
        parts.append(f"목표가 평균 {tgt:,.0f}원" if is_kr else f"목표가 평균 ${tgt:,.2f}")
        cov = r.get("커버리지")
        if cov is not None and not (isinstance(cov, float) and pd.isna(cov)):
            try:
                parts.append(f"커버리지 {int(cov)}곳")
            except (TypeError, ValueError):
                pass
        date = r.get("기준일")
        if date:
            parts.append(f"기준일 {date}")
        out[str(tk)] = " · ".join(parts)
    return out


_INDEX_URL = "https://m.stock.naver.com/api/index/{name}/basic"


def fetch_naver_index(name: str) -> dict | None:
    """네이버 금융 지수 시세(KOSPI·KOSDAQ 등) → {price, change_pct}. 실패 시 None.
    yfinance .info(지수는 ~15분 지연)를 대체 — 거래소 직결 포털 집계라 더 신선하고 정확
    (검증: 네이버 KOSPI 8,203.84/-9.99% ≈ yfinance 8,267/-9.46%, 2026-06-23)."""
    try:
        j = requests.get(_INDEX_URL.format(name=name), headers=_H, timeout=_TIMEOUT).json()
    except Exception:
        return None
    price = _num(j.get("closePrice"))
    if price is None:
        return None
    return {"price": price, "change_pct": _num(j.get("fluctuationsRatio"))}


_US_NEWS = "https://api.stock.naver.com/news/worldStock/{rc}"


def _fmt_news_dt(dt) -> str:
    """'20260623100000' → '2026-06-23'. 파싱 실패 시 '—'."""
    s = str(dt or "")
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return "—"


def _news_item(it: dict) -> dict | None:
    """네이버 해외종목 뉴스 한 건 → {뉴스, 언론사, 날짜, 링크}. 제목 없으면 None."""
    tit = (it or {}).get("tit")
    if not tit:
        return None
    oid, aid = it.get("oid"), it.get("aid")
    link = f"https://n.news.naver.com/mnews/article/{oid}/{aid}" if oid and aid else None
    return {"뉴스": tit, "언론사": it.get("ohnm") or "—", "날짜": _fmt_news_dt(it.get("dt")), "링크": link}


def latest_date_only(items: list[dict], date_key: str = "날짜") -> list[dict]:
    """가장 최신 날짜의 항목만 남긴다(뉴스·리포트 공통). 날짜 미상('—'/빈값)이면 원본 유지.
    날짜 포맷은 ISO(YYYY-MM-DD)·네이버 리포트(YY.MM.DD) 모두 사전식 정렬이 곧 시간순."""
    dates = [it.get(date_key) for it in items if it.get(date_key) and it.get(date_key) != "—"]
    if not dates:
        return items
    top = max(dates)
    return [it for it in items if it.get(date_key) == top]


def fetch_naver_us_news(symbol: str, limit: int = 8) -> list[dict]:
    """미국 종목 관련 뉴스(네이버 한국어). 증권사 리포트(한국 전용) 대신 미국 탭에서 쓴다."""
    rc = _resolve_us_reuters(_code(symbol))
    if not rc:
        return []
    try:
        j = requests.get(_US_NEWS.format(rc=rc), params={"pageSize": limit, "page": 1},
                         headers=_H, timeout=_TIMEOUT).json()
    except Exception:
        return []
    out = []
    for it in (j or []):
        n = _news_item(it)
        if n:
            out.append(n)
        if len(out) >= limit:
            break
    return out


def fetch_naver_reports(ticker: str, limit: int = 8) -> list[dict]:
    """한국 종목 최근 증권사 리포트(증권사·제목·날짜). 목표가는 리스트에 없어 컨센서스로 대체."""
    from bs4 import BeautifulSoup
    code = _code(ticker)
    url = ("https://finance.naver.com/research/company_list.naver"
           f"?searchType=itemCode&itemCode={code}")
    out: list[dict] = []
    try:
        r = requests.get(url, headers=_H, timeout=10)
        r.encoding = "euc-kr"
        soup = BeautifulSoup(r.text, "html.parser")
        tbl = soup.select_one("table.type_1")
        for tr in (tbl.select("tr") if tbl else []):
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            title  = tds[1].get_text(strip=True)
            broker = tds[2].get_text(strip=True)
            date   = tds[4].get_text(strip=True)
            if not (broker and title and _DATE_RE.fullmatch(date)):
                continue
            out.append({"증권사": broker, "리포트": title, "날짜": date})
            if len(out) >= limit:
                break
    except Exception:
        pass
    return out
