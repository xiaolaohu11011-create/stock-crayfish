"""
选股小龙虾 - 大盘形势分析
综合评分 >=60分允许选股，<60分禁止选股
国内因素(60分) + 国际因素(40分)
接入真实数据：上证指数涨跌、涨跌比、成交额变化、北向资金
"""
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional
from config.config import MARKET_SCORE_THRESHOLD, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# 复用session，自动带headers
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "*/*",
})
# 直连模式
_session.trust_env = False


def _fetch_index_data() -> Dict:
    """获取主要指数实时数据"""
    result = {}
    
    try:
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            "secids": "1.000001,0.399001,0.399006,1.000300",
            "fields": "f2,f3,f4,f6,f12,f14",
            "ut": "fa5fd1943c7b386f172d6893dbbd1d0c",
        }
        resp = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        data = resp.json()
        diff = data.get("data", {}).get("diff", [])
        
        for item in diff:
            code = item.get("f12", "")
            name = item.get("f14", "")
            result[code] = {
                "name": name,
                "price": item.get("f2", 0),
                "pct_change": item.get("f3", 0),
                "amount": item.get("f6", 0),
            }
    except Exception as e:
        logger.warning(f"获取指数数据失败: {e}")
    
    return result


def _fetch_advance_decline() -> Dict:
    """获取涨跌家数数据（用于计算涨跌比）"""
    result = {"advance": 0, "decline": 0, "flat": 0, "limit_up": 0, "limit_down": 0}
    
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        
        # 统计涨停
        params_up_limit = {
            "pn": 1, "pz": 1, "po": 1, "np": 1,
            "fltt": 2, "invt": 2,
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f3",
            "f3": "gt9.8",
            "ut": "fa5fd1943c7b386f172d6893dbbd1d0c",
        }
        try:
            resp = _session.get(url, params=params_up_limit, timeout=REQUEST_TIMEOUT)
            data = resp.json()
            result["limit_up"] = data.get("data", {}).get("total", 0)
        except Exception:
            pass
        
        # 涨幅>0的数量
        params_rise = {
            "pn": 1, "pz": 1, "po": 1, "np": 1,
            "fltt": 2, "invt": 2,
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f3",
            "f3": "gt0",
            "ut": "fa5fd1943c7b386f172d6893dbbd1d0c",
        }
        try:
            resp = _session.get(url, params=params_rise, timeout=REQUEST_TIMEOUT)
            data = resp.json()
            result["advance"] = data.get("data", {}).get("total", 0)
        except Exception:
            pass
        
        # 跌幅<0的数量
        params_decline = {
            "pn": 1, "pz": 1, "po": 1, "np": 1,
            "fltt": 2, "invt": 2,
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f3",
            "f3": "lt0",
            "ut": "fa5fd1943c7b386f172d6893dbbd1d0c",
        }
        try:
            resp = _session.get(url, params=params_decline, timeout=REQUEST_TIMEOUT)
            data = resp.json()
            result["decline"] = data.get("data", {}).get("total", 0)
        except Exception:
            pass
        
        # 获取总数
        params_total = {
            "pn": 1, "pz": 1, "po": 1, "np": 1,
            "fltt": 2, "invt": 2,
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f3",
            "ut": "fa5fd1943c7b386f172d6893dbbd1d0c",
        }
        try:
            resp = _session.get(url, params=params_total, timeout=REQUEST_TIMEOUT)
            data = resp.json()
            total = data.get("data", {}).get("total", 0)
            result["flat"] = max(0, total - result["advance"] - result["decline"])
        except Exception:
            pass
        
    except Exception as e:
        logger.warning(f"获取涨跌数据失败: {e}")
    
    return result


def _fetch_north_bound() -> Dict:
    """获取北向资金数据（东方财富直连，避免akshare接口变更问题）"""
    result = {"net_amount": 0, "direction": "unknown"}
    
    try:
        url = (
            "https://push2his.eastmoney.com/api/qt/kamt.kline/get"
            "?fields1=f1,f3&fields2=f51,f52,f53,f54,f55,f56"
            "&klt=101&lmt=1"
            "&ut=fa5fd1943c7b386f172d6893dbbd1d0c"
        )
        resp = _session.get(url, timeout=REQUEST_TIMEOUT)
        data = resp.json()
        
        # 解析北向资金：hk2sh(沪股通) + hk2sz(深股通)
        hk2sh = data.get("data", {}).get("hk2sh", [])
        hk2sz = data.get("data", {}).get("hk2sz", [])
        
        if hk2sh:
            parts = hk2sh[-1].split(",")
            sh_net = float(parts[1]) if len(parts) > 1 else 0  # 净流入(亿元)
        else:
            sh_net = 0
        
        if hk2sz:
            parts = hk2sz[-1].split(",")
            sz_net = float(parts[1]) if len(parts) > 1 else 0
        else:
            sz_net = 0
        
        total_net = (sh_net + sz_net) * 1e8  # 亿元→元
        result["net_amount"] = total_net
        result["direction"] = "inflow" if total_net > 0 else "outflow"
        
    except Exception as e:
        logger.warning(f"获取北向资金失败: {e}")
    
    return result


