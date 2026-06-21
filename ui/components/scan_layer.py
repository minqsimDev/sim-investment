"""
시장 탭 '30초 스캔 레이어' 공용 컴포넌트 (F1·F2·F3).
- scan_layer_html(items): 표 위에 얹는 리더/러거드/과열 카드 3장 + breadth 한 줄.
- 모든 수치는 호출부가 표 데이터에서 자동 산출한 값(하드코딩 없음).
- 스파크라인 색: 상승 레드 / 하락 블루 (국내 관례, F7과 동일).

items: [{"name": str, "d1": float|None, "ma20": float|None, "series": list[float]}]
"""
from __future__ import annotations

POS = "#F25560"   # 상승(레드)
NEG = "#4D90F0"   # 하락(블루)
GOLD = "#D9A441"  # 과열/주의(골드)

_SCAN_CSS = """<style>
.scan-wrap{margin:2px 0 14px}
.scan-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:10px}
@media(max-width:760px){.scan-row{grid-template-columns:1fr}}
.scan-card{background:#16181F;border:1px solid #262A33;border-radius:16px;padding:14px 16px;
  position:relative;overflow:hidden;box-shadow:0 6px 18px rgba(0,0,0,.25)}
.scan-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px}
.scan-card.lead::before{background:#F25560}
.scan-card.lag::before{background:#4D90F0}
.scan-card.hot::before{background:#D9A441}
.scan-k{font-size:10px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#7E8694;margin-bottom:6px}
.scan-card.lead .scan-k{color:#F25560}.scan-card.lag .scan-k{color:#4D90F0}.scan-card.hot .scan-k{color:#D9A441}
.scan-mid{display:flex;align-items:flex-end;justify-content:space-between;gap:10px}
.scan-name{font-size:14px;font-weight:900;color:#E7E9EE;line-height:1.2;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.scan-val{font-size:19px;font-weight:950;font-family:'SF Mono',ui-monospace,monospace;line-height:1;flex-shrink:0}
.scan-val.pos{color:#F25560}.scan-val.neg{color:#4D90F0}.scan-val.gold{color:#D9A441}
.scan-sub{font-size:10px;font-weight:700;color:#7E8694;margin-top:3px}
.scan-spark-wrap{position:relative;margin-top:8px}
.scan-spark{display:block;width:100%;height:30px}
.scan-3m{position:absolute;right:2px;top:0;font-size:8.5px;font-weight:850;color:#7E8694;
  background:rgba(14,15,19,0.7);border:1px solid #262A33;border-radius:5px;padding:1px 5px;letter-spacing:.04em}
.scan-breadth{display:flex;align-items:center;gap:12px;background:#16181F;border:1px solid #262A33;
  border-radius:12px;padding:9px 14px;flex-wrap:wrap}
.scan-breadth-txt{font-size:12px;font-weight:850;color:#9AA0AD;white-space:nowrap}
.scan-breadth-txt b.up{color:#F25560}.scan-breadth-txt b.dn{color:#4D90F0}
.scan-ratio{flex:1;min-width:120px;height:8px;border-radius:999px;overflow:hidden;
  background:#1E2029;display:flex}
.scan-ratio i{display:block;height:100%}
.scan-ratio i.up{background:#F25560}.scan-ratio i.dn{background:#4D90F0}
.scan-breadth-pct{font-size:11px;font-weight:850;color:#7E8694;white-space:nowrap}
</style>"""


def _hex_rgba(hex_c: str, a: float) -> str:
    h = hex_c.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"


