"""전 페이지 풀 캡처 — 모든 expander/toggle 펼친 상태로 저장.
CDP Page.captureScreenshot 사용(Playwright page.screenshot가 이 환경에서 행걸림 회피)."""
import base64, os, time
from playwright.sync_api import sync_playwright

OUT = "/Users/min/Downloads/siminvest_ui"
os.makedirs(OUT, exist_ok=True)
BASE = "http://localhost:8501"
G = "_auth=guest"

PAGES = [
    ("00_login_landing",     f"{BASE}/"),
    ("00b_login_form",       f"{BASE}/?_login=1"),
    ("01_home",              f"{BASE}/?{G}"),
    ("01b_overview",         f"{BASE}/overview?{G}"),
    ("02_market_summary",    f"{BASE}/market?market_tab=summary&{G}"),
    ("03_market_all",        f"{BASE}/market?market_tab=all&{G}"),
    ("04_market_us",         f"{BASE}/market?market_tab=us&{G}"),
    ("05_market_kr",         f"{BASE}/market?market_tab=kr&{G}"),
    ("06_market_crypto",     f"{BASE}/market?market_tab=crypto&{G}"),
    ("07_market_etf",        f"{BASE}/market?market_tab=etf&{G}"),
    ("08_market_commodities", f"{BASE}/market?market_tab=commodities&{G}"),
    ("09_market_fx",         f"{BASE}/market?market_tab=fx&{G}"),
    ("10_market_rates",      f"{BASE}/market?market_tab=rates&{G}"),
    ("11_portfolio",         f"{BASE}/portfolio?{G}"),
    ("12_risk",              f"{BASE}/risk?{G}"),
]

FLIP_OFF = """() => {
  const off = [...document.querySelectorAll('label[data-baseweb=checkbox]')]
    .find(l => { const i = l.querySelector('input'); return i && !i.checked; });
  if (off) { off.click(); return true; }
  return false;
}"""
OPEN_DETAILS = "() => { document.querySelectorAll('details:not([open])').forEach(d => d.open = true); return document.querySelectorAll('details').length; }"
KILL_ANIM = "*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}"
# Streamlit은 section.main 내부에서 스크롤 → 문서 높이가 뷰포트로 고정됨.
# 내부 스크롤러를 모두 height:auto·overflow:visible로 풀어 전체가 문서 흐름에 펼쳐지게 함.
UNCLIP = """
html,body{height:auto!important;overflow:visible!important}
[data-testid=stAppViewContainer],[data-testid=stMain],section.main,.main,
[data-testid=stMainBlockContainer],.block-container,[data-testid=stAppViewBlockContainer]{
  height:auto!important;max-height:none!important;min-height:0!important;overflow:visible!important}
"""


def open_everything(pg):
    # 토글/체크박스(전체 보기·표로 보기 등) 모두 ON — 각 클릭은 rerun → 대기
    for _ in range(10):
        try:
            if not pg.evaluate(FLIP_OFF):
                break
        except Exception:
            break
        pg.wait_for_timeout(2200)
    # expander(details) 전부 펼침(클라이언트, rerun 없음)
    try:
        pg.evaluate(OPEN_DETAILS)
    except Exception:
        pass
    pg.wait_for_timeout(1500)
    try:
        pg.evaluate(OPEN_DETAILS)  # 펼친 뒤 새로 생긴 expander 한 번 더
    except Exception:
        pass


FULL_H = """() => {
  const c = [document.body, document.documentElement,
    document.querySelector('section.main'),
    document.querySelector('[data-testid=stMain]'),
    document.querySelector('[data-testid=stAppViewContainer]'),
    document.querySelector('[data-testid=stMainBlockContainer]'),
    document.querySelector('.main')].filter(Boolean);
  return Math.max(...c.map(e => e.scrollHeight || 0), 1000);
}"""


def capture(pg, cdp, name):
    pg.add_style_tag(content=KILL_ANIM)
    pg.add_style_tag(content=UNCLIP)
    pg.wait_for_timeout(800)
    # 내부 스크롤 콘텐츠의 실제 높이만큼 뷰포트를 키워 전체가 한 화면에 들어오게 함
    h = int(pg.evaluate(FULL_H))
    h = min(h + 60, 18000)
    pg.set_viewport_size({"width": 1440, "height": h})
    pg.wait_for_timeout(1200)               # 리플로우 + 지연 렌더 대기
    shot = cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 70})
    path = f"{OUT}/{name}.jpeg"
    with open(path, "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    # 다음 페이지 위해 뷰포트 원복
    pg.set_viewport_size({"width": 1440, "height": 1000})
    return 1440, h, os.path.getsize(path)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        cdp = pg.context.new_cdp_session(pg)
        for name, url in PAGES:
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(6500)          # Streamlit 렌더 + 데이터
                open_everything(pg)
                w, h, sz = capture(pg, cdp, name)
                print(f"OK  {name:24} {w}x{h}  {sz//1024}KB")
            except Exception as e:
                print(f"ERR {name:24} {str(e)[:80]}")
        b.close()


if __name__ == "__main__":
    main()
