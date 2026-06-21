"""시장 '전체' 탭 — 전 자산군 통합 뷰.

미국·한국·원자재·FX·크립토를 한 화면에:
  · 통합 breadth(전 자산군 상승/하락/보합 합산)
  · 자산군 요약 카드 5장(등락·상태·리더, 클릭→서브탭)
  · 자산군 묶음 히트맵(미국/한국/원자재/FX·크립토 대표 종목)

모든 수치는 load_market_data() 각 탭 소스에서 자동 산출(하드코딩 금지).
등락색 = 한국 관례(상승 레드 / 하락 블루), 골드는 강조 전용.
"""
from __future__ import annotations

POS = "#F25560"   # 상승(레드)
NEG = "#4D90F0"   # 하락(블루)
FLAT = "#5A5F52"  # 보합(회색)

# (라벨, data 키, 이름 컬럼, 이동 서브탭 slug | None)
_SPECS = [
    ("미국",   "us_stocks",   "name", "us"),
    ("한국",   "kr_stocks",   "name", "kr"),
    ("원자재", "commodities", "name", "commodities"),
    ("FX",     "fx",          "pair", "fx"),
    ("크립토", "crypto",      "name", "crypto"),
]

_AM_CSS = """<style>
.am-wrap{margin:2px 0 8px}
/* 통합 breadth */
.am-breadth{display:flex;align-items:center;gap:12px;background:#16181F;border:1px solid #262A33;
  border-radius:12px;padding:10px 16px;flex-wrap:wrap;margin-bottom:14px}
.am-breadth-k{font-size:10px;font-weight:900;color:#7E8694;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
.am-breadth-txt{font-size:12px;font-weight:850;color:#9AA0AD;white-space:nowrap}
.am-breadth-txt b.up{color:#F25560}.am-breadth-txt b.dn{color:#4D90F0}
.am-ratio{flex:1;min-width:140px;height:9px;border-radius:999px;overflow:hidden;background:#1E2029;display:flex}
.am-ratio i{display:block;height:100%}
.am-ratio i.up{background:#F25560}.am-ratio i.dn{background:#4D90F0}.am-ratio i.fl{background:#3A3F48}
.am-breadth-pct{font-size:11px;font-weight:850;color:#7E8694;white-space:nowrap}
/* 자산군 카드 5장 */
.am-cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:16px}
@media(max-width:1100px){.am-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.am-cards{grid-template-columns:1fr}}
.am-card{display:block;background:#16181F;border:1px solid #262A33;border-left:3px solid #3A3F48;
  border-radius:14px;padding:13px 15px;text-decoration:none;transition:border-color .12s,transform .12s}
a.am-card:hover{border-color:#D9A441;transform:translateY(-1px)}
.am-card.pos{border-left-color:#F25560}.am-card.neg{border-left-color:#4D90F0}.am-card.flat{border-left-color:#5A5F52}
.am-card-top{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:8px}
.am-card-cls{font-size:13px;font-weight:950;color:#E7E9EE}
.am-badge{font-size:9px;font-weight:900;border-radius:6px;padding:2px 7px;letter-spacing:.04em;white-space:nowrap}
.am-badge.pos{color:#F25560;background:rgba(242,85,96,.13)}
.am-badge.neg{color:#4D90F0;background:rgba(77,144,240,.13)}
.am-badge.flat{color:#9AA0AD;background:rgba(100,107,121,.16)}
.am-card-chg{font-size:21px;font-weight:950;font-variant-numeric:tabular-nums;line-height:1}
.am-card-chg.pos{color:#F25560}.am-card-chg.neg{color:#4D90F0}.am-card-chg.flat{color:#9AA0AD}
.am-card-sub{font-size:10.5px;font-weight:750;color:#9AA0AD;margin-top:8px;line-height:1.5;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.am-card-sub .up{color:#F25560}.am-card-sub .dn{color:#4D90F0}
.am-go{font-size:9.5px;font-weight:800;color:#7E8694}
a.am-card:hover .am-go{color:#D9A441}
/* 자산군 묶음 히트맵 */
.am-hm-k{font-size:11px;font-weight:800;color:#7E8694;letter-spacing:.05em;text-transform:uppercase;margin:4px 0 10px}
.am-hm-group{margin-bottom:12px}
.am-hm-gk{font-size:10px;font-weight:900;color:#7E8694;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px}
.am-hm-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(108px,1fr));gap:6px}
.am-tile{border:1px solid #262A33;border-radius:9px;padding:8px 10px;min-width:0}
.am-tile-nm{display:block;font-size:11px;font-weight:850;color:#E7E9EE;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.am-tile-pct{display:block;font-size:11.5px;font-weight:900;font-variant-numeric:tabular-nums;margin-top:2px}
.am-tile-pct.pos{color:#F25560}.am-tile-pct.neg{color:#4D90F0}.am-tile-pct.flat{color:#9AA0AD}
</style>"""


def _label(key: str, raw: str) -> str:
    """원자재/FX 영문 키 → 한글·표기 라벨(각 탭 정의 재사용)."""
    if key == "commodities":
        try:
            from ui.pages.commodities import _META
            return _META.get(raw, (raw,))[0]
        except Exception:
            return raw
    if key == "fx":
        try:
            from ui.pages.fx_rates import _PAIR_LABELS
            return _PAIR_LABELS.get(raw, raw.upper())
        except Exception:
            return raw.upper()
    return raw


