import pandas as pd

_CSS = """
<style>
.exc-wrap { overflow-x: auto; margin: 6px 0 16px 0; }
.exc {
    border-collapse: collapse; width: 100%;
    font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', Calibri, sans-serif;
    font-size: 12.5px;
}
.exc th {
    background: #1F6B3C; color: #fff;
    padding: 6px 12px; border: 1px solid #145A32;
    font-weight: 700; text-align: center; white-space: nowrap;
}
.exc td {
    padding: 4px 12px; border: 1px solid #C6C6C6;
    white-space: nowrap; background: #fff;
}
.exc tr:nth-child(even) td { background: #F5F5F5; }
.exc tr:hover td { background: #E8F4EC !important; }
.exc td.txt  { text-align: left; }
.exc td.num  { text-align: right; }
.exc td.ctr  { text-align: center; }
.exc td.na   { text-align: center; color: #AAAAAA; }
.exc .pos    { color: #006100; font-weight: 700; }
.exc .neg    { color: #9C0006; font-weight: 700; }
.exc .pos-bg { background: #C6EFCE !important; color: #006100; font-weight: 700; }
.exc .neg-bg { background: #FFC7CE !important; color: #9C0006; font-weight: 700; }
/* metric cards */
[data-testid="stMetricLabel"]  { color: #1F6B3C !important; font-weight: 700 !important; font-size: 13px !important; }
[data-testid="stMetricValue"]  { font-size: 22px !important; }
[data-testid="stMetricDelta"] svg { display: none; }
</style>
"""

_CSS_INJECTED = False


def inject_css():
    import streamlit as st
    global _CSS_INJECTED
    if not _CSS_INJECTED:
        st.markdown(_CSS, unsafe_allow_html=True)
        _CSS_INJECTED = True


def excel_table(
    df: pd.DataFrame,
    rename: dict = {},
    pct_cols: list = [],
    price_cols: list = [],
    ctr_cols: list = [],
) -> str:
    df = df.copy().rename(columns=rename)
    pct_cols  = {rename.get(c, c) for c in pct_cols}
    price_cols = {rename.get(c, c) for c in price_cols}
    ctr_cols  = {rename.get(c, c) for c in ctr_cols}

    parts = ['<div class="exc-wrap"><table class="exc"><thead><tr>']
    for col in df.columns:
        parts.append(f'<th>{col}</th>')
    parts.append('</tr></thead><tbody>')

    for _, row in df.iterrows():
        parts.append('<tr>')
        for col in df.columns:
            val = row[col]
            parts.append(_cell(col, val, pct_cols, price_cols, ctr_cols))
        parts.append('</tr>')

    parts.append('</tbody></table></div>')
    return ''.join(parts)


def _cell(col, val, pct_cols, price_cols, ctr_cols) -> str:
    if val == "N/A" or (isinstance(val, float) and pd.isna(val)):
        return '<td class="na">N/A</td>'

    if col in pct_cols:
        if isinstance(val, (int, float)):
            cls = "pos-bg" if val > 0 else ("neg-bg" if val < 0 else "")
            sign = "+" if val > 0 else ""
            return f'<td class="num {cls}">{sign}{val:.2f}%</td>'
        return '<td class="na">N/A</td>'

    if col in price_cols or isinstance(val, float):
        if isinstance(val, (int, float)):
            return f'<td class="num">{val:,.2f}</td>'

    if col in ctr_cols:
        return f'<td class="ctr">{val}</td>'

    if isinstance(val, bool):
        return f'<td class="ctr">{"예" if val else "-"}</td>'

    return f'<td class="txt">{val}</td>'
