"""텔레그램 알림 연결 화면 — QR 표시 + 온디맨드 폴링으로 자동 등록."""
import streamlit as st

from core.telegram_link import issue_link
from src.telegram_alert import poll_register
from core import accounts

_POLL_SEC = 3


def render(username: str) -> None:
    st.subheader("텔레그램 위험 알림 연결")
    if accounts.get_setting(username, "telegram_chat_id"):
        st.success("연결됨 ✅  시장·보유 위험 신호가 있을 때 텔레그램으로 전해드려요.")
        return

    if st.session_state.get("_tg_link_user") != username:
        link, png = issue_link(username)
        st.session_state["_tg_link"] = link
        st.session_state["_tg_qr"] = png
        st.session_state["_tg_link_user"] = username

    st.image(st.session_state["_tg_qr"], width=220, caption="텔레그램 앱으로 QR 스캔")
    st.caption(f"또는 링크로 열기: {st.session_state['_tg_link']}")
    _await_scan(username)


@st.fragment(run_every=_POLL_SEC)
def _await_scan(username: str) -> None:
    """스캔될 때까지 몇 초마다 getUpdates 폴링. 등록되면 리런해 '연결됨' 표시."""
    try:
        regs = poll_register()
    except Exception:
        regs = []
    if any(u == username for u, _ in regs) or accounts.get_setting(username, "telegram_chat_id"):
        st.rerun()
