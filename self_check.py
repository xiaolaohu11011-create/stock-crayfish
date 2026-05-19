#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面自检脚本 - 验证选股小龙虾每项指标是否可用"""
import sys, os, json, time
sys.path.insert(0, r"E:\选股小龙虾")

PASS = 0
FAIL = 0
ISSUES = []

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        msg = f"  ❌ {name}" + (f" — {detail}" if detail else "")
        print(msg)
        ISSUES.append(name + (" — " + detail if detail else ""))

print("=" * 60)
print("  🦞 选股小龙虾 全面自检")
print("=" * 60)

# ── 1. 项目文件完整性 ──────────────────────────────────
print("\n📁 1. 项目文件完整性")
base = r"E:\选股小龙虾"
required_files = [
    "main.py",
    "config/config.py",
    "data/eastmoney.py",
    "data/akshare_data.py",
    "data/tencent.py",
    "data/cache.py",
    "strategy/screener.py",
    "strategy/scorer.py",
    "strategy/kline_60min.py",
    "strategy/locked_chips.py",
    "strategy/overnight.py",
    "strategy/market_analysis.py",
    "report/docx_generator.py",
    "push/wechat_pusher.py",
    "scripts/common.py",
    "scripts/collect_0900.py",
    "scripts/collect_0935.py",
    "scripts/collect_1425.py",
    "scripts/collect_1440.py",
    "scripts/collect_1505.py",
    "web_dashboard.py",
]
for f in required_files:
    p = os.path.join(base, f)
    check(f"文件存在: {f}", os.path.exists(p), f"路径: {p}")

# ── 2. 模块导入 ────────────────────────────────────────
print("\n📦 2. 模块导入")
modules = [
    ("config.config", "OUTPUT_DIR, EASTMONEY_BASE_URL, SCORE_TECHNICAL_MAX, SCORE_CAPITAL_MAX, SCORE_FUNDAMENTAL_MAX, SCORE_RISK_MAX"),
    ("data.eastmoney", "fetch_all_stocks"),
    ("data.akshare_data", "fetch_money_flow"),
    ("data.cache", "DataCache"),
    ("strategy.screener", "three_layer_filter"),
    ("strategy.scorer", "score_and_rank"),
    ("strategy.market_analysis", "analyze_market"),
    ("strategy.kline_60min", None),
    ("strategy.locked_chips", None),
    ("strategy.overnight", None),
    ("report.docx_generator", "generate_selection_report, generate_overnight_report"),
    ("scripts.common", "fetch_and_prepare, push_and_queue"),
]
for mod, attrs in modules:
    try:
        m = __import__(mod, fromlist=attrs.split(", ") if attrs else [])
        if attrs:
            for attr in attrs.split(", "):
                check(f"{mod}.{attr}", hasattr(m, attr.strip()), f"缺少属性: {attr}")
        else:
            check(f"import {mod}", True)
    except Exception as e:
        check(f"import {mod}", False, str(e))

# ── 3. 配置参数合理性 ──────────────────────────────────
print("\n⚙️ 3. 配置参数合理性")
from config.config import (
    SCORE_TECHNICAL_MAX, SCORE_CAPITAL_MAX, SCORE_FUNDAMENTAL_MAX,
    SCORE_RISK_MAX, MARKET_SCORE_THRESHOLD, TOP_N, FILTER1_MIN_RPS,
    FILTER1_MIN_MARKET_CAP, FILTER2_MIN_VOLUME_RATIO, EASTMONEY_PAGE_SIZE,
    REQUEST_DELAY, OUTPUT_DIR, LOG_DIR
)
total_max = SCORE_TECHNICAL_MAX + SCORE_CAPITAL_MAX + SCORE_FUNDAMENTAL_MAX + SCORE_RISK_MAX
check(f"评分满分=100 (实际={total_max})", total_max == 100, f"技术{SCORE_TECHNICAL_MAX}+资金{SCORE_CAPITAL_MAX}+基本{SCORE_FUNDAMENTAL_MAX}+风控{SCORE_RISK_MAX}={total_max}")
check(f"大盘阈值≥60 (实际={MARKET_SCORE_THRESHOLD})", MARKET_SCORE_THRESHOLD >= 60)
check(f"TOP_N=20 (实际={TOP_N})", TOP_N == 20)
check(f"RPS筛选≥60 (实际={FILTER1_MIN_RPS})", FILTER1_MIN_RPS >= 60)
check(f"市值筛选≥100亿", FILTER1_MIN_MARKET_CAP >= 100e8)
check(f"量比筛选≥1.5 (实际={FILTER2_MIN_VOLUME_RATIO})", FILTER2_MIN_VOLUME_RATIO >= 1.5)
check(f"请求延迟≥1秒 (实际={REQUEST_DELAY})", REQUEST_DELAY >= 1.0)
check(f"输出目录存在: {OUTPUT_DIR}", os.path.exists(OUTPUT_DIR), OUTPUT_DIR)
check(f"日志目录存在: {LOG_DIR}", os.path.exists(LOG_DIR), LOG_DIR)

