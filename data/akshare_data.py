"""
选股小龙虾 - akshare数据源
获取全市场5287只个股真实主力资金净流入数据（今日/3日/5日/10日）
替代原有估算值用于资金面评分
"""
import requests
import logging
import time
from typing import Dict, Optional
from config.config import AKSHARE_TIMEOUT

logger = logging.getLogger(__name__)


def fetch_money_flow() -> Dict[str, Dict]:
    """
    获取全市场个股资金流向数据（akshare接口）
    
    返回: {code: {"today_net": float, "d3_net": float, "d5_net": float, "d10_net": float}}
    """
    try:
        import akshare as ak
        
        # 使用 stock_individual_fund_flow_rank 获取全市场资金流排行
        # indicator: "今日" / "3日" / "5日" / "10日"
        result = {}
        
        for indicator, key in [("今日", "today_net"), ("3日", "d3_net"), ("5日", "d5_net"), ("10日", "d10_net")]:
            try:
                df = ak.stock_individual_fund_flow_rank(indicator=indicator)
                
                # 列名可能因版本不同而变，查找代码列和主力净流入列
                code_col = None
                net_col = None
                for col in df.columns:
                    col_lower = str(col).lower()
                    if col in ("代码", "code") or "代码" in str(col):
                        code_col = col
                    if "主力" in str(col) and "净流入" in str(col):
                        net_col = col
                
                if code_col is None or net_col is None:
                    logger.warning(f"akshare资金流({indicator})列名不匹配: {list(df.columns)}")
                    continue
                
                for _, row in df.iterrows():
                    code = str(row[code_col]).strip()
                    if not code:
                        continue
                    net_val = float(row[net_col] or 0)
                    
                    if code not in result:
                        result[code] = {"today_net": 0.0, "d3_net": 0.0, "d5_net": 0.0, "d10_net": 0.0}
                    result[code][key] = net_val
                
                logger.info(f"akshare资金流({indicator})获取{len(df)}只")
                time.sleep(0.5)  # 避免请求过快
                
            except Exception as e:
                logger.warning(f"akshare资金流({indicator})获取失败: {e}")
                continue
        
        logger.info(f"akshare资金流获取完成，共{len(result)}只")
        return result
        
    except ImportError:
        logger.warning("akshare未安装，使用估算方式")
        return {}
    except Exception as e:
        logger.warning(f"akshare资金流获取失败: {e}")
        return {}


def estimate_capital_flow(pct_change: float, volume_ratio: float, turnover_rate: float) -> float:
    """
    近似估算主力资金流入
    公式：capitalFlow = pct × volumeRatio / 50
    当涨幅为正且量比放大时，资金流入估算值较高
    
    Args:
        pct_change: 涨跌幅(%)
        volume_ratio: 量比
        turnover_rate: 换手率(%)
    
    返回: 估算资金流入值
    """
    if pct_change <= 0 or volume_ratio <= 0:
        return 0.0
    
    return pct_change * volume_ratio / 50


def enrich_with_money_flow(stocks: list, money_flow_data: Dict) -> list:
    """
    将资金流数据合并到股票列表
    
    Args:
        stocks: 股票列表（来自eastmoney）
        money_flow_data: 资金流数据（来自akshare）
    
    返回: 合并后的股票列表
    """
    for stock in stocks:
        code = stock["code"]
        
        if code in money_flow_data:
            # 使用真实数据
            mf = money_flow_data[code]
            stock["capital_flow"] = mf["today_net"]
            stock["capital_flow_3d"] = mf["d3_net"]
            stock["capital_flow_5d"] = mf["d5_net"]
            stock["capital_flow_10d"] = mf["d10_net"]
        else:
            # 使用估算方式
            stock["capital_flow"] = estimate_capital_flow(
                stock["pct_change"],
                stock["volume_ratio"],
                stock["turnover_rate"]
            )
            stock["capital_flow_3d"] = 0.0
            stock["capital_flow_5d"] = 0.0
            stock["capital_flow_10d"] = 0.0
    
    return stocks
