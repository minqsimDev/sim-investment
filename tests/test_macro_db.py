"""macro_indicators DB 왕복 — 채권금리 등 매크로를 DB-우선으로 읽기 위한 save/load.

회귀 방지: 앱 경로(load_market_data)가 매번 라이브 FRED(~9s)를 호출하던 슬로우다운.
배치가 DB에 적재 → 앱은 load_macro로 즉시 읽음. prev_value/year_ago_value(변동 표시)도 보존.
"""
import pandas as pd
from src.database import init_db, save_macro, load_macro


def _row(key, sid, val, prev, yago, date):
    return {"key": key, "series_id": sid, "value": val,
            "prev_value": prev, "year_ago_value": yago, "date": date}


def test_macro_roundtrip_preserves_change_fields(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    df = pd.DataFrame([
        _row("us10y", "DGS10", 4.2, 4.1, 3.8, "2026-06-27"),
        _row("cpi", "CPIAUCSL", 300.0, 299.0, 290.0, "2026-05-01"),
    ])
    save_macro(df, db)
    out = load_macro(db)
    r = out[out["series_id"] == "DGS10"].iloc[0]
    assert r["key"] == "us10y"            # _fetch_macro 와 동일 컬럼명(key)
    assert r["value"] == 4.2
    assert r["prev_value"] == 4.1         # 변동 표시용 — DB 왕복에서 보존
    assert r["year_ago_value"] == 3.8
    assert r["date"] == "2026-06-27"


def test_load_macro_returns_latest_per_series(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    save_macro(pd.DataFrame([_row("us10y", "DGS10", 4.0, 3.9, 3.5, "2026-06-26")]), db)
    save_macro(pd.DataFrame([_row("us10y", "DGS10", 4.3, 4.0, 3.6, "2026-06-27")]), db)
    out = load_macro(db)
    sub = out[out["series_id"] == "DGS10"]
    assert len(sub) == 1                  # 시리즈당 최신 1행
    assert sub.iloc[0]["value"] == 4.3    # 최신 관측일 값


def test_load_macro_empty_db_returns_empty(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    out = load_macro(db)
    assert out.empty                      # 콜드 DB → 빈 결과(호출부가 라이브 폴백)
