"""포트폴리오 페이지 CSS 모음 — portfolio.py에서 분리(순수 스타일 상수).
로직 의존성이 없어 안전하게 분리. portfolio.py가 import해서 사용한다.
"""

_PORT_CSS = """<style>
/* 포트폴리오 보기/정렬 라디오 우측 정렬 */
[data-testid="stRadio"] > div[role="radiogroup"]{justify-content:flex-end!important}
.port-simple-head{margin:2px 0 12px}
.port-simple-head h2{margin:0!important;color:#E7E9EE!important;font-size:24px!important;font-weight:950!important;letter-spacing:0!important;line-height:1.1!important}
.port-simple-head p{margin:5px 0 0!important;color:#7E8694!important;font-size:13px!important;font-weight:800!important}
.port-map-head{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin:6px 0 12px}
.port-map-head h3{margin:0;color:#E7E9EE;font-size:18px;font-weight:900;letter-spacing:0}
.port-map-head span{color:#7E8694;font-size:12px;font-weight:850}
.port-detail-head{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin:22px 0 14px}
.port-detail-head h3{margin:0;color:#E7E9EE;font-size:18px;font-weight:950;letter-spacing:0}
.port-detail-head span{color:#7E8694;font-size:12px;font-weight:850}
.hold-summary-line{display:flex;flex-wrap:wrap;align-items:center;gap:8px;color:#9AA0AD;font-size:12px;font-weight:800;margin:0 0 8px}
.hold-summary-pill{display:inline-flex;align-items:center;gap:5px;border-radius:999px;background:#1E2029;color:#9AA0AD;padding:5px 9px;font-size:11px;font-weight:900}
.hold-list{display:grid;gap:8px;margin-top:10px}
.hold-row{display:grid;grid-template-columns:52px minmax(0,1fr) 96px 78px 96px;gap:10px;align-items:center;
  background:rgba(22,24,31,0.92);border:1px solid #262A33;border-radius:14px;padding:10px 12px}
.hold-rank{font-size:12px;color:#7E8694;font-weight:950;font-variant-numeric:tabular-nums}
.hold-main{min-width:0}
.hold-main b{display:block;color:#E7E9EE;font-size:13px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hold-main span{display:block;color:#7E8694;font-size:11px;font-weight:800;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hold-cat{justify-self:start;border-radius:999px;padding:5px 8px;background:#1E2029;color:#9AA0AD;font-size:10px;font-weight:900;white-space:nowrap}
.hold-row-price{font-size:12px;color:#E7E9EE;font-weight:950;text-align:right;font-variant-numeric:tabular-nums}
.hold-row-chg{font-size:12px;font-weight:950;text-align:right;font-variant-numeric:tabular-nums}
.hold-row-note{font-size:11px;color:#7E8694;font-weight:850;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hold-section{margin:0 0 22px}
.hold-section-head{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin:0 0 10px}
.hold-section-head h4{margin:0;color:#E7E9EE;font-size:15px;font-weight:950;letter-spacing:0}
.hold-section-head span{color:#7E8694;font-size:12px;font-weight:850}
.hold-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(214px,1fr));gap:14px;margin-bottom:18px}
.hold-card{background:rgba(22,24,31,0.94);border:1px solid #262A33;border-radius:20px;padding:14px 16px;
  min-height:142px;box-shadow:0 10px 24px rgba(0,0,0,0.30);display:flex;flex-direction:column;gap:11px}
.hold-card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.hold-name{min-width:0}
.hold-name b{display:block;color:#E7E9EE;font-size:14px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hold-name span{display:block;color:#7E8694;font-size:11px;font-weight:800;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hold-badge{flex:0 0 auto;border-radius:999px;padding:5px 8px;background:#1E2029;color:#9AA0AD;font-size:10px;font-weight:900}
.hold-price{font-size:22px;font-weight:950;color:#E7E9EE;line-height:1;font-variant-numeric:tabular-nums}
.hold-bottom{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:auto}
.hold-stat{background:#1E2029;border:1px solid #262A33;border-radius:14px;padding:8px}
.hold-stat span{display:block;color:#7E8694;font-size:10px;font-weight:850;margin-bottom:3px}
.hold-stat b{font-size:12px;font-weight:950}
.pct-pos{color:#F25560}.pct-neg{color:#4D90F0}.pct-flat{color:#9AA0AD}
.hold-empty{background:rgba(22,24,31,0.70);border:1px dashed #262A33;border-radius:18px;padding:16px;color:#9AA0AD;font-size:13px;font-weight:800}
.hold-cat-section{margin:0 0 16px}
.hold-cat-section:last-child{margin-bottom:0}
.hold-cat-title{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:0 0 8px}
.hold-cat-title b{color:#E7E9EE;font-size:14px;font-weight:950}
.hold-cat-title span{color:#7E8694;font-size:11px;font-weight:850}
.hold-cat-summary{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}
.hold-cat-summary span{border-radius:999px;background:#1E2029;color:#9AA0AD;padding:4px 8px;font-size:10px;font-weight:900}
.hold-det-stack{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:10px}
details.hold-det{border-radius:12px;overflow:hidden;min-width:0}
details.hold-det summary{
  list-style:none;display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;align-items:center;gap:7px;
  min-height:54px;padding:8px 9px;border-radius:12px;cursor:pointer;
  border:1px solid rgba(38,42,51,0.75);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);
  transition:filter .12s,transform .12s}
details.hold-det summary::-webkit-details-marker{display:none}
details.hold-det summary:hover{filter:brightness(0.98)}
details.hold-det[open] summary{border-radius:12px 12px 0 0;border-bottom:none}
.hold-det-main{min-width:0}
.hold-det-main b{display:block;color:#E7E9EE;font-size:11px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hold-det-main span{display:block;color:#7E8694;font-size:9px;font-weight:800;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hold-det-price{display:none;color:#E7E9EE;font-size:12px;font-weight:950;font-variant-numeric:tabular-nums;white-space:nowrap}
.hold-det-chg{font-size:11.5px;font-weight:900;font-variant-numeric:tabular-nums;white-space:nowrap}
.hold-det-arrow{display:inline-flex;align-items:center;justify-content:center;font-size:11px;color:#7E8694;transition:transform .18s;flex-shrink:0}
details.hold-det[open] .hold-det-arrow{transform:rotate(180deg);color:#9AA0AD}
summary.hold-pos-bg{background:rgba(242,85,96,0.12);border-color:rgba(242,85,96,0.30)!important}
summary.hold-neg-bg{background:rgba(77,144,240,0.12);border-color:rgba(77,144,240,0.30)!important}
summary.hold-neu-bg{background:rgba(22,24,31,0.56);border-color:rgba(38,42,51,0.72)!important}
.hold-det-body{
  background:rgba(30,32,41,0.94);border:1px solid rgba(38,42,51,0.72);border-top:none;
  border-radius:0 0 12px 12px;padding:9px}
.hold-det-note{color:#9AA0AD;font-size:10.5px;line-height:1.45;font-weight:700;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.hold-det-meta{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.hold-det-meta span{
  display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:4px 7px;
  background:#1E2029;color:#9AA0AD;font-size:9px;font-weight:900}
.hold-logo{position:relative;flex:0 0 32px;width:32px;height:32px;border-radius:7px;overflow:hidden;display:grid;place-items:center;
  background:#1E2029;border:1px solid #262A33;color:#E7E9EE;font-size:8.5px;font-weight:950;text-align:center;line-height:1}
.hold-logo img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#16181F;padding:4px;box-sizing:border-box}
.hold-logo span{position:relative;z-index:0;max-width:29px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hold-logo-company{background:#1E2029}
.brand-red{background:linear-gradient(135deg,#d74333,#f2a15c);color:#fff}
.brand-dark{background:linear-gradient(135deg,#222831,#6f7c84);color:#fff}
.brand-blue{background:linear-gradient(135deg,#1f5fae,#61b4dc);color:#fff}
.brand-green{background:linear-gradient(135deg,#186c5f,#8acb91);color:#fff}
.brand-violet{background:linear-gradient(135deg,#4942a4,#b65bcf);color:#fff}
.brand-gold{background:linear-gradient(135deg,#9b6a16,#e6b84d);color:#251607}
.hold-logo-issuer{font-size:9px;letter-spacing:0;color:#fff;border:0}
.issuer-tiger{background:linear-gradient(135deg,#e24a34,#f5b43c)}
.issuer-kodex{background:linear-gradient(135deg,#2257a8,#48a2d8)}
.issuer-rise{background:linear-gradient(135deg,#202a44,#8fc6d8)}
.issuer-plus{background:linear-gradient(135deg,#5d45a5,#d45185)}
.issuer-ace{background:linear-gradient(135deg,#176b5c,#7dc88c)}
.issuer-etf{background:linear-gradient(135deg,#40515a,#91a6aa)}
.hold-logo-metal{border-radius:50%;border:0;font-size:12px;box-shadow:inset 0 2px 8px rgba(255,255,255,0.48),inset 0 -6px 10px rgba(0,0,0,0.14)}
.metal-gold{background:radial-gradient(circle at 31% 28%,#fff6b8,#e6ac2f 54%,#9a6617);color:#4a2b0b}
.metal-silver{background:radial-gradient(circle at 31% 28%,#ffffff,#cdd8de 55%,#758590);color:#293842}
.metal-copper{background:radial-gradient(circle at 31% 28%,#ffd7b0,#bd6c36 56%,#6d351d);color:#38180b}
.metal-energy{background:radial-gradient(circle at 31% 28%,#d7f1ff,#376f8a 58%,#16394d);color:#f8fbfa}
.coin-btc{background:linear-gradient(135deg,#f7931a,#ffca68);color:#3b2100}
.coin-eth{background:linear-gradient(135deg,#627eea,#9fb2ff);color:#111a3a}
.coin-sol{background:linear-gradient(135deg,#14f195,#9945ff);color:#10131f}
.issue-section{margin:16px 0 4px;background:rgba(22,24,31,0.94);border:1px solid #262A33;border-radius:18px;overflow:hidden;box-shadow:0 4px 14px rgba(0,0,0,0.30)}
.issue-head{padding:9px 16px;background:#1E2029;border-bottom:1px solid #262A33;font-size:11px;font-weight:800;color:#9AA0AD;text-transform:uppercase;letter-spacing:.6px;display:flex;justify-content:space-between;align-items:center}
.issue-head span{font-size:10px;font-weight:700;color:#7E8694;text-transform:none;letter-spacing:0}
.issue-row{display:grid;grid-template-columns:1fr auto;gap:12px;padding:12px 16px;border-bottom:1px solid #262A33;align-items:start}
.issue-row:last-child{border-bottom:none}
.issue-name{font-size:13px;font-weight:950;color:#E7E9EE;margin-bottom:5px}
.issue-note{font-size:12px;color:#9AA0AD;line-height:1.65;font-weight:650}
.issue-tp-block{display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0;min-width:88px}
.issue-tp{font-size:11px;font-weight:800;color:#9AA0AD;font-family:'SF Mono',ui-monospace,monospace;white-space:nowrap}
.issue-upside{font-size:14px;font-weight:950;font-family:'SF Mono',ui-monospace,monospace;white-space:nowrap}
.issue-upside.pos{color:#F25560}.issue-upside.neg{color:#4D90F0}.issue-upside.neu{color:#9AA0AD}
.issue-no-tp{font-size:11px;font-weight:700;color:#7E8694;white-space:nowrap}
@media(max-width:920px){
  .hold-grid{grid-template-columns:1fr}
  .hold-det-stack{grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}
  details.hold-det summary{grid-template-columns:auto minmax(0,1fr) auto auto;gap:6px;padding:7px 7px;min-height:50px}
  .hold-logo{width:28px;height:28px;flex-basis:28px}
  .hold-det-main b{font-size:10px}
  .hold-det-main span{display:none}
  .hold-det-chg{font-size:10.5px}
  .hold-row{grid-template-columns:38px minmax(0,1fr) 74px;gap:8px}
  .hold-cat,.hold-row-note{display:none}.hold-row-price{font-size:11px}
  .hold-det-price{display:none}
}
@media(min-width:921px) and (max-width:1180px){
  .hold-det-stack{grid-template-columns:repeat(4,minmax(0,1fr))}
}
@media(max-width:640px){
  .hold-det-stack{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
  .hold-det-main span{display:block}
}
.pd-header{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;margin:22px 0 12px}
.pd-header h3{margin:0;color:#E7E9EE;font-size:20px;font-weight:800;letter-spacing:-.01em}  /* 2배·굵게 */
.pd-header p{margin:0;color:#7E8694;font-size:12px;font-weight:850}
.pd-header-sub{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.pd-header .bk-badge{background:#1E2029;color:#9AA0AD;border-radius:999px;padding:4px 10px;
  font-size:10px;font-weight:900;white-space:nowrap}
.pd-source{display:inline-flex;align-items:center;border-radius:999px;padding:6px 10px;background:#1E2029;color:#9AA0AD;
  border:1px solid #262A33;font-size:11px;font-weight:950;white-space:nowrap}
.pd-card{background:rgba(22,24,31,0.84);border:1px solid rgba(38,42,51,0.86);border-radius:20px;
  box-shadow:0 8px 28px rgba(0,0,0,0.30);padding:18px 20px}
.pd-summary-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:10px}
.pd-summary-card{min-height:92px;background:rgba(22,24,31,0.92);border:1px solid #262A33;border-radius:18px;
  padding:14px 16px;display:flex;flex-direction:column;justify-content:space-between}
.pd-summary-card span{color:#7E8694;font-size:11px;font-weight:900}
.pd-summary-card b{color:#E7E9EE;font-size:20px;font-weight:950;letter-spacing:0;font-variant-numeric:tabular-nums}
.pd-summary-card small{color:#7E8694;font-size:10px;font-weight:850;line-height:1.35}
.pd-pos{color:#F25560!important}.pd-neg{color:#4D90F0!important}.pd-neu{color:#9AA0AD!important}.pd-warn{color:#E08A3C!important}
.pd-section-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:14px;margin-bottom:14px}
.pd-section-title{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:0 0 12px}
.pd-section-title b{color:#E7E9EE;font-size:14px;font-weight:950}
.pd-section-title span{color:#7E8694;font-size:11px;font-weight:850}
.pd-alloc-list{display:grid;gap:10px}
.pd-alloc-row{display:grid;grid-template-columns:86px minmax(0,1fr) 58px;align-items:center;gap:10px}
.pd-alloc-name{color:#E7E9EE;font-size:12px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pd-alloc-track{height:9px;border-radius:999px;background:#1E2029;overflow:hidden}
.pd-alloc-fill{height:100%;border-radius:999px;background:var(--sv-gold)}
.pd-alloc-pct{text-align:right;color:#9AA0AD;font-size:11px;font-weight:950;font-variant-numeric:tabular-nums}
.pd-risk-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
@media(max-width:760px){.pd-risk-list{grid-template-columns:1fr}}
.pd-risk-item{border:1px solid #262A33;border-radius:14px;background:#1E2029;padding:13px 15px;min-width:0}
.pd-risk-item b{display:block;color:#E7E9EE;font-size:12.5px;font-weight:950;margin-bottom:5px}
.pd-risk-item span{display:block;color:#9AA0AD;font-size:11.5px;font-weight:760;line-height:1.5}
.pd-empty{border:1px dashed #262A33;border-radius:18px;background:rgba(22,24,31,0.74);padding:18px;margin-bottom:12px}
.pd-empty b{display:block;color:#E7E9EE;font-size:15px;font-weight:950;margin-bottom:6px}
.pd-empty p{margin:0;color:#9AA0AD;font-size:12px;font-weight:760;line-height:1.65}
.pd-empty code{font-family:'SF Mono',ui-monospace,monospace;color:#9AA0AD;background:#1E2029;border-radius:7px;padding:2px 5px}
.pd-toggle-row{display:flex;justify-content:flex-end;margin:0 0 10px}
.pd-cat-section{margin:0 0 16px}
.pd-cat-head{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin:0 0 10px}
.pd-cat-head h4{margin:0;color:#E7E9EE;font-size:15px;font-weight:950}
.pd-cat-head span{color:#7E8694;font-size:11px;font-weight:850;text-align:right}
.pd-holding-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}
.pd-holding-card{position:relative;overflow:hidden;background:rgba(22,24,31,0.94);border:1px solid #262A33;border-radius:20px;
  padding:16px 18px;box-shadow:0 8px 22px rgba(0,0,0,0.30);min-height:256px}
.pd-holding-top{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:9px;align-items:center;margin-bottom:10px}
.pd-holding-name{min-width:0}
.pd-holding-name b{display:block;color:#E7E9EE;font-size:13px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pd-holding-name span{display:block;color:#7E8694;font-size:10px;font-weight:850;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pd-weight{border-radius:999px;padding:5px 8px;background:#1E2029;color:#9AA0AD;font-size:10px;font-weight:950}
.pd-value-row{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end;margin:2px 0 9px}
.pd-value-main span,.pd-day span{display:block;color:#7E8694;font-size:10px;font-weight:900;margin-bottom:3px}
.pd-value-main b{display:block;color:#E7E9EE;font-size:21px;font-weight:950;font-variant-numeric:tabular-nums}
.pd-day{text-align:right}
.pd-day b{font-size:12px;font-weight:950;font-variant-numeric:tabular-nums}
.pd-stat-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:9px 0}
.pd-stat{border:1px solid #262A33;background:#1E2029;border-radius:12px;padding:8px;min-width:0}
.pd-stat span{display:block;color:#7E8694;font-size:9.5px;font-weight:900;margin-bottom:3px}
.pd-stat b{display:block;color:#E7E9EE;font-size:11.5px;font-weight:950;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pd-spark{position:absolute;bottom:0;left:0;right:0;height:72px;opacity:0.09;pointer-events:none;z-index:0;margin:0}
.pd-spark svg{width:100%;height:72px;display:block}
.pd-holding-top,.pd-value-row,.pd-stat-grid,.pd-insight{position:relative;z-index:1}
.pd-insight{margin-top:9px;border-radius:13px;overflow:hidden;border:1px solid #262A33;background:#1E2029;display:flex;flex-direction:column-reverse}
.pd-insight summary{list-style:none;cursor:pointer;padding:9px 10px;color:#9AA0AD;font-size:11px;font-weight:950}
.pd-insight summary::-webkit-details-marker{display:none}
.pd-insight-body{border-bottom:1px solid #262A33;padding:10px;color:#9AA0AD;font-size:11px;font-weight:740;line-height:1.55}
.pd-insight-body b{color:#E7E9EE}
@media(max-width:1080px){.pd-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.pd-section-grid{grid-template-columns:1fr}}
@media(max-width:640px){
  .pd-summary-grid{grid-template-columns:1fr;gap:8px}
  .pd-header{display:block;margin:18px 0 10px}
  .pd-header h3{font-size:19px}  /* 헤더 크기(모바일) */
  .pd-header p{font-size:11.5px}
  .pd-source{margin-top:8px}
  .pd-card{padding:12px;border-radius:17px}
  .pd-summary-card{min-height:78px;padding:11px 12px}
  .pd-summary-card b{font-size:18px}
  .pd-section-title{display:block}
  .pd-section-title span{display:block;text-align:left;margin-top:3px}
  .pd-alloc-row{grid-template-columns:72px minmax(0,1fr) 48px;gap:8px}
  .pd-holding-grid{grid-template-columns:1fr;gap:9px}
  .pd-holding-card{min-height:0;padding:12px;border-radius:16px}
  .pd-value-main b{font-size:19px}
  .pd-stat-grid{gap:6px}
  .pd-cat-head{display:block}
  .pd-cat-head span{display:block;text-align:left;margin-top:4px}
}
@media(max-width:420px){
  .pd-stat-grid{grid-template-columns:1fr}
  .pd-value-row{grid-template-columns:1fr}
  .pd-day{text-align:left}
  .pd-weight{padding:4px 7px;font-size:9px}
}
.pd-header{margin:8px 0 12px}
.pd-header h3{font-size:20px;font-weight:800}  /* 2배·굵게 */
.pd-mode-wrap{margin:4px 0 12px}
.pd-overview{display:grid;grid-template-columns:1.25fr repeat(2,minmax(0,.72fr));gap:10px;margin:0 0 10px}
.pd-hero,.pd-metric,.pd-alert,.pd-diagnosis,.pd-table-card,.pd-rebalance-card{
  background:rgba(22,24,31,0.92);border:1px solid rgba(38,42,51,0.94);border-radius:12px;
  box-shadow:0 4px 14px rgba(0,0,0,0.30)}
.pd-hero{padding:16px 18px;min-height:112px;display:flex;flex-direction:column;justify-content:space-between}
.pd-hero span,.pd-metric span{display:block;color:#7E8694;font-size:11px;font-weight:900;margin-bottom:4px}
/* 총액 hero 무게 ↓(#12): 위험 카드(21px 헤드라인)가 1순위 앵커 — 총액은 보조 무게로 */
.pd-hero b{display:block;color:#D7DAE1;font-size:22px;font-weight:800;letter-spacing:0;font-variant-numeric:tabular-nums;line-height:1.1}
.pd-hero small,.pd-metric small{display:block;color:#7E8694;font-size:11px;font-weight:800;line-height:1.4;margin-top:5px}
.pd-hero-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.pd-chip{display:inline-flex;align-items:center;gap:5px;border-radius:999px;background:#1E2029;border:1px solid #262A33;
  color:#9AA0AD;padding:5px 8px;font-size:10px;font-weight:950;white-space:nowrap}
/* 경고 채널 = 주황(주의 #E08A3C / 위험 #E2683C). 손익 빨강(#F25560)·강조 골드(var(--sv-gold))와 분리 */
.pd-chip.warn{background:rgba(224,138,60,0.14);border-color:rgba(224,138,60,0.32);color:#E08A3C}
.pd-chip.danger{background:rgba(226,104,60,0.14);border-color:rgba(226,104,60,0.34);color:#E2683C}
/* 집중 위험 — 주황(위험)으로 통일 */
.pd-chip.conc{background:rgba(226,104,60,0.13);border-color:rgba(226,104,60,0.34);color:#E2683C}
.pd-cau{display:inline-block!important;font-size:9px;font-weight:800;color:#E08A3C;
  background:rgba(224,138,60,0.14);border-radius:5px;padding:1px 5px;margin-left:5px;letter-spacing:.02em}
.pd-metric{padding:13px 14px;min-height:112px;display:flex;flex-direction:column;justify-content:space-between}
.pd-metric b{display:block;color:#E7E9EE;font-size:20px;font-weight:950;font-variant-numeric:tabular-nums;line-height:1.15}
.pd-metric-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:0 0 8px}
.pd-overview-note{font-size:11.5px;font-weight:750;color:#7E8694;line-height:1.5;margin:0 0 12px}
.pd-overview-note b{color:#9AA0AD;font-weight:900}
/* 포트폴리오 진단 — 카드 밖으로(플랫): 테두리·배경·그림자 제거 */
.pd-diagnosis{padding:2px 0 10px;margin:0 0 14px;background:transparent;border:0;box-shadow:none}
.pd-diagnosis-head{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin-bottom:10px}
.pd-diagnosis-head b{color:#E7E9EE;font-size:20px;font-weight:800}  /* 헤더 크기·굵게 */
.pd-diagnosis-head span{color:#7E8694;font-size:11px;font-weight:850}
.pd-head-right{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.pd-header-sub .lv-badge{margin:0}
/* 골드 강조 링크 — Streamlit 기본 링크색(파랑, 하락色과 혼동)을 덮도록 !important */
.pd-jump{display:inline-flex;align-items:center;font-size:11px;font-weight:850;color:var(--sv-gold)!important;
  text-decoration:none;background:rgba(217,164,65,0.10);border:1px solid rgba(217,164,65,0.34);
  border-radius:999px;padding:3px 11px;white-space:nowrap}
.pd-jump:hover{background:rgba(217,164,65,0.18);border-color:var(--sv-gold)}
.pd-back{display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:850;color:#9AA0AD!important;
  text-decoration:none;margin:2px 0 10px}
.pd-back:hover{color:#E7E9EE}
/* 카드 수(3~5)에 맞춰 한 줄을 채움 — 3열 고정 시 4번째가 외톨이로 떨어지던 문제 해소 */
.pd-diagnosis-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin-top:16px}
.pd-diagnosis-item{border:1px solid #262A33;border-radius:10px;background:#1E2029;padding:10px 11px;border-left:3px solid #262A33}
.pd-diagnosis-item strong{display:block;color:#E7E9EE;font-size:12px;font-weight:950;margin-bottom:4px}
.pd-diagnosis-item span{display:block;color:#9AA0AD;font-size:11px;font-weight:760;line-height:1.45}
/* 진단 심각도 — 경고는 주황(주의/위험), 비중-매칭(gold/olive)은 골드 계열 유지 */
.pd-diagnosis-item.warn{border-left-color:#E08A3C}
.pd-diagnosis-item.gold{border-left-color:#C99A3C}
.pd-diagnosis-item.olive{border-left-color:#8C7A3E}
.pd-diagnosis-item.danger{border-left-color:#E2683C;background:linear-gradient(135deg,rgba(226,104,60,0.08),#1E2029 60%)}
.pd-diagnosis-item.danger strong{color:#E2683C}
/* C3: 보기 라디오를 진단 카드 상단에 붙임 */
[data-testid="stRadio"]{background:#16181F;border:1px solid #262A33;border-radius:14px;
  padding:8px 14px 4px;margin-bottom:8px}
[data-testid="stRadio"] > label{font-size:11px!important;color:#7E8694!important;font-weight:800!important}
.pd-mini-alloc{display:flex;height:12px;border-radius:999px;overflow:hidden;background:#1E2029;border:1px solid #262A33;margin:8px 0 10px}
.pd-mini-alloc i{display:block;height:100%;min-width:2px}
.pd-mini-legend{display:flex;flex-wrap:wrap;gap:6px;color:#9AA0AD;font-size:10px;font-weight:900}
.pd-mini-legend span{display:inline-flex;align-items:center;gap:5px;border-radius:999px;background:#1E2029;border:1px solid #262A33;padding:4px 7px}
.pd-mini-dot{width:7px;height:7px;border-radius:50%;display:inline-block}
.pd-conc-label{font-size:11px;font-weight:900;color:#9AA0AD;margin:2px 0 6px;display:flex;align-items:baseline;gap:7px}
.pd-conc-label span{font-size:10px;font-weight:800;color:#7E8694}
/* 탐욕 지수 바 — 회색(공포/중립) → 주황(탐욕=과열 경고). 골드(강조) 아님: 탐욕은 경고 채널 */
.gd-block{margin-top:16px;padding-top:13px;border-top:1px solid #23262E}  /* 위 자산군 바와 구분 */
.gd-track{position:relative;height:12px;border-radius:999px;border:1px solid #262A33;margin:8px 0 7px;
  background:linear-gradient(90deg,#5A5F52 0%,#C9882F 52%,#E08A3C 100%)}  /* 회색(공포)→주황(탐욕 과열) */
.gd-marker{position:absolute;top:50%;width:3px;height:18px;border-radius:3px;background:#E7E9EE;
  transform:translate(-50%,-50%);box-shadow:0 0 0 2px rgba(14,15,19,.65)}
.gd-scale{display:flex;justify-content:space-between;font-size:10px;font-weight:850;color:#7E8694;margin:0 0 4px}
/* 핵심 보유종목 — 카드 밖으로(플랫): 패널 테두리·배경·그림자 제거, 표만 남김 */
.pd-list-panel{background:transparent;border:0;box-shadow:none;padding:0;margin:0 0 14px}
.pd-list-head{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin:0 0 10px}  /* C1 좌측 기준선 통일 */
.pd-list-head b{color:#E7E9EE;font-size:20px;font-weight:800}  /* 2배·굵게 */
.pd-list-head span{color:#7E8694;font-size:11px;font-weight:850}
.pd-table-card{overflow:hidden;margin:0;border-radius:10px;border:1px solid #262A33;background:#16181F}
.pd-table-head,.pd-row{display:grid;grid-template-columns:minmax(190px,1.55fr) 74px 126px 88px 74px 56px;gap:8px;align-items:center}
.pd-table-head{padding:8px 12px;background:#1E2029;border-bottom:1px solid #262A33;color:#9AA0AD;font-size:9.5px;font-weight:950;text-transform:uppercase;letter-spacing:0}
.pd-row{min-height:54px;padding:8px 12px;border-bottom:1px solid #262A33;background:rgba(22,24,31,0.78)}
.pd-row:last-child{border-bottom:none}
.pd-row-main{display:grid;grid-template-columns:28px minmax(0,1fr);gap:8px;align-items:center;min-width:0}
.pd-row-main .hold-logo{width:28px;height:28px;border-radius:8px;font-size:8.5px}
.pd-row-name{min-width:0}.pd-row-name b{display:block;color:#E7E9EE;font-size:12px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pd-row-name span{display:block;color:#7E8694;font-size:10px;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px}
.pd-row-num{text-align:right;color:#E7E9EE;font-size:11.5px;font-weight:950;font-variant-numeric:tabular-nums;white-space:nowrap}
.pd-row-num small{display:block;color:#7E8694;font-size:9px;font-weight:850;margin-top:1px;white-space:nowrap}
.pd-row-actions{border:1px solid #262A33;border-radius:10px;background:#1E2029;overflow:hidden}
.pd-row-actions[open]{grid-column:1/-1}
.pd-row-actions[open] summary{width:52px;margin-left:auto;border-left:1px solid #262A33}
.pd-row-actions summary{list-style:none;cursor:pointer;padding:6px 7px;text-align:center}
.pd-row-actions summary::-webkit-details-marker{display:none}
.pd-row-actions summary .pd-caret{display:inline-block;transition:transform .18s;font-size:11px;color:#7E8694}
.pd-row-actions summary:hover .pd-caret{color:#9AA0AD}
.pd-row-actions[open] summary .pd-caret{transform:rotate(180deg);color:#9AA0AD}
.pd-row-detail{border-top:1px solid #262A33;padding:10px;color:#9AA0AD;font-size:11px;font-weight:740;line-height:1.55}
.pd-row-detail b{color:#E7E9EE}
/* D3 핵심 보유종목 — 카드형 행(이름 15px + 섹터·주수 12px + 비중 바 | 평가 15px + 손익 12.5px | 펼침). C2 하한 준수 */
.hl-card{overflow:hidden}
.hl-row{display:grid;grid-template-columns:minmax(0,1fr) auto 30px;gap:12px;align-items:center;
  padding:12px 14px;border-bottom:1px solid #262A33;background:rgba(22,24,31,0.78)}
.hl-row:last-child{border-bottom:0}
.hl-main{display:grid;grid-template-columns:34px minmax(0,1fr);gap:11px;align-items:center;min-width:0}
.hl-main .hold-logo{width:34px;height:34px;border-radius:9px;font-size:11px}
.hl-info{min-width:0}
.hl-name{display:block;color:#E7E9EE;font-size:15px;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hl-sub{display:block;color:#9AA0AD;font-size:12px;font-weight:750;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hl-wbar{height:5px;border-radius:999px;background:rgba(255,255,255,0.06);overflow:hidden;margin-top:8px;max-width:240px}
.hl-wbar i{display:block;height:100%;border-radius:999px}
.hl-vals{text-align:right;white-space:nowrap;min-width:0}
.hl-val{display:block;color:#E7E9EE;font-size:15px;font-weight:900;font-variant-numeric:tabular-nums}
/* C2: 손익률/금액/오늘을 점(·) 없이 간격(gap)으로 구분. 오늘은 한 단계 옅게 de-emphasize */
.hl-ret{display:flex;justify-content:flex-end;align-items:baseline;flex-wrap:wrap;gap:1px 12px;
  font-size:12.5px;font-weight:850;margin-top:4px;font-variant-numeric:tabular-nums;color:#9AA0AD}
.hl-ret-amt{font-weight:800}
.hl-ret-today{color:#7E8694;font-size:11.5px;font-weight:750}
.hl-ret-today b{font-weight:850}
.hl-exp{justify-self:end}
.hl-exp summary{list-style:none;cursor:pointer;width:30px;height:30px;display:grid;place-items:center;
  border:1px solid #262A33;border-radius:9px;background:#1E2029}
.hl-exp summary::-webkit-details-marker{display:none}
.hl-caret{font-size:12px;color:#7E8694;transition:transform .18s}
.hl-exp summary:hover .hl-caret{color:#9AA0AD}
.hl-exp[open]{grid-column:1/-1;margin-top:2px}
.hl-exp[open] summary{margin-left:auto}
.hl-exp[open] .hl-caret{transform:rotate(180deg);color:#9AA0AD}
.hl-detail{border-top:1px solid #262A33;margin-top:10px;padding-top:10px;color:#9AA0AD;
  font-size:12px;font-weight:740;line-height:1.6}
.hl-detail b{color:#E7E9EE}
@media(max-width:640px){
  .hl-row{grid-template-columns:minmax(0,1fr) auto 30px;gap:10px}
  .hl-wbar{max-width:none}
}
.pd-rebalance-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 12px}
.pd-rebalance-card{padding:14px 16px}
.pd-rebalance-card b{display:block;color:#E7E9EE;font-size:14px;font-weight:950;margin-bottom:6px}
.pd-rebalance-card p{margin:0;color:#9AA0AD;font-size:12px;font-weight:760;line-height:1.6}
/* 리밸런싱 종목별 조정 표 — 현재→목표→조정→금액 (매도 블루 / 매수 레드) */
.rb-tbl{margin:0 0 4px}
.rb-thead,.rb-trow{display:grid;grid-template-columns:1.4fr .8fr .8fr 1fr 1.1fr;gap:8px;align-items:center}
.rb-thead{font-size:10px;font-weight:900;color:#7E8694;text-transform:uppercase;letter-spacing:.04em;
  padding:0 12px 8px}
.rb-trow{min-height:46px;padding:8px 12px;border-top:1px solid #262A33;font-size:12.5px}
.rb-nm{font-weight:850;color:#E7E9EE;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rb-cur,.rb-tgt{font-variant-numeric:tabular-nums;font-weight:800;color:#C9CEDA}
.rb-tgt{color:#E7E9EE}
.rb-adj,.rb-amt{font-variant-numeric:tabular-nums;font-weight:850;text-align:right}
.rb-sell{color:#4D90F0}   /* 매도 = 블루(한국식) */
.rb-buy{color:#F25560}    /* 매수 = 레드(한국식) */
.rb-keep{color:#7E8694;font-weight:750}
.rb-move{color:#C99A3C}   /* 이동처 유입 = 골드(매수 권유 아님, 분산 방향) */
.rb-num{text-align:right}
/* 앱 vs 사용자 역할 분리 */
.rb-split{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0 4px}
.rb-role{background:#1E2029;border:1px solid #262A33;border-radius:12px;padding:12px 14px}
.rb-role.app{border-left:3px solid #C99A3C}
.rb-role.user{border-left:3px solid #5A5F52}
.rb-role-k{font-size:10px;font-weight:900;letter-spacing:.04em;text-transform:uppercase;margin-bottom:7px}
.rb-role.app .rb-role-k{color:#C99A3C}
.rb-role.user .rb-role-k{color:#9AA0AD}
.rb-role ul{margin:0;padding-left:16px}
.rb-role li{color:#C9CEDA;font-size:11.5px;font-weight:730;line-height:1.7}
@media(max-width:1080px){.rb-split{grid-template-columns:1fr}}
.rb-foot{font-size:11.5px;font-weight:700;color:#9AA0AD;line-height:1.55;margin-top:10px;
  padding-top:9px;border-top:1px solid #262A33}
@media(max-width:1080px){
  .rb-thead{display:none}
  .rb-trow{grid-template-columns:1fr 1fr;gap:4px 8px;padding:10px 12px}
  .rb-nm{grid-column:1/-1}
}
/* 운용 방식(철학) 레이어 — 추천 골드 테두리, 출처 라벨, 차이 표 */
.rbm-diag{background:rgba(217,164,65,0.08);border:1px solid var(--sv-gold);border-radius:12px;
  padding:11px 15px;margin:2px 0 12px;font-size:12.5px;font-weight:750;color:#E7E9EE;line-height:1.55}
.rbm-diag b{color:var(--sv-gold);font-weight:900}
.rbm-diag-k{display:inline-block;font-size:9px;font-weight:900;color:var(--sv-gold);letter-spacing:.06em;
  text-transform:uppercase;background:rgba(217,164,65,0.15);border-radius:6px;padding:2px 7px;margin-right:8px}
.rbm-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0 0 14px}
.rbm-card{background:#1E2029;border:1px solid #262A33;border-radius:12px;padding:13px 14px}
.rbm-card.rec{border-color:var(--sv-gold);box-shadow:0 0 0 1px rgba(217,164,65,0.25)}
.rbm-card.sel{background:#23262E}
.rbm-h{display:flex;align-items:center;gap:7px;color:#E7E9EE;font-size:13px;font-weight:950;margin-bottom:6px}
.rbm-badge{font-size:9px;font-weight:900;color:var(--sv-gold);background:rgba(217,164,65,0.15);
  border-radius:6px;padding:2px 7px;letter-spacing:.04em}
.rbm-badge.sm{margin-left:5px}
.rbm-d{color:#9AA0AD;font-size:11.5px;font-weight:730;line-height:1.5;min-height:50px}
.rbm-src{margin-top:8px;font-size:10px;font-weight:800;color:#8C7A3E;line-height:1.5}
.rbm-soon{display:block;color:#7E8694;font-weight:750;margin-top:3px}
.rbm-pending-p{margin:0 0 8px;color:#C9CEDA;font-size:12px;font-weight:750;line-height:1.6}
.rbm-pending-note{margin:0;color:#9AA0AD;font-size:11.5px;font-weight:700;line-height:1.55}
.rbm-pending-note b{color:var(--sv-gold)}
.rbm-tbl{margin:2px 0}
.rbm-thead,.rbm-trow{display:grid;grid-template-columns:1fr 1.3fr 1.1fr 1.3fr;gap:8px;align-items:center}
.rbm-thead{font-size:10px;font-weight:900;color:#7E8694;text-transform:uppercase;letter-spacing:.04em;padding:0 12px 8px}
.rbm-trow{min-height:42px;padding:8px 12px;border-top:1px solid #262A33;font-size:12px;font-weight:730;color:#C9CEDA;line-height:1.45}
.rbm-tnm{font-weight:900;color:#E7E9EE}
.rbm-honest{margin-top:11px;padding-top:10px;border-top:1px solid #262A33;
  font-size:11.5px;font-weight:700;color:#9AA0AD;line-height:1.55}
.rbm-honest b{color:#E7E9EE}
.rbm-refs{margin-top:8px;font-size:10px;font-weight:800;color:#7E8694;letter-spacing:.02em}
@media(max-width:1080px){
  .rbm-grid{grid-template-columns:1fr}
  .rbm-thead{display:none}
  .rbm-trow{grid-template-columns:1fr 1fr;gap:4px 8px}
  .rbm-tnm{grid-column:1/-1}
}
@media(max-width:1080px){
  .pd-overview{grid-template-columns:1fr 1fr}.pd-hero{grid-column:1/-1}.pd-metric-row{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-diagnosis-grid,.pd-rebalance-grid{grid-template-columns:1fr}
  .pd-table-head{display:none}.pd-row{grid-template-columns:1fr 1fr;gap:8px}.pd-row-main{grid-column:1/-1}
  .pd-row-actions{grid-column:1/-1}.pd-row-num{text-align:left}
}
@media(max-width:640px){
  .pd-overview,.pd-metric-row{grid-template-columns:1fr}
  .pd-hero b{font-size:20px}
  .pd-row{grid-template-columns:1fr}
}
.hcv-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-bottom:16px}
.hcv-card{position:relative;overflow:hidden;background:rgba(22,24,31,0.96);border:1px solid #262A33;
  border-radius:18px;padding:16px 18px 18px;box-shadow:0 4px 18px rgba(0,0,0,0.30);
  display:flex;flex-direction:column;transition:box-shadow .15s}
.hcv-card:hover{box-shadow:0 8px 28px rgba(0,0,0,0.40)}
.hcv-head{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.hcv-info{flex:1;min-width:0}
.hcv-info b{display:block;color:#E7E9EE;font-size:14px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hcv-info span{display:block;color:#7E8694;font-size:10.5px;font-weight:850;margin-top:2px}
.hcv-wt{flex-shrink:0;border-radius:999px;padding:4px 9px;background:#1E2029;color:#9AA0AD;font-size:10.5px;font-weight:950}
.hcv-val{margin-bottom:12px}
.hcv-val-num{color:#E7E9EE;font-size:25px;font-weight:950;font-variant-numeric:tabular-nums;letter-spacing:-0.025em;line-height:1.05}
.hcv-val-sub{color:#7E8694;font-size:10.5px;font-weight:850;margin-top:3px}
.hcv-pills{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:10px}
.hcv-pill{border-radius:11px;padding:9px 11px;background:#1E2029;border:1px solid #262A33}
.hcv-pill span{display:block;color:#7E8694;font-size:9px;font-weight:950;letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px}
.hcv-pill b{display:block;font-size:14px;font-weight:950;font-variant-numeric:tabular-nums;line-height:1}
.hcv-pill small{display:block;color:#7E8694;font-size:10px;font-weight:850;margin-top:3px}
.hcv-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:auto}
.hcv-st{background:#1E2029;border:1px solid #262A33;border-radius:9px;padding:7px 9px}
.hcv-st span{display:block;color:#7E8694;font-size:9px;font-weight:950;letter-spacing:.04em;text-transform:uppercase;margin-bottom:3px}
.hcv-st b{display:block;color:#E7E9EE;font-size:11px;font-weight:950;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hcv-spark{position:absolute;bottom:0;left:0;right:0;height:56px;opacity:0.07;pointer-events:none;z-index:0}
.hcv-spark svg{width:100%;height:56px;display:block}
.hcv-head,.hcv-val,.hcv-pills,.hcv-stats{position:relative;z-index:1}
@media(max-width:960px){.hcv-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.hcv-grid{grid-template-columns:1fr}}
</style>"""