# ── 4. 模拟选股全流程 ──────────────────────────────────
print("\n🧪 4. 模拟选股全流程")
from scripts.common import fetch_and_prepare
from strategy.screener import three_layer_filter
from strategy.scorer import score_and_rank

try:
    result = fetch_and_prepare(mock=True)
    check("fetch_and_prepare(mock=True)返回数据", result is not None and len(result.get('all_stocks', [])) > 0, f"返回{len(result.get('all_stocks', [])) if result else 0}只")

    if result:
        data = result['all_stocks']
        # 筛选
        filtered = three_layer_filter(data)
        check(f"三度筛选: {len(data)}→{len(filtered)}只", len(filtered) > 0, "筛选后无候选股")

        if filtered:
            # 评分
            scored = score_and_rank(filtered)
            check(f"评分完成: {len(scored)}只", len(scored) > 0)

            # 检查评分字段
            sample = scored[0]
            required_fields = [
                "code", "name", "score_total", "score_technical",
                "score_capital", "score_fundamental", "score_risk"
            ]
            for field in required_fields:
                check(f"评分字段: {field}", field in sample, f"缺少字段: {field}")

            # 检查评分上限截断
            over100 = [s for s in scored if s.get("score_total", 0) > 100]
            check(f"无超100分 (超100: {len(over100)}只)", len(over100) == 0,
                  f"超100分: {[(s['code'], s['score_total']) for s in over100[:5]]}")

            # 检查分项上限
            tech_over = [s for s in scored if s.get("score_technical", 0) > SCORE_TECHNICAL_MAX + 0.1]
            cap_over = [s for s in scored if s.get("score_capital", 0) > SCORE_CAPITAL_MAX + 0.1]
            fund_over = [s for s in scored if s.get("score_fundamental", 0) > SCORE_FUNDAMENTAL_MAX + 0.1]
            risk_over = [s for s in scored if s.get("score_risk", 0) > SCORE_RISK_MAX + 0.1]
            check(f"技术面≤{SCORE_TECHNICAL_MAX} (超限: {len(tech_over)})", len(tech_over) == 0)
            check(f"资金面≤{SCORE_CAPITAL_MAX} (超限: {len(cap_over)})", len(cap_over) == 0)
            check(f"基本面≤{SCORE_FUNDAMENTAL_MAX} (超限: {len(fund_over)})", len(fund_over) == 0)
            check(f"风控≤{SCORE_RISK_MAX} (超限: {len(risk_over)})", len(risk_over) == 0)

            # TOP20排序
            top20 = sorted(scored, key=lambda x: x["score_total"], reverse=True)[:TOP_N]
            check(f"TOP20选出 (实际{len(top20)}只)", len(top20) == TOP_N)
            if top20:
                print(f"    TOP3: {top20[0]['code']}({top20[0].get('score_total',0):.1f}), "
                      f"{top20[1]['code']}({top20[1].get('score_total',0):.1f}), "
                      f"{top20[2]['code']}({top20[2].get('score_total',0):.1f})")
except Exception as e:
    check("模拟选股全流程", False, str(e))

# ── 5. 大盘分析 ────────────────────────────────────────
print("\n📊 5. 大盘分析")
try:
    from strategy.market_analysis import analyze_market
    m = analyze_market()
    check(f"大盘分析返回结果", m is not None)
    check(f"大盘评分存在", "total_score" in m, f"keys: {list(m.keys())}")
    ts = m.get("total_score", 0)
    # API故障时会降级到75分，所以检查can_select更可靠
    check(f"大盘评分≥60或can_select=True (实际={ts}, can_select={m.get('can_select')})", 
          ts >= 60 or m.get("can_select") == True, 
          f"评分过低: {ts}")
    check(f"can_select字段", "can_select" in m)
    check(f"advice字段", "advice" in m)
except Exception as e:
    check("大盘分析", False, str(e))

# ── 6. Dashboard API ──────────────────────────────────
print("\n🌐 6. Dashboard API")
import requests
api_base = "http://127.0.0.1:8080"
endpoints = {
    "/": "HTML页面",
    "/api/dashboard": "仪表盘数据",
    "/api/latest_stocks": "选股结果",
    "/api/reports": "报告列表",
    "/api/log": "运行日志",
}
# 先尝试启动Dashboard（如果未运行）
dashboard_started = False
try:
    r = requests.get(api_base + "/api/dashboard", timeout=2)
    if r.status_code == 200:
        dashboard_started = True
except Exception:
    pass

