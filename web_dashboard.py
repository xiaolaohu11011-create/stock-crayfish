#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - Web Dashboard
本地可视化界面，浏览器打开 http://localhost:8080
启动命令: python web_dashboard.py
"""
import sys, os, json, subprocess, threading, urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.config import OUTPUT_DIR

# ── 前端页面 ──────────────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🦞 选股小龙虾</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,'Microsoft YaHei',sans-serif;background:#0f1117;color:#e1e4e8}
.header{background:linear-gradient(135deg,#1a1c2e,#2d1b4e);padding:16px 24px;border-bottom:1px solid #30363d;display:flex;align-items:center;gap:12px}
.header h1{font-size:20px;background:linear-gradient(90deg,#58a6ff,#bc8cff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.badge{margin-left:auto;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600}
.badge.ok{background:#238636;color:#fff}
.badge.warn{background:#9e6a03;color:#fff}
.tabs{display:flex;background:#161b22;border-bottom:1px solid #30363d}
.tab{padding:10px 20px;cursor:pointer;border-bottom:2px solid transparent;color:#8b949e;font-size:13px}
.tab.active{border-bottom-color:#58a6ff;color:#58a6ff}
.tab:hover{color:#c9d1d9}
.content{padding:20px}
.panel{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:16px}
.panel h2{font-size:14px;color:#58a6ff;margin-bottom:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:768px){.grid2{grid-template-columns:1fr}}
.metric{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:14px;text-align:center}
.metric .val{font-size:36px;font-weight:700;color:#58a6ff}
.metric .lbl{font-size:11px;color:#8b949e;margin-top:4px}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:6px 10px;font-size:11px;color:#8b949e;border-bottom:1px solid #21262d;background:#1c2128;position:sticky;top:0}
td{padding:6px 10px;font-size:12px;border-bottom:1px solid #21262d}
tr:hover{background:#1a1f2a}
.rank{display:inline-block;width:22px;height:22px;line-height:22px;text-align:center;border-radius:50%;font-size:11px;font-weight:700}
.r1{background:#f9d71c;color:#000}.r2{background:#c0c0c0;color:#000}.r3{background:#cd7f32;color:#fff}.rn{background:#21262d;color:#8b949e}
.bar{height:5px;border-radius:3px;background:#21262d;display:inline-block;width:60px;vertical-align:middle}
.bar-f{height:100%;border-radius:3px;background:linear-gradient(90deg,#58a6ff,#bc8cff)}
.btn{padding:6px 16px;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600}
.btn-g{background:#238636;color:#fff}.btn-g:hover{background:#2ea043}
.btn-r{background:#da3633;color:#fff}.btn-r:hover{background:#f85149}
.btn-s{background:#21262d;color:#c9d1d9;border:1px solid #30363d}.btn-s:hover{background:#30363d}
.btn:disabled{opacity:.5;cursor:not-allowed}
.inp{background:#0d1117;border:1px solid #30363d;color:#e1e4e8;padding:5px 10px;border-radius:6px;font-size:12px;width:180px}
.inp:focus{outline:none;border-color:#58a6ff}
.tag{display:inline-block;padding:1px 6px;border-radius:8px;font-size:10px;margin:1px}
.tg{background:#23863633;color:#3fb950;border:1px solid #238636}
.tr{background:#da363333;color:#f85149;border:1px solid #da3633}
.tb{background:#58a6ff33;color:#58a6ff;border:1px solid #58a6ff}
.empty{text-align:center;padding:40px;color:#8b949e}
#log{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:10px;max-height:250px;overflow-y:auto;font-family:monospace;font-size:11px;line-height:1.5;color:#8b949e}
.toast{position:fixed;top:16px;right:16px;padding:10px 16px;border-radius:8px;font-size:12px;z-index:999;display:none}
.toast.show{display:block;animation:si .3s ease}
.toast.ok{background:#238636;color:#fff}.toast.err{background:#da3633;color:#fff}
@keyframes si{from{transform:translateX(100%)}to{transform:translateX(0)}}
.detail-modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.7);z-index:998}
.detail-modal.show{display:flex;align-items:center;justify-content:center}
.detail-box{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px;max-width:500px;width:90%}
.detail-box h3{color:#58a6ff;margin-bottom:16px;font-size:16px}
.detail-row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #21262d;font-size:13px}
.detail-row .k{color:#8b949e}.detail-row .v{color:#e1e4e8;font-weight:600}
</style>
</head>
<body>
<div class="header">
  <span style="font-size:24px">🦞</span>
  <h1>选股小龙虾</h1>
  <span class="badge" id="badge">检测中</span>
</div>
<div class="tabs">
  <div class="tab active" onclick="sw('dashboard',this)">📊 仪表盘</div>
  <div class="tab" onclick="sw('stocks',this)">📈 选股结果</div>
  <div class="tab" onclick="sw('reports',this)">📄 历史报告</div>
  <div class="tab" onclick="sw('run',this)">▶️ 运行</div>
</div>
<div class="content">
  <div id="p-dashboard">
    <div class="grid2" style="margin-bottom:16px">
      <div class="panel"><h2>🧠 大盘评分</h2>
        <div style="text-align:center;padding:16px 0">
          <div id="ms" style="font-size:52px;font-weight:700;color:#58a6ff">--</div>
          <div id="ma" style="color:#8b949e;margin-top:6px">加载中</div>
          <div id="mt" style="font-size:11px;color:#484f58;margin-top:4px"></div>
        </div>
      </div>
      <div class="panel"><h2>📊 最近选股</h2><div id="ls" style="padding:8px 0">暂无数据</div></div>
    </div>
    <div class="panel"><h2>🧰 板块分布·外部工具</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px">
        <a href="https://www.sse.com.cn/market/dealingdata/overview/market/A/" target="_blank" style="text-decoration:none">
          <div style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:10px 12px;cursor:pointer">
            <div style="font-size:12px;color:#58a6ff;font-weight:600">📊 涨停关联</div>
            <div style="font-size:10px;color:#8b949e;margin-top:2px">同花顺涨停关联</div>
          </div>
        </a>
        <a href="http://hot.icfqs.com:7615/site/tdx-pc-find/page_yzfp.html" target="_blank" style="text-decoration:none">
          <div style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:10px 12px;cursor:pointer">
            <div style="font-size:12px;color:#58a6ff;font-weight:600">💰 游资追踪</div>
            <div style="font-size:10px;color:#8b949e;margin-top:2px">短线选股工具</div>
          </div>
        </a>
        <a href="https://www.xilimao.com/dxb/" target="_blank" style="text-decoration:none">
          <div style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:10px 12px;cursor:pointer">
            <div style="font-size:12px;color:#58a6ff;font-weight:600">⚡ 短线宝</div>
            <div style="font-size:10px;color:#8b949e;margin-top:2px">XiliMao短线宝</div>
          </div>
        </a>
        <a href="http://page.tdx.com.cn:7615/site/kggx/tk_yzlhb_yz.html" target="_blank" style="text-decoration:none">
          <div style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:10px 12px;cursor:pointer">
            <div style="font-size:12px;color:#58a6ff;font-weight:600">🐉 L2龙虎</div>
            <div style="font-size:10px;color:#8b949e;margin-top:2px">通达信龙虎榜</div>
          </div>
        </a>
        <a href="https://gc-sharelist.cf69.cn/stockPool2" target="_blank" style="text-decoration:none">
          <div style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:10px 12px;cursor:pointer">
            <div style="font-size:12px;color:#58a6ff;font-weight:600">📈 量化涨停</div>
            <div style="font-size:10px;color:#8b949e;margin-top:2px">量化涨停池</div>
          </div>
        </a>
      </div>
    </div>
  </div>
  <div id="p-stocks" style="display:none">
    <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center">
      <input class="inp" placeholder="🔍 搜索代码/名称" oninput="filt(this.value)">
      <button class="btn btn-s" onclick="loadS()">🔄</button>
    </div>
    <div class="panel" style="padding:0;overflow-x:auto;max-height:600px;overflow-y:auto">
      <table><thead><tr><th>#</th><th>代码</th><th>名称</th><th>总分</th><th>技术面</th><th>资金面</th><th>基本面</th><th>风控</th><th></th></tr></thead>
      <tbody id="stb"><tr><td colspan="9" class="empty">请先运行选股</td></tr></tbody></table>
    </div>
  </div>
  <div id="p-reports" style="display:none">
    <button class="btn btn-s" onclick="loadR()" style="margin-bottom:12px">🔄 刷新</button>
    <div class="panel" id="rl"><div class="empty">暂无报告</div></div>
  </div>
  <div id="p-run" style="display:none">
    <div class="panel"><h2>▶️ 运行选股</h2>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
        <label style="font-size:12px;color:#8b949e;display:flex;align-items:center;gap:4px"><input type="checkbox" id="ok" checked>K线</label>
        <label style="font-size:12px;color:#8b949e;display:flex;align-items:center;gap:4px"><input type="checkbox" id="ot" checked>套牢盘</label>
        <label style="font-size:12px;color:#8b949e;display:flex;align-items:center;gap:4px"><input type="checkbox" id="om">模拟</label>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-g" id="b1" onclick="run('selection')">🚀 综合选股</button>
        <button class="btn btn-g" id="b2" onclick="run('overnight')">🌙 隔夜套利</button>
        <button class="btn btn-r" id="b3" onclick="stop()" disabled>⏹ 停止</button>
      </div>
    </div>
    <div class="panel"><h2>📋 日志</h2><div id="log"><div>等待运行...</div></div></div>
  </div>
</div>
<div class="toast" id="toast"></div>
<div class="detail-modal" id="modal" onclick="if(event.target===this)this.classList.remove('show')">
  <div class="detail-box"><h3 id="dtitle">详情</h3><div id="dbody"></div>
    <div style="margin-top:16px;text-align:right"><button class="btn btn-s" onclick="document.getElementById('modal').classList.remove('show')">关闭</button></div>
  </div>
</div>
<script>
let S=[],pt=null;
function sw(t,el){document.querySelectorAll('.tab').forEach(e=>e.classList.remove('active'));el.classList.add('active');['dashboard','stocks','reports','run'].forEach(p=>document.getElementById('p-'+p).style.display='none');document.getElementById('p-'+t).style.display='block';if(t==='stocks')loadS();if(t==='reports')loadR();if(t==='dashboard')loadD();}
function toast(m,t='ok'){const e=document.getElementById('toast');e.textContent=m;e.className='toast '+t+' show';setTimeout(()=>e.classList.remove('show'),3000)}
async function loadD(){try{const r=await fetch('/api/dashboard');const d=await r.json();document.getElementById('ms').textContent=d.market_score??'--';document.getElementById('ma').textContent=d.market_advice||'';document.getElementById('mt').textContent=d.market_time||'';const b=document.getElementById('badge');if(d.has_result){b.textContent='有结果';b.className='badge ok'}else{b.textContent='待运行';b.className='badge warn'}if(d.stock_count>0)document.getElementById('ls').innerHTML=`<div style="font-size:14px">TOP20已选出 <span class="tag tb">${d.stock_count}只</span></div>`}catch(e){}}
async function loadS(){try{const r=await fetch('/api/latest_stocks');const d=await r.json();S=d.stocks||[];render(S)}catch(e){toast('加载失败','err')}}
function render(s){const t=document.getElementById('stb');if(!s.length){t.innerHTML='<tr><td colspan="9" class="empty">暂无数据</td></tr>';return}
t.innerHTML=s.map((x,i)=>`<tr><td><span class="rank ${i<3?'r'+(i+1):'rn'}">${i+1}</span></td><td><b>${x.code||''}</b></td><td>${x.name||''}</td><td><b style="color:#58a6ff">${(x.score_total||0).toFixed(1)}</b></td><td>${(x.score_technical||0).toFixed(1)}<div class="bar"><div class="bar-f" style="width:${Math.min((x.score_technical||0)/25*100,100)}%"></div></div></td><td>${(x.score_capital||0).toFixed(1)}<div class="bar"><div class="bar-f" style="width:${Math.min((x.score_capital||0)/35*100,100)}%"></div></div></td><td>${(x.score_fundamental||0).toFixed(1)}</td><td>${(x.score_risk||0).toFixed(1)}</td><td><button class="btn btn-s" style="padding:2px 8px;font-size:10px" onclick="detail(${i})">详情</button></td></tr>`).join('')}
function filt(k){const f=S.filter(x=>(x.code||'').includes(k)||(x.name||'').includes(k));render(f)}
function detail(i){const x=S[i];if(!x)return;document.getElementById('dtitle').textContent=x.code+' '+x.name;
document.getElementById('dbody').innerHTML=[
['价格',x.price?x.price.toFixed(2):'--'],['涨跌幅',(x.pct_change||0).toFixed(2)+'%'],['RPS',(x.rps||0).toFixed(1)],['量比',(x.volume_ratio||0).toFixed(2)],
['资金流',x.capital_flow],['市值',(x.market_cap/1e8)?.toFixed(1)+'亿'],['PE',x.pe],['换手率',(x.turnover_rate||0).toFixed(2)+'%'],
['技术面',(x.score_technical||0).toFixed(1)+'/25'],['资金面',(x.score_capital||0).toFixed(1)+'/35'],['基本面',(x.score_fundamental||0).toFixed(1)+'/25'],['风控',(x.score_risk||0).toFixed(1)+'/15'],
['总分',(x.score_total||0).toFixed(1)+'/100']
].map(r=>`<div class="detail-row"><span class="k">${r[0]}</span><span class="v">${r[1]}</span></div>`).join('');
document.getElementById('modal').classList.add('show')}
async function loadR(){try{const r=await fetch('/api/reports');const d=await r.json();const c=document.getElementById('rl');if(!d.reports?.length){c.innerHTML='<div class="empty">暂无报告</div>';return}
c.innerHTML=d.reports.map(r=>`<div style="display:flex;align-items:center;padding:8px;border-bottom:1px solid #21262d;gap:10px"><span style="font-size:16px">📄</span><div style="flex:1"><div style="font-size:13px">${r.name}</div><div style="font-size:11px;color:#8b949e">${r.size_kb} KB · ${r.mtime}</div></div><button class="btn btn-s" style="padding:2px 8px;font-size:10px" onclick="window.open('/api/report?path=${encodeURIComponent(r.path)}')">下载</button></div>`).join('')}catch(e){}}
async function run(mode){document.getElementById('b1').disabled=true;document.getElementById('b2').disabled=true;document.getElementById('b3').disabled=false;document.getElementById('log').innerHTML='';alog('启动 '+mode+'...','INFO');
try{const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,kline:document.getElementById('ok').checked,trapped:document.getElementById('ot').checked,mock:document.getElementById('om').checked})});
const d=await r.json();if(d.pid){alog('PID='+d.pid,'INFO');pollL()}else{alog('失败: '+(d.error||'未知'),'ERROR');rstBtn()}}catch(e){alog('请求失败: '+e.message,'ERROR');rstBtn()}}
function alog(m,l='INFO'){const a=document.getElementById('log');const d=document.createElement('div');d.className=l==='ERROR'?'log-ERROR':l==='WARNING'?'log-WARNING':'log-INFO';d.textContent='['+new Date().toLocaleTimeString()+'] '+m;a.appendChild(d);a.scrollTop=a.scrollHeight}
async function pollL(){try{const r=await fetch('/api/log');const d=await r.json();const a=document.getElementById('log');a.innerHTML='';(d.lines||[]).forEach(l=>{const d2=document.createElement('div');d2.className=l.includes('ERROR')?'log-ERROR':l.includes('WARNING')?'log-WARNING':'log-INFO';d2.textContent=l;a.appendChild(d2)});a.scrollTop=a.scrollHeight;if(d.running){pt=setTimeout(pollL,2000)}else{alog('运行结束','INFO');rstBtn();loadS();loadD()}}catch(e){if(pt)setTimeout(pollL,3000)}}
function rstBtn(){document.getElementById('b1').disabled=false;document.getElementById('b2').disabled=false;document.getElementById('b3').disabled=true}
loadD();setInterval(loadD,30000);
</script>
<style>.log-INFO{color:#58a6ff}.log-ERROR{color:#f85149}.log-WARNING{color:#d29922}</style>
</body>
</html>"""

