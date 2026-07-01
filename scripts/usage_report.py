#!/usr/bin/env python3
"""화면/탭 사용률 리포트 — usage 로그(JSONL) 집계 출력.

실행(프로덕션, 컨테이너 안 — HOME=/data 가 로그 경로를 잡음):
    docker compose -f deploy/docker-compose.yml exec app python scripts/usage_report.py

'views' = 그 탭을 연 세션 수(세션당 1카운트), 'uniq' = 그 탭을 연 고유 사용자 수(익명 해시).
시장 탭 가지치기 판단용 — views/uniq 가 지속적으로 낮은 탭이 후보.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.usage_log import _FILE, summarize  # noqa: E402


def main() -> int:
    data = summarize()
    if not data:
        print(f"사용 로그 없음(아직 수집 전이거나 경로 상이): {_FILE}")
        return 0
    rows = sorted(data.items(), key=lambda kv: kv[1]["views"], reverse=True)
    print(f"로그: {_FILE}")
    print(f"{'page/tab':26}{'views':>8}{'uniq':>7}")
    print("-" * 41)
    for (page, tab), e in rows:
        print(f"{page + '/' + tab:26}{e['views']:>8}{len(e['users']):>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