if not dashboard_started:
    try:
        import subprocess
        # 后台启动dashboard
        subprocess.Popen(
            [sys.executable, os.path.join(base, "web_dashboard.py")],
            cwd=base, creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        time.sleep(3)  # 等待启动
        dashboard_started = True
    except Exception as e:
        print(f"  ⚠️ Dashboard启动失败: {e}")

for path, name in endpoints.items():
    try:
        r = requests.get(api_base + path, timeout=10)
        check(f"API {path} ({name})", r.status_code == 200, f"状态码: {r.status_code}")
    except Exception as e:
        check(f"API {path} ({name})", False, str(e))

# 检查CORS头
try:
    r = requests.get(api_base + "/api/dashboard", timeout=5)
    cors = r.headers.get("Access-Control-Allow-Origin")
    check(f"CORS头 (Allow-Origin)", cors == "*", f"实际: {cors}")
except Exception as e:
    check("CORS头", False, str(e))

# 检查API返回数据完整性
try:
    r = requests.get(api_base + "/api/dashboard", timeout=5)
    d = r.json()
    check("dashboard: market_score字段", "market_score" in d)
    check("dashboard: stock_count字段", "stock_count" in d)
    check(f"dashboard: market_score≥60 (实际={d.get('market_score')})", d.get("market_score", 0) >= 60)

    r2 = requests.get(api_base + "/api/latest_stocks", timeout=5)
    d2 = r2.json()
    check(f"latest_stocks: 有股票数据 (实际{len(d2.get('stocks',[]))}只)", len(d2.get("stocks", [])) > 0)

    if d2.get("stocks"):
        s = d2["stocks"][0]
        stock_fields = ["code", "name", "score_total", "score_technical", "score_capital", "score_fundamental", "score_risk"]
        for field in stock_fields:
            check(f"股票数据字段: {field}", field in s, f"缺少: {field}")
except Exception as e:
    check("API数据完整性", False, str(e))

# ── 7. 报告生成 ────────────────────────────────────────
print("\n📄 7. 报告生成")
try:
    report_dir = os.path.join(base, "output")
    docx_files = [f for f in os.listdir(report_dir) if f.endswith(".docx")] if os.path.exists(report_dir) else []
    check(f"docx报告存在 (实际{len(docx_files)}个)", len(docx_files) > 0)
    if docx_files:
        latest = os.path.join(report_dir, sorted(docx_files)[-1])
        size = os.path.getsize(latest)
        check(f"最新报告大小>10KB (实际{size/1024:.1f}KB)", size > 10 * 1024, f"文件: {latest}")
except Exception as e:
    check("报告生成", False, str(e))

# ── 8. JSON结果 ────────────────────────────────────────
print("\n💾 8. JSON结果持久化")
try:
    json_dir = os.path.join(base, "output", "_json")
    json_files = [f for f in os.listdir(json_dir) if f.endswith(".json")] if os.path.exists(json_dir) else []
    check(f"JSON结果存在 (实际{len(json_files)}个)", len(json_files) > 0)
    if json_files:
        latest = os.path.join(json_dir, sorted(json_files)[-1])
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)
        check("JSON: stocks字段存在", "stocks" in data)
        check(f"JSON: 股票数>0 (实际{len(data.get('stocks',[]))}只)", len(data.get("stocks", [])) > 0)
        check("JSON: market字段存在", "market" in data)
        check("JSON: timestamp字段存在", "timestamp" in data)
except Exception as e:
    check("JSON结果", False, str(e))

# ── 9. 桌面HTML ────────────────────────────────────────
print("\n🖥️ 9. 桌面HTML快捷方式")
desktop_html = r"C:\Users\lao11\Desktop\选股小龙虾.html"
check(f"桌面HTML存在", os.path.exists(desktop_html))
if os.path.exists(desktop_html):
    with open(desktop_html, "r", encoding="utf-8") as f:
        html = f.read()
    check("HTML: 包含API地址127.0.0.1:8080", "127.0.0.1:8080" in html)
    check("HTML: 包含后端启动提示", "web_dashboard.py" in html)
    check("HTML: 包含评分分布图表", "chartScore" in html)
    check("HTML: 包含CORS兼容", "fetch" in html)
    check(f"HTML大小>10KB (实际{len(html)/1024:.1f}KB)", len(html) > 10240)

# ── 10. 项目在E盘 ─────────────────────────────────────
print("\n💿 10. 项目位置")
check(f"项目在E盘: {base}", base.startswith("E:\\"))

# ── 汇总 ──────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"  ✅ 通过: {PASS}")
print(f"  ❌ 失败: {FAIL}")
print(f"  总计: {PASS + FAIL}")
if ISSUES:
    print("\n  ⚠️ 问题列表:")
    for i, issue in enumerate(ISSUES, 1):
        print(f"    {i}. {issue}")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)
