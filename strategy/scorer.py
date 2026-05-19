"""
选股小龙虾 - 100分综合评分体系
总分 = 资金面(35分) + 基本面(25分) + 技术面(25分) + 风控(15分)
"""
import logging
from typing import List, Dict
from config.config import (
    SCORE_CAPITAL_MAX, SCORE_FUNDAMENTAL_MAX, SCORE_TECHNICAL_MAX, SCORE_RISK_MAX,
    PE_THRESHOLDS,
    RISK_PENALTY_PRICE_ABOVE, RISK_PENALTY_PRICE,
    RISK_PENALTY_MARKET_CAP_ABOVE, RISK_PENALTY_MARKET_CAP,
)

logger = logging.getLogger(__name__)


def calc_capital_score(stock: Dict) -> float:
    """
    资金面评分（35分）
    公式：资金流量估算值 × 10 + 10，总分不超过35分
    
    说明：
    - 严格按需求文档公式计算
    - capital_flow 在估算模式下为 0~2 范围，公式结果 10~30分
    - capital_flow 为akshare真实金额时可能远超35分，按上限截断
    - 截断意味着资金流入已到极致，需靠其他维度拉开差距
    """
    capital_flow = stock.get("capital_flow", 0) or 0
    
    score = capital_flow * 10 + 10
    
    # 按上限截断
    return round(min(max(score, 0), SCORE_CAPITAL_MAX), 2)


def calc_fundamental_score(stock: Dict) -> float:
    """
    基本面评分（25分）
    PE维度：
    - PE < 15:  25分
    - PE < 25:  20分
    - PE < 40:  15分
    - PE < 60:  10分
    - 其他:      5分
    """
    pe = stock.get("pe", 0) or 0
    
    # 负PE或0PE给5分
    if pe <= 0:
        return 5.0
    
    # 按阈值匹配
    for threshold in sorted(PE_THRESHOLDS.keys()):
        if pe < threshold:
            return float(PE_THRESHOLDS[threshold])
    
    return 5.0


def calc_technical_score(stock: Dict) -> float:
    """
    技术面评分（25分）
    公式：RPS / 4 + 量比 × 5，总分不超过25分
    
    说明：
    - 严格按需求文档公式计算
    - 当RPS高+量比大时可能超出25分，按上限截断
    - 截断意味着强趋势+大成交量在技术面维度已到顶，
      需靠其他维度（资金面、基本面）拉开差距
    """
    rps = stock.get("rps", 0) or 0
    volume_ratio = stock.get("volume_ratio", 0) or 0
    
    score = rps / 4 + volume_ratio * 5
    
    # 按上限截断
    return round(min(max(score, 0), SCORE_TECHNICAL_MAX), 2)


def calc_risk_score(stock: Dict) -> float:
    """
    风控评分（15分）
    扣分项：
    - 股价 > 100: 扣5分
    - 市值 > 500亿: 扣3分
    """
    score = SCORE_RISK_MAX
    
    price = stock.get("price", 0) or 0
    if price > RISK_PENALTY_PRICE_ABOVE:
        score += RISK_PENALTY_PRICE  # -5分
    
    market_cap = stock.get("market_cap", 0) or 0
    if market_cap > RISK_PENALTY_MARKET_CAP_ABOVE:
        score += RISK_PENALTY_MARKET_CAP  # -3分
    
    return max(score, 0)


def calc_total_score(stock: Dict) -> Dict:
    """
    计算股票综合评分
    
    Args:
        stock: 股票数据字典
    
    Returns:
        包含各维度评分和总分的股票字典
    """
    capital_score = calc_capital_score(stock)
    fundamental_score = calc_fundamental_score(stock)
    technical_score = calc_technical_score(stock)
    risk_score = calc_risk_score(stock)
    
    total = capital_score + fundamental_score + technical_score + risk_score
    
    stock["score_capital"] = round(capital_score, 2)
    stock["score_fundamental"] = round(fundamental_score, 2)
    stock["score_technical"] = round(technical_score, 2)
    stock["score_risk"] = round(risk_score, 2)
    stock["score_total"] = round(total, 2)
    
    return stock


def score_and_rank(candidates: List[Dict]) -> List[Dict]:
    """
    对候选股票进行评分并排序
    
    Args:
        candidates: 通过三层筛选的候选股列表
    
    Returns:
        按总分降序排列的股票列表
    """
    scored = []
    for stock in candidates:
        scored.append(calc_total_score(stock))
    
    # 按总分降序
    scored.sort(key=lambda x: x["score_total"], reverse=True)
    
    # 标记排名
    for i, stock in enumerate(scored):
        stock["rank"] = i + 1
    
    logger.info(f"评分完成，共{len(scored)}只候选股")
    return scored


def apply_kline_modification(stocks: List[Dict], kline_modifier: float = 5.0) -> List[Dict]:
    """
    应用K线方向修正（±5分）
    
    Args:
        stocks: 已评分的股票列表
        kline_modifier: 修正分数，默认±5分
        kline_direction: "up"/"down"/"neutral" 来自K线分析
    
    返回: 应用修正后的股票列表
    """
    for stock in stocks:
        kline_dir = stock.get("kline_direction", "neutral")
        
        if kline_dir in ("up", "strong_up"):
            stock["score_total"] += kline_modifier
        elif kline_dir in ("down", "strong_down"):
            stock["score_total"] -= kline_modifier
        
        stock["score_total"] = round(stock["score_total"], 2)
    
    # 重新排序
    stocks.sort(key=lambda x: x["score_total"], reverse=True)
    for i, stock in enumerate(stocks):
        stock["rank"] = i + 1
    
    return stocks


def apply_trapped_modification(stocks: List[Dict]) -> List[Dict]:
    """
    应用套牢盘修正（±3~5分）
    
    Args:
        stocks: 已评分的股票列表
    
    返回: 应用修正后的股票列表
    """
    for stock in stocks:
        trapped_level = stock.get("trapped_level", 0)
        
        if trapped_level == 1:
            stock["score_total"] += 3  # 1级+3分
        elif trapped_level == 4:
            stock["score_total"] -= 5  # 4级-5分
        
        stock["score_total"] = round(stock["score_total"], 2)
    
    # 重新排序
    stocks.sort(key=lambda x: x["score_total"], reverse=True)
    for i, stock in enumerate(stocks):
        stock["rank"] = i + 1
    
    return stocks
