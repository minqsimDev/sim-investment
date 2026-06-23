"""토스 /prices 응답에 '전일종가' 필드가 있는지 확인하는 1회성 점검 스크립트.

목적: 1번 최적화(배치 응답으로 종목당 캔들 호출 제거)의 실효성 확인.
실행: 토스 IP 허용목록에 등록된 환경(실서버)에서  →  python check_toss_fields.py
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
B = "https://openapi.tossinvest.com"
cid, cs = os.getenv("TOSS_CLIENT_ID"), os.getenv("TOSS_CLIENT_SECRET")

if not cid or not cs:
    raise SystemExit("❌ .env 에 TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 가 없습니다.")

tok_resp = requests.post(
    B + "/oauth2/token",
    data={"grant_type": "client_credentials", "client_id": cid, "client_secret": cs},
    timeout=15,
)
if tok_resp.status_code != 200:
    raise SystemExit(
        f"❌ 토큰 발급 실패 ({tok_resp.status_code}): {tok_resp.text}\n"
        "   → 'IP address not allowed' 이면 이 환경은 허용목록 밖입니다. 실서버에서 실행하세요."
    )

tok = tok_resp.json()["access_token"]
r = requests.get(
    B + "/api/v1/prices",
    params={"symbols": "005930,AAPL"},
    headers={"Authorization": "Bearer " + tok},
    timeout=15,
)
rows = r.json().get("result", [])
if not rows:
    raise SystemExit(f"❌ 응답 없음: {r.status_code} {r.text[:300]}")

print("=" * 60)
print("응답 필드(키) 목록:")
print(" ", list(rows[0].keys()))
print("=" * 60)
print("샘플 행 전체:")
print(json.dumps(rows[0], ensure_ascii=False, indent=2, default=str))
print("=" * 60)

PREV_KEYS = ("base", "previousClose", "prevClose", "basePrice", "closePrice", "prevPrice")
found = [k for k in PREV_KEYS if rows[0].get(k) is not None]
if found:
    print(f"✅ 전일종가 필드 발견: {found}  →  1번 최적화가 그대로 작동합니다.")
else:
    print("⚠️  전일종가로 쓸 만한 필드가 안 보입니다.")
    print("    → 위 '필드 목록'을 그대로 알려주세요(다른 이름일 수 있음). 없으면 2번(캔들 병렬화)로 전환.")
