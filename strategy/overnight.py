"""
选股小龙虾 - 隔夜套利策略
专攻尾盘选股，次日高开概率高
运行时间窗口：14:40–14:50（收盘前20分钟）
100分制评分 + K线修正 + 套牢盘修正
"""
import logging
from typing import List, Dict
from config.config import (
    OVERNIGHT_SCORE_CONDITIONS, OVERNIGHT_TOP_N,
    OVERNIGHT_KLINE_BONUS, OVERNIGHT_KLINE_PENALTY,
    OVERNIGHT_TRAPPED_BONUS, OVERNIGHT_TRAPPED_PENALTY,
)

logger = logging.getLogger(__name__)


def calc_overnight_score(stock: Dict) -> float:
    """
    计算隔夜评分（100分制）
    
    基础条件（满分100分）：
    - 涨幅3-5%: 30分
    - 振幅>5%: 25分
    - 量比>2: 20分
    - 换手率3-10%: 15分
    - 尾盘站稳: 10分（收盘价>均价）
    """
    score = 0.0
    
    pct_change = stock.get("pct_change", 0) or 0
    amplitude = stock.get("amplitude", 0) or 0
    volume_ratio = stock.get("volume_ratio", 0) or 0
    turnover_rate = stock.get("turnover_rate", 0) or 0
    close = stock.get("price", 0) or 0
    avg_price = stock.get("avg_price", 0) or 0
    
    # 涨幅3-5%: 30分
    if 3 <= pct_change <= 5:
        score += 30
    elif 0 < pct_change < 3:
        score += pct_change * 10  # 0-3%按比例
    elif 5 < pct_change <= 10:
        score += 30 - (pct_change - 5) * 2  # 超出5%略微扣分
    
    # 振幅>5%: 25分
    if amplitude > 5:
        score += 25
    elif amplitude > 0:
        score += amplitude * 5
    
    # 量比>2: 20分
    if volume_ratio > 2:
        score += 20
    elif volume_ratio > 0:
        score += volume_ratio * 10
    
    # 换手率3-10%: 15分
    if 3 <= turnover_rate <= 10:
        score += 15
    elif turnover_rate > 10:
        score += 15 - min((turnover_rate - 10) * 2, 5)  # 超过10%略微扣分
    elif turnover_rate > 0:
        score += turnover_rate * 5
    
    # 尾盘站稳: 10分（收盘价>均价）
    if close > avg_price:
        score += 10
    
    return min(score, 100.0)


def apply_overnight_modifications(stocks: List[Dict]) -> List[Dict]:
    """
    应用隔夜套利修正（±15分K线 + ±10分套牢盘）
    """
    for stock in stocks:
        # K线修正
        kline_dir = stock.get("kline_direction", "neutral")
        if kline_dir in ("strong_up", "up", "short_up"):
            stock["overnight_kline_modify"] = OVERNIGHT_KLINE_BONUS
        elif kline_dir in ("strong_down", "down"):
            stock["overnight_kline_modify"] = OVERNIGHT_KLINE_PENALTY
        else:
            stock["overnight_kline_modify"] = 0.0
        
        # 套牢盘修正
        trapped_level = stock.get("trapped_level", 0)
        if trapped_level in (1, 2):
            stock["overnight_trapped_modify"] = OVERNIGHT_TRAPPED_BONUS
        elif trapped_level in (4, 5):
            stock["overnight_trapped_modify"] = OVERNIGHT_TRAPPED_PENALTY
        else:
            stock["overnight_trapped_modify"] = 0.0
        
        # 计算总分
        base_score = stock.get("overnight_base_score", 0)
        total = base_score + stock["overnight_kline_modify"] + stock["overnight_trapped_modify"]
        stock["overnight_total_score"] = round(total, 2)
    
    # 重新排序
    stocks.sort(key=lambda x: x.get("overnight_total_score", 0), reverse=True)
    
    return stocks


def run_overnight_strategy(all_stocks: List[Dict], fetch_kline_func=None, 
                         fetch_trapped_func=None) -> List[Dict]:
    """
    执行隔夜套利策略
    
    Args:
        all_stocks: 全市场股票列表
        fetch_kline_func: K线获取函数（可选）
        fetch_trapped_func: 套牢盘获取函数（可选）
    
    Returns:
        TOP8隔夜推荐列表
    """
    logger.info("开始隔夜套利策略筛选")
    
    # Step1: 基础筛选条件（放宽条件）
    candidates = []
    for stock in all_stocks:
        pct_change = stock.get("pct_change", 0) or 0
        volume_ratio = stock.get("volume_ratio", 0) or 0
        turnover_rate = stock.get("turnover_rate", 0) or 0
        
        # 尾盘时间窗口：涨幅>0，量比>1.5，换手率>2%
        if pct_change > 0 and volume_ratio > 1.5 and turnover_rate > 2:
            candidates.append(stock)
    
    logger.info(f"Step1 基础筛选: {len(candidates)}只")
    
    # Step2: 计算基础评分
    for stock in candidates:
        stock["overnight_base_score"] = calc_overnight_score(stock)
    
    candidates.sort(key=lambda x: x["overnight_base_score"], reverse=True)
    top_100 = candidates[:100]
    
    logger.info(f"Step2 基础评分TOP100: {len(top_100)}只")
    
    # Step3: 获取K线数据，应用K线修正
    if fetch_kline_func:
        top_100 = _add_kline_direction(top_100, fetch_kline_func)
    
    # Step4: 获取套牢盘数据，应用套牢盘修正
    if fetch_trapped_func:
        top_100 = _add_trapped_level(top_100, fetch_trapped_func)
    
    # Step5: 应用完整修正
    top_100 = apply_overnight_modifications(top_100)
    
    # Step6: 取TOP8
    result = top_100[:OVERNIGHT_TOP_N]
    
    for i, stock in enumerate(result):
        stock["overnight_rank"] = i + 1
    
    logger.info(f"隔夜套利完成，推荐{len(result)}只")
    return result


def _add_kline_direction(stocks: List[Dict], fetch_func) -> List[Dict]:
    """添加K线方向"""
    for stock in stocks:
        klines = fetch_func(stock["code"])
        if klines:
            from strategy.kline_60min import analyze_60min_direction
            direction, _ = analyze_60min_direction(klines)
            stock["kline_direction"] = direction
        else:
            stock["kline_direction"] = "unknown"
    return stocks


def _add_trapped_level(stocks: List[Dict], fetch_func) -> List[Dict]:
    """添加套牢盘等级"""
    for stock in stocks:
        current_price = stock.get("price", 0)
        high_price = stock.get("high", 0)
        klines = fetch_func(stock["code"])
        if klines and current_price > 0:
            from strategy.locked_chips import calc_locked_chips
            result = calc_locked_chips(klines, current_price, high_price)
            stock["trapped_level"] = result["level"]
        else:
            stock["trapped_level"] = 0
    return stocks
