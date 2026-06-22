import base64
import streamlit as st
from pathlib import Path

from core.accounts import authenticate, create_account, get_portfolios, save_portfolio, has_accounts

_ASSETS = Path(__file__).parent.parent.parent / "assets" / "intro"


def _b64(name: str) -> str:
    return base64.b64encode((_ASSETS / name).read_bytes()).decode()


def _filter_valid_holdings(holdings: list[dict]) -> list[dict]:
    """비전 파서가 반환한 raw 목록에서 유효한 보유 행만 남김.

    qty > 0 인 행은 실제 보유 종목. qty 없어도 cash + 잔고 > 0 이면 유지.
    합계 행·헤더 행·관심종목 행 등 qty=null 쓰레기 행을 제거해
    holding_count 배지와 상세 리스트 숫자를 일치시킨다.
    """
    result = []
    for h in holdings:
        # qty 필드 중 하나라도 양수면 유효 보유
        for key in ("shares", "보유수량", "quantity", "qty"):
            try:
                if float(h[key]) > 0:
                    result.append(h)
                    break
            except (KeyError, TypeError, ValueError):
                pass
        else:
            # qty 없음 → eval_amount > 0 이면 유지 (ETF·펀드·현금 등 수량 대신 금액 기준 종목 포함)
            for key in ("eval_amount", "평가금액", "purchase_amount", "매입금액"):
                try:
                    if float(h[key]) > 0:
                        result.append(h)
                        break
                except (KeyError, TypeError, ValueError):
                    pass
    return result


