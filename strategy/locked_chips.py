"""
选股小龙虾 - 套牢盘分析
计算60分钟K线成交量加权平均成本，与现价对比判断筹码分布
五级判定：1级✨无/极少 → 5级⛔严重套牢
"""
import logging
from typing import List, Dict, Tuple
from config.config import TRAPPED_LEVELS

logger = logging.getLogger(__name__)


def calc_locked_chips(klines: List[Dict], current_price: float, high_price: float) -> Dict:
    """
    计算套牢盘数据
    
    Args:
        klines: 60分钟K线列表，每根含 open/high/low/close/volume
        current_price: 当前价格
        high_price: 今日最高价
    
    Returns:
        {
            "avg_cost": 加权平均成本,
            "trapped_ratio": 套牢比例(%),
            "trapped_depth": 套牢深度(%),
            "level": 1-5级,
            "level_desc": 等级描述,
            "level_emoji": 表情符号,
            "score_modify": 评分修正,
            "level_no_recommend": 是否不建议推荐,
        }
    """
    if not klines or current_price <= 0:
        return _default_result()
    
    # 计算加权平均成本
    total_volume = 0.0
    weighted_sum = 0.0
    
    for kline in klines:
        close = kline.get("close", 0)
        volume = kline.get("volume", 0)
        if close > 0 and volume > 0:
            weighted_sum += close * volume
            total_volume += volume
    
    if total_volume <= 0:
        return _default_result()
    
    avg_cost = weighted_sum / total_volume
    
    # 套牢比例 = (平均成本 - 现价) / 平均成本 × 100%
    trapped_ratio = (avg_cost - current_price) / avg_cost * 100 if avg_cost > 0 else 0.0
    
    # 套牢深度 = (最高价 - 现价) / 现价 × 100%
    trapped_depth = (high_price - current_price) / current_price * 100 if current_price > 0 else 0.0
    
    # 判定等级
    level, level_info = _judge_level(trapped_ratio)
    
    return {
        "avg_cost": round(avg_cost, 3),
        "trapped_ratio": round(trapped_ratio, 2),
        "trapped_depth": round(trapped_depth, 2),
        "level": level,
        "level_desc": level_info["desc"],
        "level_emoji": level_info["emoji"],
        "score_modify": level_info["score"],
        "level_no_recommend": level >= 5,
    }


def _judge_level(trapped_ratio: float) -> Tuple[int, Dict]:
    """
    根据套牢比例判定等级
    1级: 极少/无套牢  → +3分
    2级: <20%        → 不调整
    3级: 20%-50%     → 不调整
    4级: 50%-80%     → -5分
    5级: >80%        → 严重套牢，不推荐
    """
    for level in sorted(TRAPPED_LEVELS.keys()):
        info = TRAPPED_LEVELS[level]
        if trapped_ratio < info["max_ratio"]:
            return level, info
    
    return 5, TRAPPED_LEVELS[5]


def _default_result() -> Dict:
    return {
        "avg_cost": 0.0,
        "trapped_ratio": 0.0,
        "trapped_depth": 0.0,
        "level": 0,
        "level_desc": "数据不足",
        "level_emoji": "",
        "score_modify": 0.0,
        "level_no_recommend": False,
    }


def get_overnight_trapped_modify(level: int) -> float:
    """
    隔夜套利套牢盘修正
    - 1-2级（筹码干净）→ +10分
    - 4-5级（套牢较重）→ -10分
    - 3级 → 0分
    """
    if level in (1, 2):
        return 10.0
    elif level in (4, 5):
        return -10.0
    else:
        return 0.0


def batch_analyze_locked_chips(stocks: List[Dict], fetch_func) -> List[Dict]:
    """
    批量分析套牢盘
    
    Args:
        stocks: 股票列表
        fetch_func: K线获取函数，签名为 fetch_func(code) -> List[Dict]
    
    Returns:
        更新了 trapped_* 字段的股票列表
    """
    for stock in stocks:
        code = stock["code"]
        current_price = stock.get("price", 0)
        high_price = stock.get("high", 0)
        
        klines = fetch_func(code) if fetch_func else None
        
        if klines and current_price > 0:
            result = calc_locked_chips(klines, current_price, high_price)
            stock.update(result)
        else:
            result = _default_result()
            stock.update(result)
    
    return stocks
