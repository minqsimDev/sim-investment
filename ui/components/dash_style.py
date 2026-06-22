"""Clean minimal dashboard styling."""
from base64 import b64encode
from html import escape as html_escape
import io
from pathlib import Path

import streamlit as st
import pandas as pd

# ── Color tokens (Dark Theme) ─────────────────────────────────────────────────
NAVY     = "#F3F5F8"   # headings (text only — bg uses BASALT)
CHARCOAL = "#9AA0AD"   # medium text
BG       = "#0E0F13"   # main background
WHITE    = "#16181F"   # card / widget surface
BORDER   = "#262A33"   # line
POS      = "#F25560"   # 상승 (한국식 레드)
NEG      = "#4D90F0"   # 하락 (한국식 블루)
POS_BG   = "rgba(242,85,96,0.13)"
NEG_BG   = "rgba(77,144,240,0.13)"
META     = "#7E8694"   # muted secondary text
TEXT     = "#E7E9EE"   # primary text
ACCENT   = "#D9A441"   # gold
ACCENT2  = "#D9A441"   # gold
SALMON   = "#D9A441"   # compat
LIGHT    = "#1E2029"   # subtle surface
SEA      = "#D9A441"   # gold
BASALT   = "#0E0F13"
GRADIENT = "linear-gradient(135deg,#1A1C24 0%,#16181F 100%)"
SOFT_GRADIENT = "linear-gradient(135deg,rgba(217,164,65,0.08) 0%,rgba(217,164,65,0.03) 100%)"
# kept for any remaining palette refs
SKY      = "#4D90F0"
LIME     = "#D9A441"
RED      = "#F25560"
WINE     = "#F25560"
SLATE    = "#0E0F13"
OLIVE    = "#7E8694"

APP_SHELL_CSS = f"""<style>
:root {{
    --sv-basalt:{BASALT};
    --sv-deep:{TEXT};
    --sv-sea:{SEA};
    --sv-sea2:{LIGHT};
    --sv-hallasan:{ACCENT};
    --sv-oreum:#8fae8c;
    --sv-tangerine:{ACCENT2};
    --sv-camellia:{NEG};
    --sv-green:{POS};
    --sv-gradient:{GRADIENT};
    --sv-soft-gradient:{SOFT_GRADIENT};
    --sv-paper:{BG};
    --sv-card:rgba(22,24,31,0.97);
    --sv-line:{BORDER};
    --sv-muted:{META};
    --sv-shadow:0 22px 55px rgba(15,31,42,0.12);
}}

/* Streamlit 기본 헤더(60px 고정 바)는 툴바·상태·메뉴를 모두 숨겨 빈 껍데기인데
   z-index 999990 불투명 블러로 커스텀 헤더(.sv-shell 로고·네비) 상단을 덮어 잘라먹었다(#3).
   실제 헤더는 sv-shell이므로 빈 기본 헤더는 숨겨 가림을 제거한다. */
header[data-testid="stHeader"] {{
    display:none !important;
}}

[data-testid="stToolbar"],
[data-testid="stTopNav"],
div[data-testid="stTopNav"] {{
    display:none !important;
}}

[data-testid="stToolbar"] {{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    width:100% !important;
    max-width:1380px !important;
    margin:0 auto !important;
    padding:8px 28px 0 !important;
    background:transparent !important;
}}
[data-testid="stToolbar"] > div {{
    width:auto !important;
    min-width:0 !important;
}}
[data-testid="stToolbar"] .rc-overflow {{
    display:inline-flex !important;
    align-items:center !important;
    gap:3px !important;
    padding:6px !important;
    background:rgba(22,24,31,0.90) !important;
    border:1px solid rgba(38,42,51,0.95) !important;
    border-radius:20px !important;
    box-shadow:0 10px 26px rgba(15,31,42,0.07) !important;
}}
[data-testid="stToolbar"] .rc-overflow-item {{
    border-radius:17px !important;
    display:inline-flex !important;
    opacity:1 !important;
    position:relative !important;
}}
[data-testid="stToolbar"] .rc-overflow-item-rest,
[data-testid="stToolbar"] .rc-overflow-item-suffix {{
    display:none !important;
}}
[data-testid="stToolbar"] .rc-overflow-item-hidden {{
    display:inline-flex !important;
    opacity:1 !important;
    visibility:visible !important;
    height:auto !important;
    overflow:visible !important;
}}
[data-testid="stTopNavSection"] {{
    border-radius:14px !important;
    padding:9px 14px !important;
    min-height:36px !important;
    color:#7E8694 !important;
}}
[data-testid="stTopNavSection"] p {{
    color:#7E8694 !important;
    font-size:13px !important;
    font-weight:900 !important;
    letter-spacing:0 !important;
}}
[data-testid="stTopNavSection"]:hover {{
    background:#1E2029 !important;
}}
[data-testid="stToolbar"] .rc-overflow-item:has([data-testid="stTopNavDropdownLink"][aria-current="page"]) [data-testid="stTopNavSection"] {{
    background:{BASALT} !important;
    color:#ffffff !important;
    box-shadow:0 10px 24px rgba(31,36,35,0.20) !important;
}}
[data-testid="stToolbar"] .rc-overflow-item:has([data-testid="stTopNavDropdownLink"][aria-current="page"]) [data-testid="stTopNavSection"] p,
[data-testid="stToolbar"] .rc-overflow-item:has([data-testid="stTopNavDropdownLink"][aria-current="page"]) [data-testid="stTopNavSection"] svg {{
    color:#ffffff !important;
    fill:#ffffff !important;
}}
[data-testid="stTopNavPopover"] {{
    border:1px solid {BORDER} !important;
    border-radius:18px !important;
    overflow:hidden !important;
    box-shadow:0 18px 40px rgba(15,31,42,0.14) !important;
    background:#16181F !important;
}}
[data-testid="stTopNavDropdownLink"] {{
    border-radius:12px !important;
    margin:3px 5px !important;
}}
[data-testid="stTopNavDropdownLink"][aria-current="page"] {{
    background:{BASALT} !important;
    color:#ffffff !important;
}}
[data-testid="stTopNavDropdownLink"] p {{
    font-size:13px !important;
    font-weight:800 !important;
    letter-spacing:0 !important;
}}

[data-testid="stTopNav"],
div[data-testid="stTopNav"] {{
    max-width:1380px !important;
    margin:0 auto !important;
    padding:0 28px 10px !important;
    background:transparent !important;
}}
[data-testid="stTopNav"] nav,
[data-testid="stTopNav"] ul {{
    background:rgba(22,24,31,0.90) !important;
    border:1px solid rgba(38,42,51,0.95) !important;
    border-radius:20px !important;
    padding:6px !important;
    box-shadow:0 10px 26px rgba(15,31,42,0.07) !important;
}}
[data-testid="stTopNav"] a,
[data-testid="stTopNav"] button {{
    border-radius:17px !important;
    color:#7E8694 !important;
    font-size:13px !important;
    font-weight:850 !important;
    letter-spacing:0 !important;
}}
[data-testid="stTopNav"] a[aria-current="page"],
[data-testid="stTopNav"] button[aria-current="page"],
[data-testid="stTopNav"] [aria-selected="true"] {{
    background:{BASALT} !important;
    color:#ffffff !important;
    box-shadow:0 10px 24px rgba(31,36,35,0.20) !important;
}}

.sv-shell {{
    max-width:1380px;
    margin:0 auto;
    padding:14px 28px 10px;
}}
.sv-app-header {{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:18px;
}}
.sv-brand {{
    display:flex;
    gap:14px;
    align-items:center;
    min-width:0;
    color:inherit !important;
    text-decoration:none !important;
}}
.sv-logo {{
    width:clamp(42px,5.2vw,58px);
    height:clamp(42px,5.2vw,58px);
    border-radius:0;
    background:transparent;
    border:0;
    display:grid;
    place-items:center;
    font-weight:950;
    box-shadow:none;
    position:relative;
    overflow:visible;
    flex:0 0 auto;
    padding:0;
}}
.sv-logo img {{
    width:100%;
    height:100%;
    display:block;
    object-fit:contain;
    border-radius:0;
    filter:brightness(0) invert(1);
}}
.sv-logo span {{
    color:{BASALT};
    font-size:34px;
    line-height:1;
    letter-spacing:0;
}}
.sv-brand h1 {{
    margin:0 !important;
    padding:0 !important;
    color:#EFE8D6 !important;            /* 크림 */
    font-size:clamp(19px,2.2vw,24px) !important;
    line-height:1.05 !important;
    font-weight:950 !important;
    letter-spacing:0 !important;
}}
.sv-brand p {{
    margin:2px 0 0 !important;
    padding:0 !important;
    color:#C9C0A8 !important;            /* 연한 크림 */
    font-size:clamp(10px,1.2vw,12px) !important;
    font-weight:700 !important;
    letter-spacing:.01em !important;
}}
.sv-nav {{
    display:inline-flex;
    align-items:center;
    gap:6px;
    padding:6px 8px;
    background:rgba(22,24,31,0.90);
    border:1px solid rgba(38,42,51,0.95);
    border-radius:18px;
    box-shadow:0 12px 30px rgba(66,87,107,0.10);
    flex:0 0 auto;
}}
.sv-nav a {{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-height:36px;
    padding:0 14px;
    border-radius:12px;
    color:{OLIVE} !important;
    text-decoration:none !important;
    font-size:13px;
    font-weight:900;
    letter-spacing:0;
    white-space:nowrap;
    flex-shrink:0;               /* 모바일에서 압축돼 글자 잘리는 것 방지(넘치면 nav가 가로 스크롤) */
}}
.sv-nav a:hover {{
    background:#1E2029;
    color:{TEXT} !important;
}}
.sv-nav a.active {{
    background:{ACCENT};
    color:#0E0F13 !important;
    box-shadow:0 6px 18px rgba(217,164,65,0.30);
}}
.sv-nav-sep {{
    width:1px;height:20px;background:rgba(38,42,51,0.9);margin:0 6px;
}}
.sv-nav-refresh {{
    display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;
    width:36px;height:36px;border-radius:14px;
    color:#7E8694 !important;text-decoration:none !important;
    font-size:18px !important;line-height:1;
    transition:background 0.15s,color 0.15s;
}}
.sv-nav-refresh:hover {{
    background:#1E2029;color:{TEXT} !important;
}}
.sv-acct-name {{
    font-size:12px;font-weight:850;color:{TEXT};max-width:120px;overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap;margin:0 6px 0 2px;
}}
.sv-acct {{
    display:inline-flex;align-items:center;flex-shrink:0;height:32px;padding:0 12px;border-radius:999px;
    border:1px solid {BORDER};background:#16181F;
    color:#C9CEDA !important;text-decoration:none !important;
    font-size:12px !important;font-weight:850;white-space:nowrap;
    transition:border-color 0.15s,color 0.15s;
}}
.sv-acct:hover {{ border-color:{ACCENT};color:{ACCENT} !important; }}
@media(max-width:920px) {{
    .sv-shell {{ padding:18px 16px 10px; }}
    .sv-app-header {{ flex-direction:column; align-items:flex-start; }}
    .sv-nav {{ width:100%; overflow-x:auto; box-sizing:border-box; }}
    [data-testid="stTopNav"], div[data-testid="stTopNav"] {{ padding:0 16px 10px !important; }}
    [data-testid="stToolbar"] {{ padding:8px 16px 0 !important; }}
    [data-testid="stToolbar"] .rc-overflow {{ max-width:100%; overflow-x:auto !important; }}
}}
@media(max-width:560px) {{
    .sv-shell {{ padding:12px 12px 8px; }}
    .sv-brand {{ gap:10px; }}
    .sv-nav a {{ min-height:32px; padding:0 10px; font-size:12px; }}
    .sv-nav-refresh {{ width:32px; height:32px; border-radius:12px; }}
}}

[data-testid="stToolbar"],
[data-testid="stTopNav"],
div[data-testid="stTopNav"] {{
    display:none !important;
}}
</style>"""

