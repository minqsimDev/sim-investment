"""
네이버 금융 컨센서스 — 한국 종목 목표주가·투자의견(코스피·코스닥 광범위) + 최근 증권사 리포트.

Yahoo 컨센서스(yfinance)는 한국 대형주 일부만 커버하는 반면, 네이버는 증권사 리서치
컨센서스를 폭넓게 제공한다. 표시 보강용 — 계산/판단은 호출부에서 한다.

- fetch_naver_consensus(tickers): 종목별 컨센서스 목표가·투자의견·최근 리포트 증권사 수
- fetch_naver_reports(ticker):    종목별 최근 증권사 리포트(증권사·제목·날짜)
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

_H = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}
_TIMEOUT = 8
_DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{2}")


def _code(ticker: str) -> str:
    """'005930.KS' → '005930' (티커에서 거래소 접미사 제거)."""
    return str(ticker).split(".")[0].strip()


def _num(v):
    try:
        s = re.sub(r"[^\d.\-]", "", str(v))
        return float(s) if s not in ("", "-", ".") else None
    except (TypeError, ValueError):
        return None


def _opinion_label(mean) -> str:
    """네이버 recommMean(1~5, 높을수록 매수)을 기존 한글 라벨로 변환."""
    m = _num(mean)
    if m is None:
        return "—"
    if m >= 4.5: return "강력매수"
    if m >= 3.5: return "매수"
    if m >= 2.5: return "보유"
    if m >= 1.5: return "시장하회"
    return "매도"


def _fetch_one(ticker: str) -> dict:
    code = _code(ticker)
    out = {"ticker": ticker, "목표가_평균": None, "투자의견": "—",
           "리포트수": None, "컨센서스일": None}
    try:
        j = requests.get(f"https://m.stock.naver.com/api/stock/{code}/integration",
                         headers=_H, timeout=_TIMEOUT).json()
        c = j.get("consensusInfo") or {}
        out["목표가_평균"] = _num(c.get("priceTargetMean"))
        out["투자의견"] = _opinion_label(c.get("recommMean"))
        out["컨센서스일"] = c.get("createDate")
        res = j.get("researches") or []
        out["리포트수"] = len({x.get("bnm") for x in res if x.get("bnm")}) or None
    except Exception:
        pass
    return out


def fetch_naver_consensus(tickers: list[str]) -> pd.DataFrame:
    """네이버 컨센서스 — 종목별 목표가 평균·투자의견·최근 리포트 증권사 수(병렬)."""
    cols = ["ticker", "목표가_평균", "투자의견", "리포트수", "컨센서스일"]
    if not tickers:
        return pd.DataFrame(columns=cols)
    with ThreadPoolExecutor(max_workers=min(len(tickers), 10)) as ex:
        rows = [f.result() for f in as_completed({ex.submit(_fetch_one, t): t for t in tickers})]
    rows.sort(key=lambda r: tickers.index(r["ticker"]))
    return pd.DataFrame(rows, columns=cols)


def fetch_naver_reports(ticker: str, limit: int = 8) -> list[dict]:
    """종목별 최근 증권사 리포트(증권사·제목·날짜). 목표가는 리스트에 없어 컨센서스로 대체한다."""
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
            # 컬럼: 종목명 | 제목 | 증권사 | 첨부 | 작성일 | 조회
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