_AJ_CSS = """<style>
.aj-block{background:#16181F;border:1px solid #262A33;border-radius:20px;padding:18px 24px 20px;margin:0 0 10px}
.aj-top{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}
.aj-top h3{margin:0;color:#E7E9EE;font-size:20px;font-weight:800;letter-spacing:-.01em}  /* 2배·굵게 */
/* 상태 배지 2개 — 단계(초록 계열·정보) + 페이스(골드/회색/주황·평가). 목표수정 아이콘과 높이 28px·라운딩 통일 */
.aj-stage,.aj-pace{display:inline-flex;align-items:center;height:28px;box-sizing:border-box;padding:0 12px;
  border-radius:999px;font-size:11px;font-weight:800;white-space:nowrap;
  border:1px solid #262A33;background:rgba(255,255,255,.05);color:#9AA0AD}
/* 단계(진행 phase) — 초록 계열 단계별 농도 */
.aj-stage.s-early{color:#9AA0AD;background:rgba(255,255,255,.05);border-color:#262A33}      /* 초반: 중립 */
.aj-stage.s-cruise{color:#3DD68C;background:rgba(61,214,140,.12);border-color:rgba(61,214,140,.34)}  /* 순항: 초록 */
.aj-stage.s-final{color:#27A37A;background:rgba(39,163,122,.14);border-color:rgba(39,163,122,.40)}    /* 막바지: 진초록 */
.aj-stage.s-reached{color:#0E140F;background:#3DD68C;border-color:#3DD68C}                  /* 도달: 초록 강조(filled) */
/* 페이스(예정 대비) — 앞섬=골드 / 부합=중립 / 뒤처짐=주황 경고(P&L 빨강·파랑과 분리) */
.aj-pace.ahead{color:var(--sv-gold);background:rgba(217,164,65,.12);border-color:rgba(217,164,65,.34)}
.aj-pace.ontrack{color:#9AA0AD;background:rgba(255,255,255,.05);border-color:#262A33}
.aj-pace.behind{color:#E08A3C;background:rgba(224,138,60,.13);border-color:rgba(224,138,60,.38)}
.aj-top-row{margin-bottom:0}
/* [순항중][페이스]는 badge_col 우측 정렬. 단계↔페이스 간격(16px) = 컬럼 간격(=페이스↔톱니)과 맞춰 3개 등간격 */
.aj-badgewrap{display:flex;justify-content:flex-end;align-items:center;gap:13px}
/* 자산 여정 — 카드 밖으로(플랫): 카드 강제 CSS 제거, 헤더·그리드는 페이지에 바로 */
.aj-marker{display:none}
/* 목표 수정 톱니 — 배지와 동일 높이(28px)·라운딩 */
[data-testid="stPopover"] button{border-radius:999px!important;font-weight:850!important;
  height:28px!important;min-width:28px!important;padding:0 9px!important;
  display:inline-flex!important;align-items:center!important;justify-content:center!important;
  min-height:0!important;line-height:1!important;white-space:nowrap!important;
  margin-left:0!important;margin-top:0!important;box-shadow:none!important;
  background:rgba(217,164,65,.10)!important;border:1px solid rgba(217,164,65,.40)!important;color:var(--sv-gold)!important}
[data-testid="stPopover"] button [data-testid="stIconMaterial"]{font-size:17px!important}
[data-testid="stPopover"] button:hover{background:rgba(217,164,65,.2)!important;border-color:var(--sv-gold)!important}
[data-testid="stPopover"] button [data-testid="stMarkdownContainer"] p{margin:0!important;line-height:1.2!important}
.aj-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:24px;align-items:center}
@media(max-width:820px){.aj-grid{grid-template-columns:1fr;gap:16px}}
.aj-headline .lbl{font-size:12px;font-weight:800;color:#9AA0AD;display:block;margin-bottom:1px}
.aj-headline .val{font-size:44px;font-weight:950;color:#E7E9EE;line-height:1;
  letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.aj-val-up{color:#F25560}   /* 추이 헤드라인 수익률 — 상승=빨강(한국식) */
.aj-val-down{color:#4D90F0} /* 하락=파랑 */
/* 진행률 바(클릭 가능) — 고정 높이(120px)로 위 투명 오버레이 버튼 정렬 안정. 우하단 힌트 */
.aj-chart{margin-top:10px;height:120px;box-sizing:border-box;border-radius:12px;padding:4px;
  position:relative}
.aj-chart svg{height:100%}
.aj-chart-hint{position:absolute;right:9px;bottom:6px;font-size:10.5px;font-weight:850;color:#9A7B2E;
  opacity:.8;transition:opacity .15s;pointer-events:none;z-index:2}
/* 추이 등장 애니메이션 — 바닥(0)에서 천천히 차오름 */
.aj-chart-trend svg{animation:aj-rise .8s cubic-bezier(.22,.61,.36,1) both;transform-origin:bottom}
@keyframes aj-rise{from{transform:scaleY(0);opacity:.25}to{transform:scaleY(1);opacity:1}}
/* 바 위 투명 오버레이 버튼 = '바 클릭'으로 추이 전환(아래 별도 버튼 없이). hover 시 옅은 골드 틴트 */
/* 그래프 클릭=전환 오버레이. 컨테이너 testid 가 Streamlit 버전마다 다름
   (1.37.x: element-container / 1.58.x: stElementContainer) → 양쪽 모두 매칭. */
.aj-barclick-anchor{height:0;margin:0;padding:0;line-height:0}
[data-testid="stVerticalBlock"]:has(> [data-testid="element-container"] .aj-barclick-anchor),
[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .aj-barclick-anchor){gap:0!important}
[data-testid="element-container"]:has(.aj-barclick-anchor) + [data-testid="element-container"],
[data-testid="stElementContainer"]:has(.aj-barclick-anchor) + [data-testid="stElementContainer"]{
  margin-top:-104px!important;height:120px!important;position:relative;z-index:6}
[data-testid="element-container"]:has(.aj-barclick-anchor) + [data-testid="element-container"] button,
[data-testid="stElementContainer"]:has(.aj-barclick-anchor) + [data-testid="stElementContainer"] button{
  height:120px!important;width:100%!important;min-height:0!important;border:0!important;border-radius:12px!important;
  background:transparent!important;color:transparent!important;box-shadow:none!important;cursor:pointer!important;
  padding:0!important;transition:background .15s!important}
[data-testid="element-container"]:has(.aj-barclick-anchor) + [data-testid="element-container"] button:hover,
[data-testid="stElementContainer"]:has(.aj-barclick-anchor) + [data-testid="stElementContainer"] button:hover{
  background:rgba(217,164,65,0.07)!important}
.aj-cards{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.aj-card{background:rgba(255,255,255,.03);border:1px solid #262A33;border-radius:14px;padding:12px 14px;min-width:0}
.aj-card .k{font-size:11px;font-weight:800;color:#9AA0AD;display:flex;align-items:center;gap:6px}
.aj-card .v{font-size:19px;font-weight:950;color:#E7E9EE;margin-top:5px;
  font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.aj-auto{font-size:9px;font-weight:800;color:var(--sv-gold);background:rgba(217,164,65,.13);
  border-radius:5px;padding:1px 5px;letter-spacing:.02em}
.aj-pop-t{font-size:13px;font-weight:900;color:#E7E9EE;margin-bottom:8px}
/* D5: 목표 수정 트리거 — 골드 아웃라인 "⚙ 목표 수정" 라벨 칩(헤더 옆) */
div[data-testid="stPopover"] > div button{
  background:rgba(217,164,65,.10)!important;border:1px solid rgba(217,164,65,.42)!important;
  color:var(--sv-gold)!important;border-radius:999px!important;font-weight:850!important;
  height:28px!important;min-width:28px!important;padding:0 9px!important;
  display:inline-flex!important;align-items:center!important;justify-content:center!important;
  min-height:0!important;line-height:1!important;
  margin-left:0!important;margin-top:0!important;box-shadow:none!important;white-space:nowrap!important}
div[data-testid="stPopover"] > div button:hover{
  background:rgba(217,164,65,.18)!important;border-color:var(--sv-gold)!important;color:var(--sv-gold)!important}
</style>"""