GLOBAL_CSS = f"""<style>
/* ── 빈 상태(empty state) 공용 — 미연결·로딩 실패 등 중립 '준비 중' ── */
.sv-empty{{display:flex;flex-direction:column;align-items:center;gap:8px;text-align:center;
  background:#16181F;border:1px dashed #2E333D;border-radius:14px;padding:22px 18px;margin:8px 0}}
.sv-empty .es-chip{{font-size:10.5px;font-weight:800;letter-spacing:.04em;color:#7E8694;
  background:rgba(126,134,148,.12);border:1px solid #2E333D;border-radius:999px;padding:3px 11px}}
.sv-empty .es-msg{{font-size:12.5px;font-weight:700;color:#9AA0AD;line-height:1.5}}
.sv-empty .es-sub{{font-size:11px;font-weight:600;color:#7E8694;line-height:1.45}}
/* ── 용어 설명 글로사리 ── */
.sv-glossary{{display:flex;flex-direction:column;gap:11px}}
.sv-glossary .gl-item{{display:flex;flex-direction:column;gap:2px}}
.sv-glossary .gl-item b{{font-size:12.5px;font-weight:850;color:#E7E9EE}}
.sv-glossary .gl-item span{{font-size:11.5px;font-weight:600;color:#9AA0AD;line-height:1.5}}
/* ── Hide Streamlit chrome ───────────────────────────────────── */
[data-testid="stStatusWidget"] {{ display:none !important; }}
.stAppDeployButton {{ display:none !important; }}
#MainMenu {{ display:none !important; }}
footer {{ display:none !important; }}

/* ── Layout ─────────────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing:border-box; }}
/* "Press Enter to submit/apply" 등 입력 안내 문구 숨김 */
[data-testid="InputInstructions"] {{ display:none !important; }}
/* CSS/스크립트만 출력하는 빈 컨테이너(스타일 전용 st.markdown, script/style 전용 st.html)가
   세로 블록의 flex gap 을 누적시켜 상단에 큰 빈 여백을 만든다(#6) → 보이지 않는 것만 접어 gap 에서 제외.
   (style/script 'only-child' 만 타겟 → 보이는 내용을 가진 st.html/markdown 은 영향 없음) */
[data-testid="stVerticalBlock"] > [data-testid="element-container"]:has(> [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] > style:only-child),
[data-testid="stVerticalBlock"] > [data-testid="element-container"]:has(> [data-testid="stHtml"] > style:only-child),
[data-testid="stVerticalBlock"] > [data-testid="element-container"]:has(> [data-testid="stHtml"] > script:only-child) {{
    display:none !important;
}}
html, body {{ background:{BG} !important; }}
html, body, .stApp {{ width:100% !important; max-width:100% !important; overflow-x:hidden !important; }}
.stApp {{
    background:
        linear-gradient(180deg,#0E0F13 0%,#0E0F13 100%) !important;
    min-height:100vh !important;
}}
/* ── Scroll fix ─────────────────────────────────────────────── */
/* section.main must be height-constrained so overflow-y triggers scroll */
[data-testid="stApp"],
[data-testid="stAppViewContainer"] {{ overflow:visible !important; }}
section.main {{ height:100vh !important; overflow-y:auto !important; overflow-x:hidden !important; }}
[data-testid="stMain"] {{ background:transparent !important; }}
.stMainBlockContainer,
[data-testid="stAppViewBlockContainer"],
[data-testid="block-container"] {{
    width:100% !important;
    max-width:1380px !important;
    margin-left:auto !important;
    margin-right:auto !important;
    padding:clamp(0.75rem,1.2vw,1rem) clamp(0.75rem,1.7vw,1.5rem) 2rem !important;
    min-width:0 !important;
}}
.element-container,
[data-testid="element-container"],
[data-testid="stMarkdown"],
[data-testid="stVerticalBlock"],
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stHorizontalBlock"],
[data-testid="column"],
.stPlotlyChart,
.stDataFrame,
.stHtml,
.stIFrame {{
    max-width:100% !important;
    min-width:0 !important;
}}
[data-testid="stHorizontalBlock"] {{
    width:100% !important;
    gap:clamp(0.55rem,1vw,1rem) !important;
}}
[data-testid="column"] {{
    min-width:0 !important;
}}
img, svg, canvas, iframe, video {{
    max-width:100% !important;
}}
iframe {{
    width:100% !important;
}}
.mkt-card,.risk-card,.risk-hist-card,.ov-nav-card,.fin-t,
.mkt-phdr,.jj-alert,.jj-footer {{
    max-width:100%;
    min-width:0;
}}
.mkt-card *, .risk-card *, .risk-hist-card *, .ov-nav-card *,
.mkt-phdr *, .jj-alert *, .jj-footer *, .stMarkdown * {{
    min-width:0;
}}
@media(max-width:640px) {{
    .stMainBlockContainer,
    [data-testid="stAppViewBlockContainer"],
    [data-testid="block-container"] {{
        padding:0.75rem 0.75rem 1.4rem !important;
    }}
    h1, h2 {{ font-size:1.18rem !important; }}
    p, .stMarkdown p {{ font-size:12.5px; }}
}}
@media(max-width:900px) {{
    div[data-testid="stHorizontalBlock"]:not(:has([data-testid="stPageLink"])) {{
        flex-wrap:wrap !important;
    }}
    div[data-testid="stHorizontalBlock"]:not(:has([data-testid="stPageLink"])) > div[data-testid="column"] {{
        flex:1 1 min(100%, 360px) !important;
        width:auto !important;
        min-width:min(100%, 320px) !important;
    }}
}}
@media(max-width:680px) {{
    div[data-testid="stHorizontalBlock"]:not(:has([data-testid="stPageLink"])) {{
        flex-direction:column !important;
    }}
    div[data-testid="stHorizontalBlock"]:not(:has([data-testid="stPageLink"])) > div[data-testid="column"] {{
        flex:1 1 100% !important;
        width:100% !important;
        min-width:0 !important;
    }}
}}

/* ── Sidebar — hidden ────────────────────────────────────────── */
section[data-testid="stSidebar"] {{ display:none !important; }}
[data-testid="stSidebarCollapsedControl"] {{ display:none !important; }}

/* ── Typography ──────────────────────────────────────────────── */
h1, h2 {{ color:{NAVY} !important; font-size:1.35rem !important; font-weight:800 !important; letter-spacing:0 !important; margin-bottom:0 !important; }}
p, .stMarkdown p {{ color:{META}; font-size:14px; }}
h1,h2,h3,h4,h5,h6,p,span,b,strong,small,div {{
    overflow-wrap:break-word;
}}

/* ── DataFrame card elevation ────────────────────────────────── */
[data-testid="stDataFrameResizable"] {{
    border-radius:16px !important;
    overflow:hidden !important;
    box-shadow:0 4px 18px rgba(15,31,42,0.08) !important;
    border:1px solid {BORDER} !important;
}}

/* ── AG Grid ─────────────────────────────────────────────────── */
.ag-root-wrapper {{ border:none !important; border-radius:0 !important; }}
.ag-header {{ background:#1E2029 !important; border-bottom:1px solid {BORDER} !important; min-height:36px !important; }}
.ag-header-row {{ min-height:36px !important; }}
.ag-header-cell {{ border-right:none !important; padding:0 16px !important; }}
.ag-header-cell-text {{
    color:{META} !important; font-size:12px !important; font-weight:700 !important;
    text-transform:none !important; letter-spacing:0 !important;
}}
.ag-cell {{
    font-size:14px !important; color:{TEXT} !important;
    border-right:none !important;
    border-bottom:1px solid {BORDER} !important;
    padding:0 16px !important; line-height:36px !important;
}}
.ag-row {{ min-height:36px !important; border-bottom:none !important; }}
.ag-row-odd  {{ background:rgba(255,255,255,0.03) !important; }}
.ag-row-even {{ background:{WHITE} !important; }}
.ag-row-hover .ag-cell {{ background:rgba(159,203,211,0.12) !important; }}
.ag-paging-panel {{ background:{BG} !important; border-top:1px solid {BORDER} !important; font-size:11px !important; color:{META} !important; }}

/* ── Buttons ─────────────────────────────────────────────────── */
.stButton > button,
.stDownloadButton > button {{
    background:{WHITE} !important; border:1px solid {BORDER} !important;
    color:{META} !important; font-size:12px !important; padding:7px 12px !important;
    border-radius:14px !important; font-weight:750 !important;
    box-shadow:0 2px 8px rgba(15,31,42,0.06) !important;
    justify-content:center !important;  /* 라벨 가로 중앙(풀폭 버튼에서 좌측 흐름 방지) */
}}
/* 버튼 내부 라벨(마크다운/텍스트)도 항상 중앙 정렬 */
.stButton > button p, .stDownloadButton > button p,
.stButton > button div, .stDownloadButton > button div {{
    text-align:center !important; width:100% !important;
}}
.stButton > button:hover,
.stDownloadButton > button:hover {{
    background:{LIGHT} !important; border-color:{ACCENT} !important; color:{NAVY} !important;
}}

/* ── Expander ─────────────────────────────────────────────────── */
.streamlit-expanderHeader {{
    font-size:12px !important; color:{CHARCOAL} !important;
    font-weight:700 !important; border-radius:10px !important;
}}
/* R5: 접힘 헤더의 골드 외곽선(테마 primaryColor) 제거 → 일반 테두리. 골드는 인터랙션 전용 */
[data-testid="stExpander"], [data-testid="stExpander"] > details {{
    border:1px solid {BORDER} !important; border-radius:12px !important;
}}
[data-testid="stExpander"] summary:hover {{ color:{ACCENT} !important; }}

/* ── 세그먼트 토글 (st.radio horizontal 커스텀) — 선택 칸만 골드 ───────────── */
div[role="radiogroup"] {{
    display:inline-flex !important; flex-wrap:wrap; gap:0 !important;
    background:#16181F; border:1px solid {BORDER}; border-radius:10px; padding:3px;
    margin:2px 0 14px;
}}
div[role="radiogroup"] > label {{
    margin:0 !important; padding:7px 16px !important; border-radius:7px;
    cursor:pointer; transition:background .12s, color .12s; min-height:0 !important;
}}
/* 동그란 라디오 마커 제거 */
div[role="radiogroup"] > label > div:first-child {{ display:none !important; }}
div[role="radiogroup"] > label div, div[role="radiogroup"] > label p {{
    color:#9AA0AD; font-size:13px; font-weight:800;
}}
div[role="radiogroup"] > label:hover div, div[role="radiogroup"] > label:hover p {{ color:#E7E9EE; }}
/* 선택 칸 = 골드 배경 + 다크 텍스트 */
div[role="radiogroup"] > label:has(input:checked) {{ background:{ACCENT}; }}
div[role="radiogroup"] > label:has(input:checked) div,
div[role="radiogroup"] > label:has(input:checked) p {{ color:#0E0F13 !important; font-weight:900; }}

/* ── Misc ────────────────────────────────────────────────────── */
hr {{ border-color:{BORDER} !important; margin:.8rem 0 !important; }}
/* 기본 Streamlit 알림 박스(파란 info·노란 warning 등)를 다크+골드 컨셉으로 통일 */
.stAlert, [data-testid="stAlert"] {{
    border-radius:14px !important; font-size:12px !important;
    background:#16181F !important;
    border:1px solid {BORDER} !important;
    border-left:3px solid #3A4048 !important;
    box-shadow:0 6px 18px rgba(0,0,0,0.25) !important;
}}
[data-testid="stAlert"] [data-testid="stAlertContainer"],
[data-testid="stAlert"] div[role="alert"],
[data-testid="stAlert"] [data-baseweb="notification"] {{
    background:transparent !important; color:{CHARCOAL} !important;
}}
[data-testid="stAlert"] p,
[data-testid="stAlert"] span,
[data-testid="stAlert"] div {{ color:{CHARCOAL} !important; }}
[data-testid="stAlert"] svg {{ fill:{META} !important; color:{META} !important; }}
/* 변형 강조: 경고·에러=레드, 성공=블루 (지원 버전에서만 적용, 미지원 시 무채) */
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]),
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {{ border-left-color:#F25560 !important; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) svg,
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) svg {{ fill:#F25560 !important; color:#F25560 !important; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {{ border-left-color:#4D90F0 !important; }}
/* ── 파일 업로더 한글화 + 다크 컨셉(전역 — 포트폴리오·로그인 업로더 공용) ── */
[data-testid="stFileUploaderDropzone"] {{
    background:#16181F !important; border:1px dashed #3A4048 !important; border-radius:14px !important;
}}
[data-testid="stFileUploaderDropzoneInstructions"] {{ display:flex !important; flex-direction:column !important; justify-content:center !important; }}
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small {{ display:none !important; }}
[data-testid="stFileUploaderDropzoneInstructions"]::before {{
    content:"여기로 파일을 끌어다 놓으세요"; display:block;
    font-size:14px; font-weight:750; color:{TEXT};
}}
[data-testid="stFileUploaderDropzoneInstructions"]::after {{
    content:"최대 200MB · PNG·JPG·JPEG"; display:block; margin-top:3px;
    font-size:11px; font-weight:600; color:{META};
}}
[data-testid="stFileUploaderDropzone"] button {{
    font-size:0 !important; display:inline-flex !important;
    align-items:center !important; justify-content:center !important; min-width:116px !important;
}}
/* P0 픽스: 원래 아이콘(SVG)만 숨김 — font-size:0 은 텍스트만 죽이고 SVG 는 width 가 남아
   라벨이 우측으로 밀림(로그인 업로더와 동일). svg 만 타겟(파일 input 보호 — 안전). */
[data-testid="stFileUploaderDropzone"] button svg {{ display:none !important; }}
[data-testid="stFileUploaderDropzone"] button::after {{
    content:"파일 선택"; font-size:13px; font-weight:800;
}}
div[data-testid="stCaption"] {{ font-size:12px !important; color:{META} !important; }}
.stNumberInput input,
.stTextInput input {{
    background:rgba(255,255,255,0.05) !important;
    border:1px solid {BORDER} !important;
    border-radius:14px !important;
    color:{TEXT} !important;
    font-size:15px !important;
    font-weight:850 !important;
}}
.stNumberInput label,
.stTextInput label {{
    color:{META} !important;
    font-size:12px !important;
    font-weight:850 !important;
}}
</style>"""