# ── API 路由 ──────────────────────────────────────────────────

def _api_dashboard():
    """仪表盘数据"""
    result = {
        "market_score": None,
        "market_advice": "",
        "market_time": "",
        "has_result": False,
        "stock_count": 0,
    }
    try:
        from strategy.market_analysis import analyze_market
        m = analyze_market()
        result["market_score"] = m.get("total_score")
        result["market_advice"] = m.get("advice", "")
        result["market_time"] = m.get("timestamp", "")
    except Exception:
        pass
    # 检查最新结果文件
    json_dir = os.path.join(OUTPUT_DIR, "_json")
    if os.path.exists(json_dir):
        files = sorted(Path(json_dir).glob("*.json"), key=os.path.getmtime, reverse=True)
        if files:
            result["has_result"] = True
            try:
                with open(files[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
                result["stock_count"] = len(data.get("stocks", []))
            except Exception:
                pass
    return json.dumps(result, ensure_ascii=False)


def _api_latest_stocks():
    """最新选股结果"""
    json_dir = os.path.join(OUTPUT_DIR, "_json")
    if not os.path.exists(json_dir):
        return json.dumps({"stocks": []})
    files = sorted(Path(json_dir).glob("*.json"), key=os.path.getmtime, reverse=True)
    if not files:
        return json.dumps({"stocks": []})
    with open(files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
    return json.dumps({"stocks": data.get("stocks", [])}, ensure_ascii=False)


def _api_reports():
    """报告列表"""
    reports = []
    if os.path.exists(OUTPUT_DIR):
        for f in sorted(Path(OUTPUT_DIR).glob("*.docx"), key=os.path.getmtime, reverse=True):
            reports.append({
                "name": f.name,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    return json.dumps({"reports": reports}, ensure_ascii=False)


# 运行进程管理
_current_proc = None
_log_lines = []


def _api_run(body: str):
    """启动选股进程"""
    global _current_proc, _log_lines
    if _current_proc and _current_proc.poll() is None:
        return json.dumps({"error": "已有任务在运行"})
    try:
        params = json.loads(body) if body else {}
        mode = params.get("mode", "selection")
        kline = params.get("kline", True)
        trapped = params.get("trapped", True)
        mock = params.get("mock", False)

        cmd = [sys.executable, "main.py", "--mode=" + mode, "--no-push"]
        if kline:
            cmd.append("--kline")
        if trapped:
            cmd.append("--trapped")
        if mock:
            cmd.append("--mock")

        _log_lines = []
        _current_proc = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
        )
        def _reader():
            for line in iter(_current_proc.stdout.readline, ""):
                _log_lines.append(line.rstrip())
                if len(_log_lines) > 500:
                    _log_lines.pop(0)
            _current_proc.stdout.close()
        threading.Thread(target=_reader, daemon=True).start()
        return json.dumps({"pid": _current_proc.pid})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _api_log():
    """获取运行日志"""
    global _current_proc
    running = _current_proc is not None and _current_proc.poll() is None
    return json.dumps({"lines": _log_lines[-100:], "running": running})


# ── HTTP Handler ──────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send_html(HTML_PAGE)
        elif path == "/api/dashboard":
            self._send_json(_api_dashboard())
        elif path == "/api/latest_stocks":
            self._send_json(_api_latest_stocks())
        elif path == "/api/reports":
            self._send_json(_api_reports())
        elif path == "/api/log":
            self._send_json(_api_log())
        elif path == "/api/report":
            params = urllib.parse.parse_qs(parsed.query)
            fpath = params.get("path", [""])[0]
            self._send_file(fpath)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else ""
            self._send_json(_api_run(body))
        else:
            self.send_error(404)

    def _send_html(self, html: str):
        content = html.encode("utf-8")
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data: str):
        content = data.encode("utf-8")
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_file(self, fpath: str):
        try:
            if not fpath or not os.path.exists(fpath):
                self.send_error(404)
                return
            # 安全校验：只允许下载 output 目录下的文件
            real_output = os.path.realpath(OUTPUT_DIR)
            real_fpath = os.path.realpath(fpath)
            if not real_fpath.startswith(real_output):
                self.send_error(403)
                return
            with open(fpath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            import time
            ascii_name = f"report_{time.strftime('%Y%m%d_%H%M%S')}.docx"
            self.send_header("Content-Disposition", f'attachment; filename="{ascii_name}"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            try:
                self.send_error(500, str(e))
            except:
                pass


# ── 启动 ──────────────────────────────────────────────────────

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    import socket
    port = 8080
    for p in [8080, 8081, 8082, 8090]:
        try:
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", p))
            s.close()
            port = p
            break
        except OSError:
            continue

    server = ThreadedHTTPServer(("127.0.0.1", port), DashboardHandler)
    print("=" * 40)
    print("  [选股小龙虾] Dashboard")
    print("=" * 40)
    print(f"  浏览器打开: http://localhost:{port}")
    print("  按 Ctrl+C 停止")
    print("=" * 40)

    # 自动打开浏览器
    import webbrowser
    webbrowser.open(f"http://localhost:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
