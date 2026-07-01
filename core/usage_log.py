"""가벼운 사용 이벤트 로그 — 화면/탭 사용률 계측(가지치기 판단용).

원칙:
- 세션당 (page,tab) 첫 조회만 1건 기록 → Streamlit 리런 과다카운트 방지("탭을 연 세션 수" 근사).
- JSONL append + 파일락. **완전 best-effort**: 로깅 실패가 UI를 절대 막지 않는다.
- 사용자는 해시로만 저장(익명 유니크 카운트, 원문 username 미보관). 게스트=guest.
- 저장: ~/.siminvest_usage.jsonl (prod=/data 볼륨 영속).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

_FILE = Path.home() / ".siminvest_usage.jsonl"
_LOCK = Path.home() / ".siminvest_usage.lock"


def _uid() -> str:
    """세션 사용자 → 익명 해시 id. streamlit 미가용/미로그인 시 폴백."""
    try:
        import streamlit as st
        if st.session_state.get("auth_role") == "guest":
            return "guest"
        u = st.session_state.get("username")
        if u:
            return "u_" + hashlib.sha256(str(u).encode()).hexdigest()[:12]
    except Exception:
        pass
    return "anon"


def _append(rec: dict) -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **rec}
    line = json.dumps(rec, ensure_ascii=False)
    try:
        from core.locking import file_lock
        with file_lock(_LOCK):
            with open(_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass   # best-effort: 계측 실패는 무시


def log_tab_view(page: str, tab: str) -> None:
    """세션당 (page,tab) 첫 조회만 1건 기록. 절대 예외를 밖으로 던지지 않는다."""
    try:
        import streamlit as st
        seen = st.session_state.setdefault("_usage_seen", set())
        key = (page, tab or "summary")
        if key in seen:
            return
        seen.add(key)
        _append({"event": "tab_view", "page": page, "tab": key[1], "uid": _uid()})
    except Exception:
        pass


def summarize(path=None) -> dict:
    """JSONL → {(page,tab): {"views": n, "users": set(uid)}} 집계."""
    p = Path(path) if path else _FILE
    out: dict = {}
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except (ValueError, TypeError):
            continue
        k = (r.get("page", "?"), r.get("tab", "?"))
        e = out.setdefault(k, {"views": 0, "users": set()})
        e["views"] += 1
        e["users"].add(r.get("uid", "?"))
    return out