_METRIC_CSS = f"""<style>
.ms{{display:flex;background:{WHITE};border-radius:18px;border:1px solid {BORDER};box-shadow:0 4px 18px rgba(15,31,42,0.07);overflow-x:auto;margin:0 0 8px}}
.mc{{flex:1;min-width:105px;padding:14px 18px;border-right:1px solid {BORDER}}}
.mc:last-child{{border-right:none}}
.ml{{font-size:10px;font-weight:700;letter-spacing:0.4px;color:{META};margin-bottom:4px;text-transform:uppercase}}
.mv{{font-size:18px;font-weight:800;color:{NAVY};font-variant-numeric:tabular-nums;font-family:'SF Mono','Cascadia Code',ui-monospace,monospace;line-height:1.2;letter-spacing:0}}
.md{{font-size:11px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums;font-family:'SF Mono','Cascadia Code',ui-monospace,monospace}}
.mp{{color:{POS}}}.mn{{color:{NEG}}}.mna{{color:{META}}}
</style>"""

_SH_CSS = f"""<style>
.sh{{margin:22px 0 10px}}
.sh-t{{font-size:15px;font-weight:800;color:{NAVY};display:block;margin-bottom:2px;letter-spacing:0}}
.sh-s{{font-size:11px;color:{META};display:block;margin-top:2px}}
</style>"""

