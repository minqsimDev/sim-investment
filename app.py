import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="sinvest",
    page_icon="📊",
    layout="wide",
)

# ── 사이드바: FRED API 키 ─────────────────────────────────────────────────────
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

# ── 페이지 등록 ───────────────────────────────────────────────────────────────
from ui.pages import overview, portfolio

pg = st.navigation({
    "대시보드": [
        st.Page(overview.render,  title="전체 현황",      icon="📊", url_path="overview", default=True),
        st.Page(portfolio.render, title="보유 포트폴리오", icon="💼", url_path="portfolio"),
    ]
})

pg.run()