def _spark_svg(vals: list[float], w: int = 150, h: int = 30, color: str | None = None) -> str:
    pts = [v for v in (vals or []) if isinstance(v, (int, float))]
    if len(pts) < 2:
        return f'<svg class="scan-spark" viewBox="0 0 {w} {h}"></svg>'
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or 1.0
    n = len(pts)
    step = w / (n - 1)
    pad = 3
    coords = []
    for i, v in enumerate(pts):
        x = i * step
        y = pad + (h - 2 * pad) * (1 - (v - lo) / rng)
        coords.append(f"{x:.1f},{y:.1f}")
    if color:  # 종목 고유색(원자재 시그니처). 없으면 등락 방향색(레드/블루)
        fill = _hex_rgba(color, 0.10)
    else:
        color = POS if pts[-1] >= pts[0] else NEG
        fill = "rgba(242,85,96,0.10)" if pts[-1] >= pts[0] else "rgba(77,144,240,0.10)"
    path = "M" + " L".join(coords)
    area = f"M{coords[0]} L" + " L".join(coords[1:]) + f" L{(n-1)*step:.1f},{h} L0,{h} Z"
    return (
        f'<svg class="scan-spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
        f'<path d="{area}" fill="{fill}" stroke="none"/>'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def _fmt_pct(v) -> str:
    if not isinstance(v, (int, float)):
        return "—"
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def scan_layer_html(items: list[dict], spark_label: str = "3개월 추이") -> str:
    """리더/러거드/과열 카드 + breadth. items에서 전부 자동 산출."""
    valid = [it for it in items if isinstance(it.get("d1"), (int, float))]
    if not valid:
        return ""

    leader = max(valid, key=lambda x: x["d1"])
    laggard = min(valid, key=lambda x: x["d1"])
    hot_pool = [it for it in items if isinstance(it.get("ma20"), (int, float))]
    # 과열 카드는 리더/부진과 같은 종목 중복 노출 금지 → 다음 후보로 대체
    hot = None
    _taken = {leader.get("name"), laggard.get("name")}
    for cand in sorted(hot_pool, key=lambda x: x["ma20"], reverse=True):
        if cand.get("name") not in _taken:
            hot = cand
            break

    up = sum(1 for it in valid if it["d1"] > 0)
    dn = sum(1 for it in valid if it["d1"] < 0)
    flat = len(valid) - up - dn
    total = len(valid)
    up_pct = up / total * 100 if total else 0
    dn_pct = dn / total * 100 if total else 0

    def _card(cls, k, it, val, val_cls, sub):
        return (
            f'<div class="scan-card {cls}">'
            f'<div class="scan-k">{k}</div>'
            f'<div class="scan-mid"><div class="scan-name">{it["name"]}</div>'
            f'<div class="scan-val {val_cls}">{val}</div></div>'
            f'<div class="scan-sub">{sub}</div>'
            # 스파크라인 = 3개월 추이임을 명확히(큰 숫자=오늘) → '3M' 배지
            f'<div class="scan-spark-wrap">{_spark_svg(it.get("series", []), color=it.get("color"))}'
            f'<span class="scan-3m">3M</span></div>'
            f'</div>'
        )

    cards = (
        _card("lead", "오늘의 리더", leader, _fmt_pct(leader["d1"]),
              "pos" if leader["d1"] >= 0 else "neg", "당일 최고")
        + _card("lag", "부진", laggard, _fmt_pct(laggard["d1"]),
                "pos" if laggard["d1"] >= 0 else "neg", "당일 최저")
    )
    if hot:
        cards += _card("hot", "과열 점검", hot, _fmt_pct(hot["ma20"]),
                       "gold", "MA20 이격 최대")

    breadth = (
        '<div class="scan-breadth">'
        f'<span class="scan-breadth-txt">상승 <b class="up">{up}</b> · 하락 <b class="dn">{dn}</b>'
        + (f' · 보합 {flat}' if flat else '') +
        '</span>'
        '<div class="scan-ratio">'
        f'<i class="up" style="width:{up_pct:.1f}%"></i>'
        f'<i class="dn" style="width:{dn_pct:.1f}%"></i>'
        '</div>'
        f'<span class="scan-breadth-pct">상승 {up_pct:.0f}%</span>'
        '</div>'
    )
    return f'{_SCAN_CSS}<div class="scan-wrap"><div class="scan-row">{cards}</div>{breadth}</div>'