_SHARED_CSS = """
<style>
[data-testid="stAppViewContainer"] { background: #0E0F13 !important; }
/* #4: 콘텐츠 수직 중앙 — 컬럼 폭 깨짐 방지를 위해 main 레벨에서 센터링(블록컨테이너는 일반 블록 유지) */
[data-testid="stAppViewContainer"] > .main {
  padding: 0 !important;
  min-height: 100vh; display: flex; flex-direction: column; justify-content: center;
}
[data-testid="stAppViewBlockContainer"] { max-width: none !important; padding: 0 !important; }
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
#MainMenu { display: none !important; }
footer { display: none !important; }
.stAppDeployButton { display: none !important; }

/* #4: 폼을 살짝 밝은 패널 카드(#16181C)로 감싸 배경과 분리 */
/* 크기 보강: width:100%로 컬럼을 채워(콘텐츠 폭으로 쪼그라드는 문제 해결) 카드를 충분히 크게 */
div[data-testid="stForm"] {
  background: #16181C !important;
  border: 1px solid #262A33 !important;
  border-radius: 16px !important;
  padding: 30px 28px !important;
  width: 100% !important;
  max-width: 420px !important;
  margin: 0 auto !important;
  box-shadow: 0 16px 40px rgba(0,0,0,0.35) !important;
}
div[data-testid="stTextInput"] label {
  font-size: 11px !important;
  letter-spacing: 0.08em !important;
  color: #9AA0AD !important;
  font-weight: 500 !important;
}
/* #2: 입력 박스를 baseweb 래퍼에 적용 → 눈(보기) 아이콘까지 한 입력 필드로 통합 */
div[data-testid="stTextInput"] [data-baseweb="input"] {
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid #262A33 !important;
  border-radius: 11px !important;
  min-height: 48px !important;     /* 크기 보강: 입력창 높이 ↑ */
}
div[data-testid="stTextInput"] [data-baseweb="input"] input {
  background: transparent !important;
  border: none !important;
  color: #E7E9EE !important;
  font-size: 14px !important;      /* 크기 보강: 입력 글씨 ↑ */
  padding: 6px 4px !important;
}
div[data-testid="stTextInput"] label { margin-bottom: 2px !important; }
/* #3: 플레이스홀더 밝기 상향(WCAG) */
div[data-testid="stTextInput"] [data-baseweb="input"] input::placeholder {
  color: #8A93A0 !important;
  opacity: 1 !important;
}
/* #3: 포커스 시 래퍼에 골드 테두리 + 글로우 (클릭 시 골드 테두리) */
div[data-testid="stTextInput"] [data-baseweb="input"]:focus-within {
  border-color: #E0A33E !important;
  box-shadow: 0 0 0 3px rgba(224,163,62,0.18) !important;
}
/* #2+#3: 눈 아이콘 버튼 — 입력창과 같은 배경(투명)·높이로 붙이고 파란 기본 포커스 제거 */
div[data-testid="stTextInput"] [data-baseweb="input"] button {
  background: transparent !important;
  border: none !important;
  color: #9AA0AD !important;
}
div[data-testid="stTextInput"] [data-baseweb="input"] button:hover { color: #E0A33E !important; }
div[data-testid="stTextInput"] [data-baseweb="input"] button:focus,
div[data-testid="stTextInput"] [data-baseweb="input"] button:focus-visible {
  outline: none !important; box-shadow: none !important; color: #E0A33E !important;
}
/* #3: 로그인 화면 모든 버튼의 파란 기본 outline 제거(골드 테마 통일) */
.stApp button:focus, .stApp button:focus-visible,
.stApp a:focus, .stApp a:focus-visible { outline: none !important; }
/* "Press Enter to submit form" 등 입력 안내 문구 숨김 */
[data-testid="InputInstructions"] { display: none !important; }
div[data-testid="stFormSubmitButton"] > button {
  width: 100%;
  height: 50px;
  border-radius: 12px;
  background: #D9A441 !important;
  color: #0E0F13 !important;
  border: none !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  letter-spacing: 0.08em !important;
  margin-top: 8px;
}
div[data-testid="stFormSubmitButton"] > button:hover { background: rgba(217,164,65,0.85) !important; }
div[data-testid="stButton"] > button {
  background: transparent !important;
  border: none !important;
  color: #7E8694 !important;
  font-size: 11px !important;
  letter-spacing: 0.04em !important;
  padding: 4px 0 !important;
  height: auto !important;
}
div[data-testid="stButton"] > button:hover { color: #9AA0AD !important; }
/* #4: 보조 액션(돌아가기 등) 정렬. 버튼 컨테이너(element-container)가 내용폭(63px)으로
   줄어 있어 정렬 제어가 안 됐다 → 컬럼 폭을 꽉 채우게 강제. */
[data-testid="stElementContainer"]:has(> div[data-testid="stButton"]) { width: 100% !important; }
div[data-testid="stButton"] { margin: 2px 0 0 !important; width: 100% !important;
  display: flex !important; justify-content: flex-start !important; }
div[data-testid="stButton"] > button { width: auto !important; }
/* 폼 카드(로그인·회원가입)는 max-width:420 가운데 정렬(좌측 504). 돌아가기도 같은 420 센터
   박스로 만들어 '카드 좌측 끝'에 정확히 맞춘다(flex-start). 폼이 없는 화면(포트폴리오 등록)은
   콘텐츠가 컬럼을 꽉 채우므로 기본(컬럼 좌측)에 이미 정렬됨 — 여기엔 적용 안 함. */
[data-testid="stVerticalBlock"]:has([data-testid="stForm"]) div[data-testid="stButton"] {
  max-width: 420px !important; margin-left: auto !important; margin-right: auto !important; }
/* 셋업 CTA(분석하기·저장하고 시작·기존 포트폴리오) = 위 카드(드롭존) 폭에 맞춘 반투명 골드 버튼.
   (돌아가기 등 보조 링크와 구분해 key 로 타겟. ※ st-key 클래스는 Streamlit 1.39+; 1.37.x 에선
   미적용되어 기본 텍스트 버튼으로 폴백 — 깨지진 않음.) */
.st-key-btn_analyze div[data-testid="stButton"],
.st-key-btn_save_portfolio div[data-testid="stButton"],
.st-key-btn_use_existing div[data-testid="stButton"] {
  max-width: none !important; width: 100% !important; margin: 8px auto 0 !important; }
.st-key-btn_analyze div[data-testid="stButton"] > button,
.st-key-btn_save_portfolio div[data-testid="stButton"] > button,
.st-key-btn_use_existing div[data-testid="stButton"] > button {
  width: 100% !important; height: auto !important; padding: 12px 16px !important;
  background: rgba(217,164,65,0.12) !important; border: 1px solid rgba(217,164,65,0.55) !important;
  border-radius: 12px !important; color: #E7E9EE !important;
  font-size: 14px !important; font-weight: 750 !important; letter-spacing: 0.02em !important; }
.st-key-btn_analyze div[data-testid="stButton"] > button:hover,
.st-key-btn_save_portfolio div[data-testid="stButton"] > button:hover,
.st-key-btn_use_existing div[data-testid="stButton"] > button:hover {
  background: rgba(217,164,65,0.20) !important; border-color: #D9A441 !important; }
.stApp [data-testid="column"] [data-testid="stVerticalBlock"] { gap: 0.55rem !important; }

/* 파일 업로더 한국어화 — 골드 점선 CTA(포트폴리오 화면 업로더와 통일) */
/* 세로 중앙정렬 CTA: 안내문구 위 · '파일 선택' 버튼 아래 가운데(기본은 좌측 안내+우측 버튼이라 어색) */
[data-testid="stFileUploaderDropzone"] {
  background: rgba(217,164,65,0.06) !important;
  border: 1.5px dashed rgba(217,164,65,0.5) !important;
  border-radius: 16px !important;
  transition: border-color .15s, background .15s;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 10px !important;
  text-align: center !important;
  padding: 22px 16px !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: #D9A441 !important;
  background: rgba(217,164,65,0.12) !important;
}
/* 3단계 시각 안내(① 캡처 → ② 끌어놓기 → ③ 자동 인식) — 포트폴리오 업로더와 동일 */
.scr-steps{display:flex;align-items:stretch;gap:8px;margin:4px 0 14px;flex-wrap:wrap}
.scr-step{display:flex;align-items:center;gap:9px;flex:1;min-width:150px;
  background:#1E2029;border:1px solid #262A33;border-radius:12px;padding:10px 12px}
.scr-step-n{flex:0 0 22px;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;
  background:rgba(217,164,65,.15);color:#D9A441;font-size:12px;font-weight:950}
.scr-step b{display:block;color:#E7E9EE;font-size:13px;font-weight:850}
.scr-step em{display:block;color:#9AA0AD;font-size:12px;font-weight:700;font-style:normal;margin-top:1px}
.scr-step-arr{display:flex;align-items:center;color:#7E8694;font-size:16px;font-weight:900}
@media(max-width:640px){.scr-step-arr{display:none}.scr-step{min-width:0;flex:1 1 100%}}
/* 안내문구: 원문(span/small) 숨기고 ::before/::after 로 교체(dash_style 와 동일·버전 견고) */
/* Streamlit DOM 은 [버튼][안내] 순서라 column 에선 버튼이 위로 옴 → order 로 안내를 위로(안내 위·버튼 아래) */
[data-testid="stFileUploaderDropzoneInstructions"] {
  display: flex !important; flex-direction: column !important;
  align-items: center !important; justify-content: center !important; text-align: center !important;
  order: -1 !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small { display: none !important; }
[data-testid="stFileUploaderDropzoneInstructions"]::before {
  content: "여기로 이미지를 끌어다 놓으세요"; display: block;
  font-size: 14px; font-weight: 750; color: #C7CBD2;
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
}
[data-testid="stFileUploaderDropzoneInstructions"]::after {
  content: "PNG · JPG · JPEG · WEBP"; display: block; margin-top: 3px;
  font-size: 11px; font-weight: 600; color: #7E8694;
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
}
/* 아래 '파일 선택' 버튼 스타일/라벨은 *브라우즈 버튼만* 대상.
   파일 업로드 후 나타나는 칩의 삭제(aria-label^="Remove")·추가(aria-label="Add files")
   버튼까지 '파일 선택'으로 둔갑시키면 안 되므로 명시적으로 제외(브라우즈 버튼 aria-label="" 빈값). */
[data-testid="stFileUploaderDropzone"] button:not([aria-label="Add files"]):not([aria-label^="Remove"]) {
  font-size: 0 !important;
  color: transparent !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-width: 116px !important;
  padding: 8px 18px !important;
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(217,164,65,0.55) !important;
  border-radius: 10px !important;
  transition: background .15s, border-color .15s !important;
}
/* P0 픽스: 버튼 내용(아이콘 폰트 div + 'Browse files')을 숨겨 ::after 라벨을 정중앙에.
   아이콘이 svg 가 아니라 Material 폰트 글리프라 'svg' 셀렉터론 안 잡힘 → 자식 전체.
   파일 input 보호(:not(input)) + 칩 버튼 제외(위와 동일). */
[data-testid="stFileUploaderDropzone"] button:not([aria-label="Add files"]):not([aria-label^="Remove"]) > *:not(input) { display: none !important; }
[data-testid="stFileUploaderDropzone"] button:not([aria-label="Add files"]):not([aria-label^="Remove"]):hover {
  background: rgba(217,164,65,0.14) !important;
  border-color: #D9A441 !important;
}
[data-testid="stFileUploaderDropzone"] button:not([aria-label="Add files"]):not([aria-label^="Remove"])::after {
  content: "파일 선택";
  font-size: 13px !important;
  font-weight: 800 !important;
  color: #E7E9EE !important;
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
}
</style>
"""

