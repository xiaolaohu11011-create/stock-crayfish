"""
选股小龙虾 - 三层梯度筛选引擎
从全A股5181只出发，每层设置严格量化条件逐步收窄范围
"""
import logging
from typing import List, Dict
from config.config import (
    FILTER1_MIN_MARKET_CAP, FILTER1_MIN_TURNOVER_RATE, FILTER1_MIN_RPS,
    FILTER1_MIN_CONDITIONS,
    FILTER2_MIN_VOLUME_RATIO, FILTER2_MIN_PCT_CHANGE, FILTER2_MIN_CONDITIONS,
    FILTER3_CAPITAL_FLOW_POSITIVE,
)

logger = logging.getLogger(__name__)


def filter_layer1(stocks: List[Dict]) -> List[Dict]:
    """
    第一梯度：基础筛选
    目标：从全市场筛选出20-30只候选股（实际约1300+只，条件偏宽松）
    
    筛选条件（满足至少2项）：
    1. 总市值 > 100亿（排除壳股、小盘垃圾股）
    2. 换手率 > 3%（市场交易活跃）
    3. 涨幅为正且RPS > 60（趋势向上）
    
    RPS = 涨幅排名百分位（简化：用涨跌幅代替）
    """
    result = []
    
    for stock in stocks:
        conditions_met = 0
        
        # 条件1：总市值 > 100亿
        market_cap = stock.get("market_cap", 0) or 0
        if market_cap > FILTER1_MIN_MARKET_CAP:
            conditions_met += 1
        
        # 条件2：换手率 > 3%
        turnover_rate = stock.get("turnover_rate", 0) or 0
        if turnover_rate > FILTER1_MIN_TURNOVER_RATE:
            conditions_met += 1
        
        # 条件3：涨幅为正且RPS > 60（趋势向上）
        pct_change = stock.get("pct_change", 0) or 0
        rps = stock.get("rps", 0) or 0
        if pct_change > 0 and rps > FILTER1_MIN_RPS:
            conditions_met += 1
        
        if conditions_met >= FILTER1_MIN_CONDITIONS:
            stock["_filter1_conditions"] = conditions_met
            result.append(stock)
    
    logger.info(f"第一梯度筛选：{len(stocks)}只 → {len(result)}只")
    return result


def filter_layer2(stocks: List[Dict]) -> List[Dict]:
    """
    第二梯度：量价筛选
    目标：从第一梯度中筛选出10-15只
    
    筛选条件（满足至少1项）：
    1. 量比 > 1.5（成交量放大，资金关注）
    2. 涨幅 > 2%（价格强势）
    """
    result = []
    
    for stock in stocks:
        conditions_met = 0
        
        # 条件1：量比 > 1.5
        volume_ratio = stock.get("volume_ratio", 0) or 0
        if volume_ratio > FILTER2_MIN_VOLUME_RATIO:
            conditions_met += 1
        
        # 条件2：涨幅 > 2%
        pct_change = stock.get("pct_change", 0) or 0
        if pct_change > FILTER2_MIN_PCT_CHANGE:
            conditions_met += 1
        
        if conditions_met >= FILTER2_MIN_CONDITIONS:
            stock["_filter2_conditions"] = conditions_met
            result.append(stock)
    
    logger.info(f"第二梯度筛选：{len(stocks)}只 → {len(result)}只")
    return result


def filter_layer3(stocks: List[Dict]) -> List[Dict]:
    """
    第三梯度：资金筛选
    目标：从第二梯度中筛选出20-25只
    
    筛选条件：
    - 主力资金流入 > 0（资金净流入为正）
    """
    result = []
    
    for stock in stocks:
        capital_flow = stock.get("capital_flow", 0) or 0
        
        if capital_flow > 0:
            result.append(stock)
    
    logger.info(f"第三梯度筛选：{len(stocks)}只 → {len(result)}只")
    return result


def three_layer_filter(all_stocks: List[Dict]) -> List[Dict]:
    """
    执行完整三层梯度筛选
    
    Args:
        all_stocks: 全市场股票列表
    
    返回: 通过三层筛选的候选股列表
    """
    logger.info(f"开始三层梯度筛选，初始股票数：{len(all_stocks)}")
    
    # 预计算RPS排名（基于涨跌幅百分位）
    _calc_rps_for_all(all_stocks)
    
    # 第一梯度
    step1 = filter_layer1(all_stocks)
    
    # 第二梯度
    step2 = filter_layer2(step1)
    
    # 第三梯度
    step3 = filter_layer3(step2)
    
    logger.info(f"三层梯度筛选完成，候选股数：{len(step3)}")
    return step3


def _calc_rps_for_all(stocks: List[Dict]) -> None:
    """
    计算全市场RPS（Relative Price Strength）
    基于当日涨跌幅在全市场的排名百分位
    
    RPS含义：涨跌幅排名超过全市场X%的股票
    - RPS=90 表示涨幅排名超过90%的股票（即前10%）
    - RPS=50 表示排名超过50%的股票（即中位数）
    
    直接修改stock字典，添加 rps 字段
    """
    # 收集所有有效涨跌幅
    valid_stocks = [(i, s.get("pct_change", 0) or 0) for i, s in enumerate(stocks)]
    
    # 按涨跌幅降序排序
    sorted_stocks = sorted(valid_stocks, key=lambda x: x[1], reverse=True)
    
    total = len(sorted_stocks)
    if total == 0:
        return
    
    # 计算排名百分位
    for rank, (idx, pct) in enumerate(sorted_stocks):
        # RPS = (总数量 - 排名) / 总数量 * 100
        rps = (total - rank) / total * 100
        stocks[idx]["rps"] = round(rps, 1)
    
    rps_above_90 = sum(1 for s in stocks if s.get("rps", 0) >= 90)
    logger.info(f"RPS计算完成，RPS>=90共{rps_above_90}只")
