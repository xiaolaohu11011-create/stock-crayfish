"""
选股小龙虾 - 腾讯行情API（备用数据源）
用于大盘指数、个股实时价格、日K线
"""
import requests
import logging
from typing import Dict, List, Optional
from config.config import TENCENT_BASE_URL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


# 主要指数代码映射
INDEX_CODES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000300": "沪深300",
    "sh000016": "上证50",
    "sz399905": "中证500",
    "hkHSI": "恒生指数",
    "usNDX": "纳斯达克100",
    "usSPX": "标普500",
}


def fetch_index_quote(codes: List[str] = None) -> Dict[str, Dict]:
    """
    获取大盘指数实时行情
    
    Args:
        codes: 指数代码列表，默认使用主要指数
    
    返回: {code: {name, price, pct_change, ...}}
    """
    if codes is None:
        codes = list(INDEX_CODES.keys())
    
    result = {}
    
    # 腾讯API每次最多查询50个
    for i in range(0, len(codes), 50):
        batch = codes[i:i+50]
        url = TENCENT_BASE_URL + ",".join(batch)
        
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            lines = resp.text.strip().split("\n")
            
            for line in lines:
                parts = line.split("~")
                if len(parts) < 50:
                    continue
                
                code = parts[2].strip()  # 实际代码
                result[code] = {
                    "name": parts[1],
                    "price": _safe_float(parts[3]),
                    "pct_change": _safe_float(parts[32]),
                    "change": _safe_float(parts[31]),
                    "open": _safe_float(parts[5]),
                    "high": _safe_float(parts[33]),
                    "low": _safe_float(parts[34]),
                    "volume": _safe_float(parts[36]),
                    "amount": _safe_float(parts[37]),
                }
                
        except Exception as e:
            logger.warning(f"获取指数行情失败: {e}")
    
    return result


def fetch_single_quote(code: str) -> Optional[Dict]:
    """
    获取单个股票实时行情
    
    Args:
        code: 股票代码 如 "000001"（需要加市场前缀）
    
    返回: 行情数据 dict
    """
    # 判断市场
    if code.startswith(("0", "3")):
        market = "sz"
    else:
        market = "sh"
    
    url = f"{TENCENT_BASE_URL}{market}{code}"
    
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        parts = resp.text.split("~")
        
        if len(parts) < 50:
            return None
        
        return {
            "code": code,
            "name": parts[1],
            "price": _safe_float(parts[3]),
            "pct_change": _safe_float(parts[32]),
            "change": _safe_float(parts[31]),
            "open": _safe_float(parts[5]),
            "high": _safe_float(parts[33]),
            "low": _safe_float(parts[34]),
            "volume": _safe_float(parts[36]),
            "amount": _safe_float(parts[37]),
            "bid1": _safe_float(parts[9]),
            "ask1": _safe_float(parts[19]),
            "volume_ratio": _safe_float(parts[49]),
            "turnover_rate": _safe_float(parts[38]),
        }
        
    except Exception as e:
        logger.warning(f"获取{code}行情失败: {e}")
        return None


