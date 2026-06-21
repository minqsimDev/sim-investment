"""Portfolio asset journey scene."""
from __future__ import annotations

import math

import streamlit as st


_ROUTE_POINTS = [
    [28, 234],
    [96, 222],
    [152, 206],
    [214, 182],
    [276, 168],
    [336, 140],
    [402, 118],
    [472, 86],
    [566, 58],
]


def _route_split(progress: float) -> tuple[list[list[float]], list[list[float]]]:
    pts = _ROUTE_POINTS
    if progress <= 0:
        return [pts[0]], pts[:]
    if progress >= 1:
        return pts[:], [pts[-1]]

    lengths: list[float] = []
    total = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        length = math.hypot(dx, dy)
        lengths.append(length)
        total += length

    target = progress * total
    walked = [pts[0]]
    current = 0.0
    for i, seg_len in enumerate(lengths):
        if current + seg_len >= target:
            t = (target - current) / max(seg_len, 0.0001)
            mx = pts[i][0] + t * (pts[i + 1][0] - pts[i][0])
            my = pts[i][1] + t * (pts[i + 1][1] - pts[i][1])
            return walked + [[mx, my]], [[mx, my]] + pts[i + 1:]
        walked.append(pts[i + 1])
        current += seg_len
    return pts[:], [pts[-1]]