_LOGO_ANIM_CSS = """
<style>
  .sim-login-page, .sim-login-page * { box-sizing: border-box; }
  .sim-login-page {
    width: 100%; min-height: 88vh; background: #0E0F13;
    display: flex; align-items: flex-start; justify-content: center;
    padding-top: 7vh;
    font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
  }
  .sim-login-wrap {
    display: flex; flex-direction: column; align-items: center;
    width: 400px; max-width: 90vw;
  }
  .sim-logo {
    width: 220px; height: 220px; opacity: 0; transform: scale(0.96);
    animation: sim-logo-appear 2.8s cubic-bezier(0.4, 0, 0.2, 1) forwards 0.3s;
  }
  .sim-logo img { width: 100%; height: 100%; display: block; filter: brightness(0) invert(1); }
  @keyframes sim-logo-appear { to { opacity: 1; transform: scale(1); } }
  .sim-title {
    opacity: 0; margin-top: 20px; font-size: 14px; letter-spacing: 0.28em;
    font-weight: 500; color: #EFE8D6;   /* 크림 — 헤더 로고와 통일 */
    animation: sim-fade 1s ease forwards 3.3s;
  }
  .sim-sub {
    opacity: 0; margin-top: 8px; font-size: 13px; letter-spacing: 0.04em;
    font-weight: 600; color: #C9CDD4; animation: sim-fade 1s ease forwards 3.6s;
  }
  .sim-sub b { color: #D9A441; font-weight: 800; }
  .sim-value {
    opacity: 0; margin-top: 6px; font-size: 11.5px; letter-spacing: 0.01em;
    color: #9AA0AD; text-align: center; line-height: 1.5; max-width: 320px;
    animation: sim-fade 1s ease forwards 3.8s;
  }
  .sim-btns {
    opacity: 0; margin-top: 40px; width: 100%;
    display: flex; flex-direction: column; align-items: center; gap: 0;
    animation: sim-fade-up 1s ease forwards 4.0s;
  }
  .sim-btn-primary {
    display: flex; align-items: center; justify-content: center;
    width: 100%; height: 50px; border-radius: 12px;
    background: #D9A441; color: #0E0F13 !important; border: none;
    font-size: 13px; font-weight: 600; letter-spacing: 0.08em;
    text-decoration: none !important; cursor: pointer;
    transition: background 0.2s, transform 0.12s;
  }
  .sim-btn-primary:hover { background: rgba(217,164,65,0.85); }
  .sim-btn-primary:active { transform: scale(0.98); }
  .sim-btn-secondary {
    display: flex; align-items: center; justify-content: center;
    width: 100%; height: 44px; border-radius: 12px;
    background: rgba(255,255,255,0.06); color: #E7E9EE !important;
    border: 1px solid #262A33;
    font-size: 12px; font-weight: 500; letter-spacing: 0.06em;
    text-decoration: none !important; cursor: pointer;
    transition: background 0.2s, border-color 0.2s;
  }
  .sim-btn-secondary:hover { background: rgba(255,255,255,0.10); border-color: #D9A441; }
  .sim-btn-guest {
    display: flex; align-items: center; justify-content: space-between;
    width: 100%; height: 48px; border-radius: 12px; padding: 0 18px;
    background: #1C1F27; color: #E7E9EE !important;
    border: 1px solid #3A3F48;
    font-size: 13px; font-weight: 600; letter-spacing: 0.03em;
    text-decoration: none !important; cursor: pointer;
    transition: background 0.2s, border-color 0.2s;
  }
  .sim-btn-guest .g-arrow { color: #9AA0AD; font-weight: 700; }
  .sim-btn-guest:hover { background: #22262F; border-color: #D9A441; }
  .sim-btn-guest:hover .g-arrow { color: #D9A441; }
  .sim-guest-note {
    margin-top: 7px; font-size: 11px; color: #7E8694; letter-spacing: 0.02em;
  }
  .sim-signup-link {
    margin-top: 20px; font-size: 12.5px; color: #9AA0AD !important;
    text-decoration: none !important; letter-spacing: 0.01em;
  }
  .sim-signup-link b { color: #D9A441; font-weight: 700; }
  .sim-signup-link:hover b { color: rgba(217,164,65,0.82); }
  .sim-trust {
    /* WCAG AA(#5): 면책 문구 대비 2.35:1 → 5.2:1 (캡션 토큰과 통일) */
    opacity: 0; margin-top: 40px; font-size: 10px; color: #7E8694;
    text-align: center; line-height: 1.6; letter-spacing: 0.01em; max-width: 360px;
    animation: sim-fade 1s ease forwards 4.4s;
  }
  .sim-divider {
    display: flex; align-items: center; width: 100%; margin: 12px 0; gap: 10px;
    color: #7E8694; font-size: 10px; letter-spacing: 0.06em;
  }
  .sim-divider::before, .sim-divider::after {
    content: ''; flex: 1; height: 1px; background: #262A33;
  }
  @keyframes sim-fade    { to { opacity: 1; } }
  @keyframes sim-fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
</style>
"""


