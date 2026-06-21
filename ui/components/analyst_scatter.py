"""
애널리스트 전망 산점도 — 상승여력 %(x) × 커버리지(애널리스트 수, y), 점 크기 = 시가총액.

라벨 충돌 회피: 시총 상위 N개만 리더선(leader line) 주석으로 빈 공간에 분산 배치하고,
나머지는 hover 전용. 점/라벨이 플롯 밖으로 잘리지 않도록 축 범위·마진에 여백을 둔다.
미국·한국 탭이 이 동일 로직을 공유한다(표시 전용 — 계산은 호출부에서 끝낸다).
"""
from __future__ import annotations

import math

import plotly.graph_objects as go


def analyst_scatter_fig(points: list[dict], *, label_top: int = 5, assumed_width: int = 700):
    """points: [{name, x(상승여력%), y(애널수), ticker, rank(시총순위·작을수록 큼), hover}, ...]
    상승여력·커버리지가 모두 있는 점만 넘긴다. 반환: go.Figure (점 없으면 None)."""
    pts = [p for p in points if p.get("x") is not None and p.get("y") is not None]
    if not pts:
        return None

    def _rank(p: dict) -> float:
        r = p.get("rank")
        return float(r) if isinstance(r, (int, float)) and r and r > 0 else 99.0

    _maxproxy = max((1.0 / _rank(p) for p in pts), default=1.0)
    # 시총 상위 label_top개만 상시 라벨, 나머지는 hover
    _label = {p["ticker"] for p in sorted(pts, key=_rank)[:label_top]}

    # 색 깊이 = 상승여력 크기(트리맵의 발산 스케일과 동일 개념). 여력 클수록 진하게,
    # 0 근처는 옅게 — 단 어두운 배경에 묻히지 않게 농도 하한(0.45)을 둔다.
    _maxup = max((abs(p["x"]) for p in pts), default=1.0) or 1.0

    def _depth_rgba(x: float) -> str:
        m = min(abs(x) / _maxup, 1.0)
        a = 0.45 + 0.5 * m
        rgb = "242,85,96" if x >= 0 else "77,144,240"   # 상회=레드 / 하회=블루
        return f"rgba({rgb},{a:.2f})"

    xs, ys, cols, sizes, hover = [], [], [], [], []
    labeled = []  # (x, y, name)
    for p in pts:
        proxy = 1.0 / _rank(p)
        sizes.append(15 + math.sqrt(proxy / _maxproxy) * (46 - 15))   # 15~46px area비례
        xs.append(p["x"]); ys.append(p["y"])
        cols.append(_depth_rgba(p["x"]))
        hover.append(p.get("hover", p["name"]))
        if p["ticker"] in _label:
            labeled.append((p["x"], p["y"], p["name"]))

    # 축 범위 여백(마커는 안쪽, 라벨은 상단 헤드룸) — 점/라벨이 잘리지 않게
    _xlo, _xhi = min(xs), max(xs)
    _ylo, _yhi = min(ys), max(ys)
    _xpad = (_xhi - _xlo) * 0.12 + 4
    _ypad = (_yhi - _ylo) * 0.15 + 2
    _xmin, _xmax = _xlo - _xpad, _xhi + _xpad
    _ymin, _ymax = max(0.0, _ylo - _ypad), _yhi + _ypad * 1.6

    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="markers", cliponaxis=False,
        marker=dict(size=sizes, sizemode="diameter", color=cols, opacity=1.0,
                    line=dict(width=1, color="#0E0F13")),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>",
    ))
    fig.add_vline(x=0, line_width=1.5, line_dash="dot", line_color="#7E8694")

    # 라벨 충돌 회피 — 점 픽셀 위치를 추정해, 이미 놓인 라벨/범례와 안 겹치는 첫 후보 오프셋 선택
    _marg = dict(l=10, r=34, t=46, b=6)
    _pw = assumed_width - _marg["l"] - _marg["r"]
    _ph = 360 - _marg["t"] - _marg["b"]

    def _to_px(xv, yv):
        fx = (xv - _xmin) / ((_xmax - _xmin) or 1)
        fy = (yv - _ymin) / ((_ymax - _ymin) or 1)
        return _marg["l"] + fx * _pw, _marg["t"] + (1 - fy) * _ph

    def _ov(a, b):
        return not (a[0]+a[2] <= b[0] or b[0]+b[2] <= a[0]
                    or a[1]+a[3] <= b[1] or b[1]+b[3] <= a[1])

    # 후보 오프셋(px): 위·바깥쪽(점에서 떨어진 곳) 우선 → 막히면 더 멀리
    _cand = [(0,-30),(38,-26),(50,2),(38,30),(0,42),(-38,30),(-50,2),(-38,-26),
             (0,-60),(66,-48),(80,4),(66,54),(0,72),(-66,54),(-80,4),(-66,-48),
             (0,-90),(0,100)]
    _placed = [(_marg["l"], _marg["t"], 156, 40)]  # 좌상단 범례 영역 예약
    _lh = 16
    for (xv, yv, nm) in sorted(labeled, key=lambda p: -p[1]):  # 커버리지 높은 순
        _bw = max(46, len(nm) * 8 + 10)
        _ppx, _ppy = _to_px(xv, yv)
        _ax, _ay = _cand[0]
        for (cx, cy) in _cand:
            box = (_ppx + cx - _bw/2, _ppy + cy - _lh/2, _bw, _lh)
            if any(_ov(box, b) for b in _placed):
                continue
            if box[0] < 2 or box[0] + box[2] > _pw + _marg["l"] + _marg["r"] - 2 or box[1] < 2:
                continue
            _ax, _ay = cx, cy
            _placed.append(box)
            break
        else:
            _placed.append((_ppx + _ax - _bw/2, _ppy + _ay - _lh/2, _bw, _lh))
        fig.add_annotation(
            x=xv, y=yv, text=nm, showarrow=True,
            ax=_ax, ay=_ay, axref="pixel", ayref="pixel",
            arrowhead=0, arrowwidth=1, arrowcolor="#5A6170", standoff=3,
            font=dict(size=10, color="#E7E9EE"),
            bgcolor="rgba(14,15,19,0.82)", bordercolor="#2A2F3A", borderwidth=1, borderpad=2,
            xanchor="center", yanchor="middle",
        )
    # 색 범례 — 군집이 몰리는 우상단을 피해 좌상단에 배치
    fig.add_annotation(
        xref="paper", yref="paper", x=0.0, y=1.0, xanchor="left", yanchor="top",
        align="left", showarrow=False, font=dict(size=10),
        text="<span style='color:#F25560'>●</span> 상승여력(목표가 상회)<br>"
             "<span style='color:#4D90F0'>●</span> 목표가 하회<br>"
             "<span style='color:#9AA0AD;font-size:9px'>※ 진할수록 여력 큼</span>",
        bgcolor="rgba(14,15,19,0.72)", bordercolor="#262A33", borderwidth=1, borderpad=5,
    )
    fig.update_layout(
        height=360, margin=_marg,
        paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
        xaxis=dict(title=dict(text="상승여력 % (목표가 평균 대비)", font=dict(size=10)),
                   range=[_xmin, _xmax], showgrid=True, gridcolor="#262A33",
                   zeroline=False, ticksuffix="%", tickfont=dict(size=9, color="#7E8694")),
        yaxis=dict(title=dict(text="애널리스트 수(커버리지)", font=dict(size=10)),
                   range=[_ymin, _ymax], showgrid=True, gridcolor="#262A33",
                   tickfont=dict(size=9, color="#7E8694")),
        showlegend=False,
    )
    return fig