def fetch_realtime_batch(codes: List[str]) -> Dict[str, Dict]:
    """
    批量获取个股实时行情（腾讯接口）
    
    Args:
        codes: 股票代码列表，如 ["600519", "000001"]
    
    返回: {code: {name, price, pct_change, volume, amount, volume_ratio, turnover_rate}}
    """
    if not codes:
        return {}
    
    result = {}
    batch_size = 50  # 腾讯每次最多50个
    
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        # 构建带市场前缀的代码
        prefixed = []
        for code in batch:
            if code.startswith(("0", "3")):
                prefixed.append(f"sz{code}")
            else:
                prefixed.append(f"sh{code}")
        
        url = TENCENT_BASE_URL + ",".join(prefixed)
        
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            lines = resp.text.strip().split("\n")
            
            for line in lines:
                parts = line.split("~")
                if len(parts) < 50:
                    continue
                
                # 提取纯代码（去掉市场前缀）
                full_code = parts[2].strip()
                code = full_code[2:] if len(full_code) > 2 else full_code
                
                # 腾讯返回的代码格式是 sh600519 或 sz000001，需要提取纯代码
                raw_code = parts[2].strip()
                if raw_code.startswith(("sh", "sz")):
                    code = raw_code[2:]
                else:
                    code = raw_code
                
                result[code] = {
                    "code": code,
                    "name": parts[1],
                    "price": _safe_float(parts[3]),
                    "pct_change": _safe_float(parts[32]),
                    "change": _safe_float(parts[31]),
                    "open": _safe_float(parts[5]),
                    "high": _safe_float(parts[33]),
                    "low": _safe_float(parts[34]),
                    "volume": _safe_float(parts[36]),
                    "amount": _safe_float(parts[37]),
                    "volume_ratio": _safe_float(parts[49]),
                    "turnover_rate": _safe_float(parts[38]),  # 腾讯直接返回百分比值，无需转换
                    "market_cap": _safe_float(parts[45]) * 1e8,  # 腾讯返回亿元，转元
                }
                
        except Exception as e:
            logger.warning(f"腾讯行情批次 {i//batch_size+1} 失败: {e}")
    
    logger.info(f"腾讯行情获取完成，共 {len(result)} 只")
    return result


def fetch_daily_kline(code: str, days: int = 5) -> Optional[List[Dict]]:
    """
    获取个股日K线数据（腾讯接口，稳定可靠）
    
    Args:
        code: 股票代码 如 "600519"
        days: 获取最近N天
    
    返回: [{date, open, close, high, low, volume}]
    """
    # 判断市场前缀
    if code.startswith(("0", "3")):
        prefix = "sz"
    else:
        prefix = "sh"
    
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {
        "_var": f"kline_dayqfq_{code}",
        "param": f"{prefix}{code},day,,,{days},qfq",
    }
    
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        json_str = resp.text.split("=", 1)[1].strip()
        import json
        d = json.loads(json_str)
        
        stock_data = d.get("data", {}).get(f"{prefix}{code}", {})
        raw_klines = stock_data.get("day", []) or stock_data.get("qfqday", [])
        
        result = []
        for kline in raw_klines:
            # 格式: ["2026-05-15", "1335.150", "1332.950", "1339.280", "1327.110", "58184.000"]
            if len(kline) >= 6:
                result.append({
                    "date": kline[0],
                    "open": float(kline[1]),
                    "close": float(kline[2]),
                    "high": float(kline[3]),
                    "low": float(kline[4]),
                    "volume": float(kline[5]),
                })
        
        return result
        
    except Exception as e:
        logger.warning(f"获取{code}日K线失败: {e}")
        return None


def fetch_index_kline(index_code: str, days: int = 5) -> Optional[List[Dict]]:
    """
    获取指数日K线数据（腾讯接口）
    
    Args:
        index_code: 指数代码 如 "000001"（上证）
        days: 获取最近N天
    
    返回: [{date, open, close, high, low, volume}]
    """
    # 指数前缀映射
    if index_code.startswith("000"):  # 上证指数系列
        prefix = "sh"
    elif index_code.startswith("399"):  # 深证指数系列
        prefix = "sz"
    else:
        prefix = "sh"
    
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {
        "_var": f"kline_day_{index_code}",
        "param": f"{prefix}{index_code},day,,,{days},",
    }
    
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        json_str = resp.text.split("=", 1)[1].strip()
        import json
        d = json.loads(json_str)
        
        stock_data = d.get("data", {}).get(f"{prefix}{index_code}", {})
        raw_klines = stock_data.get("day", []) or stock_data.get("qfqday", [])
        
        result = []
        for kline in raw_klines:
            if len(kline) >= 6:
                result.append({
                    "date": kline[0],
                    "open": float(kline[1]),
                    "close": float(kline[2]),
                    "high": float(kline[3]),
                    "low": float(kline[4]),
                    "volume": float(kline[5]),
                })
        
        return result
        
    except Exception as e:
        logger.warning(f"获取指数{index_code}日K线失败: {e}")
        return None


def _safe_float(val) -> float:
    if val is None or val == "" or val == "-":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