def _inject_guest_restore_js() -> None:
    st.html("""
<script>
(function(){
  try {
    var params = new URLSearchParams(window.location.search);
    var wantsApp = window.location.pathname !== "/" || params.has("trend") || params.has("refresh");
    var isExplicitLogin = params.has("_login") || params.has("_register");
    if (
      window.localStorage.getItem("siminvest_auth_role") === "guest" &&
      wantsApp &&
      !isExplicitLogin &&
      !params.has("_auth") &&
      !params.has("_user")
    ) {
      params.set("_auth", "guest");
      var next = window.location.pathname + "?" + params.toString();
      window.location.replace(next);
    }
  } catch (e) {}
})();
</script>
""")


def _logo_header(subtitle: str = "") -> str:
    logo = _b64("sim_heart_logo_transparent.png")
    # #2 영역(1번 문제): 서브텍스트를 충분히 밝은 회색(#9AA0AD)으로 — 다크 배경에서 또렷
    sub_html = f'<div style="font-size:12px;letter-spacing:0.08em;color:#9AA0AD;margin-top:5px;font-weight:600;">{subtitle}</div>' if subtitle else ""
    return f"""
<div style="display:flex;flex-direction:column;align-items:center;padding:8px 0 22px;gap:6px;
     font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif;">
  <!-- #1: 다크 배경에서 心 로고가 안 보이던 문제 → invert로 흰색 처리 -->
  <img src="data:image/png;base64,{logo}" width="60" height="60" alt="心"
       style="display:block;opacity:0.95;filter:brightness(0) invert(1);">
  <!-- #1: 브랜드명이 검정(#1c1a14)이라 안 보이던 문제 → 밝은 흰색으로 -->
  <div style="font-size:15px;letter-spacing:0.18em;font-weight:800;color:#EFE8D6;margin-top:8px;">SIM INVESTMENT</div>
  {sub_html}
</div>
"""