_FIN_CSS = f"""<style>
/* ── Compact financial table ─────────────────────────────────── */
.fin-t{{background:{WHITE};border:1px solid {BORDER};border-radius:18px;overflow:hidden;overflow-x:auto;margin-bottom:8px;box-shadow:0 4px 18px rgba(15,31,42,0.07)}}
.fin-t table{{width:100%;border-collapse:collapse}}
.fin-t thead th{{background:#1E2029;color:{META};font-size:11px;font-weight:700;text-transform:none;letter-spacing:0;padding:9px 16px;text-align:left;white-space:nowrap;border-bottom:1px solid {BORDER}}}
.fin-t thead th.r{{text-align:right}}
.fin-t tbody tr:nth-child(even){{background:rgba(255,255,255,0.03)}}
.fin-t tbody tr:hover td{{background:rgba(159,203,211,0.10)}}
.fin-t td{{padding:8px 16px;color:{TEXT};border-bottom:1px solid {BORDER};white-space:nowrap;font-size:14px}}
.fin-t td.r{{text-align:right;font-family:'SF Mono','Cascadia Code',ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.fin-t .sym{{font-weight:700;font-size:12px;color:{NAVY};font-family:'SF Mono',ui-monospace,monospace}}
.fin-t .nm{{color:{META};font-size:11px}}
.fin-t .pos{{color:{POS};font-weight:700}}
.fin-t .neg{{color:{NEG};font-weight:700}}
.fin-t .neu{{color:{META}}}
.fin-t .bull{{font-size:10px;padding:3px 9px;border-radius:999px;background:{POS_BG};color:{POS};font-weight:700}}
.fin-t .bear{{font-size:10px;padding:3px 9px;border-radius:999px;background:{NEG_BG};color:{NEG};font-weight:700}}
.fin-t .neut{{font-size:10px;padding:3px 9px;border-radius:999px;background:{BG};color:{META};font-weight:600}}
.fin-t .sep td{{border-top:1px solid {BORDER}}}
/* ── Regime level badges ── */
.rl-high{{display:inline-block;padding:3px 9px;border-radius:999px;font-size:10px;font-weight:700;background:{NEG_BG};color:{NEG};white-space:nowrap}}
.rl-mid{{display:inline-block;padding:3px 9px;border-radius:999px;font-size:10px;font-weight:700;background:rgba(232,137,47,0.12);color:#a85d12;white-space:nowrap}}
.rl-low{{display:inline-block;padding:3px 9px;border-radius:999px;font-size:10px;font-weight:700;background:{POS_BG};color:{POS};white-space:nowrap}}
.rl-na{{display:inline-block;padding:3px 9px;border-radius:999px;font-size:10px;font-weight:600;background:{BG};color:{META};white-space:nowrap}}
.fin-t .sig{{font-weight:700;font-size:12px;color:{CHARCOAL};white-space:nowrap}}
.fin-t .cmt{{color:{CHARCOAL};font-size:12px}}
</style>"""