def _extract(data: dict) -> list[dict]:
    classes = []
    for label, key, namecol, tab in _SPECS:
        df = data.get(key)
        items = []
        if df is not None and not getattr(df, "empty", True):
            for _, r in df.iterrows():
                c = r.get("change_pct")
                if isinstance(c, (int, float)):
                    items.append((_label(key, str(r.get(namecol, ""))), float(c)))
        classes.append({"label": label, "key": key, "tab": tab, "items": items})
    return classes


def _stat(items: list[tuple]) -> dict:
    up = sum(1 for _, v in items if v > 0.05)
    dn = sum(1 for _, v in items if v < -0.05)
    flat = len(items) - up - dn
    avg = sum(v for _, v in items) / len(items) if items else 0.0
    leader = max(items, key=lambda x: x[1]) if items else None
    # 상태는 헤드라인 등락(avg) 부호와 모순되지 않게: 강세는 평균이 +이고 상승 우위일 때만
    if up >= dn and avg >= 0.05:
        status, scls = "강세", "pos"
    elif dn >= up and avg <= -0.05:
        status, scls = "약세", "neg"
    else:
        status, scls = "혼조", "flat"
    return {"up": up, "dn": dn, "flat": flat, "avg": avg, "leader": leader,
            "status": status, "scls": scls}


def _chg_cls(v: float) -> str:
    return "pos" if v > 0.05 else ("neg" if v < -0.05 else "flat")


def _fmt(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def _tile_bg(v: float) -> str:
    if abs(v) <= 0.05:
        return "#1E2029"
    mag = min(abs(v) / 5.0, 1.0)
    a = 0.14 + mag * 0.46
    rgb = "242,85,96" if v > 0 else "77,144,240"
    return f"rgba({rgb},{a:.2f})"


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def all_markets_html(data: dict, suffix: str = "") -> str:
    classes = _extract(data)
    all_items = [it for c in classes for it in c["items"]]
    total = len(all_items) or 1
    up = sum(1 for _, v in all_items if v > 0.05)
    dn = sum(1 for _, v in all_items if v < -0.05)
    flat = total - up - dn
    up_pct, dn_pct, fl_pct = up / total * 100, dn / total * 100, flat / total * 100

    # ── 1. 통합 breadth ──
    breadth = (
        '<div class="am-breadth">'
        '<span class="am-breadth-k">전 자산군 등락</span>'
        f'<span class="am-breadth-txt">상승 <b class="up">{up}</b> · 하락 <b class="dn">{dn}</b>'
        + (f' · 보합 {flat}' if flat else '') +
        f' · 총 {total}종목</span>'
        '<div class="am-ratio">'
        f'<i class="up" style="width:{up_pct:.1f}%"></i>'
        f'<i class="fl" style="width:{fl_pct:.1f}%"></i>'
        f'<i class="dn" style="width:{dn_pct:.1f}%"></i></div>'
        f'<span class="am-breadth-pct">상승 {up_pct:.0f}%</span>'
        '</div>'
    )

    # ── 2. 자산군 카드 5장 ──
    cards = ""
    for c in classes:
        s = _stat(c["items"])
        chg_cls = _chg_cls(s["avg"])
        lead = ""
        if s["leader"]:
            ln, lv = s["leader"]
            lead = f'리더 {_esc(ln)} <span class="{_chg_cls(lv)}">{_fmt(lv)}</span> · '
        sub = f'{lead}<span class="up">▲{s["up"]}</span> <span class="dn">▼{s["dn"]}</span>'
        go = '<span class="am-go">자세히 →</span>' if c["tab"] else '<span class="am-go">통합 뷰</span>'
        inner = (
            '<div class="am-card-top">'
            f'<span class="am-card-cls">{c["label"]}</span>'
            f'<span class="am-badge {s["scls"]}">{s["status"]}</span></div>'
            f'<div class="am-card-chg {chg_cls}">{_fmt(s["avg"])}</div>'
            f'<div class="am-card-sub">{sub}</div>'
            f'<div style="margin-top:6px">{go}</div>'
        )
        if c["tab"]:
            cards += f'<a class="am-card {s["scls"]}" href="?market_tab={c["tab"]}{suffix}" target="_self">{inner}</a>'
        else:
            cards += f'<div class="am-card {s["scls"]}">{inner}</div>'
    cards_html = f'<div class="am-cards">{cards}</div>'

    # ── 3. 자산군 묶음 히트맵 (미국/한국/원자재/FX·크립토) ──
    by_key = {c["key"]: c["items"] for c in classes}

    def _tiles(items, cap):
        top = sorted(items, key=lambda x: -abs(x[1]))[:cap]
        out = ""
        for nm, v in top:
            out += (
                f'<div class="am-tile" style="background:{_tile_bg(v)}">'
                f'<span class="am-tile-nm">{_esc(nm)}</span>'
                f'<span class="am-tile-pct {_chg_cls(v)}">{_fmt(v)}</span></div>'
            )
        return out

    groups = [
        ("미국", _tiles(by_key.get("us_stocks", []), 6)),
        ("한국", _tiles(by_key.get("kr_stocks", []), 6)),
        ("원자재", _tiles(by_key.get("commodities", []), 6)),
        ("FX · 크립토", _tiles(by_key.get("fx", []), 5) + _tiles(by_key.get("crypto", []), 4)),
    ]
    hm = '<div class="am-hm-k">자산군 묶음 히트맵 · 색 = 1D% 등락(상승 레드 / 하락 블루)</div>'
    for gk, tiles in groups:
        if tiles:
            hm += (f'<div class="am-hm-group"><div class="am-hm-gk">{gk}</div>'
                   f'<div class="am-hm-tiles">{tiles}</div></div>')

    return _AM_CSS + '<div class="am-wrap">' + breadth + cards_html + hm + '</div>'