_AT_CSS = """<style>
.at-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin:0 0 8px}  /* C1 좌측 기준선 통일 */
.at-head b{color:#E7E9EE;font-size:20px;font-weight:800}  /* 2배·굵게 */
.at-head span{color:#7E8694;font-size:11px;font-weight:850}
.at-head span .up{color:#F25560}.at-head span .down{color:#4D90F0}
/* 추이 헤더 = 자산 여정 복귀 링크(그래프/헤더 클릭 전환) */
.at-back{color:#E7E9EE;font-size:20px;font-weight:800;text-decoration:none;cursor:pointer}
.at-back:hover{color:var(--sv-gold)}
/* 기간 라디오 — 우측 정렬 + 옵션 글자 가운데 */
[data-testid="stRadio"] div[role="radiogroup"]{justify-content:flex-end!important}
[data-testid="stRadio"] div[role="radiogroup"] label{text-align:center!important;justify-content:center!important}
.at-empty{background:#16181F;border:1px dashed #2E333D;border-radius:16px;padding:16px 18px;margin:0 0 10px;
  color:#9AA0AD;font-size:12px;font-weight:700}
.at-empty b{color:#E7E9EE;font-size:13px;font-weight:900;display:block;margin-bottom:3px}
</style>"""

_ASEC_CSS = """<style>
/* D2: '지나온 경로(자산 추이) 펼치기' 스트립 — 진행률 바 바로 아래, 클릭 affordance(hover 밝아짐).
   토글 제거: 여정(현재 위치)과 추이(지나온 경로)는 보완 관계라 같은 자리에서 펼쳐 연결한다. */
[data-testid="element-container"]:has(.asec-strip-anchor) + [data-testid="element-container"] button{
  background:rgba(217,164,65,.06)!important;border:1px solid rgba(217,164,65,.26)!important;
  border-radius:12px!important;color:#9AA0AD!important;font-size:12px!important;font-weight:850!important;
  padding:7px 12px!important;min-height:0!important;margin-top:-2px!important;box-shadow:none!important;
  transition:background .15s,border-color .15s,color .15s!important}
[data-testid="element-container"]:has(.asec-strip-anchor) + [data-testid="element-container"] button:hover{
  background:rgba(217,164,65,.14)!important;border-color:var(--sv-gold)!important;color:var(--sv-gold)!important}
.asec-strip-anchor{height:0;margin:0;padding:0}
</style>"""