def _pline(points: list[list[float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _krw_compact(value: float | int | None) -> str:
    if value is None:
        return "데이터 대기"
    from core.journey import krw_compact  # 전 화면 공통 단일 포맷
    return krw_compact(value)


def _growth_eta(current_asset: float | int | None, target_asset: float | int | None, annual_growth_rate: float) -> str:
    current = float(current_asset or 0)
    target = float(target_asset or 0)
    rate = float(annual_growth_rate or 0)
    if target <= 0:
        return "목표 설정 필요"
    if current >= target:
        return "목표 도달"
    if current <= 0 or rate <= 0:
        return "성장률 설정 필요"
    years = math.log(target / current) / math.log(1 + rate)
    months = max(1, round(years * 12))
    if months < 12:
        return f"약 {months}개월"
    return f"약 {months // 12}년 {months % 12}개월"


def _pct_text(value: float) -> str:
    return f"{value * 100:.1f}%"


def _build_html(
    progress: float,
    current_asset: float | int | None,
    target_asset: float | int | None,
    annual_growth_rate: float,
) -> str:
    progress = max(0.0, min(1.0, float(progress or 0)))
    walked, future = _route_split(progress)
    hx, hy = walked[-1]
    tx, ty = _ROUTE_POINTS[-1]
    progress_label = _pct_text(progress)

    current = float(current_asset or 0)
    target = float(target_asset or 0)
    remaining = max(0.0, target - current) if target else None
    remaining_label = _krw_compact(remaining)
    current_label = _krw_compact(current_asset)
    target_label = _krw_compact(target_asset)
    eta = _growth_eta(current_asset, target_asset, annual_growth_rate)
    growth_label = f"{annual_growth_rate * 100:.0f}%" if annual_growth_rate else "미설정"
    status = "목표 도달" if progress >= 1 else ("순항 중" if progress >= 0.4 else "초반 구간")

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
html,body{{margin:0;background:transparent;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#E7E9EE}}
.journey{{position:relative;overflow:hidden;border:1px solid #262A33;border-radius:18px;background:#16181F;box-shadow:0 16px 36px rgba(0,0,0,.30)}}
.journey-shell{{display:grid;grid-template-columns:minmax(230px,.86fr) minmax(280px,1.14fr);gap:18px;min-height:316px;padding:20px}}
.journey-copy{{display:flex;flex-direction:column;justify-content:space-between;min-width:0}}
.journey-kicker{{display:inline-flex;width:max-content;align-items:center;border-radius:999px;background:rgba(217,164,65,0.14);color:#E7E9EE;border:1px solid #262A33;padding:6px 10px;font-size:11px;font-weight:900}}
.journey h2{{margin:14px 0 8px;color:#E7E9EE;font-size:30px;line-height:1.08;font-weight:950;letter-spacing:0}}
.journey p{{margin:0;color:#9AA0AD;font-size:12px;font-weight:760;line-height:1.55}}
.journey-primary{{margin-top:4px}}
.journey-meta{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:18px}}
.journey-stat{{border:1px solid #262A33;background:#1E2029;border-radius:12px;padding:10px 11px;min-width:0}}
.journey-stat span{{display:block;color:#9AA0AD;font-size:10px;font-weight:900;margin-bottom:4px}}
.journey-stat b{{display:block;color:#E7E9EE;font-size:14px;font-weight:950;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.journey-visual{{position:relative;border:1px solid #262A33;border-radius:16px;background:#0E0F13;min-height:276px;overflow:hidden}}
.journey-visual svg{{display:block;width:100%;height:100%}}
.grid-line{{stroke:#262A33;stroke-width:1}}
.route-base{{stroke:#262A33;stroke-width:10;stroke-linecap:round;stroke-linejoin:round}}
.route-future{{stroke:url(#futureStroke);stroke-width:4;stroke-dasharray:7 8;stroke-linecap:round;stroke-linejoin:round;animation:trailDash 16s linear infinite}}
.route-past{{stroke:url(#routeStroke);stroke-width:10;stroke-linecap:round;stroke-linejoin:round;filter:url(#glow)}}
.route-area{{fill:url(#area);opacity:.86}}
.route-dot{{fill:#ffffff;stroke:#D9A441;stroke-width:3}}
.summit-target{{fill:#E7E9EE;stroke:#ffffff;stroke-width:5}}
.target-ring{{fill:none;stroke:#D9A441;stroke-width:2;opacity:.46;animation:ringPulse 2.8s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
.shelter{{fill:#1E2029;stroke:#262A33;stroke-width:1.5}}
.milestone-label{{font-size:10px;font-weight:900;fill:#9AA0AD}}
.journey-handle{{cursor:pointer;outline:none}}
.journey-handle .handle-core{{fill:#D9A441;stroke:#ffffff;stroke-width:5}}
.journey-handle .handle-pulse{{fill:#D9A441;opacity:.24;animation:handlePulse 2.4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
.progress-chip{{font-size:11px;font-weight:950;fill:#E7E9EE}}
.axis-label{{font-size:10px;font-weight:850;fill:#9AA0AD}}
.journey-panel{{position:absolute;right:18px;bottom:18px;width:min(268px,calc(100% - 36px));border:1px solid #262A33;border-radius:14px;background:#16181F;box-shadow:0 14px 28px rgba(0,0,0,.35);padding:14px 15px;transform:translateY(10px);opacity:0;pointer-events:none;transition:opacity .18s,transform .18s}}
.journey-panel.show{{opacity:1;transform:translateY(0);pointer-events:auto}}
.journey-panel b{{display:block;color:#E7E9EE;font-size:13px;font-weight:950;margin-bottom:6px}}
.journey-panel p{{margin:4px 0;color:#9AA0AD;font-size:11px;font-weight:760;line-height:1.5}}
.journey-hint{{position:absolute;left:18px;bottom:18px;border-radius:999px;background:rgba(22,24,31,.9);border:1px solid #262A33;color:#9AA0AD;padding:6px 10px;font-size:10px;font-weight:900}}
@keyframes trailDash{{to{{stroke-dashoffset:-160}}}}
@keyframes ringPulse{{0%,100%{{transform:scale(.92);opacity:.24}}50%{{transform:scale(1.18);opacity:.42}}}}
@keyframes handlePulse{{0%,100%{{transform:scale(1);opacity:.18}}50%{{transform:scale(2.3);opacity:.05}}}}
@media(max-width:680px){{
  .journey-shell{{grid-template-columns:1fr;gap:12px;padding:14px;min-height:0}}
  .journey h2{{font-size:25px}}
  .journey-visual{{min-height:238px}}
  .journey-meta{{grid-template-columns:repeat(2,minmax(0,1fr))}}
}}
</style>
</head>
<body>
<div class="journey">
  <div class="journey-shell">
    <section class="journey-copy">
      <div>
        <span class="journey-kicker">ASSET JOURNEY · {status}</span>
        <h2>목표까지<br>{remaining_label}원</h2>
        <p class="journey-primary">현재 {current_label}원에서 목표 {target_label}원까지 가는 경로입니다. 큰 일러스트보다 지금 위치와 다음 구간을 먼저 보여줍니다.</p>
      </div>
      <div class="journey-meta" aria-label="자산 여정 요약">
        <div class="journey-stat"><span>진행률</span><b>{progress_label}</b></div>
        <div class="journey-stat"><span>예상 기간</span><b>{eta}</b></div>
        <div class="journey-stat"><span>연 성장률</span><b>{growth_label}</b></div>
        <div class="journey-stat"><span>앞으로 갈 길</span><b>{remaining_label}원</b></div>
      </div>
    </section>
    <section class="journey-visual" aria-label="자산 여정">
      <svg viewBox="0 0 620 300" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="routeStroke" x1="28" y1="234" x2="566" y2="58" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#D9A441"/>
            <stop offset="46%" stop-color="#D9A441"/>
            <stop offset="100%" stop-color="#E7E9EE"/>
          </linearGradient>
          <linearGradient id="futureStroke" x1="28" y1="234" x2="566" y2="58" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#9AA0AD"/>
            <stop offset="100%" stop-color="#262A33"/>
          </linearGradient>
          <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#D9A441" stop-opacity=".24"/>
            <stop offset="100%" stop-color="#D9A441" stop-opacity=".05"/>
          </linearGradient>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#D9A441" flood-opacity=".22"/>
          </filter>
        </defs>

        <line class="grid-line" x1="26" y1="70" x2="590" y2="70"/>
        <line class="grid-line" x1="26" y1="135" x2="590" y2="135"/>
        <line class="grid-line" x1="26" y1="200" x2="590" y2="200"/>
        <text class="axis-label" x="28" y="34">목표</text>
        <text class="axis-label" x="28" y="266">시작</text>

        <path class="route-area" d="M {_ROUTE_POINTS[0][0]} {_ROUTE_POINTS[0][1]} L {_pline(_ROUTE_POINTS)} L {_ROUTE_POINTS[-1][0]} 260 L {_ROUTE_POINTS[0][0]} 260 Z"/>
        <polyline class="route-base" points="{_pline(_ROUTE_POINTS)}" fill="none"/>
        <polyline class="route-future" points="{_pline(future)}" fill="none"/>
        <polyline class="route-past" points="{_pline(walked)}" fill="none"/>

        <g transform="translate({_ROUTE_POINTS[0][0]} {_ROUTE_POINTS[0][1]})">
          <circle class="route-dot" r="7"/>
          <text class="milestone-label" x="-4" y="26">시작</text>
        </g>
        <g class="shelter" transform="translate({_ROUTE_POINTS[4][0] - 34} {_ROUTE_POINTS[4][1] - 16})">
          <rect width="68" height="28" rx="14"/>
          <text class="milestone-label" x="34" y="18" text-anchor="middle">중간점</text>
        </g>
        <circle class="target-ring" cx="{tx}" cy="{ty}" r="27"/>
        <circle class="summit-target" cx="{tx}" cy="{ty}" r="11"/>
        <text class="milestone-label" x="{tx - 8}" y="{ty - 30}">목표</text>

        <g id="journey-hiker" class="journey-handle" role="button" tabindex="0" aria-label="자산 여정">
          <circle class="handle-pulse" cx="{hx:.1f}" cy="{hy:.1f}" r="11"/>
          <circle class="handle-core" cx="{hx:.1f}" cy="{hy:.1f}" r="12"/>
          <text class="progress-chip" x="{hx + 18:.1f}" y="{hy - 12:.1f}">{progress_label}</text>
        </g>
      </svg>
      <div class="journey-hint">클릭 · 여정 보기</div>
      <div id="journey-panel" class="journey-panel">
        <b>현재 위치 {progress_label}</b>
        <p>걸어온 길 {progress_label} · 앞으로 갈 길 {_pct_text(1 - progress)}</p>
        <p>목표까지 남은 금액은 {remaining_label}원, 현재 성장률 기준 예상 기간은 {eta}입니다.</p>
      </div>
    </section>
  </div>
</div>
<script>
const panel = document.getElementById("journey-panel");
const handle = document.getElementById("journey-hiker");
function togglePanel() {{ panel.classList.toggle("show"); }}
handle.addEventListener("click", togglePanel);
handle.addEventListener("keydown", e => {{ if (e.key === "Enter" || e.key === " ") {{ e.preventDefault(); togglePanel(); }} }});
</script>
</body>
</html>"""


def render_mountain(
    progress: float,
    height: int = 340,
    current_asset: float | int | None = None,
    target_asset: float | int | None = None,
    annual_growth_rate: float = 0.0,
) -> None:
    from ui.components.html_embed import embed_html

    embed_html(
        _build_html(
            progress=progress,
            current_asset=current_asset,
            target_asset=target_asset,
            annual_growth_rate=annual_growth_rate,
        ),
        height=height,
    )
