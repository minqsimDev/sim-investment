# 하이브리드 자산 추이 + SSOT 부채 해소 + 야간 예열 스킵

2026-07-08 · 승인됨

## 배경

- 매일 실제 총자산 스냅샷을 기록 중(`_record_today_snapshot` → `core.accounts.record_snapshot`, 하루 1포인트, 730일 보관)이지만 **읽는 곳이 없음**.
- 자산 추이 차트(`_portfolio_value_series` + `_asset_trend_svg`)는 PR #88 여정+목표엔진 통합 때 토글이 제거돼 **현재 죽은 코드** — 이번에 하이브리드 시리즈로 부활시킨다.
- `_portfolio_value_series`는 `data.session.cached_download`(yfinance 직행)를 써서 SSOT의 마지막 부채 1곳.
- `app.py` 캐시 예열 스레드가 야간·주말에도 25분마다 `force=True` 네트워크 갱신 — 낭비.

## 설계

### A. 하이브리드 자산 추이 (부활)

- `core/accounts.py`에 `get_snapshots(username) -> list[dict]` 리더 추가(`record_snapshot` 대칭, 읽기 전용).
- `portfolio.py`에 순수 함수 `_stitch_series(approx, snaps) -> (series, measured_from)`:
  - 첫 스냅샷 날짜 **이전** = 근사(현재수량×과거종가) 그대로.
  - 첫 스냅샷 날짜 **이후** = 실측만 사용, 미방문일은 직전 실측값 ffill.
  - 스냅샷 0개 → 근사 그대로 + `measured_from=None`(현행 동일, 배포 직후 안전).
  - 경계 점프는 그대로 노출(정직한 값).
- 렌더 위치: 자산 여정 섹션(`_render_asset_journey` 로그인 경로), `_goal_engine_block` 뒤
  "📈 자산 추이" expander. 기간 = 투자 시작일~현재(여정 컨텍스트와 동일).
  차트는 기존 `_asset_trend_svg`(골드 단일선) 재사용 + 캡션 "MM/DD부터 실측" 1줄.
- 게스트는 username 없음 → 추이 미노출(현행 동일).

### B. SSOT 부채 해소

- `_portfolio_value_series`를 `data.loader.batch_close_history`(DB-우선 → 라이브 폴백 → 자가 적재)
  경유로 교체. start→period 토큰 변환 후 받아 start 이후로 트림.
- 시그니처 단순화: `(positions, fx, start)` — 유일 호출처(추이 expander)가 시작일 기준이므로
  period 분기 제거. `_yf_history_symbol`(크립토 BTC→BTC-USD 정규화)은 유지.

### C. 야간 예열 스킵

- `app.py` `_bg` 루프에서 25분 재예열 직전 `any_open(["US", "KR"])` 체크 —
  둘 다 마감이면 `_warm(force=True)`·캐시 클리어 스킵.
- 부팅 1회 예열은 무조건 유지. 크립토는 09:00 배치 스냅샷 고정 정책이라 판단에서 제외.

### 범위 제외

- 입금·수익 분리 시각화(별도 브랜치), 실현손익·배당, 리밸런싱 후속 루프.

## 테스트

- `tests/test_stitch_series.py` 신규: 경계(이전=근사·이후=실측), ffill, 스냅샷 0개,
  근사 None, total≤0 스냅샷 무시.
- 기존 테스트 전체 통과 + dev 서버에서 추이 expander 실동작 확인.
