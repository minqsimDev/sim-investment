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
