"""
텔레그램 위험 알림 (성장_로드맵 C).

- 봇 토큰: .env `TELEGRAM_BOT_TOKEN` (코드/깃 하드코딩 금지 — `.gitignore`에 .env 포함)
- 설정·상태: `~/.siminvest_alerts.json` (chat_id, 규칙 on/off·임계, 마지막 발송 시각)
- 규칙(MVP): ① 종합 위험 점수 ≥ 80  ② 보유 종목 일일 ≤ -5%
- Streamlit은 상시 서버가 아니므로(로드맵 C4), 평가·발송은 데이터 갱신 배치(`main.py`)나
  아래 CLI(`python -m src.telegram_alert run`)에서 수행한다. 발송은 서버 측에서만.

CLI:
  python -m src.telegram_alert getme     # 토큰 유효성 확인(getMe)
  python -m src.telegram_alert connect   # /start 한 사용자의 chat_id 저장
  python -m src.telegram_alert test      # 테스트 메시지 발송
  python -m src.telegram_alert run       # 규칙 평가 후 발송(쿨다운 적용)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from core.locking import file_lock

load_dotenv()

_API = "https://api.telegram.org/bot{token}/{method}"
_CFG = Path.home() / ".siminvest_alerts.json"
_LOCK_FILE = Path.home() / ".siminvest_alerts.lock"
_COOLDOWN_H = 12  # 같은 알림 재발송 최소 간격(시간) — 중복 발송 방지
_BRAND = "SIM INVESTMENT"
_SIGN = "\n\n_SIM INVESTMENT · 진심으로 보는 투자_"  # 기본 서명(이탤릭)
# 위험 알림용 서명 — 면책(매매 권유 아님) 한 줄을 얹어 정체성 유지
_ALERT_SIGN = "\n\n_점검을 돕는 참고 정보일 뿐, 판단은 늘 직접._" + _SIGN

_DEFAULT_CFG = {
    "chat_id": None,
    "rules": {
        "risk_score":   {"enabled": True, "threshold": 80},
        "holding_drop": {"enabled": True, "threshold": -5.0},
    },
    "last_sent": {},  # rule key -> ISO timestamp
}


# ── 설정 저장/로드 ──────────────────────────────────────────────────────────
def load_cfg() -> dict:
    try:
        d = json.loads(_CFG.read_text())
    except Exception:
        d = {}
    cfg = json.loads(json.dumps(_DEFAULT_CFG))  # deep copy
    for k, v in d.items():
        if k == "rules" and isinstance(v, dict):
            for rk, rv in v.items():
                cfg["rules"].setdefault(rk, {}).update(rv or {})
        else:
            cfg[k] = v
    cfg.setdefault("last_sent", {})
    return cfg


def save_cfg(cfg: dict) -> None:
    tmp = _CFG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _CFG)


# ── 텔레그램 API ────────────────────────────────────────────────────────────
def _token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def is_configured() -> bool:
    return bool(_token())


def _api(method: str, **params):
    import requests
    token = _token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 미설정 (.env 확인)")
    r = requests.post(_API.format(token=token, method=method), json=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API 오류: {data.get('description', data)}")
    return data["result"]


def get_me() -> dict:
    """봇 토큰 유효성 확인 — 봇 정보 반환."""
    return _api("getMe")


def send_message(text: str, chat_id=None) -> bool:
    cfg = load_cfg()
    cid = chat_id or cfg.get("chat_id")
    if not cid:
        raise RuntimeError("chat_id 없음 — 봇에 /start 후 connect 하세요")
    try:
        _api("sendMessage", chat_id=cid, text=text, parse_mode="Markdown")
        return True
    except Exception as e:
        print(f"[telegram] 발송 실패: {e}", file=sys.stderr)
        return False


def send_test(chat_id=None) -> bool:
    """연결 확인용 환영 메시지 — 세련된 브랜드 톤."""
    msg = (f"✦ *{_BRAND}*\n"
           f"알림이 연결되었어요.\n\n"
           f"앞으로 시장과 보유 자산에 의미 있는 위험 신호가 보일 때만 "
           f"이 대화로 조용히 전해드릴게요.\n"
           f"평소엔 울리지 않는, 꼭 필요한 순간의 알림입니다."
           f"{_SIGN}")
    return send_message(msg, chat_id)


def connect() -> int | None:
    """getUpdates에서 가장 최근 메시지의 chat_id를 저장. 사용자가 먼저 봇에 /start 해야 함."""
    updates = _api("getUpdates")
    cid = None
    for u in reversed(updates):
        msg = u.get("message") or u.get("edited_message") or {}
        chat = msg.get("chat") or {}
        if chat.get("id"):
            cid = chat["id"]
            break
    if cid is None:
        return None
    cfg = load_cfg()
    cfg["chat_id"] = cid
    save_cfg(cfg)
    return cid


def poll_register() -> list[tuple[str, int]]:
    """getUpdates 로 /start <nonce> 수신 → 계정 chat_id 저장. 락으로 단일 소비자 직렬화."""
    from core import accounts

    registered: list[tuple[str, int]] = []
    with file_lock(_LOCK_FILE):
        cfg = load_cfg()
        pending = cfg.get("pending", {})
        offset = cfg.get("update_offset")
        updates = _api("getUpdates", offset=offset, timeout=0)
        seen: set[str] = set()
        welcomes: list[int] = []
        for u in updates:
            cfg["update_offset"] = u.get("update_id", 0) + 1
            msg = u.get("message") or {}
            text = (msg.get("text") or "").strip()
            cid = (msg.get("chat") or {}).get("id")
            if cid and text.startswith("/start"):
                parts = text.split(maxsplit=1)
                if len(parts) == 2 and parts[1].strip() not in seen:
                    nonce = parts[1].strip()
                    rec = pending.get(nonce)
                    if rec and rec.get("exp", 0) >= time.time():
                        username = rec["username"]
                        seen.add(nonce)
                        pending.pop(nonce, None)
                        accounts.set_setting(username, "telegram_chat_id", cid)
                        registered.append((username, cid))
                        welcomes.append(cid)
        cfg["pending"] = pending
        save_cfg(cfg)
    # 환영 발송은 락 밖에서(네트워크 I/O를 임계구역에서 분리)
    for cid in welcomes:
        try:
            send_test(cid)
        except Exception:
            pass
    return registered


# ── 규칙 평가 ───────────────────────────────────────────────────────────────
def _col_from_level(lv: str) -> str:
    """risk_signals.py와 동일 매핑 — 게이지 점수 산식 일치."""
    lv = (lv or "").upper()
    if lv in ("HIGH", "RISK-OFF", "BEARISH", "STRONG"):
        return "high"
    if lv in ("LOW", "RISK-ON", "BULLISH", "WEAK", "FALLING"):
        return "low"
    if lv == "N/A":
        return "na"
    return "mid"


def risk_score_now() -> tuple[int, int, int, int]:
    """DB 최신 risk_signals → (score 0~100, n_high, n_mid, n_low). 앱 게이지와 동일 산식."""
    from src.database import load_latest_risk_signals, DEFAULT_DB
    df = load_latest_risk_signals(DEFAULT_DB)
    if df is None or df.empty:
        return 0, 0, 0, 0
    cols = [_col_from_level(lv) for lv in df["level"]]
    n_high, n_mid, n_low = cols.count("high"), cols.count("mid"), cols.count("low")
    total = len(cols) or 1
    raw = (n_high * 100 + n_mid * 55 + n_low * 10) / total
    return int(round(max(0, min(100, raw)))), n_high, n_mid, n_low


def _daily_change(tickers: list[str]) -> dict:
    """티커별 1D% — DB indicator_summary 우선, 누락분은 yfinance 5일봉으로 보강."""
    out: dict[str, float] = {}
    want = set(tickers)
    try:
        from src.database import load_latest_indicator_summary, DEFAULT_DB
        df = load_latest_indicator_summary(DEFAULT_DB)
        if df is not None and not df.empty and "symbol" in df.columns:
            for _, r in df.iterrows():
                sym, v = r.get("symbol"), r.get("return_1d_pct")
                if sym in want and isinstance(v, (int, float)):
                    out[sym] = float(v)
    except Exception:
        pass
    missing = [t for t in tickers if t not in out]
    if missing:
        try:
            from data.session import cached_download
            raw = cached_download(missing, period="5d", interval="1d",
                                  progress=False, auto_adjust=True)
            if raw is not None and not raw.empty:
                multi = len(missing) > 1
                for tk in missing:
                    try:
                        c = raw["Close"][tk].dropna() if multi else raw["Close"].dropna()
                        if len(c) >= 2 and float(c.iloc[-2]):
                            out[tk] = round((float(c.iloc[-1]) / float(c.iloc[-2]) - 1) * 100, 2)
                    except Exception:
                        pass
        except Exception:
            pass
    return out


def _portfolio_daily(username: str) -> list[dict]:
    """유저의 저장 포트폴리오 보유 종목 → [{name, ticker, d1}]. 일일%는 지표 DB/시세에서."""
    from core import accounts
    tickers, names = [], {}
    for p in accounts.get_portfolios(username):
        for h in (p.get("holdings") or []):
            tk = h.get("ticker")
            if tk:
                tickers.append(tk)
                names[tk] = h.get("name") or tk
    if not tickers:
        return []
    d1 = _daily_change(list(dict.fromkeys(tickers)))
    return [{"name": names[tk], "ticker": tk, "d1": d1[tk]} for tk in d1]


def _cooldown_ok(cfg: dict, key: str, now: datetime) -> bool:
    last = cfg.get("last_sent", {}).get(key)
    if not last:
        return True
    try:
        return (now - datetime.fromisoformat(last)).total_seconds() >= _COOLDOWN_H * 3600
    except Exception:
        return True


def run(verbose: bool = True) -> list[str]:
    """연결된 유저별로 시장위험 + 본인 보유급락 평가·발송. 반환=발송 키 목록."""
    from core import accounts
    cfg = load_cfg()
    now = datetime.now(timezone.utc)
    rules = cfg.get("rules", _DEFAULT_CFG["rules"])
    cfg.setdefault("last_sent", {})
    sent: list[str] = []

    score, nh, nm, nl = risk_score_now() if rules.get("risk_score", {}).get("enabled") else (0, 0, 0, 0)

    for username, cid in accounts.users_with_telegram():
        # 규칙 ①: 시장 종합 위험(공통 점수, 쿨다운은 유저별)
        r1 = rules.get("risk_score", {})
        if r1.get("enabled") and score >= r1.get("threshold", 80):
            key = f"{username}:risk_score"
            if _cooldown_ok(cfg, key, now):
                msg = (f"⚠️ *종합 위험 {score}*  ·  방어 우선 구간\n\n"
                       f"시장 국면 신호가 위험 쪽으로 기울었어요.\n"
                       f"`위험 {nh}   주의 {nm}   완충 {nl}`\n\n"
                       f"› 점검 포인트 — 보유 비중과 헤지 여부{_ALERT_SIGN}")
                if send_message(msg, cid):
                    cfg["last_sent"][key] = now.isoformat()
                    sent.append(key)
        # 규칙 ②: 본인 보유 종목 급락
        r2 = rules.get("holding_drop", {})
        if r2.get("enabled"):
            thr = r2.get("threshold", -5.0)
            for h in _portfolio_daily(username):
                if h["d1"] <= thr:
                    key = f"{username}:holding_drop:{h['ticker']}"
                    if _cooldown_ok(cfg, key, now):
                        msg = (f"🔻 *{h['name']}*  {h['d1']:+.1f}%  ·  보유 종목 급락\n\n"
                               f"오늘 하루 큰 폭으로 내렸어요.  _(경보 기준 {thr:+.0f}%)_\n\n"
                               f"› 점검 포인트 — 비중과 추가 하방 위험{_ALERT_SIGN}")
                        if send_message(msg, cid):
                            cfg["last_sent"][key] = now.isoformat()
                            sent.append(key)
    save_cfg(cfg)
    if verbose:
        print(f"[telegram] 발송 {len(sent)}건: {sent}")
    return sent


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "getme":
        print(get_me())
    elif cmd == "connect":
        cid = connect()
        print(f"연결됨: chat_id={cid}" if cid else "수신 메시지 없음 — 봇에게 /start 를 먼저 보내세요")
    elif cmd == "test":
        print("발송 성공" if send_test() else "발송 실패")
    elif cmd == "run":
        run()
    else:
        print(f"알 수 없는 명령: {cmd}  (getme|connect|test|run)")
