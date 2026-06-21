"""로그인 상태 전체 캡처(minqsim/0000) — 로그인 화면(Liquid 배경) → 인증 후 전 페이지.
CDP Page.captureScreenshot 사용. _capture_ui.py 의 인증 버전."""
import base64, os
from playwright.sync_api import sync_playwright

OUT = "/Users/min/Downloads/siminvest_ui_authed"
os.makedirs(OUT, exist_ok=True)
BASE = "http://localhost:8501"
USER, PW = "minqsim", "0000"

# 로그인 후(인증 세션) 캡처할 페이지 — 게스트 파라미터 없음
AUTHED_PAGES = [
    ("03_home",              f"{BASE}/"),                              # 첫 화면(Liquid 배경)
    ("04_overview",          f"{BASE}/overview"),
    ("05_portfolio",         f"{BASE}/portfolio"),
    ("06_market_summary",    f"{BASE}/market?market_tab=summary"),
    ("07_market_all",        f"{BASE}/market?market_tab=all"),
    ("08_market_us",         f"{BASE}/market?market_tab=us"),
    ("09_market_kr",         f"{BASE}/market?market_tab=kr"),
    ("10_market_crypto",     f"{BASE}/market?market_tab=crypto"),
    ("11_market_etf",        f"{BASE}/market?market_tab=etf"),
    ("12_market_commodities", f"{BASE}/market?market_tab=commodities"),
    ("13_market_fx",         f"{BASE}/market?market_tab=fx"),
    ("14_market_rates",      f"{BASE}/market?market_tab=rates"),
    ("15_risk",              f"{BASE}/risk"),
]

KILL_ANIM = "*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}"
UNCLIP = """
html,body{height:auto!important;overflow:visible!important}
[data-testid=stAppViewContainer],[data-testid=stMain],section.main,.main,
[data-testid=stMainBlockContainer],.block-container,[data-testid=stAppViewBlockContainer]{
  height:auto!important;max-height:none!important;min-height:0!important;overflow:visible!important}
"""
FLIP_OFF = """() => {
  const off = [...document.querySelectorAll('label[data-baseweb=checkbox]')]
    .find(l => { const i = l.querySelector('input'); return i && !i.checked; });
  if (off) { off.click(); return true; }
  return false;
}"""
OPEN_DETAILS = "() => { document.querySelectorAll('details:not([open])').forEach(d => d.open = true); return 1; }"
FULL_H = """() => {
  const c = [document.body, document.documentElement,
    document.querySelector('section.main'),
    document.querySelector('[data-testid=stMain]'),
    document.querySelector('[data-testid=stAppViewContainer]'),
    document.querySelector('[data-testid=stMainBlockContainer]'),
    document.querySelector('.main')].filter(Boolean);
  return Math.max(...c.map(e => e.scrollHeight || 0), 1000);
}"""


def open_everything(pg):
    for _ in range(10):
        try:
            if not pg.evaluate(FLIP_OFF):
                break
        except Exception:
            break
        pg.wait_for_timeout(2200)
    for _ in range(2):
        try:
            pg.evaluate(OPEN_DETAILS)
        except Exception:
            pass
        pg.wait_for_timeout(1200)


def capture(pg, cdp, name, *, keep_bg=False):
    pg.add_style_tag(content=KILL_ANIM)
    if not keep_bg:
        pg.add_style_tag(content=UNCLIP)
    pg.wait_for_timeout(800)
    h = 1000 if keep_bg else min(int(pg.evaluate(FULL_H)) + 60, 18000)
    pg.set_viewport_size({"width": 1440, "height": h})
    pg.wait_for_timeout(1200)
    shot = cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 72})
    path = f"{OUT}/{name}.jpeg"
    with open(path, "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    pg.set_viewport_size({"width": 1440, "height": 1000})
    return h, os.path.getsize(path)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        cdp = pg.context.new_cdp_session(pg)

        # ── 1) 로그인 화면(로그아웃 상태) — Liquid 배경 보존하려 UNCLIP 미적용 ──
        pg.goto(BASE, wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(7000)  # bg 셰이더 워밍 + 렌더
        try:
            h, sz = capture(pg, cdp, "01_login_landing", keep_bg=True)
            print(f"OK  01_login_landing   1440x{h}  {sz//1024}KB")
        except Exception as e:
            print("ERR landing", str(e)[:80])

        pg.goto(f"{BASE}/?_login=1", wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(6000)
        # 폼 채우기 — Streamlit 입력은 키보드 타이핑 + 커밋(blur)이 있어야 React 상태가 갱신됨
        try:
            pg.wait_for_selector('div[data-testid="stTextInput"] input', timeout=15000)
            inputs = pg.query_selector_all('div[data-testid="stTextInput"] input')
            if len(inputs) >= 2:
                inputs[0].click(); inputs[0].fill("")
                pg.keyboard.type(USER, delay=40)
                inputs[1].click(); inputs[1].fill("")
                pg.keyboard.type(PW, delay=40)
                pg.keyboard.press("Tab")  # 커밋(blur)
            pg.wait_for_timeout(1200)
            h, sz = capture(pg, cdp, "02_login_form", keep_bg=True)
            print(f"OK  02_login_form      1440x{h}  {sz//1024}KB")
        except Exception as e:
            print("ERR login form", str(e)[:80])

        # ── 2) 로그인 제출 ──
        try:
            btn = pg.query_selector('div[data-testid="stFormSubmitButton"] button')
            if btn:
                btn.click()
            else:
                pg.keyboard.press("Enter")
            pg.wait_for_timeout(8000)  # 인증 + rerun
            # 로그인 성공 확인 — 본문에 로그인 폼이 사라졌는지
            still_login = pg.query_selector('div[data-testid="stFormSubmitButton"] button')
            print("로그인 후 폼 잔존?:", bool(still_login))
        except Exception as e:
            print("ERR submit", str(e)[:80])

        # ── 3) 인증 후 전 페이지 ──
        for name, url in AUTHED_PAGES:
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(6500)
                open_everything(pg)
                keep = name == "03_home"  # 홈은 배경 보이게 풀높이 클립 해제 안 함
                h, sz = capture(pg, cdp, name, keep_bg=keep)
                print(f"OK  {name:22} 1440x{h}  {sz//1024}KB")
            except Exception as e:
                print(f"ERR {name:22} {str(e)[:80]}")

        b.close()


if __name__ == "__main__":
    main()
