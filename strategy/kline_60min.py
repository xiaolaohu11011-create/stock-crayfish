"""
选股小龙虾 - 60分钟K线技术分析
三重时间窗口分析：短期3根/中期5根/长期8根
8档方向判定规则
"""
import logging
from typing import List, Dict, Tuple, Optional
from config.config import KLINE_WINDOWS, KLINE_MODIFY_SCORE

logger = logging.getLogger(__name__)


def analyze_60min_direction(klines: List[Dict]) -> Tuple[str, float]:
    """
    分析60分钟K线方向
    
    Args:
        klines: K线列表，每根包含 open/high/low/close/volume
               按时间顺序排列（最旧在前）
    
    Returns:
        (direction, modify_score)
        direction: "strong_up"|"up"|"neutral"|"down"|"strong_down"|"unknown"
        modify_score: ±5分修正值
    """
    if not klines or len(klines) < 3:
        return "unknown", 0.0
    
    n = len(klines)
    
    # 三个窗口方向
    short_dir = _window_direction(klines, KLINE_WINDOWS["short"])
    mid_dir = _window_direction(klines, KLINE_WINDOWS["mid"])
    long_dir = _window_direction(klines, KLINE_WINDOWS["long"])
    
    # 综合判定：取多数方向
    directions = [short_dir, mid_dir, long_dir]
    up_count = sum(1 for d in directions if d in ("strong_up", "up"))
    down_count = sum(1 for d in directions if d in ("strong_down", "down"))
    neutral_count = sum(1 for d in directions if d == "neutral")
    
    if up_count >= 2:
        final_dir = "up"
    elif down_count >= 2:
        final_dir = "down"
    elif up_count == 1 and down_count == 1 and neutral_count == 1:
        # 三足鼎立，用长期方向
        final_dir = long_dir
    else:
        final_dir = "neutral"
    
    # 计算修正分数
    if final_dir in ("strong_up", "up"):
        modify = KLINE_MODIFY_SCORE
    elif final_dir in ("strong_down", "down"):
        modify = -KLINE_MODIFY_SCORE
    else:
        modify = 0.0
    
    return final_dir, modify


def _window_direction(klines: List[Dict], window_size: int) -> str:
    """
    计算单个窗口的方向
    
    8档规则：
    - 强势向上：上涨数 > 下跌数×2 且 上涨数 >= 2
    - 偏多向上：上涨数 > 下跌数
    - 横盘震荡：上涨数 = 下跌数 或均为0
    - 偏空向下：下跌数 > 上涨数
    - 强势向下：下跌数 > 上涨数×2 且 下跌数 >= 2
    """
    klines = klines[-window_size:]  # 取最近window_size根
    
    up_count = 0
    down_count = 0
    flat_count = 0
    
    for i in range(1, len(klines)):
        prev_close = klines[i - 1]["close"]
        curr_close = klines[i]["close"]
        
        if curr_close > prev_close:
            up_count += 1
        elif curr_close < prev_close:
            down_count += 1
        else:
            flat_count += 1
    
    # 判定
    if up_count > down_count * 2 and up_count >= 2:
        return "strong_up"
    elif up_count > down_count:
        return "up"
    elif down_count > up_count * 2 and down_count >= 2:
        return "strong_down"
    elif down_count > up_count:
        return "down"
    else:
        return "neutral"


def get_overnight_kline_modify(kline_dir: str) -> float:
    """
    隔夜套利K线修正
    - 方向明确向上/短期向上/偏多向上 → +15分
    - 方向明确向下/强势下跌 → -15分
    """
    if kline_dir in ("strong_up", "up", "short_up"):
        return 15.0
    elif kline_dir in ("strong_down", "down"):
        return -15.0
    else:
        return 0.0


def batch_analyze_klines(stocks: List[Dict], fetch_func) -> List[Dict]:
    """
    批量分析K线方向
    
    Args:
        stocks: 股票列表
        fetch_func: K线获取函数，签名为 fetch_func(code) -> List[Dict]
    
    Returns:
        更新了 kline_direction 和 kline_modify 的股票列表
    """
    for stock in stocks:
        code = stock["code"]
        klines = fetch_func(code) if fetch_func else None
        
        if klines:
            direction, modify = analyze_60min_direction(klines)
            stock["kline_direction"] = direction
            stock["kline_modify"] = modify
        else:
            stock["kline_direction"] = "unknown"
            stock["kline_modify"] = 0.0
    
    return stocks
