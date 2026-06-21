"""텔레그램 온보딩용 단기 nonce 딥링크 + QR. 폴링 등록기와 같은 상태 파일을 공유."""
import io
import json
import os
import secrets
import time
from pathlib import Path

_STATE = Path.home() / ".siminvest_alerts.json"
_TTL = 600  # nonce 유효(초)


def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    tmp = _STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _STATE)


def _qr_png(data: str) -> bytes:
    import qrcode
    buf = io.BytesIO()
    qrcode.make(data).save(buf, format="PNG")
    return buf.getvalue()


def issue_link(username: str, bot_username: str = "sim_investment_bot") -> tuple[str, bytes]:
    nonce = secrets.token_urlsafe(16)
    d = _load()
    d.setdefault("pending", {})[nonce] = {"username": username, "exp": time.time() + _TTL}
    _save(d)
    link = f"https://t.me/{bot_username}?start={nonce}"
    return link, _qr_png(link)


def resolve_nonce(nonce: str) -> str | None:
    d = _load()
    rec = d.get("pending", {}).get(nonce)
    if not rec:
        return None
    if rec.get("exp", 0) < time.time():
        d["pending"].pop(nonce, None)
        _save(d)
        return None
    return rec.get("username")


def consume_nonce(nonce: str) -> None:
    d = _load()
    if d.get("pending", {}).pop(nonce, None) is not None:
        _save(d)
