"""
SIM Liquid Ink 배경 — WebGL 셰이더 캔버스를 부모 문서에 고정 주입.

원본: ~/Downloads/SIM Liquid Background (standalone).html 의 self-contained 셰이더만 추출.
- Streamlit 마크다운은 <script>를 실행 안 하므로 components.html 부트스트랩으로 부모 DOM에 주입.
- 로그인 화면('/' 이면서 인증 셸 .sv-shell 부재)에서만 표시(body.sim-liquid-on 토글).
  인증 후 전체현황/그 외 페이지에선 숨김 + 앱 배경 원복.
- pointer-events:none → 클릭/스크롤 막지 않음. 마우스 따라 잉크가 번지고 클릭 시 파문.
"""
from __future__ import annotations

import streamlit.components.v1 as components

_VERT = r"""attribute vec2 a_pos;
void main(){ gl_Position = vec4(a_pos, 0.0, 1.0); }"""

_FRAG = r"""precision highp float;
uniform vec2  u_res;
uniform float u_time;
uniform vec2  u_mouse;
uniform vec3  u_trail[24];
uniform vec3  u_clicks[8];

float hash21(vec2 p){
  p = fract(p * vec2(123.34, 345.45));
  p += dot(p, p + 34.345);
  return fract(p.x * p.y);
}
float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f*f*(3.0-2.0*f);
  float a = hash21(i);
  float b = hash21(i+vec2(1.0,0.0));
  float c = hash21(i+vec2(0.0,1.0));
  float d = hash21(i+vec2(1.0,1.0));
  return mix(mix(a,b,u.x), mix(c,d,u.x), u.y);
}
float fbm(vec2 p){
  float v=0.0, a=0.5;
  mat2 m = mat2(1.6,1.2,-1.2,1.6);
  for(int i=0;i<5;i++){ v += a*vnoise(p); p = m*p; a*=0.5; }
  return v;
}

void main(){
  vec2 uv = gl_FragCoord.xy / u_res;
  float asp = u_res.x / u_res.y;
  vec2 p  = vec2(uv.x*asp, uv.y);
  vec2 mp = vec2(u_mouse.x*asp, u_mouse.y);

  vec2 warp = vec2(0.0);
  for(int i=0;i<24;i++){
    vec3 tr = u_trail[i];
    if(tr.z <= 0.0) continue;
    vec2 tp = vec2(tr.x*asp, tr.y);
    vec2 d  = p - tp;
    float dist = length(d);
    float infl = tr.z * exp(-dist*5.5);
    warp += vec2(-d.y, d.x) * infl * 1.05;
    warp += normalize(d + 1e-4) * infl * 0.22;
  }

  float t = u_time * 0.032;
  vec2 flow = vec2(0.16, 0.05) * u_time * 0.02;
  vec2 q = p*1.85 + warp + flow;
  vec2 a1 = vec2(fbm(q + t), fbm(q + vec2(5.2,1.3) - t));
  vec2 a2 = vec2(fbm(q + 2.6*a1 + vec2(1.7,9.2) + t*0.7),
                 fbm(q + 2.6*a1 + vec2(8.3,2.8) - t*0.5));
  float f = fbm(q + 3.0*a2 + t*1.7);

  float ripple = 0.0;
  for(int i=0;i<8;i++){
    vec3 c = u_clicks[i];
    if(c.z < 0.0) continue;
    vec2 cp = vec2(c.x*asp, c.y);
    float dd = length(p - cp);
    float r  = c.z*0.42;
    ripple += exp(-pow((dd-r)*9.0,2.0)) * exp(-c.z*1.9);
  }

  float v = pow(clamp((f - 0.55)*1.85, 0.0, 1.0), 1.35);
  vec3 bg    = vec3(0.008,0.008,0.012);
  vec3 amber = vec3(0.44,0.27,0.07);
  vec3 gold  = vec3(0.97,0.69,0.22);
  vec3 col = mix(bg, amber, smoothstep(0.13, 0.56, v));
  col = mix(col, gold, smoothstep(0.44, 0.92, v));
  col += gold * ripple * 0.18;
  col += gold * exp(-length(p-mp)*5.0) * 0.03;
  gl_FragColor = vec4(col, 1.0);
}"""

