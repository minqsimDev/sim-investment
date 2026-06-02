"""
Bloomberg-lite dashboard styling.
Color palette: dark navy sidebar, charcoal table headers, light gray page bg.
"""
import io
import pandas as pd

# ── Color tokens ──────────────────────────────────────────────────────────────
NAVY     = "#1C2B3A"
CHARCOAL = "#2D3748"
BG       = "#F7F8FA"
WHITE    = "#FFFFFF"
BORDER   = "#E2E8F0"
POS      = "#276749"
NEG      = "#9B2335"
POS_BG   = "#F0FFF6"
NEG_BG   = "#FFF5F5"
META     = "#718096"
TEXT     = "#1A202C"

GLOBAL_CSS = f"""<style>
/* ── Hide Streamlit chrome ───────────────────────────────────── */
header[data-testid="stHeader"] {{ display:none !important; }}
[data-testid="stToolbar"] {{ display:none !important; }}
.stAppDeployButton {{ display:none !important; }}
#MainMenu {{ display:none !important; }}
footer {{ display:none !important; }}

/* ── Layout ─────────────────────────────────────────────────── */
.stApp {{ background:{BG} !important; }}
.stMainBlockContainer {{ padding:1.2rem 2.4rem 2rem !important; max-width:1600px !important; }}

/* ── Sidebar ─────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{ background:{NAVY} !important; }}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] span:not([data-baseweb]) {{ color:#A0AEC0 !important; font-size:11px !important; }}
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4 {{
    color:#E2E8F0 !important; font-size:10px !important;
    text-transform:uppercase !important; letter-spacing:1.2px !important; font-weight:700 !important;
}}
section[data-testid="stSidebar"] input {{
    background:#2D3748 !important; border:1px solid #4A5568 !important;
    color:#E2E8F0 !important; font-size:12px !important; border-radius:2px !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{
    color:#A0AEC0 !important; font-size:12px !important; border-radius:2px !important;
}}
section[data-testid="stSidebar"] [aria-current="page"] {{
    background:rgba(255,255,255,.08) !important; color:#E2E8F0 !important;
}}

/* ── Typography ──────────────────────────────────────────────── */
h1 {{ color:{NAVY} !important; font-size:1.2rem !important; font-weight:700 !important; letter-spacing:-0.2px !important; margin-bottom:0 !important; }}
p, .stMarkdown p {{ color:{META}; font-size:12px; }}

/* ── AG Grid (st.dataframe) ──────────────────────────────────── */
.ag-root-wrapper {{ border:1px solid {BORDER} !important; border-radius:2px !important; }}
.ag-header {{ background:{CHARCOAL} !important; border-bottom:1px solid {NAVY} !important; min-height:30px !important; }}
.ag-header-row  {{ min-height:30px !important; }}
.ag-header-cell {{ border-right:1px solid #3D4F63 !important; padding:0 10px !important; }}
.ag-header-cell-text {{
    color:#CBD5E0 !important; font-size:9.5px !important; font-weight:600 !important;
    text-transform:uppercase !important; letter-spacing:.5px !important;
}}
.ag-cell {{
    font-size:12px !important; color:{TEXT} !important;
    border-right:1px solid #F0F4F8 !important;
    border-bottom:1px solid #F0F4F8 !important;
    padding:0 10px !important; line-height:28px !important;
}}
.ag-row {{ min-height:28px !important; border-bottom:none !important; }}
.ag-row-odd  {{ background:#FAFBFC !important; }}
.ag-row-even {{ background:{WHITE} !important; }}
.ag-row-hover .ag-cell {{ background:#EEF2F7 !important; }}
.ag-paging-panel {{ background:{BG} !important; border-top:1px solid {BORDER} !important; font-size:11px !important; color:{META} !important; }}

/* ── Buttons ─────────────────────────────────────────────────── */
.stButton > button,
.stDownloadButton > button {{
    background:transparent !important; border:1px solid #CBD5E0 !important;
    color:#4A5568 !important; font-size:11px !important; padding:3px 10px !important;
    border-radius:2px !important; font-weight:400 !important;
    box-shadow:none !important;
}}
.stButton > button:hover,
.stDownloadButton > button:hover {{
    background:#EDF2F7 !important; border-color:#A0AEC0 !important;
}}

/* ── Misc ────────────────────────────────────────────────────── */
hr {{ border-color:{BORDER} !important; margin:.6rem 0 !important; }}
.stAlert {{ border-radius:2px !important; font-size:12px !important; }}
.streamlit-expanderHeader {{ font-size:11.5px !important; color:#4A5568 !important; font-weight:600 !important; }}
div[data-testid="stCaption"] {{ font-size:10.5px !important; color:{META} !important; }}
</style>"""

