"""데이터 배치 스케줄러 — 사이드카 컨테이너로 상시 구동.

매일 KST 지정 시각(기본 06:00, 미국 장마감 후)에 `main.py`를 실행해 SQLite(market_data.db)의
기술지표·리스크 시그널·가격 스냅샷을 갱신한다. Streamlit 앱은 요청 기반이라 스스로 배치를
못 돌리므로, 같은 이미지·볼륨을 공유하는 이 프로세스가 작성기(writer) 역할을 한다.

env:
  BATCH_HOUR        실행 시각(KST 0~23, 기본 6)
  BATCH_RUN_ON_START 부팅 직후 1회 즉시 실행 여부(기본 1)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

_KST = timezone(timedelta(hours=9))
_HOUR = max(0, min(23, int(os.getenv("BATCH_HOUR", "6"))))


def _log(msg: str) -> None:
    print(f"[batch] {datetime.now(_KST):%Y-%m-%d %H:%M:%S KST} {msg}", flush=True)


def _run() -> None:
    _log("main.py 실행 시작")
    try:
        r = subprocess.run([sys.executable, "main.py"], cwd=os.path.dirname(os.path.dirname(__file__)) or ".")
        _log(f"main.py 종료코드 {r.returncode}")
    except Exception as e:  # 스케줄러는 절대 죽지 않는다 — 다음 주기 재시도
        _log(f"main.py 실행 예외: {e}")


_SNAPSHOT_SEC = max(60, int(os.getenv("SNAPSHOT_INTERVAL_SEC", "600")))   # 장중 시세 스냅샷 주기


def _markets_open() -> bool:
    try:
        from core.market_hours import any_open
        return any_open(["US", "KR"])
    except Exception:
        return False


def _snapshot(include_crypto: bool, label: str) -> None:
    """quotes 스냅샷 — config 유니버스 + 전 계정 보유를 라이브로 받아 DB 적재(복원력).
    include_crypto=True 면 크립토만(09:00 고정용), False 면 비크립토만(장중·마감 종가용)."""
    try:
        from data.fetcher import universe_tickers, snapshot_quotes
        from core.market_hours import market_of
        tks = [t for t in universe_tickers(include_accounts=True)
               if (market_of(t) == "CRYPTO") == include_crypto]
        n = snapshot_quotes(tks)
        _log(f"{label} 스냅샷 — {n}/{len(tks)} 적재(quotes)")
    except Exception as e:
        _log(f"{label} 스냅샷 예외: {e}")


def main() -> None:
    _log(f"스케줄러 기동 — 일배치 KST {_HOUR:02d}:00 · 크립토 09:00 · 장중/마감 스냅샷 {_SNAPSHOT_SEC}s")
    last_full = None     # 일배치 중복 방지(날짜)
    crypto_date = None   # 크립토 09:00 스냅샷 중복 방지(날짜)
    was_open = False     # 직전 틱 개장 여부 — open→closed 전환 시 종가 확정
    now = datetime.now(_KST)
    if os.getenv("BATCH_RUN_ON_START", "1").strip().lower() in ("1", "true", "yes", "on"):
        _run()
        last_full = now.date()
        _snapshot(include_crypto=True, label="크립토(기동)")   # 기동 즉시 크립토 1회
        if now.hour >= 9:
            crypto_date = now.date()                          # 9시 이후 기동이면 오늘분 완료로 간주
    while True:
        time.sleep(_SNAPSHOT_SEC)
        now = datetime.now(_KST)
        today = now.date()
        open_now = _markets_open()
        if now.hour == _HOUR and last_full != today:
            _run()                                   # 매일 1회 풀 배치(지표·리스크·컨센서스·종가)
            last_full = today
        if now.hour >= 9 and crypto_date != today:
            _snapshot(include_crypto=True, label="크립토 09:00")   # 매일 09:00 크립토 하루 고정
            crypto_date = today
        if open_now:
            _snapshot(include_crypto=False, label="장중")          # 장중 비크립토
        elif was_open:
            _snapshot(include_crypto=False, label="마감 종가")      # open→closed 전환 시 그날 종가 확정
        was_open = open_now


if __name__ == "__main__":
    main()