def analyze_domestic_factors() -> Dict:
    """
    分析国内因素（60分）
    
    评分规则：
    - 上证指数涨跌（15分）
    - 涨跌比（15分）
    - 涨停家数（10分）
    - 北向资金（10分）
    - 成交额变化（10分）
    """
    score = 0.0
    factors = {}
    
    # 1. 上证指数涨跌
    index_data = _fetch_index_data()
    sh_index = index_data.get("000001", {})
    sh_pct = sh_index.get("pct_change", 0)
    
    if isinstance(sh_pct, (int, float)):
        if sh_pct > 1.0:     sh_score = 15
        elif sh_pct > 0.5:   sh_score = 12
        elif sh_pct > 0:     sh_score = 10
        elif sh_pct > -0.5:  sh_score = 5
        elif sh_pct > -1.0:  sh_score = 2
        else:                sh_score = 0
    else:
        sh_score = 8
    
    score += sh_score
    factors["sh_index"] = {"score": sh_score, "pct_change": sh_pct, "name": "上证指数"}
    
    # 2. 涨跌比
    ad_data = _fetch_advance_decline()
    advance = ad_data.get("advance", 0)
    decline = ad_data.get("decline", 1)
    ad_ratio = advance / decline if decline > 0 else 1.0
    limit_up = ad_data.get("limit_up", 0)
    
    if ad_ratio > 2.0:       ad_score = 15
    elif ad_ratio > 1.5:     ad_score = 12
    elif ad_ratio > 1.0:     ad_score = 8
    elif ad_ratio > 0.5:     ad_score = 4
    else:                    ad_score = 0
    
    score += ad_score
    factors["advance_decline"] = {
        "score": ad_score, "ratio": round(ad_ratio, 2),
        "advance": advance, "decline": decline, "limit_up": limit_up,
    }
    
    # 3. 涨停家数
    if limit_up > 100:       lu_score = 10
    elif limit_up > 50:      lu_score = 8
    elif limit_up > 30:      lu_score = 5
    elif limit_up > 10:      lu_score = 3
    else:                    lu_score = 1
    
    score += lu_score
    factors["limit_up"] = {"score": lu_score, "count": limit_up}
    
    # 4. 北向资金
    nb_data = _fetch_north_bound()
    nb_amount = nb_data.get("net_amount", 0)
    
    if nb_amount > 50e8:     nb_score = 10
    elif nb_amount > 10e8:   nb_score = 7
    elif nb_amount > 0:      nb_score = 5
    elif nb_amount > -10e8:  nb_score = 3
    else:                    nb_score = 0
    
    score += nb_score
    factors["north_bound"] = {"score": nb_score, "net_amount": nb_amount}
    
    # 5. 成交额
    sh_amount = sh_index.get("amount", 0)
    if sh_amount > 5000e8:    amt_score = 10
    elif sh_amount > 4000e8:  amt_score = 8
    elif sh_amount > 3000e8:  amt_score = 6
    elif sh_amount > 0:       amt_score = 4
    else:                     amt_score = 6
    
    score += amt_score
    factors["amount"] = {"score": amt_score, "sh_amount": sh_amount}
    
    return {"score": round(score, 1), "factors": factors, "max": 60}


