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


def _seconds_until_next() -> float:
    now = datetime.now(_KST)
    nxt = now.replace(hour=_HOUR, minute=0, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


def main() -> None:
    _log(f"스케줄러 기동 — 매일 KST {_HOUR:02d}:00 실행")
    if os.getenv("BATCH_RUN_ON_START", "1").strip().lower() in ("1", "true", "yes", "on"):
        _run()
    while True:
        wait = _seconds_until_next()
        _log(f"다음 실행까지 {wait / 3600:.1f}h 대기")
        time.sleep(wait)
        _run()


if __name__ == "__main__":
    main()