# 부모 문서 컨텍스트에서 실행될 코드(window/document = 부모). __VERT__/__FRAG__ 치환.
_PARENT_CODE = r"""
(function(){
  if (window.__simInkReady) return;
  window.__simInkReady = true;
  var VERT = `__VERT__`;
  var FRAG = `__FRAG__`;

  // 1) 고정 캔버스(맨 뒤)
  var canvas = document.createElement('canvas');
  canvas.id = 'sim-ink-bg';
  canvas.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;display:none;z-index:-1;pointer-events:none';
  document.body.insertBefore(canvas, document.body.firstChild);

  // 2) 스코핑 스타일 — 홈/로그인('/')에서만 앱 배경 투명 + 캔버스 표시
  var stl = document.createElement('style');
  stl.textContent =
    "body.sim-liquid-on #sim-ink-bg{display:block!important}" +
    "body.sim-liquid-on,body.sim-liquid-on .stApp,body.sim-liquid-on [data-testid=stApp]," +
    "body.sim-liquid-on [data-testid=stAppViewContainer],body.sim-liquid-on [data-testid=stHeader]," +
    "body.sim-liquid-on [data-testid=stMain],body.sim-liquid-on section.main,body.sim-liquid-on .main," +
    "body.sim-liquid-on [data-testid=stMainBlockContainer],body.sim-liquid-on .block-container," +
    "body.sim-liquid-on [data-testid=stAppViewBlockContainer]," +
    "body.sim-liquid-on .sim-login-page{background:transparent!important;background-color:transparent!important}";
  document.head.appendChild(stl);

  // 3) 경로 감시 → 로그인 화면('/')에서만 켜기(클라이언트 네비게이션 대응).
  //    인증 후 앱은 헤더 셸(.sv-shell)을 렌더하므로, 같은 '/'라도 전체현황 등
  //    로그인 후 페이지에선 배경을 끈다(움직이는 잉크 불필요).
  function scope(){
    var p = location.pathname;
    var atRoot = (p === '/' || p === '' || p === '/home' || p.slice(-6) === '/home');
    var authedApp = !!document.querySelector('.sv-shell');
    document.body.classList.toggle('sim-liquid-on', atRoot && !authedApp);
  }
  scope();
  setInterval(scope, 400);

  // 4) WebGL 렌더러(원본 standalone 셰이더 이식)
  var TRAIL_N=24, CLICK_N=8, TRAIL_LIFE=3.6, CLICK_LIFE=5.0;
  var gl = canvas.getContext('webgl', {antialias:false, alpha:false, premultipliedAlpha:false, preserveDrawingBuffer:true});
  if(!gl){ return; }
  function comp(type, src){ var s=gl.createShader(type); gl.shaderSource(s,src); gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(s)); return s; }
  var prog=gl.createProgram();
  gl.attachShader(prog, comp(gl.VERTEX_SHADER, VERT));
  gl.attachShader(prog, comp(gl.FRAGMENT_SHADER, FRAG));
  gl.bindAttribLocation(prog,0,'a_pos');
  gl.linkProgram(prog); gl.useProgram(prog);
  var U={}; ['u_res','u_time','u_mouse','u_trail','u_clicks'].forEach(function(n){ U[n]=gl.getUniformLocation(prog,n); });
  var b=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,b);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0,2,gl.FLOAT,false,0,0);
  var target={x:0.5,y:0.6}, smooth={x:0.5,y:0.6};
  var trail=[], clicks=[];
  var trailBuf=new Float32Array(TRAIL_N*3), clickBuf=new Float32Array(CLICK_N*3);
  function resize(){ var dpr=Math.min(window.devicePixelRatio||1,1.5);
    var w=Math.max(1,Math.floor(window.innerWidth*dpr)), h=Math.max(1,Math.floor(window.innerHeight*dpr));
    if(canvas.width!==w||canvas.height!==h){ canvas.width=w; canvas.height=h; } gl.viewport(0,0,canvas.width,canvas.height); }
  window.addEventListener('resize', resize); resize();
  window.addEventListener('pointermove', function(e){ target.x=e.clientX/window.innerWidth; target.y=1.0-e.clientY/window.innerHeight; }, {passive:true});
  window.addEventListener('pointerdown', function(e){ clicks.unshift({x:e.clientX/window.innerWidth, y:1.0-e.clientY/window.innerHeight, born:performance.now()/1000}); if(clicks.length>CLICK_N) clicks.length=CLICK_N; });
  var startT=performance.now();
  function frame(){
    // 숨김 상태(로그인 후 페이지 등)에선 GL 연산 생략 — rAF만 유지해 복귀 시 즉시 재개
    if(!document.body.classList.contains('sim-liquid-on')){ requestAnimationFrame(frame); return; }
    var now=performance.now()/1000, t=(performance.now()-startT)/1000;
    smooth.x+=(target.x-smooth.x)*0.04; smooth.y+=(target.y-smooth.y)*0.04;
    var last=trail[0];
    if(!last || Math.hypot(smooth.x-last.x, smooth.y-last.y)>0.006){ trail.unshift({x:smooth.x,y:smooth.y,born:now}); if(trail.length>TRAIL_N) trail.length=TRAIL_N; }
    for(var i=0;i<TRAIL_N;i++){ var p=trail[i];
      if(p){ var age=1.0-(now-p.born)/TRAIL_LIFE; trailBuf[i*3]=p.x; trailBuf[i*3+1]=p.y; trailBuf[i*3+2]=age>0?age*age:0; }
      else { trailBuf[i*3]=0; trailBuf[i*3+1]=0; trailBuf[i*3+2]=0; } }
    for(var j=0;j<CLICK_N;j++){ var c=clicks[j];
      if(c){ var el=now-c.born; if(el<CLICK_LIFE){ clickBuf[j*3]=c.x; clickBuf[j*3+1]=c.y; clickBuf[j*3+2]=el; }
        else { clickBuf[j*3]=0; clickBuf[j*3+1]=0; clickBuf[j*3+2]=-1; } }
      else { clickBuf[j*3]=0; clickBuf[j*3+1]=0; clickBuf[j*3+2]=-1; } }
    gl.uniform2f(U.u_res, canvas.width, canvas.height);
    gl.uniform1f(U.u_time, t);
    gl.uniform2f(U.u_mouse, smooth.x, smooth.y);
    gl.uniform3fv(U.u_trail, trailBuf);
    gl.uniform3fv(U.u_clicks, clickBuf);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
"""


def liquid_background() -> None:
    """홈·로그인 화면에서 호출 — Liquid Ink WebGL 배경을 부모 문서에 1회 주입(이후 경로 감시로 자동 표시/숨김)."""
    code = _PARENT_CODE.replace("__VERT__", _VERT).replace("__FRAG__", _FRAG)
    boot = (
        '<script type="text/plain" id="sim-ink-src">' + code + "</script>"
        "<script>(function(){try{"
        "var pdoc=window.parent.document, pwin=window.parent;"
        "if(pwin.__simInkInjected) return; pwin.__simInkInjected=true;"
        "var c=document.getElementById('sim-ink-src').textContent;"
        "var s=pdoc.createElement('script'); s.textContent=c; pdoc.body.appendChild(s);"
        "}catch(e){console.error('liquid-bg',e);}})();</script>"
    )
    components.html(boot, height=0, width=0)
