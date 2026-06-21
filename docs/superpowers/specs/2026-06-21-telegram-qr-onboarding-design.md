# 텔레그램 QR 온보딩 + 유저별 위험 알림 — 설계

작성일: 2026-06-21 · 브랜치: `feat/telegram-qr-onboarding`

## 1. 목적
신규/기존 SIM 유저가 **앱에서 QR을 스캔**해 자기 텔레그램을 연결하고, 이후 **본인 포트폴리오 기준 개인화 위험 알림**을 받게 한다. 현재 단일 `chat_id`(운영자 1명) 구조를 다중 구독자(유저별)로 전환한다.

## 2. 범위
- **포함**: QR 딥링크 발급, 폴링 기반 자동 등록, 유저 계정에 chat_id 저장, 유저별 알림(시장 종합위험 + 본인 보유 급락), 다듬은 메시지 문구.
- **비포함(non-goals)**: 웹훅/상시 데몬, 텔레그램 외 채널, 유저별 알림 규칙 커스터마이즈 UI(기본 임계 고정), 실시간(분초) 등록.

## 3. 핵심 결정 (합의됨)
| 항목 | 결정 |
|---|---|
| 등록 방식 | **폴링** (공개 서버 불필요, Streamlit 현실에 적합) |
| 폴링 타이밍 | **연결화면 온디맨드** — QR 띄운 동안 `st.fragment`로 수 초마다 `getUpdates` |
| 알림 범위 | **유저별 개인화** (시장 위험 공통 + 본인 포트폴리오 보유 급락) |
| 구독자 저장 | 유저 계정 설정(`accounts.set_setting(username, "telegram_chat_id", …)`) |

## 4. 아키텍처 / 컴포넌트
- `core/telegram_link.py` (신규) — 온보딩 토큰·딥링크·QR.
  - `issue_link(username) -> (deeplink, qr_png_bytes)`: 단기 **nonce** 발급(랜덤, 10분 TTL) → `pending` 저장(`~/.siminvest_alerts.json`의 `pending: {nonce: {username, exp}}`) → 딥링크 `https://t.me/sim_investment_bot?start=<nonce>` → `qrcode` 라이브러리로 PNG.
  - `resolve_nonce(nonce) -> username | None`: 유효·미만료 시 username, 아니면 None(만료/소비 제거).
- `src/telegram_alert.py` (개편)
  - `poll_register(max_wait_s=0) -> list[(username, chat_id)]`: `getUpdates(offset)` 읽어 `/start <nonce>` 처리 → `resolve_nonce` → `accounts.set_setting(username,"telegram_chat_id",cid)` → 환영 발송 → nonce 소비 → offset 저장(중복 방지).
  - `run(verbose)`: **연결된 모든 유저**를 순회. 각 유저에 ① 시장 종합위험(공통 계산 1회) ② 본인 포트폴리오 보유 급락(아래) 평가·발송. 쿨다운/last_sent은 유저별로.
  - 구독자 열거: `accounts` 전체에서 `telegram_chat_id` 설정된 유저.
- `ui/pages/*` — 설정/연결 화면에 "텔레그램 알림 연결" 섹션(QR 표시 + 온디맨드 폴링 + "연결됨" 상태).

## 5. 데이터 모델
- 유저 계정(`~/.siminvest_accounts.json`) settings: `telegram_chat_id`, (선택) `telegram_rules`/`telegram_last_sent`.
- 봇 상태(`~/.siminvest_alerts.json`): `pending`(nonce→{username,exp}), `update_offset`(getUpdates 중복 방지). 단일 `chat_id` 필드는 제거(유저별 이전).
- 보유: `accounts.get_portfolios(username)` / 스냅샷의 보유 종목. 일일% = 지표 DB(`return_1d_pct`)·없으면 토스/yfinance.

## 6. 플로우 (시퀀스)
1. 유저가 앱에서 "텔레그램 알림 연결" → `issue_link(username)` → QR 표시.
2. 폰으로 QR 스캔 → 텔레그램 앱이 봇과 `/start <nonce>` 전송.
3. 연결화면이 `st.fragment`로 `poll_register()` 호출 → 해당 nonce 발견 → username에 chat_id 저장 → 환영 메시지.
4. 화면이 "연결됨 ✅"로 갱신(폴링 중지).
5. 이후 배치/CLI `run()`이 유저별 위험 평가·발송.

## 7. 보안
- nonce = 추측 불가 랜덤(>=128bit), 10분 TTL, 1회 사용 후 소비. username 평문 노출/위조 불가.
- 봇 토큰은 `.env`만. chat_id는 로컬 계정 파일(서버측).
- getUpdates offset 관리로 동일 업데이트 재처리 방지.

## 8. 테스트 (QR 전문가 에이전트)
- **자동(에이전트)**: nonce 발급/TTL/1회성, 딥링크 포맷, **QR PNG 디코딩**(생성 PNG를 디코더로 읽어 딥링크 일치 확인), `getUpdates` 응답 **모킹**한 `poll_register` 등록 로직, 유저별 `run()` 단위테스트(가짜 계정·포트폴리오·위험점수). 외부 텔레그램 전송은 모킹.
- **사람(당신)**: 실제 폰으로 QR 스캔→`/start` 왕복 1회(에이전트는 폰 없음). 봇 `@sim_investment_bot`로 마지막 확인.
- 의존성: `qrcode[pil]`(QR 생성), 테스트용 QR 디코더(`pyzbar` 또는 순수 검증). requirements 추가.

## 9. 위험/주의
- `getUpdates`와 (미래)웹훅은 상호배타 — 폴링 유지하는 한 웹훅 설정 금지.
- 동시 폴링 시 offset 경쟁: 온디맨드 폴링은 단일 사용자 흐름 가정. 운영 다중 동시 연결은 후속 과제.
- 1wk 등 토스 미지원 데이터는 알림 계산에 사용 안 함.
- 면책: 알림은 "참고 정보·판단은 직접" 유지(권유 아님).

## 10. 완료 기준
- 앱에서 QR 발급·표시, 폰 스캔으로 유저 계정에 chat_id 저장, "연결됨" 표시.
- `run()`이 2명 이상 유저에게 각자 포트폴리오 기준으로 분리 발송(쿨다운 동작).
- 자동 테스트 그린, 실스캔 1회 확인.
