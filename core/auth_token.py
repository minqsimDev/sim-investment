"""세션 복원용 서명 토큰(HMAC).

배경: 멀티페이지 하드 nav 시 Streamlit session_state 가 끊겨, 인증 유저를 URL 파라미터로
복원해 왔다. 과거엔 `?_user=<평문 username>` 을 그대로 신뢰 → **비밀번호 없이 아무 계정이나
접근**되는 인증 우회였다. 이 모듈은 username 을 서버 시크릿으로 HMAC 서명해 위조를 막는다.

토큰 = urlsafe_b64( username + "\x1f" + hmac_sha256(secret, username) ). verify 는 서명을
재계산해 constant-time 비교 후 username 을 돌려준다(불일치/변조 시 None).

시크릿 우선순위:
  1) 환경변수 APP_SECRET (권장 — 배포 시 주입)
  2) 없으면 HOME 의 ~/.siminvest_secret 에 랜덤 32바이트를 1회 생성·영속(0600).
     볼륨(/data)에 남아 재시작·재배포에도 토큰이 유지된다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path

_SEP = b"\x1f"
_secret_cache: bytes | None = None


def _secret() -> bytes:
    global _secret_cache
    if _secret_cache is not None:
        return _secret_cache
    env = os.getenv("APP_SECRET")
    if env:
        _secret_cache = env.encode()
        return _secret_cache
    # 영속 시크릿 파일(없으면 생성). 동시 생성 경쟁은 무해(둘 중 하나로 수렴, 토큰만 한 번 무효화).
    path = Path.home() / ".siminvest_secret"
    try:
        if path.exists():
            _secret_cache = path.read_bytes().strip()
            if _secret_cache:
                return _secret_cache
        sec = base64.urlsafe_b64encode(os.urandom(32))
        path.write_bytes(sec)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        _secret_cache = sec
    except OSError:
        # 파일조차 못 쓰는 환경 — 프로세스 수명 동안만 유효한 임시 시크릿(재시작 시 토큰 무효화).
        _secret_cache = os.urandom(32)
    return _secret_cache


def _sig(username: str) -> bytes:
    return hmac.new(_secret(), username.encode("utf-8"), hashlib.sha256).digest()


def make_token(username: str) -> str:
    """username → 위조 불가 세션 복원 토큰(URL-safe)."""
    raw = username.encode("utf-8") + _SEP + _sig(username)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def user_param(username: str) -> str:
    """URL 세션복원 파라미터 'key=value' 문자열 — _user=<서명토큰>. (앞의 ?/& 는 호출부가 붙임)"""
    return f"_user={make_token(username)}" if username else ""


def verify_token(token: str) -> str | None:
    """토큰 검증 → username(유효) 또는 None(변조·형식오류). constant-time 비교."""
    if not token:
        return None
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad)
        username_b, _, sig = raw.partition(_SEP)
        if not sig:
            return None
        username = username_b.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if hmac.compare_digest(sig, _sig(username)):
        return username
    return None