_METRIC_CSS = """<style>
.ms{display:flex;background:#fff;border:1px solid #E2E8F0;border-radius:2px;overflow-x:auto;margin:0 0 4px}
.mc{flex:1;min-width:95px;padding:9px 14px;border-right:1px solid #E2E8F0}
.mc:last-child{border-right:none}
.ml{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:#718096;margin-bottom:3px}
.mv{font-size:16px;font-weight:700;color:#1C2B3A;font-variant-numeric:tabular-nums;font-family:'SF Mono','Cascadia Code',ui-monospace,monospace;line-height:1.3}
.md{font-size:10px;font-weight:600;margin-top:1px;font-variant-numeric:tabular-nums;font-family:'SF Mono','Cascadia Code',ui-monospace,monospace}
.mp{color:#276749}.mn{color:#9B2335}.mna{color:#A0AEC0}
</style>"""

_SH_CSS = """<style>
.sh{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1.5px solid #2D3748;padding-bottom:4px;margin:16px 0 8px}
.sh-t{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:1.3px;color:#2D3748}
.sh-s{font-size:9.5px;color:#A0AEC0}
</style>"""

_TS_CSS = """<style>
.ts{font-size:10px;color:#A0AEC0;font-family:'SF Mono',ui-monospace,monospace;margin:2px 0 10px;}
</style>"""


_FIN_CSS = f"""<style>
/* ── Compact financial table ─────────────────────────────────── */
.fin-t{{background:{WHITE};border:1px solid {BORDER};border-radius:2px;overflow-x:auto;margin-bottom:4px}}
.fin-t table{{width:100%;border-collapse:collapse}}
.fin-t thead th{{background:{CHARCOAL};color:#CBD5E0;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;padding:6px 12px;text-align:left;white-space:nowrap}}
.fin-t thead th.r{{text-align:right}}
.fin-t tbody tr:nth-child(even){{background:#FAFBFC}}
.fin-t tbody tr:hover td{{background:#EEF2F7}}
.fin-t td{{padding:4px 12px;color:{TEXT};border-bottom:1px solid #F0F4F8;white-space:nowrap;font-size:12px}}
.fin-t td.r{{text-align:right;font-family:'SF Mono','Cascadia Code',ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.fin-t .sym{{font-weight:700;font-size:11px;color:{NAVY};font-family:'SF Mono',ui-monospace,monospace}}
.fin-t .nm{{color:{META};font-size:10.5px}}
.fin-t .pos{{color:{POS};font-weight:600}}
.fin-t .neg{{color:{NEG};font-weight:600}}
.fin-t .neu{{color:{META}}}
.fin-t .bull{{font-size:9px;padding:1px 6px;border-radius:2px;background:{POS_BG};color:{POS};font-weight:700}}
.fin-t .bear{{font-size:9px;padding:1px 6px;border-radius:2px;background:{NEG_BG};color:{NEG};font-weight:700}}
.fin-t .neut{{font-size:9px;padding:1px 6px;border-radius:2px;background:{BG};color:{META};font-weight:600}}
.fin-t .sep td{{border-top:1px solid #CBD5E0}}
/* ── Regime level badges ─────────────────────────────────────── */
.rl-high{{display:inline-block;padding:1px 7px;border-radius:2px;font-size:9px;font-weight:700;background:{NEG_BG};color:{NEG};white-space:nowrap}}
.rl-mid{{display:inline-block;padding:1px 7px;border-radius:2px;font-size:9px;font-weight:700;background:#FFFBEB;color:#92400E;white-space:nowrap}}
.rl-low{{display:inline-block;padding:1px 7px;border-radius:2px;font-size:9px;font-weight:700;background:{POS_BG};color:{POS};white-space:nowrap}}
.rl-na{{display:inline-block;padding:1px 7px;border-radius:2px;font-size:9px;font-weight:600;background:{BG};color:#A0AEC0;white-space:nowrap}}
.fin-t .sig{{font-weight:600;font-size:11px;color:{CHARCOAL};white-space:nowrap}}
.fin-t .cmt{{color:#4A5568;font-size:11px}}
</style>"""


def inject_css():
    import re, streamlit as st
    combined = GLOBAL_CSS + _METRIC_CSS + _SH_CSS + _TS_CSS + _FIN_CSS
    parts = re.findall(r"<style>(.*?)</style>", combined, re.DOTALL)
    st.markdown("<style>" + "\n".join(parts) + "</style>", unsafe_allow_html=True)


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


def section_header(title: str, sub: str = "") -> str:
    s = f'<span class="sh-s">{sub}</span>' if sub else ""
    return f'<div class="sh"><span class="sh-t">{title}</span>{s}</div>'


def timestamp_bar(ts: str, note: str = "yfinance · FRED · 5분 캐시") -> str:
    return f'<div class="ts">기준: {ts} &nbsp;·&nbsp; {note}</div>'


# ── Styling helpers ────────────────────────────────────────────────────────────

def style_returns(df: pd.DataFrame, col: str) -> "pd.io.formats.style.Styler":
    def _f(v):
        if not isinstance(v, (int, float)) or pd.isna(v):
            return ""
        if v > 0.005:
            return f"background-color:{POS_BG};color:{POS};font-weight:600"
        if v < -0.005:
            return f"background-color:{NEG_BG};color:{NEG};font-weight:600"
        return ""
    return df.style.map(_f, subset=[col])


def numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Convert 'N/A' strings to NaN in numeric columns."""
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ── Export helpers ─────────────────────────────────────────────────────────────

def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name[:31], index=False)
    return buf.getvalue()