_PB_CSS = """<style>
/* 위험 카드: 위험=주황(경고 채널, 손익 빨강과 분리), 주의=앰버, 양호=초록. 좌측 4px 바 + 배지 라벨로 읽힘 */
.pb-card{border:1px solid #262A33;border-left:4px solid #E2683C;border-radius:18px;
  background:#15171E;padding:18px 22px;margin:2px 0 16px}
.pb-card.pb-warn{border-left-color:#E08A3C;background:linear-gradient(135deg,rgba(224,138,60,0.07),#16181F 60%)}
.pb-card.pb-safe{border-left-color:#3FB27F;background:#16181F}
.pb-sev{display:inline-block;font-size:11px;font-weight:900;color:#E2683C;background:rgba(226,104,60,0.14);
  border-radius:999px;padding:3px 10px;letter-spacing:.04em}
.pb-warn .pb-sev{color:#E08A3C;background:rgba(224,138,60,0.14)}
.pb-safe .pb-sev{color:#3FB27F;background:rgba(63,178,127,0.14)}
.pb-head{font-size:21px;font-weight:950;color:#E7E9EE;letter-spacing:-.02em;margin:10px 0 14px;line-height:1.25}
.pb-scen{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}
@media(max-width:720px){.pb-scen{grid-template-columns:1fr}}
.pb-s{background:rgba(255,255,255,0.03);border:1px solid #262A33;border-radius:12px;padding:11px 13px}
.pb-s span{display:block;font-size:11px;font-weight:800;color:#9AA0AD;margin-bottom:5px}
.pb-s b{font-size:15px;font-weight:950;color:#E7E9EE;font-variant-numeric:tabular-nums}
/* C4: 보더 명도 낮춰 배경에 안착(떠 보임 해소) — 좌측 보더 없이 옅은 채움+낮은 대비 테두리 */
.pb-action{background:rgba(217,164,65,0.10);border:1px solid rgba(217,164,65,0.18);border-radius:12px;
  padding:11px 14px;font-size:13.5px;font-weight:850;color:#E7E9EE}
.pb-action b{color:var(--sv-gold)}
.pb-cost{display:block;margin-top:5px;font-size:11.5px;font-weight:700;color:#9AA0AD}
.pb-bench{margin-top:10px;font-size:12px;font-weight:700;color:#9AA0AD;font-variant-numeric:tabular-nums}
/* E1: 재배분 '실행 예정' 표시 — 위험카드 바로 아래 한 줄(조언→행동 연결) */
.pb-plan{margin:8px 0 0;padding:9px 13px;border-radius:11px;font-size:12px;font-weight:800;color:#C9CEDA;
  background:rgba(217,164,65,0.08);border:1px solid rgba(217,164,65,0.20)}
.pb-plan b{color:var(--sv-gold)}
.pb-plan-link{margin-left:8px;color:var(--sv-gold)!important;text-decoration:none;font-weight:850;white-space:nowrap}
.pb-plan-link:hover{text-decoration:underline}
/* 내 계좌 탐욕 지수 — 게이지는 리스크 게이지와 동일 처리(명도·라벨). 색만으로 의미 전달 금지 */
[data-testid="stVerticalBlockBorderWrapper"]:has(.agr-title){
  background:#16181F;border:1px solid #262A33;border-radius:16px;padding:6px 6px 2px}
.agr-title{font-size:11px;font-weight:800;color:#7E8694;letter-spacing:.05em;text-align:center;margin:6px 0 0}
/* 탐욕 온도계 — 가로 막대(청록 공포→골드 중립→짙은빨강 탐욕) + 값 마커 + 구간 라벨 */
.agr-therm{margin:12px 8px 4px}
.agr-therm-val{text-align:center;font-size:30px;font-weight:950;color:#E7E9EE;line-height:1;
  font-variant-numeric:tabular-nums;font-family:'SF Mono',ui-monospace,monospace;margin-bottom:10px}
.agr-therm-track{position:relative;height:14px;border-radius:999px;
  background:linear-gradient(90deg,#3A8FC2 0%,var(--sv-gold) 50%,#C46A2B 100%)}
.agr-therm-marker{position:absolute;top:50%;width:4px;height:24px;border-radius:3px;background:#E7E9EE;
  transform:translate(-50%,-50%);box-shadow:0 0 0 2px rgba(14,15,19,.65),0 1px 4px rgba(0,0,0,.4)}
.agr-therm-scale{display:flex;justify-content:space-between;margin-top:8px;
  font-size:10px;font-weight:850;color:#7E8694}
.agr-band{display:flex;justify-content:center;align-items:center;gap:8px;margin-top:2px}
.agr-band .pill{font-size:12px;font-weight:900;color:#E7E9EE;border:1px solid #3A3F49;
  border-radius:999px;padding:3px 11px;background:rgba(255,255,255,0.04)}
.agr-band .pill.hot{border-color:var(--sv-gold);color:#E7B85C}
.agr-interp{text-align:center;font-size:11.5px;font-weight:700;color:#8A8F9B;margin-top:7px;line-height:1.5}
.agr-comp{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:6px 12px;align-items:center;
  font-size:12px;font-weight:700;padding:7px 2px;border-top:1px solid #23262E}
.agr-comp:first-of-type{border-top:0}
.agr-comp .nm{color:#E7E9EE}.agr-comp .rw{color:#9AA0AD;font-variant-numeric:tabular-nums}
.agr-comp .ct{color:#7E8694;font-variant-numeric:tabular-nums;text-align:right;min-width:64px}
.agr-comp .note{grid-column:1/-1;color:#7E8694;font-size:11px;font-weight:600;margin-top:-2px}
.agr-foot{font-size:11px;font-weight:700;color:#7E8694;margin-top:8px;line-height:1.5}
/* 벤치마크 비교 */
.bm-card{background:#16181F;border:1px solid #262A33;border-radius:16px;padding:16px 20px;margin:0 0 10px}
.bm-title{font-size:13px;font-weight:950;color:#E7E9EE;margin-bottom:12px}
.bm-row{display:grid;grid-template-columns:120px 1fr 64px;gap:12px;align-items:center;margin:7px 0}
.bm-lbl{font-size:12px;font-weight:800;color:#9AA0AD;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bm-lbl.mine{color:var(--sv-gold);font-weight:950}
.bm-track{height:12px;border-radius:999px;background:rgba(255,255,255,0.05);overflow:hidden}
.bm-track i{display:block;height:100%;border-radius:999px}
.bm-mine{background:var(--sv-gold)}.bm-other{background:#5E6573}  /* 내 포트폴리오 = 골드(강조), 벤치마크 = 회색 */
.bm-val{text-align:right;font-size:13px;font-weight:900;color:#9AA0AD;font-variant-numeric:tabular-nums}
.bm-val.mine{color:var(--sv-gold)}
.bm-cap{margin-top:11px;font-size:11.5px;font-weight:700;color:#7E8694;line-height:1.5}
/* 리밸런싱 보기 버튼 — 골드 */
.st-key-pb_rebal_btn button{background:rgba(217,164,65,0.12)!important;border:1px solid rgba(217,164,65,0.42)!important;
  color:var(--sv-gold)!important;border-radius:12px!important;font-weight:850!important;margin:-6px 0 14px!important}
.st-key-pb_rebal_btn button:hover{background:rgba(217,164,65,0.2)!important;border-color:var(--sv-gold)!important}
</style>"""