_MARKET_CSS = f"""<style>
/* ── Market page header ─────────────────────────── */
.mkt-phdr{{
  background:#16181F;border:1px solid {BORDER};border-left:3px solid {ACCENT};
  border-radius:18px;padding:clamp(15px,2vw,20px) clamp(16px,2.6vw,28px);margin-bottom:16px;
  display:flex;align-items:center;
  box-shadow:0 8px 24px rgba(0,0,0,0.25);
}}
.mkt-phdr-title{{font-size:clamp(18px,2.2vw,22px)!important;font-weight:950!important;
  color:{TEXT}!important;margin:0!important;letter-spacing:-0.045em!important}}
.mkt-phdr-sub{{font-size:clamp(10px,1.1vw,11.5px);color:{META};
  margin:3px 0 0!important;font-weight:700;letter-spacing:0.02em}}
.mkt-phdr-right{{margin-left:auto;display:flex;align-items:center}}
@media(max-width:640px) {{
  .mkt-phdr{{border-radius:18px;margin-bottom:12px}}
  .mkt-phdr-sub{{line-height:1.35}}
  .jj-footer{{font-size:11px;margin:22px 0 8px;padding:10px}}
}}

/* ── Stats chips bar ────────────────────────────── */
.mkt-chips{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}}
.mkt-chip{{background:#16181F;border:1px solid {BORDER};
  border-radius:14px;padding:8px 14px;display:flex;align-items:center;gap:8px;
  box-shadow:0 2px 8px rgba(0,0,0,0.25)}}
.mkt-chip-lbl{{font-size:10px;font-weight:700;color:{META};white-space:nowrap;
  letter-spacing:0.2px}}
.mkt-chip-val{{font-size:13px;font-weight:800;
  font-family:'SF Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.mkt-chip-val.pos{{color:{POS}}}.mkt-chip-val.neg{{color:{NEG}}}.mkt-chip-val.neu{{color:{META}}}
/* 모바일: 핵심 지표 칩은 줄바꿈 대신 한 줄 가로 스크롤 */
@media (max-width:768px){{
  .mkt-chips{{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch}}
  .mkt-chips::-webkit-scrollbar{{display:none}}
  .mkt-chip{{flex:0 0 auto}}
}}

/* ── Section header — Jeju style (h3 + muted right span) ───── */
.mkt-sec{{display:flex;justify-content:space-between;align-items:flex-end;
  gap:10px;margin:22px 0 12px;padding:0}}
.mkt-sec-t{{font-size:18px;font-weight:900;color:{NAVY};letter-spacing:-0.045em}}
.mkt-sec-s{{font-size:12px;color:{META};font-weight:800;letter-spacing:0.02em}}
/* ── Sub-section eyebrow (used inside cards / for sector labels) ── */
.mkt-eyebrow{{font-size:10px;font-weight:800;color:{META};text-transform:uppercase;
  letter-spacing:1px;margin:14px 0 6px;display:inline-block}}

/* ── Risk signal card grid ──────────────────────── */
.risk-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
  gap:10px;margin:10px 0 14px}}
.risk-card{{background:#16181F;border:1px solid {BORDER};
  border-left:4px solid {BORDER};border-radius:16px;
  padding:14px 16px;box-shadow:0 3px 12px rgba(0,0,0,0.25)}}
.risk-card.rc-high{{border-left-color:#F25560;
  background:linear-gradient(135deg,rgba(242,85,96,0.10) 0%,#16181F 55%)}}
.risk-card.rc-mid{{border-left-color:{ACCENT2}}}
.risk-card.rc-low{{border-left-color:#3FB27F;
  background:linear-gradient(135deg,rgba(63,178,127,0.10) 0%,#16181F 55%)}}
.risk-card.rc-na{{border-left-color:{BORDER}}}
.risk-card-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.risk-card-name{{font-size:13px;font-weight:800;color:{TEXT}}}
.risk-card-badge{{display:inline-flex;align-items:center;gap:4px;
  padding:4px 10px;border-radius:999px;font-size:11px;font-weight:700}}
.risk-card-badge.high{{background:rgba(242,85,96,0.15);color:#F25560;
  border:1px solid rgba(242,85,96,0.30)}}
.risk-card-badge.mid{{background:rgba(217,164,65,0.15);color:#D9A441;
  border:1px solid rgba(217,164,65,0.30)}}
.risk-card-badge.low{{background:rgba(63,178,127,0.15);color:#3FB27F;
  border:1px solid rgba(63,178,127,0.28)}}
.risk-card-badge.na{{background:rgba(255,255,255,0.04);color:{META};border:1px solid {BORDER}}}
.risk-card-note{{font-size:12px;color:{CHARCOAL};line-height:1.6;margin:0}}
.risk-alert{{border-radius:16px;padding:14px 18px;margin-bottom:12px;
  font-size:13px;font-weight:700;display:flex;align-items:center;gap:10px}}
.risk-alert.red{{background:rgba(242,85,96,0.10);border:1px solid rgba(242,85,96,0.30);color:#F25560}}
.risk-alert.amber{{background:rgba(217,164,65,0.10);border:1px solid rgba(217,164,65,0.32);color:#D9A441}}
.risk-hist-card{{background:#16181F;border:1px solid {BORDER};
  border-radius:20px;padding:18px 20px;box-shadow:0 4px 16px rgba(0,0,0,0.25);
  margin-bottom:16px}}

/* ── Market analysis table (Jeju row layout) ─── */
.mkt-card{{background:#16181F;border:1px solid {BORDER};
  border-radius:24px;padding:22px 22px 18px;
  box-shadow:0 18px 40px rgba(0,0,0,0.30)}}
.mkt-analysis-table{{display:grid;gap:9px;margin:0}}
.mkt-row{{display:grid;grid-template-columns:1fr 0.6fr 0.7fr 1.4fr;
  gap:10px;align-items:center;padding:11px 14px;
  border:1px solid {BORDER};border-radius:16px;
  background:rgba(255,255,255,0.03);font-size:13px}}
.mkt-row:hover{{background:rgba(255,255,255,0.07);transition:background 0.15s}}
.mkt-row-name{{font-weight:800;color:{TEXT};font-size:13.5px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}}
.mkt-row-chg{{font-size:13px;font-weight:800;font-family:'SF Mono',ui-monospace,monospace;
  font-variant-numeric:tabular-nums}}
.mkt-row-chg.pos{{color:{POS}}}.mkt-row-chg.neg{{color:{NEG}}}.mkt-row-chg.neu{{color:{META}}}
.mkt-row-note{{font-size:12px;color:{CHARCOAL};line-height:1.45}}

/* ── Market news/theme card grid ─────────────── */
.mkt-news-grid{{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin:0}}
.mkt-news-card{{border:1px solid {BORDER};background:#16181F;
  border-radius:18px;padding:14px 16px}}
.mkt-news-card h4{{margin:0 0 7px;font-size:14px;font-weight:850;color:{TEXT}}}
.mkt-news-card p{{margin:0;color:{CHARCOAL};font-size:12px;line-height:1.55}}
/* D3: 테마카드 보더는 일관된 무채색 — 가격 등락색(레드/블루) 오용 제거(테마는 편집 맥락) */
.mkt-news-card.alert-card,
.mkt-news-card.good-card,
.mkt-news-card.warn-card{{border-left:3px solid #3A4048;background:#16181F}}
/* ── Overview nav cards ─────────────────────────────────── */
.ov-nav-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:20px 0 14px}}
.ov-nav-card{{display:block;text-decoration:none;background:#16181F;
  border:1px solid {BORDER};border-radius:20px;padding:20px 22px;
  box-shadow:0 4px 18px rgba(0,0,0,0.25);
  transition:box-shadow 0.18s,transform 0.18s;cursor:pointer}}
.ov-nav-card:hover{{box-shadow:0 12px 32px rgba(0,0,0,0.40);
  transform:translateY(-2px);border-color:{SEA}}}
.ov-nav-card-icon{{font-size:28px;margin-bottom:10px;display:block}}
.ov-nav-card-title{{font-size:15px;font-weight:800;color:{TEXT};margin:0 0 4px;display:block}}
.ov-nav-card-desc{{font-size:12px;color:{META};margin:0;line-height:1.5;display:block}}
.ov-nav-card-arrow{{float:right;color:{SEA};font-size:18px;margin-top:-28px}}
</style>"""

