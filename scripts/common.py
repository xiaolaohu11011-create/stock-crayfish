#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 脚本公共模块
抽取所有定时脚本的公共流程，减少重复代码
"""
import sys
import os
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Callable

# 绕过系统代理：东方财富API需直连，代理可能阻断push2his域名
# 仅在有代理环境下生效，无代理时不影响
_system_proxies = {}
try:
    import urllib.request as _urllib_req
    _system_proxies = _urllib_req.getproxies()
except Exception:
    pass

if _system_proxies:
    os.environ['NO_PROXY'] = 'push2his.eastmoney.com,push2.eastmoney.com'
    for _k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
        os.environ.pop(_k, None)

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.eastmoney import fetch_all_stocks, fetch_60min_kline
from data.akshare_data import fetch_money_flow, enrich_with_money_flow
from strategy.screener import three_layer_filter
from strategy.scorer import score_and_rank, apply_kline_modification, apply_trapped_modification
from strategy.kline_60min import batch_analyze_klines
from strategy.locked_chips import batch_analyze_locked_chips
from strategy.market_analysis import analyze_market
from report.docx_generator import generate_selection_report, generate_overnight_report
from push.wechat_pusher import push_report, push_overnight_report, save_to_queue
from push.feishu_pusher import push_report_feishu
from config.config import OUTPUT_DIR, LOG_DIR, TOP_N, PUSH_QUEUE_FILE, FEISHU_WEBHOOK_URL


def setup_script_logging(script_name: str) -> logging.Logger:
    """配置脚本日志"""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(
                os.path.join(LOG_DIR, f'{script_name}_{datetime.now().strftime("%Y%m%d")}.log'),
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(script_name)


def fetch_and_prepare(use_cache: bool = True, mock: bool = False) -> Optional[Dict]:
    """
    获取全市场数据并添加资金流信息
    
    Args:
        use_cache: 是否使用缓存
        mock: 非交易时段用模拟数据跑完整流程（测试用）
    
    Returns:
        {
            "all_stocks": [...],
            "market": {...},
        }
        失败返回None
    """
    logger = logging.getLogger(__name__)
    
    # 1. 大盘分析
    market = analyze_market()
    
    # 2. 获取全市场数据
    if mock:
        logger.info("模拟模式：生成模拟数据...")
        all_stocks = _generate_mock_stocks(2000)
    else:
        logger.info("获取东方财富全市场数据...")
        all_stocks = fetch_all_stocks(use_cache=use_cache)
    
    if len(all_stocks) < 100:
        logger.error(f"数据获取不足，仅{len(all_stocks)}只，跳过")
        return None
    
    # 3. 资金流数据
    if not mock:
        logger.info("获取资金流数据...")
        money_flow = fetch_money_flow()
        all_stocks = enrich_with_money_flow(all_stocks, money_flow)
    
    # 4. 混合架构：如果东方财富数据缺少关键字段（turnover_rate/volume_ratio），用腾讯接口补充
    # 第一层筛选后补充候选股（更快），如果数据缺失严重则补充全市场
    # 4. 混合架构：先快速补充全市场关键字段（只补前500只，避免太慢）
    _supplement_missing_fields(all_stocks, candidate_only=True)
    
    return {"all_stocks": all_stocks, "market": market}


def _supplement_missing_fields(stocks: List[Dict], candidate_only: bool = False) -> None:
    """
    补充缺失的关键字段（换手率、量比）
    当东方财富/新浪备用源数据不完整时，用腾讯接口补充
    
    Args:
        stocks: 股票列表
        candidate_only: 是否只补充候选股（筛选后的少量股票，更快）
    """
    logger = logging.getLogger(__name__)
    
    # 找出缺失 turnover_rate 或 volume_ratio 的股票
    missing = []
    for s in stocks:
        if not s.get("turnover_rate") or not s.get("volume_ratio"):
            missing.append(s["code"])
    
    if not missing:
        return
    
    # 如果只补充候选股，限制数量
    if candidate_only and len(missing) > 500:
        logger.info(f"有{len(missing)}只股票缺少字段，候选股模式只补充前500只...")
        missing = missing[:500]
    else:
        logger.info(f"有{len(missing)}只股票缺少换手率/量比，尝试用腾讯接口补充...")
    
    try:
        from data.tencent import fetch_realtime_batch
        
        # 分批补充（每批50只）
        batch_size = 50
        supplemented = 0
        stock_map = {s["code"]: s for s in stocks}
        
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i+batch_size]
            tencent_data = fetch_realtime_batch(batch)
            
            for code, data in tencent_data.items():
                if code in stock_map:
                    stock = stock_map[code]
                    if not stock.get("turnover_rate") and data.get("turnover_rate"):
                        stock["turnover_rate"] = data["turnover_rate"]
                        supplemented += 1
                    if not stock.get("volume_ratio") and data.get("volume_ratio"):
                        stock["volume_ratio"] = data["volume_ratio"]
                        supplemented += 1
            
            time.sleep(0.05 if candidate_only else 0.2)  # 候选股模式更短延迟
        
        logger.info(f"腾讯接口补充完成：{supplemented}个字段")
        
    except Exception as e:
        logger.warning(f"腾讯接口补充失败: {e}")


def run_selection_pipeline(
    all_stocks: List[Dict],
    market: Dict,
    kline: bool = True,
    trapped: bool = True,
    report_suffix: str = "",
) -> Optional[Dict]:
    """
    执行综合选股流程
    
    Args:
        all_stocks: 全市场股票列表
        market: 大盘分析结果
        kline: 是否启用K线分析
        trapped: 是否启用套牢盘分析
        report_suffix: 报告文件名后缀
    
    Returns:
        {
            "top20": [...],
            "report_path": str,
            "market": {...},
        }
        失败返回None
    """
    logger = logging.getLogger(__name__)
    
    if not market.get("can_select", True):
        logger.warning(f"大盘评分不足，禁止选股: {market.get('advice', '')}")
        return None
    
    # 三层筛选
    logger.info("执行三层梯度筛选...")
    candidates = three_layer_filter(all_stocks)
    
    if len(candidates) < 5:
        logger.warning(f"候选股不足，仅{len(candidates)}只")
        return None
    
    # 评分
    logger.info("执行100分综合评分...")
    scored = score_and_rank(candidates)
    
    # K线分析（只分析TOP50，控制耗时）
    if kline:
        logger.info("分析60分钟K线（TOP50）...")
        top50 = scored[:50]
        top50 = batch_analyze_klines(top50, fetch_60min_kline)
        # 将K线结果合并回主列表
        kline_map = {s["code"]: s for s in top50}
        for s in scored:
            if s["code"] in kline_map:
                s["kline_direction"] = kline_map[s["code"]].get("kline_direction", "unknown")
                s["kline_modify"] = kline_map[s["code"]].get("kline_modify", 0)
    scored = apply_kline_modification(scored)
    
    # 套牢盘分析
    if trapped:
        logger.info("分析套牢盘（TOP50）...")
        top50 = scored[:50]
        top50 = batch_analyze_locked_chips(top50, fetch_60min_kline)
        trapped_map = {s["code"]: s for s in top50}
        for s in scored:
            if s["code"] in trapped_map:
                ts = trapped_map[s["code"]]
                for key in ("trapped_level", "trapped_ratio", "avg_cost", "level_desc", "level_emoji", "score_modify", "level_no_recommend"):
                    if key in ts:
                        s[key] = ts[key]
    scored = apply_trapped_modification(scored)
    
    # TOP20
    top20 = scored[:TOP_N]
    for stock in top20:
        stock["market"] = market
    
    # 生成报告
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = f"_{report_suffix}" if report_suffix else ""
    report_path = os.path.join(OUTPUT_DIR, f"选股报告{suffix}_{ts}.docx")
    generate_selection_report(top20, report_path)
    
    return {
        "top20": top20,
        "report_path": report_path,
        "market": market,
    }


def run_overnight_pipeline(
    all_stocks: List[Dict],
    market: Dict,
) -> Optional[Dict]:
    """
    执行隔夜套利流程
    
    Args:
        all_stocks: 全市场股票列表
        market: 大盘分析结果
    
    Returns:
        {
            "top8": [...],
            "report_path": str,
        }
        失败返回None
    """
    from strategy.overnight import run_overnight_strategy
    
    logger = logging.getLogger(__name__)
    
    logger.info("执行隔夜套利策略...")
    result = run_overnight_strategy(
        all_stocks,
        fetch_kline_func=fetch_60min_kline,
        fetch_trapped_func=fetch_60min_kline
    )
    
    if not result:
        logger.warning("隔夜策略无结果")
        return None
    
    # 过滤严重套牢股
    filtered = [s for s in result if not s.get("level_no_recommend", False)]
    if not filtered:
        filtered = result[:3]  # 至少保留3只
    
    # 添加市场信息
    for stock in filtered:
        stock["market"] = market
    
    # 生成报告
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(OUTPUT_DIR, f"隔夜套利_{ts}.docx")
    generate_overnight_report(filtered, report_path)
    
    return {
        "top8": filtered,
        "report_path": report_path,
    }


def push_and_queue(
    report_type: str,
    report_path: str,
    market: Dict,
    top_stocks: list = None,
) -> None:
    """
    推送报告并入队兜底
    
    Args:
        report_type: "selection" 或 "overnight"
        report_path: 报告路径
        market: 大盘分析结果
        top_stocks: 股票列表（用于摘要推送）
    """
    market_score = market.get("total_score", 0)
    
    if report_type == "selection":
        push_report(report_path, market_score, top_stocks)
        # 飞书推送（GitHub Actions 云端走这里）
        if FEISHU_WEBHOOK_URL:
            push_report_feishu(top_stocks or [], report_path)
    elif report_type == "overnight":
        push_overnight_report(report_path, top_stocks)
        if FEISHU_WEBHOOK_URL:
            push_report_feishu(top_stocks or [], report_path)
    
    save_to_queue({
        "type": report_type,
        "report_path": report_path,
        "timestamp": datetime.now().isoformat(),
        "market_score": market_score,
    }, PUSH_QUEUE_FILE)


def log_elapsed(start_time: datetime, task_name: str, result_count: int = 0) -> None:
    """记录耗时"""
    logger = logging.getLogger(__name__)
    elapsed = (datetime.now() - start_time).total_seconds()
    elapsed_min = elapsed / 60
    logger.info(f"{task_name}完成！推荐{result_count}只，耗时{elapsed:.1f}秒({elapsed_min:.1f}分钟)")
    
    if elapsed > 600:  # 10分钟
        logger.warning("执行超时！可能影响推送时效")


def _generate_mock_stocks(count: int = 2000) -> List[Dict]:
    """生成模拟股票数据（非交易时段测试用）"""
    import random
    random.seed(42)
    
    stocks = []
    for i in range(count):
        market_cap = 10 ** random.uniform(8.5, 11.5)
        pct_change = random.gauss(0.1, 2.5)
        turnover_rate = min(random.lognormvariate(1.0, 0.8), 30)
        volume_ratio = min(random.lognormvariate(0.3, 0.6), 8)
        price = random.uniform(3, 200)
        capital_flow = max(0, pct_change) * volume_ratio / 50 if pct_change > 0 else 0
        amount = market_cap * turnover_rate / 100 * 0.01
        amplitude = abs(random.gauss(3, 2))
        avg_price = price * random.uniform(0.97, 1.03)
        
        # PE
        pe_ranges = [(5,15),(15,25),(25,40),(40,60),(60,100),(0,0)]
        pe_range = pe_ranges[random.randint(0, 5)]
        pe = random.uniform(pe_range[0], pe_range[1]) if pe_range[1] > pe_range[0] else random.choice([0, -5])
        
        stocks.append({
            "code": f"{i:06d}", "name": f"模拟{i}",
            "price": price,
            "pct_change": pct_change,
            "turnover_rate": turnover_rate,
            "volume_ratio": volume_ratio,
            "pe": pe,
            "market_cap": market_cap,
            "capital_flow": capital_flow,
            "amount": amount,
            "amplitude": amplitude,
            "avg_price": avg_price,
            "high": price * (1 + amplitude / 100),
            "change": random.uniform(-1, 2),
            "volume": random.uniform(1e6, 1e9),
            "open": random.uniform(3, 200),
        })
    
    # 计算RPS
    sorted_idx = sorted(range(len(stocks)), key=lambda i: stocks[i]["pct_change"], reverse=True)
    total = len(sorted_idx)
    for rank, idx in enumerate(sorted_idx):
        stocks[idx]["rps"] = round((total - rank) / total * 100, 1)
    
    return stocks
