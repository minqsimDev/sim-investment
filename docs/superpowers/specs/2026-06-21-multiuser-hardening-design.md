# 멀티유저 안전 하드닝 — 설계

작성일: 2026-06-21 · 브랜치: `feat/multiuser-hardening`

## 1. 목적
여러 사용자가 **동시에** 안전하게 쓸 수 있게, 공유 상태의 동시 쓰기 correctness와 유저별 데이터 격리의 남은 구멍을 막는다.

## 2. 배경 (현재 상태)
- ✅ 인앱 보유/리스크는 이미 유저별 — `st.session_state`(세션별) + `accounts.json`(username 키, fcntl 락).
- ❌ **`~/.siminvest_alerts.json`**(텔레그램 nonce·offset·cfg)는 **락 없이** read-modify-write → 동시 발급/등록 시 lost-update.
- ❌ **텔레그램 폴링 offset 경쟁** — `getUpdates`는 봇당 단일 스트림인데 세션별 온디맨드 폴링이 경쟁.
- ❌ **증권사 자격증명** `~/.siminvest_auth.json` — username 키 없는 **전역 1개**. 멀티유저에서 서로 덮어씀.

## 3. 범위
- **포함**: (A) `alerts.json` 동시 쓰기 락 + 텔레그램 폴링 단일소비자 직렬화, (B) 증권사 자격증명 유저별 분리.
- **비포함(non-goals)**: 배포/HTTPS/세션 격리·부하 테스트, 자격증명 암호화, 텔레그램 전용 데몬.

## 4. 핵심 결정 (합의됨)
| 항목 | 결정 |
|---|---|
| 자격증명 저장 | **계정별 평문**(`accounts.json` settings, 현 보안수준 유지·격리만) |
| 기존 전역 cred | **읽기 폴백 유지**(강제 마이그레이션 없음), 신규 저장은 계정별 |
| 텔레그램 폴링 | **공유 파일락으로 직렬화**(전용 데몬 없음) |
| 연결 성공 판정 | "내 계정에 chat_id 생겼나"(`get_setting`)로 — 자기 poll 결과에 의존 안 함 |

## 5. 컴포넌트 / 인터페이스
- `core/locking.py` (신규) — `file_lock(lock_path: str|Path)` 컨텍스트매니저(fcntl flock; fcntl 없으면 no-op yield). `accounts.py`의 기존 `_locked()`를 이걸로 대체(동작 동일).
- `core/telegram_link.py` (수정) — `issue_link`/`consume_nonce`/`resolve_nonce`(만료 삭제 포함)의 RMW를 `file_lock(_LOCK)`로 감쌈. `_LOCK = ~/.siminvest_alerts.lock`.
- `src/telegram_alert.py` (수정) — `poll_register()` 전체(load_cfg→getUpdates→offset·set_setting·save_cfg→nonce소비)를 `file_lock(_LOCK)`로 감쌈 → 단일 소비자. `load_cfg`/`save_cfg`는 `pending` 등 미지 키 보존(load-merge-save) 유지.
- `core/auth.py` (수정) — `save_credentials(username, provider, app_key, app_secret, account_no)` → `accounts.set_setting(username,"brokerage",{...})`. `load_saved_credentials(username)` → 계정별 우선, 없으면 전역 파일 읽기 폴백. username 없으면(게스트) 저장 거부·로드는 폴백만.
- `ui/pages/telegram_connect.py` (수정) — 성공 조건을 `accounts.get_setting(username,"telegram_chat_id")` 존재로.
- 호출부(`core/auth.py` 로그인 흐름, 로그인/포트폴리오 페이지에서 save/load 호출처) — username 인자 전달하도록 갱신.

## 6. 데이터 / 동시성 규약
- `alerts.json`은 **단일 락(`~/.siminvest_alerts.lock`)** 하에서만 RMW. telegram_link·telegram_alert 양쪽이 같은 락 사용, 서로의 키(`pending` vs `chat_id/rules/last_sent/update_offset`)를 load-merge-save로 보존.
- 락 구간은 load→mutate→save 전체. 단발 atomic write만으로는 lost-update 불가.
- 자격증명은 `accounts.set_setting`(이미 fcntl 락)로 저장 → 별도 락 불필요.

## 7. 오류 처리
- fcntl 미지원 플랫폼: `file_lock`은 no-op(현 accounts.py와 동일 동작) — 단일 프로세스 가정.
- 락 획득 실패/예외: 컨텍스트 종료 시 항상 해제(try/finally).
- 전역 cred 폴백 파일 없음/손상: None 반환(로그만).

## 8. 테스트
- `core/locking.py`: 락 진입/해제, 중첩 호출 안전.
- `alerts.json` 동시성: 스레드 N개가 각자 `issue_link` → 모든 nonce가 `pending`에 보존(lost-update 0). poll_register 동시 호출이 직렬화돼 같은 /start 이중 처리 안 됨.
- 자격증명 격리: `save_credentials("alice",…)`/`("bob",…)` → 각자 `load_saved_credentials`만 자기 것. 전역 폴백: 계정별 없을 때만 전역 읽음.
- 연결 성공 판정: 다른 경로가 chat_id 저장 → 연결 화면이 성공 감지.

## 9. 위험/주의
- telegram_link·telegram_alert가 같은 파일을 공유하는 결합은 유지(락+merge로 안전). 추후 pending을 cfg로 통합하면 더 깔끔(별도 과제).
- 폴링 직렬화로 동시 연결은 순차 처리 — 처리량보다 correctness 우선(소수 동시 사용 가정).
- 기존 전역 cred 폴백은 단일소유 호환용. 멀티유저 본격화 시 폴백 제거 고려(후속).

## 10. 완료 기준
- 동시 쓰기 테스트에서 alerts.json lost-update 0, 텔레그램 이중 처리 0.
- userA/userB 증권사 자격증명 완전 격리(교차 노출 0), 기존 단일 cred 호환.
- 전체 테스트 그린(기존 선존재 실패 제외), 1.37.1 로드 OK.