# ── Shared Jeju primitives reused across pages ────────────────────────────────
_JEJU_CSS = f"""<style>
/* ── Eyebrow pill (above hero or section heroes) ─────────── */
.jj-eyebrow{{display:inline-flex;padding:8px 11px;border-radius:999px;
  background:rgba(255,255,255,0.05);color:{TEXT};font-size:11px;
  font-weight:950;letter-spacing:0.06em;text-transform:uppercase;
  border:1px solid {BORDER}}}

/* ── Tags (color chips for inline annotations) ───────────── */
.jj-tag{{display:inline-flex;border-radius:999px;padding:5px 10px;
  font-size:11px;font-weight:800;background:rgba(255,255,255,0.06);color:{CHARCOAL};
  margin:3px 4px 0 0;letter-spacing:0.01em;white-space:nowrap}}
.jj-tag.dark{{background:{ACCENT};color:#0E0F13}}
.jj-tag.orange{{background:rgba(217,164,65,0.16);color:#D9A441}}
.jj-tag.green{{background:rgba(242,85,96,0.14);color:#F25560}}
.jj-tag.red{{background:rgba(77,144,240,0.14);color:#4D90F0}}
.jj-tag.sea{{background:rgba(159,203,211,0.20);color:#3a5458}}

/* ── Metric list rows (Jeju: bold name + small sub + right value) ── */
.jj-metric{{display:flex;justify-content:space-between;align-items:center;
  padding:13px 0;border-bottom:1px solid {BORDER}}}
.jj-metric:last-child{{border-bottom:0}}
.jj-metric b{{font-size:14px;color:{NAVY};font-weight:900;letter-spacing:-0.01em}}
.jj-metric small{{display:block;color:{META};margin-top:3px;font-size:11.5px;
  font-weight:700}}
.jj-up{{color:{POS};font-weight:950;font-family:'SF Mono',ui-monospace,monospace;
  font-variant-numeric:tabular-nums}}
.jj-down{{color:{NEG};font-weight:950;font-family:'SF Mono',ui-monospace,monospace;
  font-variant-numeric:tabular-nums}}
.jj-warn{{color:{ACCENT2};font-weight:950;font-family:'SF Mono',ui-monospace,monospace;
  font-variant-numeric:tabular-nums}}
.jj-flat{{color:{META};font-weight:950;font-family:'SF Mono',ui-monospace,monospace;
  font-variant-numeric:tabular-nums}}

/* ── Chart container with subtle ruled grid background ───── */
.jj-chart{{height:230px;border:1px solid {BORDER};border-radius:24px;
  background:linear-gradient(180deg,rgba(159,203,211,0.18),rgba(255,255,255,0.10)),
    repeating-linear-gradient(to top,transparent 0 45px,rgba(15,31,42,0.05) 46px);
  padding:16px;position:relative;overflow:hidden}}
.jj-chart svg{{width:100%;height:100%;overflow:visible}}

/* ── Volatility bar rows (Jeju gradient fill) ───────────── */
.jj-bar-row{{display:grid;grid-template-columns:88px 1fr 58px;gap:12px;
  align-items:center;margin:11px 0;font-size:13px}}
.jj-bar-row b{{font-size:12.5px;font-weight:900;color:{TEXT};display:flex;align-items:center;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.jj-dot{{flex:0 0 auto;width:7px;height:7px;border-radius:50%;margin-right:5px}}
.jj-bar{{height:10px;border-radius:999px;background:rgba(255,255,255,0.08);overflow:hidden}}
.jj-bar i{{display:block;height:100%;border-radius:999px;
  background:linear-gradient(90deg,{SEA},{ACCENT2})}}
.jj-bar-val{{text-align:right;font-size:13px;font-weight:900;
  font-family:'SF Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}}

/* ── Alert strip (basalt bar with orange icon) ──────────── */
.jj-alert{{background:{BASALT};color:#ffffff;border-radius:20px;padding:14px 16px;
  display:flex;gap:12px;align-items:center;margin-top:14px}}
.jj-alert-icon{{width:42px;height:42px;border-radius:14px;background:{ACCENT2};
  display:grid;place-items:center;font-size:22px;font-weight:950;flex:0 0 auto;
  color:#ffffff}}
.jj-alert b{{font-size:14px;color:#ffffff;font-weight:950;letter-spacing:-0.01em}}
.jj-alert small{{color:#d8e6eb;font-size:12px;line-height:1.5;display:block;margin-top:2px}}

/* ── Risk-score donut (centerpiece for risk page) ───────── */
.jj-risk-score{{width:200px;height:200px;border-radius:50%;margin:12px auto;
  display:grid;place-items:center;position:relative}}
.jj-risk-score:after{{content:"";width:148px;height:148px;border-radius:50%;
  background:#16181F;position:absolute;
  box-shadow:inset 0 4px 12px rgba(0,0,0,0.35)}}
.jj-risk-score div{{position:relative;z-index:1;text-align:center}}
.jj-risk-score strong{{font-size:46px;letter-spacing:-0.06em;font-weight:950;
  color:{TEXT};line-height:1;display:block}}
.jj-risk-score span{{display:block;font-size:12px;font-weight:900;margin-top:6px;
  letter-spacing:0.04em}}
.jj-rs-cap{{text-align:center;color:{META};font-size:12px;font-weight:800;
  margin-top:6px}}

/* ── Action list (left label + right paragraph) ─────────── */
.jj-action-list{{display:grid;gap:10px}}
.jj-action{{display:grid;grid-template-columns:120px 1fr;gap:14px;
  border:1px solid {BORDER};background:rgba(255,255,255,0.03);border-radius:18px;padding:14px 16px;
  align-items:start}}
.jj-action b{{font-size:13.5px;font-weight:950;letter-spacing:-0.01em}}
.jj-action p{{margin:0;color:{CHARCOAL};font-size:12.5px;line-height:1.55}}
.jj-action.up b{{color:{POS}}}
.jj-action.down b{{color:{NEG}}}
.jj-action.warn b{{color:{ACCENT2}}}
.jj-action.flat b{{color:{META}}}
@media(max-width:920px){{.jj-action{{grid-template-columns:1fr;gap:6px}}}}

/* ── Footer note ────────────────────────────────────────── */
.jj-footer{{text-align:center;color:{META};font-size:12px;font-weight:700;
  margin:30px 0 14px;padding:14px;letter-spacing:0.02em}}
</style>"""


_PRETENDARD_CSS = """<style>
.num,.up,.down{font-variant-numeric:tabular-nums;}
.up{color:#F25560;font-weight:600;}
.down{color:#4D90F0;font-weight:600;}
</style>"""


def inject_css():
    import re
    combined = GLOBAL_CSS + _METRIC_CSS + _SH_CSS + _FIN_CSS + _MARKET_CSS + _JEJU_CSS
    parts = re.findall(r"<style>(.*?)</style>", combined, re.DOTALL)
    st.markdown("<style>" + "\n".join(parts) + "</style>", unsafe_allow_html=True)
    st.markdown(_PRETENDARD_CSS, unsafe_allow_html=True)


def inject_shell_css():
    st.markdown(APP_SHELL_CSS, unsafe_allow_html=True)


def mark_active_nav(path: str):
    safe_path = path.replace('"', "")
    st.markdown(
        f"""
<style>
.sv-nav a[data-path="{safe_path}"] {{
    background:{ACCENT} !important;
    color:#0E0F13 !important;
    box-shadow:0 6px 18px rgba(217,164,65,0.30) !important;
}}
</style>
        """,
        unsafe_allow_html=True,
    )


def _asset_data_uri(filename: str, mime: str = "image/png") -> str:
    root = Path(__file__).resolve().parents[2]
    candidates = [
        root / "ui" / "assets" / filename,
        root / "assets" / "intro" / filename,
        root / "assets" / filename,
    ]
    for path in candidates:
        try:
            return f"data:{mime};base64,{b64encode(path.read_bytes()).decode('ascii')}"
        except FileNotFoundError:
            continue
    return ""