def render() -> None:
    from ui.components.liquid_bg import liquid_background
    liquid_background()  # Liquid Ink 배경(로그인 화면)
    st.markdown(_SHARED_CSS, unsafe_allow_html=True)
    _inject_guest_restore_js()

    if st.query_params.get("_login") == "1":
        st.session_state.login_screen = "login"
        st.query_params.clear()
    elif st.query_params.get("_register") == "1":
        st.session_state.login_screen = "register"
        st.query_params.clear()

    screen = st.session_state.get("login_screen")
    if screen == "login":
        _render_login()
    elif screen == "register":
        _render_register()
    elif screen == "setup_portfolio":
        _render_portfolio_setup()
    else:
        _render_landing()


def _render_landing() -> None:
    logo = _b64("sim_heart_logo_transparent.png")
    st.markdown(f"""
{_LOGO_ANIM_CSS}
<div class="sim-login-page">
  <div class="sim-login-wrap">
    <div class="sim-logo">
      <img src="data:image/png;base64,{logo}" alt="心">
    </div>
    <div class="sim-title">SIM INVESTMENT</div>
    <div class="sim-sub">진심<b>(心)</b>으로 보는 투자</div>
    <div class="sim-value">내 포트폴리오의 가장 큰 리스크를 먼저 짚어주는 투자 코치</div>
    <div class="sim-btns">
      <a class="sim-btn-primary" href="?_login=1" target="_top">로그인</a>
      <div class="sim-divider">또는</div>
      <a class="sim-btn-guest" href="?_auth=guest" target="_top">
        <span>게스트로 둘러보기</span><span class="g-arrow">&rarr;</span>
      </a>
      <div class="sim-guest-note">가입 없이 바로 체험</div>
      <a class="sim-signup-link" href="?_register=1" target="_top">처음이신가요? <b>계정 만들기</b></a>
    </div>
    <div class="sim-trust">투자 참고용 · 매매 권유 아님 · 데이터는 실시간이 아닐 수 있습니다</div>
  </div>
</div>
""", unsafe_allow_html=True)


