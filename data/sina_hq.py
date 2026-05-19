#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 新浪 hq.sinajs.cn 实时行情补充源
混合架构方案B：用于补充/替代东方财富 push2 被阻断时的实时行情
"""
import requests
import logging
import time
from typing import List, Dict, Optional
from config.config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

_sina_session = requests.Session()
_sina_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn/",
})
_sina_session.trust_env = False  # 禁用系统代理，避免干扰


def fetch_realtime_batch(codes: List[str]) -> Dict[str, Dict]:
    """
    批量获取实时行情（hq.sinajs.cn）
    
    Args:
        codes: 股票代码列表，如 ["600519", "000001"]
    
    返回: {code: {name, price, pct_change, volume, amount, ...}}
    """
    if not codes:
        return {}
    
    # 构建新浪格式代码
    sina_codes = []
    for code in codes:
        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        sina_codes.append(f"{prefix}{code}")
    
    result = {}
    batch_size = 800  # 新浪每批上限约800
    
    for i in range(0, len(sina_codes), batch_size):
        batch = sina_codes[i:i+batch_size]
        try:
            url = f"https://hq.sinajs.cn/list={','.join(batch)}"
            resp = _sina_session.get(url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "gbk"
            
            for line in resp.text.strip().split("\n"):
                try:
                    # 解析: var hq_str_sh600519="贵州茅台,1770.00,...";
                    if "=" not in line:
                        continue
                    var_part, data_part = line.split("=", 1)
                    full_code = var_part.split("_")[-1]  # sh600519
                    code = full_code[2:]  # 600519
                    
                    # 去掉末尾的 "; 或 ;
                    data_str = data_part.strip().strip('"').rstrip('";')
                    if not data_str:
                        continue
                    
                    fields = data_str.split(",")
                    if len(fields) < 32:
                        continue
                    
                    name = fields[0]
                    open_price = _safe_float(fields[1])
                    prev_close = _safe_float(fields[2])
                    price = _safe_float(fields[3])
                    high = _safe_float(fields[4])
                    low = _safe_float(fields[5])
                    volume = _safe_float(fields[8])  # 成交手数
                    amount = _safe_float(fields[9])  # 成交金额（元）
                    
                    if price <= 0:
                        continue
                    
                    # 计算涨跌幅
                    pct_change = round((price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0
                    
                    result[code] = {
                        "code": code,
                        "name": name,
                        "price": price,
                        "pct_change": pct_change,
                        "change": round(price - prev_close, 2),
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "volume": volume * 100,  # 手→股
                        "amount": amount,
                        # 以下字段新浪不提供，需从其他源补充或估算
                        "turnover_rate": 0,
                        "volume_ratio": 0,
                        "pe": 0,
                        "market_cap": 0,
                        "amplitude": round((high - low) / prev_close * 100, 2) if prev_close > 0 else 0,
                    }
                    
                except Exception as e:
                    logger.debug(f"解析行情行失败: {e}")
                    continue
            
            logger.debug(f"新浪行情批次 {i//batch_size+1}: 获取 {len(result)} 只")
            
        except Exception as e:
            logger.warning(f"新浪行情批次 {i//batch_size+1} 失败: {e}")
        
        time.sleep(0.3)  # 批次间短暂延迟
    
    logger.info(f"新浪 hq 获取完成，共 {len(result)} 只")
    return result


def fetch_realtime_single(code: str) -> Optional[Dict]:
    """
    获取单只股票实时行情
    
    Args:
        code: 股票代码，如 "600519"
    
    返回: 行情数据 dict，失败返回 None
    """
    result = fetch_realtime_batch([code])
    return result.get(code)


def merge_with_sina(stocks: List[Dict], sina_data: Dict[str, Dict]) -> List[Dict]:
    """
    将新浪行情数据合并到股票列表
    用于东方财富数据不完整时补充实时价格
    
    Args:
        stocks: 原有股票列表（来自东方财富或其他源）
        sina_data: 新浪行情数据 {code: {...}}
    
    返回: 合并后的股票列表
    """
    # 构建索引
    sina_dict = sina_data
    
    merged = []
    for stock in stocks:
        code = stock.get("code", "")
        if code in sina_dict:
            sina = sina_dict[code]
            # 以新浪实时价格为准，保留原有字段
            merged_stock = dict(stock)
            merged_stock.update({
                "price": sina["price"],
                "pct_change": sina["pct_change"],
                "change": sina["change"],
                "high": sina["high"],
                "low": sina["low"],
                "open": sina["open"],
                "volume": sina["volume"],
                "amount": sina["amount"],
            })
            # 如果原数据没有这些字段，用新浪的（虽然新浪也没有，但保留结构）
            if not merged_stock.get("turnover_rate"):
                merged_stock["turnover_rate"] = 0
            if not merged_stock.get("volume_ratio"):
                merged_stock["volume_ratio"] = 0
            merged.append(merged_stock)
        else:
            merged.append(stock)
    
    logger.info(f"行情合并完成: 原{len(stocks)}只，新浪补充{len([s for s in merged if s.get('code') in sina_dict])}只")
    return merged


def _safe_float(val) -> float:
    """安全转换为 float"""
    if val is None or val == "" or val == "-":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