_ONBOARD_CSS = """<style>
.ob-hero{background:linear-gradient(135deg,rgba(217,164,65,.10),#16181F 60%);border:1px solid #262A33;
  border-radius:20px;padding:22px 24px;margin:6px 0 14px}
.ob-hero h2{margin:0;color:#E7E9EE;font-size:22px;font-weight:950;letter-spacing:-.02em}
.ob-hero p{margin:8px 0 0;color:#9AA0AD;font-size:13px;font-weight:700;line-height:1.55}
.ob-steps{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
.ob-step{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:850;color:#9AA0AD;
  background:#1E2029;border:1px solid #262A33;border-radius:999px;padding:5px 12px}
.ob-step b{color:var(--sv-gold)}
.ob-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:0 0 16px}
@media(max-width:860px){.ob-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.ob-c{background:#16181F;border:1px solid #262A33;border-radius:14px;padding:14px 15px}
.ob-c .ic{font-size:18px}
.ob-c b{display:block;color:#E7E9EE;font-size:13px;font-weight:900;margin:7px 0 4px}
.ob-c span{display:block;color:#9AA0AD;font-size:11px;font-weight:650;line-height:1.5}
.ob-explore{display:inline-flex;align-items:center;gap:5px;color:#9AA0AD;font-size:12.5px;font-weight:850;
  text-decoration:none;margin:4px 0 2px}
.ob-explore:hover{color:#E7E9EE}
</style>"""
