# 종목 삭제 (편집 토글) — 설계

작성일: 2026-06-22

## 목적
로그인 유저가 포트폴리오의 개별 보유 종목을 직접 삭제할 수 있게 한다.
현재는 스크린샷으로 보유 전체를 통째로 교체하는 방법뿐이라, 한 종목만 정리하려면
전체를 다시 캡처해야 한다. 삭제 기능이 이를 보완한다.

## 범위 (MVP)
- **삭제만.** 수량/평가금액 수동 편집, 종목 추가, 일괄 선택 삭제는 범위 밖(YAGNI).

## 위치 & 동작
`ui/pages/portfolio.py`의 `pf=holdings`("전체 보유종목") 뷰에 **"편집" 토글**을 추가한다.

- **편집 OFF (기본)**: 기존 읽기 전용 HTML 패널(`_holdings_panel_html`) 그대로. 화면 변화 없음.
- **편집 ON**: 상호작용 리스트로 전환. 저장 원본인 `st.session_state["brokerage_holdings"]`를
  순서대로 순회하며 각 행에 `종목명 · 평가금액 · 🗑` 표시.

## 삭제 흐름 (실수 방지 2단계)
1. 행의 🗑 클릭 → 그 행만 `"삭제할까요? [삭제 확정] [취소]"`로 전환.
   대기 상태는 `st.session_state["_pending_delete_holding"] = <index>`로 추적.
2. **삭제 확정**:
   - 해당 인덱스를 `brokerage_holdings`에서 제거(원본 리스트 직접 조작).
   - `st.session_state["brokerage_holdings"]` 갱신.
   - **`core.accounts.save_portfolio`로 영속화** — 기존 포트폴리오 이름·현금 유지
     (스크린샷 적용 경로와 동일 패턴). 안 하면 하드 nav(`?_user=`) 후 옛 보유로 복원됨.
   - `_pending_delete_holding` 클리어 → `st.rerun()`.
3. **취소**: `_pending_delete_holding`만 클리어 → `st.rerun(scope="fragment")` 또는 rerun.

## 핵심 설계 포인트
- **인덱스 기반 삭제**: 정렬·가공된 `positions`가 아니라 원본 `brokerage_holdings`를 직접
  순회·삭제하여 매핑이 모호하지 않게 한다(동일 티커 중복도 안전).
- **영속화 필수**: 세션만 바꾸면 nav 후 되돌아온다(기존에 고친 스크린샷 버그와 동일 함정).
- **마지막 1종목 삭제**: 빈 배열이 되면 `render()`가 온보딩으로 보낸다. 편집 리스트에
  안내문("마지막 종목을 지우면 온보딩으로 돌아갑니다") 노출.
- 자산 여정·진단·총액은 모두 `brokerage_holdings`에서 파생 → 삭제 즉시 자동 반영.

## 영향 범위
- 변경: `ui/pages/portfolio.py` (`pf=holdings` 분기 + 편집 리스트 렌더 헬퍼 1개).
- 재사용: `core.accounts.save_portfolio`, `get_portfolios`.
- 신규 함수: `_render_holdings_editor(positions, key)` 정도 1개.

## 테스트
- 단위: 인덱스 삭제 후 `brokerage_holdings`/`save_portfolio` 결과 검증
  (격리 계정 저장소에 종목 3개 저장 → 1개 삭제 → 2개 남고 영속화, 포트폴리오 중복 없음).
- 수동/구동: 앱에서 편집 토글 → 삭제 확정 → 총액·여정 즉시 갱신 + 하드 nav 후 유지 확인.
