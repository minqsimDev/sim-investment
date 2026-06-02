import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="SIMvest",
    page_icon="📊",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 설정")
    fred_input = st.text_input(
        label="FRED API 키",
        type="password",
        placeholder="fred.stlouisfed.org",
        value=os.getenv("FRED_API_KEY", ""),
        label_visibility="collapsed",
    )
    if fred_input:
        os.environ["FRED_API_KEY"] = fred_input
        st.success("FRED 연결됨", icon="✅")
    else:
        st.warning("매크로 데이터 비활성화", icon="⚠️")
    st.divider()
    st.caption("투자 참고용  ·  매매 권유 아님")

# ── Pages ─────────────────────────────────────────────────────────────────────
from ui.pages import overview, portfolio, commodities, us_stocks, fx_rates, risk_signals, major_movers

pg = st.navigation({
    "대시보드": [
        st.Page(overview.render,      title="전체 현황",      icon="📊", url_path="overview",      default=True),
        st.Page(portfolio.render,     title="보유 포트폴리오", icon="💼", url_path="portfolio"),
    ],
    "시장": [
        st.Page(commodities.render,   title="원자재",         icon="🛢", url_path="commodities"),
        st.Page(us_stocks.render,     title="미국 주식",       icon="📈", url_path="us-stocks"),
        st.Page(fx_rates.render,      title="FX & 금리",       icon="💱", url_path="fx-rates"),
    ],
    "분석": [
        st.Page(major_movers.render,  title="주요 이동",       icon="🔥", url_path="major-movers"),
    ],
    "리스크": [
        st.Page(risk_signals.render,  title="리스크 모니터",   icon="🚦", url_path="risk-signals"),
    ],
})

pg.run()
