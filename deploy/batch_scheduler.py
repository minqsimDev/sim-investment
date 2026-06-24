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


def _snapshot() -> None:
    """장중 시세 스냅샷 — fetch_all 호출로 quotes 테이블을 따뜻하게 유지(소스 장애 복원력)."""
    try:
        from data.fetcher import fetch_all
        fetch_all()
        _log("장중 시세 스냅샷 갱신(quotes)")
    except Exception as e:
        _log(f"스냅샷 예외: {e}")


def main() -> None:
    _log(f"스케줄러 기동 — 일배치 KST {_HOUR:02d}:00 · 장중 스냅샷 {_SNAPSHOT_SEC}s")
    last_full = None  # 일배치 중복 방지(날짜)
    if os.getenv("BATCH_RUN_ON_START", "1").strip().lower() in ("1", "true", "yes", "on"):
        _run()
        last_full = datetime.now(_KST).date()
    while True:
        time.sleep(_SNAPSHOT_SEC)
        now = datetime.now(_KST)
        if now.hour == _HOUR and last_full != now.date():
            _run()                 # 매일 1회 풀 배치(지표·리스크·컨센서스)
            last_full = now.date()
        elif _markets_open():
            _snapshot()            # 장중 시세 스냅샷(quotes 갱신)


if __name__ == "__main__":
    main()