def _render_login() -> None:
    st.markdown(_logo_header("로그인"), unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login_form"):
            username = st.text_input("아이디", placeholder="아이디 입력")
            password = st.text_input("비밀번호", placeholder="비밀번호 입력", type="password")
            submitted = st.form_submit_button("로그인", use_container_width=True)

        if st.button("← 돌아가기", key="btn_login_back"):
            st.session_state.login_screen = None
            st.rerun()

        st.markdown("""
<!-- #2: '계정 만들기' 링크 골드 강조 / #4: 돌아가기와 간격 좁힘(margin-top 축소) -->
<div style="text-align:center;margin-top:2px;font-size:12.5px;color:#9AA0AD;
     font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif;">
  계정이 없으신가요?&nbsp;
  <a href="?_register=1" target="_top"
     style="color:#E0A33E;font-weight:700;text-decoration:none;border-bottom:1px solid rgba(224,163,62,0.5);padding-bottom:1px;">계정 만들기</a>
</div>
""", unsafe_allow_html=True)

    if submitted:
        if not username or not password:
            with col:
                st.error("아이디와 비밀번호를 입력해 주세요.")
            return
        acc = authenticate(username, password)
        if acc is None:
            with col:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
            return

        portfolios = get_portfolios(username)
        if portfolios:
            first = portfolios[0]
            st.session_state.update({
                "authenticated": True,
                "auth_role": "user",
                "username": username,
                "brokerage_provider": "screenshot",
                "brokerage_holdings": _filter_valid_holdings(first["holdings"]),
                "brokerage_cash_balance": first.get("cash", 0.0),
                "login_screen": None,
            })
            st.query_params["_user"] = username
        else:
            st.session_state.update({
                "username": username,
                "login_screen": "setup_portfolio",
            })
        st.rerun()


def _render_register() -> None:
    st.markdown(_logo_header("계정 만들기"), unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("register_form"):
            username = st.text_input("아이디", placeholder="2자 이상")
            password = st.text_input("비밀번호", placeholder="4자 이상", type="password")
            confirm  = st.text_input("비밀번호 확인", placeholder="비밀번호 재입력", type="password")
            submitted = st.form_submit_button("계정 만들기", use_container_width=True)

        if st.button("← 돌아가기", key="btn_register_back"):
            st.session_state.login_screen = None
            st.rerun()

    if submitted:
        if password != confirm:
            with col:
                st.error("비밀번호가 일치하지 않습니다.")
            return
        err = create_account(username, password)
        if err:
            with col:
                st.error(err)
            return
        st.session_state.update({
            "username": username,
            "login_screen": "setup_portfolio",
        })
        st.rerun()


def _logo_loading_html(logo_b64: str) -> str:
    return f"""
<div style="position:fixed;inset:0;z-index:9999;
     background:rgba(0,0,0,0.45);backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px);
     display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;
     font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif;">
  <style>
    @keyframes sim-pulse {{
      0%,100% {{ opacity:0.4; transform:scale(0.92); }}
      50%      {{ opacity:0.9; transform:scale(1.0);  }}
    }}
    .sim-loading-logo {{
      animation: sim-pulse 2.2s ease-in-out infinite;
    }}
    @keyframes sim-dot {{
      0%,80%,100% {{ opacity:0.2; transform:translateY(0);   }}
      40%          {{ opacity:1;   transform:translateY(-6px); }}
    }}
    .sim-dot {{ display:inline-block; width:6px; height:6px; border-radius:50%;
      background:#fff; margin:0 3px;
    }}
    .sim-dot:nth-child(1) {{ animation:sim-dot 1.4s ease-in-out infinite 0s;   }}
    .sim-dot:nth-child(2) {{ animation:sim-dot 1.4s ease-in-out infinite 0.2s; }}
    .sim-dot:nth-child(3) {{ animation:sim-dot 1.4s ease-in-out infinite 0.4s; }}
  </style>
  <img class="sim-loading-logo" src="data:image/png;base64,{logo_b64}"
       width="80" height="80" alt="心">
  <div style="display:flex;flex-direction:column;align-items:center;gap:10px;">
    <div style="font-size:13px;letter-spacing:0.12em;color:#fff;">종목 분석 중</div>
    <div><span class="sim-dot"></span><span class="sim-dot"></span><span class="sim-dot"></span></div>
  </div>
</div>
"""


def _prefetch_market_data() -> None:
    """분석 대기 시간에 시장 데이터를 백그라운드로 미리 로드."""
    import threading
    def _fetch():
        try:
            from data.loader import load_market_data, load_target_prices
            load_market_data()
            load_target_prices()
        except Exception:
            pass
    threading.Thread(target=_fetch, daemon=True).start()


def _render_portfolio_setup() -> None:
    username = st.session_state.get("username", "")
    logo_b64 = _b64("sim_heart_logo_transparent.png")

    st.markdown(_logo_header("포트폴리오 등록"), unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
<div class="scr-steps">
  <div class="scr-step"><span class="scr-step-n">1</span><div><b>증권사 앱 캡처</b><em>보유 종목 화면을 스크린샷</em></div></div>
  <div class="scr-step-arr">→</div>
  <div class="scr-step"><span class="scr-step-n">2</span><div><b>끌어다 놓기</b><em>아래에 이미지를 드롭</em></div></div>
  <div class="scr-step-arr">→</div>
  <div class="scr-step"><span class="scr-step-n">3</span><div><b>자동 인식</b><em>종목·평가금액 추출</em></div></div>
</div>
""", unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "스크린샷 업로드",
            type=["png", "jpg", "jpeg", "webp"],
            key="portfolio_image_upload",
            label_visibility="collapsed",
            accept_multiple_files=True,
        )

        has_files = bool(uploaded)
        analyze_clicked = has_files and st.button("분석하기", key="btn_analyze", use_container_width=True)

    if analyze_clicked:
        loading_slot = st.empty()
        loading_slot.markdown(_logo_loading_html(logo_b64), unsafe_allow_html=True)
        _prefetch_market_data()
        try:
            from core.vision_parser import parse_portfolio_image

            files = uploaded if isinstance(uploaded, list) else [uploaded]
            first = files[0]
            img_bytes = first.read()
            mt = first.type or "image/png"
            extra = [(f.read(), f.type or "image/png") for f in files[1:]]
            holdings = parse_portfolio_image(img_bytes, media_type=mt, extra_images=extra)
            holdings = _filter_valid_holdings(holdings)
            st.session_state["_parsed_holdings"] = holdings
        except Exception as e:
            loading_slot.empty()
            with col:
                st.error(f"분석 실패: {e}")
        else:
            loading_slot.empty()

    parsed = st.session_state.get("_parsed_holdings")
    with col:
        if parsed:
            rows_html = "".join(
                f'<div style="display:flex;justify-content:space-between;padding:7px 0;'
                f'border-bottom:1px solid rgba(255,255,255,0.06);font-size:12px;">'
                f'<span style="color:#E7E9EE;font-weight:500;">{h.get("name","—")}</span>'
                f'<span style="color:#9AA4B2;">{h.get("ticker") or h.get("asset_class","")}</span>'
                f'</div>'
                for h in parsed
            )
            st.markdown(f"""
<div style="font-size:11px;color:#9AA4B2;margin:4px 0 6px;
     font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif;">
  {len(parsed)}개 종목 감지됨
</div>
<div style="background:rgba(255,255,255,0.04);border:1px solid #262A33;border-radius:14px;
     padding:12px 16px;margin-bottom:14px;max-height:220px;overflow-y:auto;
     font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif;">
  {rows_html}
</div>
""", unsafe_allow_html=True)

            pf_name = st.text_input("포트폴리오 이름", value="내 포트폴리오", key="pf_name_input")

            if st.button("저장하고 시작", key="btn_save_portfolio", use_container_width=True):
                name = pf_name.strip() or "내 포트폴리오"
                save_portfolio(username, parsed, name=name)
                st.session_state.pop("_parsed_holdings", None)
                st.session_state.update({
                    "authenticated": True,
                    "auth_role": "user",
                    "brokerage_provider": "screenshot",
                    "brokerage_holdings": _filter_valid_holdings(parsed),
                    "brokerage_cash_balance": 0.0,
                    "login_screen": None,
                })
                st.query_params["_user"] = username
                st.rerun()

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        existing = get_portfolios(username)
        if existing:
            if st.button("기존 포트폴리오로 시작", key="btn_use_existing", use_container_width=True):
                first = existing[0]
                st.session_state.pop("_parsed_holdings", None)
                st.session_state.update({
                    "authenticated": True,
                    "auth_role": "user",
                    "brokerage_provider": "screenshot",
                    "brokerage_holdings": _filter_valid_holdings(first["holdings"]),
                    "brokerage_cash_balance": first.get("cash", 0.0),
                    "login_screen": None,
                })
                st.query_params["_user"] = username
                st.rerun()

        if st.button("← 돌아가기", key="btn_setup_back"):
            st.session_state.login_screen = None
            st.rerun()