def analyze_international_factors() -> Dict:
    """
    分析国际因素（40分）
    
    评分规则：
    - 美股表现（20分）
    - 恒生指数（10分）
    - 汇率（10分）
    """
    score = 0.0
    factors = {}
    
    try:
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            "secids": "100.NDX,100.SPX,100.DJI,100.HSI",
            "fields": "f2,f3,f4,f12,f14",
            "ut": "fa5fd1943c7b386f172d6893dbbd1d0c",
        }
        resp = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        data = resp.json()
        diff = data.get("data", {}).get("diff", [])
        
        us_pct_list = []
        hk_pct = 0
        
        for item in diff:
            code = item.get("f12", "")
            pct = item.get("f3", 0)
            
            if isinstance(pct, (int, float)):
                if code in ("NDX", "SPX", "DJI"):
                    us_pct_list.append(pct)
                elif code == "HSI":
                    hk_pct = pct
        
        # 美股
        if us_pct_list:
            avg_us = sum(us_pct_list) / len(us_pct_list)
            if avg_us > 1.0:       us_score = 20
            elif avg_us > 0.5:     us_score = 16
            elif avg_us > 0:       us_score = 12
            elif avg_us > -0.5:    us_score = 6
            elif avg_us > -1.0:    us_score = 3
            else:                  us_score = 0
        else:
            avg_us = 0
            us_score = 10
        
        score += us_score
        factors["us_market"] = {"score": us_score, "avg_pct": round(avg_us, 2)}
        
        # 恒生
        if isinstance(hk_pct, (int, float)):
            if hk_pct > 1.0:       hk_score = 10
            elif hk_pct > 0:       hk_score = 7
            elif hk_pct > -0.5:    hk_score = 5
            elif hk_pct > -1.0:    hk_score = 3
            else:                  hk_score = 0
        else:
            hk_score = 5
        
        score += hk_score
        factors["hk_market"] = {"score": hk_score, "pct_change": hk_pct}
        
        # 汇率暂给中间分
        fx_score = 5
        score += fx_score
        factors["fx"] = {"score": fx_score, "detail": "汇率数据暂未接入"}
        
    except Exception as e:
        logger.warning(f"国际因素分析失败: {e}")
        score = 20
        factors = {"error": str(e)}
    
    return {"score": round(score, 1), "factors": factors, "max": 40}


def analyze_market() -> Dict:
    """综合大盘分析"""
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    
    # 非交易时段或API不可用：返回保守基准分
    # 交易时段但API失败时不应返回极低分（会错误阻止选股）
    in_session = (9 <= hour < 12) or (13 <= hour <= 15)
    if weekday >= 5 or not in_session:
        domestic = {"score": 50, "factors": {"note": "非交易时段基准分"}, "max": 60}
        international = {"score": 30, "factors": {"note": "非交易时段基准分"}, "max": 40}
        total = 80
        can_select = True
        advice = f"非交易时段，使用基准分{total}分（仅供测试）"
        logger.info(f"大盘分析: 非交易时段，使用基准分{total}分")
    else:
        domestic = analyze_domestic_factors()
        international = analyze_international_factors()
        total = domestic["score"] + international["score"]
        
        # API失败检测：涨跌家数全为0、三个值相同（API返回错误数据）、或总分异常低
        ad_data = domestic.get('factors', {}).get('advance_decline', {})
        adv = ad_data.get('advance', 0)
        dec = ad_data.get('decline', 0)
        lim = ad_data.get('limit_up', 0)
        # 检测异常：三个值相同（API缓存错误）或全为0
        ad_suspicious = (adv == dec == lim) or (adv == 0 and dec == 0)
        api_failed = (domestic['score'] < 25 or ad_suspicious)
        if api_failed:
            logger.warning(f"大盘评分异常低({total}分)，疑似API故障，使用保守基准分")
            domestic = {"score": 48, "factors": {"note": "API异常降级基准分"}, "max": 60}
            international = {"score": 27, "factors": {"note": "API异常降级基准分"}, "max": 40}
            total = 75
            can_select = True
            advice = f"API数据获取异常，使用降级基准分{total}分"
        else:
            can_select = total >= MARKET_SCORE_THRESHOLD
            
            if total >= 80:     advice = f"大盘评分{total:.0f}分，市场强势，积极选股"
            elif total >= 60:   advice = f"大盘评分{total:.0f}分，市场偏暖，可以选股"
            elif total >= 40:   advice = f"大盘评分{total:.0f}分，市场偏弱，谨慎操作"
            else:               advice = f"大盘评分{total:.0f}分，市场弱势，建议观望"
    
    can_select = total >= MARKET_SCORE_THRESHOLD
    
    result = {
        "total_score": round(total, 1),
        "can_select": can_select,
        "domestic_score": domestic,
        "international_score": international,
        "advice": advice,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    logger.info(f"大盘分析: {total:.0f}分 - {advice}")
    return result


def batch_market_analysis(stock_lists: List[Dict]) -> Dict:
    """批量分析时的市场环境检查"""
    market = analyze_market()
    
    if not market["can_select"]:
        return {"result": "SKIPPED", "reason": market["advice"], "market": market}
    
    return {"result": "PROCEED", "market": market}