def render_shell_header(pages=None):
    logo_src = _asset_data_uri("sim_heart_logo_transparent.png") or _asset_data_uri("sim_heart_logo.png")
    logo_html = f'<img src="{logo_src}" alt="SIM INVESTMENT 心 로고">' if logo_src else "<span>心</span>"
    is_guest = st.session_state.get("auth_role") == "guest"
    _username = st.session_state.get("username", "")
    if is_guest:
        _suffix = "?_auth=guest"
        refresh_href = "?refresh=1&_auth=guest"
    elif _username:
        _suffix = f"?_user={_username}"
        refresh_href = f"?refresh=1&_user={_username}"
    else:
        _suffix = ""
        refresh_href = "?refresh=1"
    nav_items = [
        ("전체 현황",  f"/{_suffix}",              "/"),
        ("포트폴리오", f"/portfolio{_suffix}",     "/portfolio"),
        ("시장",       f"/market{_suffix}",         "/market"),
        ("리스크",     f"/risk{_suffix}",           "/risk"),
    ]
    nav_html = "".join(
        f'<a href="{html_escape(href)}" data-path="{html_escape(path)}" target="_self">{html_escape(label)}</a>'
        for label, href, path in nav_items
    )
    # 계정 컨트롤 — 게스트=로그인/가입 진입, 로그인=사용자명+로그아웃 (둘 다 /?logout=1로 세션 종료)
    if is_guest:
        acct_html = '<a class="sv-acct" href="/?logout=1" target="_top">로그인 / 가입</a>'
    elif _username:
        acct_html = (f'<span class="sv-acct-name">{html_escape(_username)}</span>'
                     f'<a class="sv-acct" href="/?logout=1" target="_top">로그아웃</a>')
    else:
        acct_html = ""
    # 계정 블록(사용자명·로그아웃)을 새로고침과 구분선으로 분리
    acct_sep = '<span class="sv-nav-sep" aria-hidden="true"></span>' if acct_html else ""
    st.markdown(
        f"""
<div class="sv-shell">
  <div class="sv-app-header">
    <a class="sv-brand" href="/" target="_self" aria-label="SIM INVESTMENT 홈">
      <div class="sv-logo">{logo_html}</div>
      <div>
        <h1>SIM INVESTMENT</h1>
        <p>진심으로 보는 투자</p>
      </div>
    </a>
    <nav class="sv-nav" aria-label="주요 메뉴">
      {nav_html}
      <span class="sv-nav-sep" aria-hidden="true"></span>
      <a class="sv-nav-refresh" href="{html_escape(refresh_href)}" target="_top" title="새로고침">↻</a>
      {acct_sep}
      {acct_html}
    </nav>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def metric_strip(items: list[dict]) -> str:
    cells = []
    for it in items:
        val, delta, pos = it.get("value", "N/A"), it.get("delta"), it.get("positive")
        if delta is None:
            dhtml = '<div class="md mna">—</div>'
        elif pos is True:
            dhtml = f'<div class="md mp">▲ {delta}</div>'
        elif pos is False:
            dhtml = f'<div class="md mn">▼ {delta}</div>'
        else:
            dhtml = f'<div class="md mna">{delta}</div>'
        cells.append(f'<div class="mc"><div class="ml">{it["label"]}</div><div class="mv">{val}</div>{dhtml}</div>')
    return '<div class="ms">' + "".join(cells) + "</div>"


def empty_state(msg: str, sub: str = "데이터가 연결되면 표시됩니다") -> None:
    """빈 상태 공용 컴포넌트 — 미연결·로딩 실패 등을 중립 '준비 중'으로 통일.

    에러 원문(스택·HTTP 코드 등)을 노출하지 말고 사용자용 문구만 전달한다.
    파랑 st.info 대신 중립 회색 스켈레톤 카드로 미완성 인상을 줄인다.
    """
    sub_html = f'<div class="es-sub">{html_escape(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="sv-empty"><span class="es-chip">준비 중</span>'
        f'<div class="es-msg">{html_escape(msg)}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def data_source_note(source: str, *, updated: str = "", delay: str = "",
                     cached: str = "", extra: str = "") -> str:
    """갱신·출처 표기 통일 — '출처 {source} · {신선도}' 한 줄(캡션용).

    데이터별 신선도는 실제로 다르므로(시세 지연 / 컨센서스 캐시 / DB 일일) 정보는 유지하되
    표기 구조만 1종으로 맞춘다. 예: '기술지표 · 출처 로컬 DB · 업데이트 2026-06-17'.
    """
    parts = [extra] if extra else []
    parts.append(f"출처 {source}")
    if updated:
        parts.append(f"업데이트 {updated}")
    if delay:
        parts.append(f"{delay} 지연")
    if cached:
        parts.append(f"{cached} 캐시")
    return " · ".join(parts)


# 전문 용어 설명 — '진심으로 보는 투자' 초보 친화. 데이터 문자열·표 컬럼에 박힌 용어를
# 인라인 툴팁 대신 페이지 하단 접이식으로 1~2줄 설명한다(단일 출처).
_GLOSSARY = {
    "β": "베타 — 시장 대비 변동성. β1.0은 시장과 같은 폭, β2.0은 약 2배로 출렁이는 고변동 종목입니다.",
    "MA20 이격": "현재가가 20일 이동평균선에서 떨어진 정도(%). 양수면 단기 과열, 음수면 과매도 쪽으로 봅니다.",
    "breadth": "상승·하락 폭 — 오른 종목과 내린 종목의 비율. 지수보다 시장 전반의 강약을 보여줍니다.",
    "추세": "20·60일 이동평균 배열로 본 방향 — 상승 / 하락 / 보합.",
    "상승여력": "애널리스트 평균 목표가 대비 현재가의 상승 여지(%). 음수면 현재가가 목표가를 넘어선 상태입니다.",
    "감지 임계값": "평소 변동성(σ) 대비 얼마나 큰 하루 움직임을 '주요 이동'으로 잡을지 기준(기본 2.0σ).",
    "집중도": "상위 1~3개 종목이 전체에서 차지하는 비중. 높을수록 분산이 약해 개별 악재에 취약합니다.",
}


def glossary_expander(*keys: str) -> None:
    """전문 용어 설명 접이식(페이지 하단). keys 미지정 시 전체 용어 표시."""
    items = [(k, _GLOSSARY[k]) for k in (keys or _GLOSSARY) if k in _GLOSSARY]
    if not items:
        return
    with st.expander("📖 용어 설명", expanded=False):
        st.markdown(
            '<div class="sv-glossary">' + "".join(
                f'<div class="gl-item"><b>{html_escape(k)}</b>'
                f'<span>{html_escape(v)}</span></div>' for k, v in items)
            + '</div>',
            unsafe_allow_html=True,
        )


_PERIOD_DAYS = {"1W": 7, "1M": 30, "3M": 92, "6M": 183, "1Y": 366}


def period_toggle(key: str, options=("1W", "1M", "3M"), default: str = "3M", align: str = "right"):
    """차트 기간 토글(공통). (선택 라벨, 일수) 반환.

    데이터가 이미 받아온 기간을 '슬라이스'하는 용도 — 옵션은 받아온 범위 안에서만 제공할 것.
    스타일·라벨은 가격 추이 비교(period_radio)와 통일: 가운데 칩, 1W/1M/3M/6M.
    align='left'면 차트 위 컨트롤로 좌측 배치(종목상세), 기본 'right'.
    """
    _just = "flex-end" if align == "right" else "flex-start"
    st.markdown(
        f'<style>[data-testid="stRadio"]{{display:flex!important;justify-content:{_just}!important}}'
        f'[data-testid="stRadio"] div[role="radiogroup"]{{justify-content:{_just}!important;flex-wrap:wrap}}'
        f'[data-testid="stRadio"] div[role="radiogroup"] label{{justify-content:center!important;text-align:center!important}}</style>',
        unsafe_allow_html=True)
    opts = list(options)
    idx = opts.index(default) if default in opts else len(opts) - 1
    sel = st.radio("기간", opts, index=idx, horizontal=True,
                   key=key, label_visibility="collapsed")
    return sel, _PERIOD_DAYS.get(sel, 92)


# 가격 추이 비교 공통 기간 선택 — 원자재·크립토·외환 통일(라벨·세트·우측정렬)
_PERIOD_MAP = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y", "5Y": "5y"}
_PERIOD_RADIO_CSS = (
    "<style>"
    # stRadio 컨테이너(풀폭)를 flex-end → 라디오 블록 통째로 페이지 우측에 배치
    "[data-testid=\"stRadio\"]{display:flex!important;justify-content:flex-end!important}"
    "[data-testid=\"stRadio\"] div[role=\"radiogroup\"]{justify-content:flex-end!important;flex-wrap:wrap}"
    # 칩 안 글자 가운데 정렬
    "[data-testid=\"stRadio\"] div[role=\"radiogroup\"] label{justify-content:center!important;text-align:center!important}"
    "</style>"
)


_PERIOD_RADIO_CSS_FILL = (
    "<style>"
    # 풀폭 세그먼트 — 칩이 동일 너비로 한 줄 가득(위 카드 너비에 맞춤). 모바일에서도 적층/줄바꿈 없음.
    "[data-testid=\"stRadio\"]{display:block!important;width:100%}"
    "[data-testid=\"stRadio\"] div[role=\"radiogroup\"]{display:flex!important;justify-content:stretch!important;"
    "flex-wrap:nowrap!important;gap:6px;width:100%}"
    "[data-testid=\"stRadio\"] div[role=\"radiogroup\"] label{flex:1 1 0!important;min-width:0!important;"
    "justify-content:center!important;text-align:center!important}"
    "</style>"
)


_PERIOD_RADIO_CSS_CARD = (
    "<style>"
    # 콤팩트 우측 정렬 — 칩 자연 너비 한 줄(카드 한 칸 수준 폭), 줄바꿈 없음.
    "[data-testid=\"stRadio\"]{display:flex!important;justify-content:flex-end!important}"
    "[data-testid=\"stRadio\"] div[role=\"radiogroup\"]{justify-content:flex-end!important;flex-wrap:nowrap!important;gap:5px}"
    "[data-testid=\"stRadio\"] div[role=\"radiogroup\"] label{justify-content:center!important;text-align:center!important;"
    "padding:4px 9px!important}"
    "</style>"
)


def period_radio(key: str, default: str = "3M", align: str = "right") -> tuple[str, str]:
    """가격 추이 비교 공통 기간 선택. 반환 (라벨, yfinance 기간 코드). 옵션 1M/3M/6M/1Y/5Y.
    align: 'right'(기본·우측), 'fill'(풀폭 동일너비), 'card'(콤팩트 우측·한 줄)."""
    _css = {"fill": _PERIOD_RADIO_CSS_FILL, "card": _PERIOD_RADIO_CSS_CARD}.get(align, _PERIOD_RADIO_CSS)
    st.markdown(_css, unsafe_allow_html=True)
    labels = list(_PERIOD_MAP.keys())
    idx = labels.index(default) if default in labels else 1
    sel = st.radio("기간", labels, index=idx, horizontal=True,
                   key=key, label_visibility="collapsed")
    return sel, _PERIOD_MAP[sel]


def section_header(title: str, sub: str = "") -> str:
    s = f'<span class="sh-s">{sub}</span>' if sub else ""
    return f'<div class="sh"><span class="sh-t">{title}</span>{s}</div>'


def mkt_page_header(icon: str, title: str, subtitle: str = "") -> str:
    sub = f'<div class="mkt-phdr-sub">{subtitle}</div>' if subtitle else ""
    return (
        f'<div class="mkt-phdr">'
        f'<div><div class="mkt-phdr-title">{title}</div>{sub}</div>'
        f'</div>'
    )


def mkt_section_header(title: str, sub: str = "") -> str:
    s = f'<span class="mkt-sec-s">{sub}</span>' if sub else ""
    return f'<div class="mkt-sec"><span class="mkt-sec-t">{title}</span>{s}</div>'


def mkt_stats_chips(items: list[dict]) -> str:
    """items: [{label, value, cls}]  cls ∈ {pos, neg, neu}"""
    html = '<div class="mkt-chips">'
    for it in items:
        html += (
            f'<span class="mkt-chip">'
            f'<span class="mkt-chip-lbl">{it["label"]}</span>'
            f'<span class="mkt-chip-val {it.get("cls","neu")}">{it["value"]}</span>'
            f'</span>'
        )
    return html + '</div>'


# ── Jeju primitives — shared builders ──────────────────────────────────────────

def jj_eyebrow(text: str) -> str:
    return f'<span class="jj-eyebrow">{text}</span>'


def jj_tag(text: str, tone: str = "") -> str:
    """tone ∈ '', 'dark', 'orange', 'green', 'red', 'sea'"""
    cls = f"jj-tag {tone}".strip()
    return f'<span class="{cls}">{text}</span>'


def jj_alert_strip(title: str, note: str = "", icon: str = "!") -> str:
    note_html = f"<small>{note}</small>" if note else ""
    return (
        f'<div class="jj-alert">'
        f'<div class="jj-alert-icon">{icon}</div>'
        f'<div><b>{title}</b>{note_html}</div>'
        f'</div>'
    )


def jj_footer(text: str = "SIM INVESTMENT · 데이터는 참고용이며 매매 권유가 아닙니다.") -> str:
    return f'<div class="jj-footer">{text}</div>'


def pct(v: float) -> str:
    """수익률 한국식 색 HTML. st.markdown(pct(1.6), unsafe_allow_html=True)"""
    cls  = "up" if v >= 0 else "down"
    sign = "+" if v >= 0 else "−"
    return f'<span class="{cls}">{sign}{abs(v):.2f}%</span>'


def color_change(val):
    """pandas Styler용: 양수=레드(#F25560), 음수=블루(#4D90F0)"""
    if isinstance(val, (int, float)):
        if val > 0:
            return "color: #F25560"
        if val < 0:
            return "color: #4D90F0"
    return ""


def bar_color(v: float) -> str:
    """Plotly 막대 색: 양수=레드, 음수=블루"""
    return "#F25560" if v >= 0 else "#4D90F0"


def jj_risk_donut(score: int, label: str, tone: str = "warn") -> str:
    """
    Jeju-style conic donut for a 0-100 risk score.
    tone ∈ 'good' (green), 'warn' (tangerine), 'risk' (camellia)
    """
    score = max(0, min(100, int(score)))
    color = {
        "good": POS,
        "warn": ACCENT2,
        "risk": NEG,
    }.get(tone, ACCENT2)
    bg = f"conic-gradient({color} 0 {score}%,#dce7e3 {score}% 100%)"
    return (
        f'<div class="jj-risk-score" style="background:{bg}">'
        f'<div><strong>{score}</strong>'
        f'<span style="color:{color}">{label}</span></div>'
        f'</div>'
    )


def jj_action_item(label: str, desc: str, tone: str = "warn") -> str:
    """tone ∈ 'up', 'down', 'warn', 'flat'"""
    return (
        f'<div class="jj-action {tone}">'
        f'<b>{label}</b>'
        f'<p>{desc}</p>'
        f'</div>'
    )


def jj_action_list(items: list[dict]) -> str:
    """items: [{label, desc, tone}]"""
    inner = "".join(jj_action_item(i["label"], i["desc"], i.get("tone", "warn")) for i in items)
    return f'<div class="jj-action-list">{inner}</div>'


# ── Styling helpers ────────────────────────────────────────────────────────────

def style_returns(df: pd.DataFrame, col: str) -> "pd.io.formats.style.Styler":
    def _f(v):
        if not isinstance(v, (int, float)) or pd.isna(v):
            return ""
        if v > 0.005:
            return f"background-color:{POS_BG};color:{POS};font-weight:700"
        if v < -0.005:
            return f"background-color:{NEG_BG};color:{NEG};font-weight:700"
        return ""
    return df.style.map(_f, subset=[col])


def numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Convert 'N/A' strings to NaN in numeric columns."""
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ── Loading indicator: 유기적(블롭) 로더 ─────────────────────────────────────────
# Claude Design 'Organic Loaders' #1(아메바 모핑 + 느린 회전)을 다크+오렌지 테마로 적용.
# 단일 잉크 블롭이 살아있듯 border-radius를 모핑하며 14s에 한 바퀴 천천히 회전(무텍스트).
# 전 페이지 공용(show_skeleton) — 한 곳만 바꾸면 전역 적용.
_LOADER_CSS = """<style>
@keyframes ov-morph{
  0%,100%{border-radius:60% 40% 47% 53% / 62% 53% 47% 38%}
  25%{border-radius:40% 60% 62% 38% / 47% 62% 38% 53%}
  50%{border-radius:52% 48% 35% 65% / 40% 47% 53% 60%}
  75%{border-radius:46% 54% 58% 42% / 56% 38% 62% 44%}
}
@keyframes ov-roll{to{offset-distance:100%}}
.ov-loader-wrap{display:grid;place-items:center;min-height:140px;padding:20px 0}
.ov-loader{width:26px;height:26px;opacity:.5;
  background:radial-gradient(circle at 38% 33%,rgba(255,213,150,.62) 0%,rgba(245,158,11,.55) 58%,rgba(201,122,12,.44) 100%);
  box-shadow:0 6px 18px rgba(245,158,11,.16);
  offset-path:circle(15px at 50% 50%);
  animation:ov-morph 3s ease-in-out infinite, ov-roll 2.2s linear infinite}
@media(prefers-reduced-motion:reduce){
  .ov-loader{offset-path:none;animation:ov-morph 8s ease-in-out infinite}
}
</style>"""

_LOADER_HTML = '<div class="ov-loader-wrap"><div class="ov-loader" role="status" aria-label="불러오는 중"></div></div>'


def show_skeleton():
    """데이터 로딩 중 유기적 블롭 로더 표시. 완료 시 반환된 placeholder.empty() 호출."""
    ph = st.empty()
    ph.markdown(_LOADER_CSS + _LOADER_HTML, unsafe_allow_html=True)
    return ph


# ── Export helpers ─────────────────────────────────────────────────────────────

def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name[:31], index=False)
    return buf.getvalue()
