"""
选股小龙虾 - 东方财富API数据源
获取全A股5181只实时行情（60分K线、涨幅排行）
分页拉取，56页×100条/页
"""
import requests
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional
from config.config import (
    EASTMONEY_BASE_URL, EASTMONEY_KLINE_URL, EASTMONEY_MIN_KLINE_URL,
    EASTMONEY_PAGE_SIZE, EASTMONEY_TOTAL_PAGES,
    REQUEST_TIMEOUT, REQUEST_RETRY, REQUEST_DELAY,
    KLINE_TIMEOUT, KLINE_RETRY, KLINE_FAST_FAIL,
)

logger = logging.getLogger(__name__)

# 缓存层延迟导入
def _get_cache():
    from data.cache import cache, today_key, KEY_ALL_STOCKS
    return cache, today_key, KEY_ALL_STOCKS

# 复用session + 请求头
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "*/*",
})
# 直连模式，trust_env=False 避免系统代理干扰
# 如有代理环境且直连不通，fetch_60min_kline 有降级重试逻辑
_session.trust_env = False


def _build_clist_params(page: int, page_size: int = EASTMONEY_PAGE_SIZE) -> dict:
    """构建东方财富行情列表请求参数"""
    return {
        "pn": page,
        "pz": page_size,
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f26,f22,f11,f62,f128,f136,f115,f152",
        "ut": "fa5fd1943c7b386f172d6893dbbd1d0c",
    }


def fetch_all_stocks(use_cache: bool = True) -> List[Dict]:
    """
    分页拉取全A股实时行情数据

    Args:
        use_cache: 是否使用缓存（默认True，同一天内只拉取一次）

    返回: 股票列表
    """
    # 非交易日/非交易时段检查
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    weekday_cn = ['周一','周二','周三','周四','周五','周六','周日'][weekday]
    
    if weekday >= 5:  # 周六=5, 周日=6
        logger.warning(f"非交易日（{weekday_cn}），跳过数据拉取")
        return []
    
    # 交易时段：9:00-11:30, 13:00-15:00
    # 允许15:00-15:30（收盘数据刚写完）
    in_session = (9 <= hour < 12) or (13 <= hour <= 15)
    if not in_session:
        logger.warning(f"非交易时段（{now.strftime('%H:%M')}），东方财富无实时数据，跳过")
        return []
    
    # 尝试缓存
    if use_cache:
        cache, today_key, KEY_ALL_STOCKS = _get_cache()
        cached = cache.get(today_key(KEY_ALL_STOCKS), max_age=3600*8)
        if cached and len(cached) >= 2000:  # 缓存不完整时不使用
            logger.info(f"缓存命中: 全市场{len(cached)}只股票")
            return cached
        elif cached:
            logger.info(f"缓存不完整({len(cached)}只)，重新拉取")

    all_stocks = []
    first_page_ok = False  # 首页成功标记

    for page in range(1, EASTMONEY_TOTAL_PAGES + 1):
        page_ok = False
        for attempt in range(REQUEST_RETRY):
            try:
                params = _build_clist_params(page)
                resp = _session.get(EASTMONEY_BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
                data = resp.json()

                if data.get("data") is None or data["data"].get("diff") is None:
                    if page == 1 and attempt == REQUEST_RETRY - 1:
                        logger.error("首页连续失败，API可能不可用（非交易时段？），终止拉取")
                        return []
                    logger.warning(f"第{page}页无数据，跳过")
                    break

                diff = data["data"]["diff"]
                for item in diff:
                    stock = {
                        "code": item.get("f12", ""),
                        "name": item.get("f14", ""),
                        "price": _safe_float(item.get("f2")),
                        "pct_change": _safe_float(item.get("f3")),
                        "change": _safe_float(item.get("f4")),
                        "volume": _safe_float(item.get("f5")),
                        "amount": _safe_float(item.get("f6")),
                        "amplitude": _safe_float(item.get("f7")),
                        "turnover_rate": _safe_float(item.get("f8")),
                        "pe": _safe_float(item.get("f9")),
                        "high": _safe_float(item.get("f15")),
                        "low": _safe_float(item.get("f16")),
                        "open": _safe_float(item.get("f17")),
                        "volume_ratio": _safe_float(item.get("f10")),
                        "market_cap": _safe_float(item.get("f20")),
                        "avg_price": _safe_float(item.get("f11")),
                    }
                    if stock["code"] and stock["price"] and stock["price"] > 0:
                        all_stocks.append(stock)

                logger.info(f"第{page}页获取{len(diff)}只，累计{len(all_stocks)}只")
                page_ok = True
                if page == 1:
                    first_page_ok = True
                break

            except Exception as e:
                logger.warning(f"第{page}页获取失败(尝试{attempt+1}/{REQUEST_RETRY}): {e}")
                if attempt < REQUEST_RETRY - 1:
                    time.sleep(3 + attempt * 2)
        
        # 首页都没成功，尝试新浪备用源
        if not first_page_ok and page == 1:
            logger.warning("东方财富首页失败，尝试腾讯备用源...")
            from data.tencent import fetch_realtime_batch
            codes = _get_stock_code_list()
            if codes:
                tencent_data = fetch_realtime_batch(codes)
                if tencent_data and len(tencent_data) > 0:
                    # 转换为标准格式
                    result = []
                    for code, info in tencent_data.items():
                        if info.get("price", 0) > 0:
                            result.append({
                                "code": code,
                                "name": info.get("name", ""),
                                "price": info.get("price", 0),
                                "pct_change": info.get("pct_change", 0),
                                "change": info.get("change", 0),
                                "volume": info.get("volume", 0),
                                "amount": info.get("amount", 0),
                                "amplitude": 0,
                                "turnover_rate": info.get("turnover_rate", 0),
                                "pe": 0,
                                "high": info.get("high", 0),
                                "low": info.get("low", 0),
                                "open": info.get("open", 0),
                                "volume_ratio": info.get("volume_ratio", 0),
                                "market_cap": info.get("market_cap", 0),
                                "avg_price": info.get("price", 0),
                            })
                    logger.info(f"腾讯备用源获取成功: {len(result)}只")
                    return result
            logger.error("腾讯备用源也失败，终止")
            return []
        
        if not page_ok:
            continue

        time.sleep(REQUEST_DELAY + 0.5 * (page % 5))  # 动态延迟减少限流

    logger.info(f"东方财富数据拉取完成，共{len(all_stocks)}只股票")

    # 如果东方财富数据不完整（<2000只），尝试腾讯备用源补充
    if len(all_stocks) < 2000:
        from data.tencent import fetch_realtime_batch
        codes = _get_stock_code_list()
        if codes:
            logger.info(f"东方财富仅{len(all_stocks)}只，尝试腾讯备用源（{len(codes)}代码）...")
            tencent_data = fetch_realtime_batch(codes)
            if tencent_data:
                result = []
                for code, info in tencent_data.items():
                    if info.get("price", 0) > 0:
                        # 已有东方财富数据则合并
                        existing = next((s for s in all_stocks if s["code"] == code), None)
                        if existing:
                            existing.update({
                                "price": info.get("price", existing.get("price", 0)),
                                "pct_change": info.get("pct_change", existing.get("pct_change", 0)),
                                "change": info.get("change", existing.get("change", 0)),
                                "volume": info.get("volume", existing.get("volume", 0)),
                                "amount": info.get("amount", existing.get("amount", 0)),
                                "volume_ratio": info.get("volume_ratio", existing.get("volume_ratio", 0)),
                                "turnover_rate": info.get("turnover_rate", existing.get("turnover_rate", 0)),
                                "high": info.get("high", existing.get("high", 0)),
                                "low": info.get("low", existing.get("low", 0)),
                                "open": info.get("open", existing.get("open", 0)),
                            })
                            result.append(existing)
                        else:
                            result.append({
                                "code": code,
                                "name": info.get("name", ""),
                                "price": info.get("price", 0),
                                "pct_change": info.get("pct_change", 0),
                                "change": info.get("change", 0),
                                "volume": info.get("volume", 0),
                                "amount": info.get("amount", 0),
                                "amplitude": 0,
                                "turnover_rate": info.get("turnover_rate", 0),
                                "pe": 0,
                                "high": info.get("high", 0),
                                "low": info.get("low", 0),
                                "open": info.get("open", 0),
                                "volume_ratio": info.get("volume_ratio", 0),
                                "market_cap": info.get("market_cap", 0),
                                "avg_price": info.get("price", 0),
                            })
                if len(result) > len(all_stocks):
                    all_stocks = result
                    logger.info(f"腾讯备用源补充后共{len(all_stocks)}只")

    # 写入缓存
    if use_cache:
        try:
            cache, _, KEY_ALL_STOCKS = _get_cache()
            cache.set(today_key(KEY_ALL_STOCKS), all_stocks)
            logger.info("已写入缓存")
        except Exception as e:
            logger.warning(f"缓存写入失败: {e}")

    return all_stocks


# K线快速失败标记（模块级，用于批量模式）
_kline_api_available = None

def fetch_60min_kline(code: str, market: int = 0, use_cache: bool = True) -> Optional[List[Dict]]:
    """
    获取60分钟K线数据（最近12根K线）
    优化：短超时、少重试、快速失败模式
    """
    global _kline_api_available
    
    # 快速失败：如果之前已确认API不可用，直接返回None
    if KLINE_FAST_FAIL and _kline_api_available is False:
        return None
    
    if use_cache:
        try:
            from data.cache import cache, KEY_KLINE_60MIN
            cached = cache.get(KEY_KLINE_60MIN.format(code=code), max_age=3600)
            if cached:
                return cached
        except Exception:
            pass

    prefix = "0" if code.startswith(("0", "3")) else "1"
    secid = f"{prefix}.{code}"

    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": 60,
        "fqt": 1,
        "beg": "0",
        "end": "20500101",
        "lmt": 12,
        "ut": "fa5fd1943c7b386f172d6893dbbd1d0c",
    }

    # 尝试获取60分钟K线（短超时、少重试）
    for attempt in range(KLINE_RETRY):
        try:
            resp = _session.get(EASTMONEY_KLINE_URL, params=params, timeout=KLINE_TIMEOUT)
            data = resp.json()
            klines = data.get("data", {}).get("klines", [])

            result = []
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 6:
                    result.append({
                        "time": parts[0],
                        "open": float(parts[1]),
                        "close": float(parts[2]),
                        "high": float(parts[3]),
                        "low": float(parts[4]),
                        "volume": float(parts[5]),
                    })

            if result:
                _kline_api_available = True
                if use_cache:
                    try:
                        from data.cache import cache, KEY_KLINE_60MIN
                        cache.set(KEY_KLINE_60MIN.format(code=code), result)
                    except Exception:
                        pass
                return result
            # 有响应但无K线数据（如非交易时段）
            return None

        except Exception as e:
            if attempt < KLINE_RETRY - 1:
                logger.debug(f"{code} 60min kline attempt {attempt+1} failed, retry...")
            else:
                logger.warning(f"获取{code}的60分钟K线失败: {e}")
                if KLINE_FAST_FAIL:
                    _kline_api_available = False
                    logger.warning("60分钟K线API不可用，后续请求将快速跳过")

    return None


def fetch_realtime_quote(codes: List[str]) -> Dict[str, Dict]:
    """
    批量获取个股实时行情（备用接口）
    """
    secids = []
    for code in codes:
        prefix = "0" if code.startswith(("0", "3")) else "1"
        secids.append(f"{prefix}.{code}")

    params = {
        "secids": ",".join(secids[:50]),
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f20",
        "ut": "fa5fd1943c7b386f172d6893dbbd1d0c",
    }

    result = {}
    try:
        resp = _session.get(
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            params=params, timeout=REQUEST_TIMEOUT
        )
        data = resp.json()
        diff = data.get("data", {}).get("diff", [])
        for item in diff:
            code = item.get("f12", "")
            result[code] = {
                "price": _safe_float(item.get("f2")),
                "pct_change": _safe_float(item.get("f3")),
                "high": _safe_float(item.get("f15")),
                "low": _safe_float(item.get("f16")),
                "open": _safe_float(item.get("f17")),
                "volume_ratio": _safe_float(item.get("f10")),
                "turnover_rate": _safe_float(item.get("f8")),
                "market_cap": _safe_float(item.get("f20")),
            }
    except Exception as e:
        logger.warning(f"批量获取实时行情失败: {e}")

    return result


def _safe_float(val) -> float:
    """安全转换为float，失败返回0.0"""
    if val is None or val == "-" or val == "":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# =============================================================================
# 新浪行情备用数据源
# 当东方财富API被封/不可用时使用
# =============================================================================

_sina_session = requests.Session()
_sina_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn/",
})


def _get_stock_code_list() -> List[str]:
    """获取全A股代码列表（用于新浪行情查询）
    优先从缓存/东方财富已获取的数据中提取，否则用akshare
    """
    # 尝试从缓存获取
    try:
        cache, today_key, KEY_ALL_STOCKS = _get_cache()
        cached = cache.get(today_key(KEY_ALL_STOCKS), max_age=3600*8)
        if cached and len(cached) > 1000:
            return [s["code"] for s in cached if s.get("code")]
    except Exception:
        pass
    
    # 用akshare获取（不依赖东方财富实时行情）
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        codes = df["code"].tolist()
        logger.info(f"akshare获取代码列表: {len(codes)}只")
        return codes
    except Exception as e:
        logger.warning(f"akshare获取代码列表失败: {e}")
    
    return []


def fetch_all_stocks_sina() -> List[Dict]:
    """新浪行情备用数据源：批量获取全A股实时行情
    新浪行情每批最多约800只，分批获取
    返回格式与fetch_all_stocks相同
    """
    logger.info("使用新浪行情备用数据源...")
    
    codes = _get_stock_code_list()
    if not codes:
        logger.error("无法获取股票代码列表，新浪备用源不可用")
        return []
    
    # 构建新浪代码格式: sh600519, sz000001
    sina_codes = []
    for code in codes:
        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        sina_codes.append(f"{prefix}{code}")
    
    all_stocks = []
    batch_size = 800
    
    for i in range(0, len(sina_codes), batch_size):
        batch = sina_codes[i:i+batch_size]
        try:
            url = f"https://hq.sinajs.cn/list={','.join(batch)}"
            resp = _sina_session.get(url, timeout=15)
            resp.encoding = "gbk"
            
            for line in resp.text.strip().split("\n"):
                try:
                    # 解析: var hq_str_sh600519="...";
                    var_part, data_part = line.split("=\"")
                    full_code = var_part.split("_")[-1]  # sh600519
                    market_prefix = full_code[:2]  # sh/sz
                    code = full_code[2:]  # 600519
                    
                    fields = data_part.rstrip('";').split(",")
                    if len(fields) < 32:
                        continue
                    
                    name = fields[0]
                    open_price = _safe_float(fields[1])
                    prev_close = _safe_float(fields[2])
                    price = _safe_float(fields[3])
                    high = _safe_float(fields[4])
                    low = _safe_float(fields[5])
                    volume = _safe_float(fields[8])  # 手
                    amount = _safe_float(fields[9])  # 元
                    
                    if price <= 0:
                        continue
                    
                    pct_change = round((price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0
                    amplitude = round((high - low) / prev_close * 100, 2) if prev_close > 0 else 0
                    
                    stock = {
                        "code": code,
                        "name": name,
                        "price": price,
                        "pct_change": pct_change,
                        "change": round(price - prev_close, 2),
                        "volume": volume * 100,  # 手→股
                        "amount": amount,
                        "amplitude": amplitude,
                        "turnover_rate": 0,  # 新浪无换手率
                        "pe": 0,
                        "high": high,
                        "low": low,
                        "open": open_price,
                        "volume_ratio": 0,  # 新浪无量比
                        "market_cap": 0,
                        "avg_price": amount / (volume * 100) if volume > 0 else price,
                    }
                    all_stocks.append(stock)
                    
                except Exception:
                    continue
                    
            logger.info(f"新浪行情第{i//batch_size+1}批: 累计{len(all_stocks)}只")
            time.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"新浪行情第{i//batch_size+1}批失败: {e}")
    
    logger.info(f"新浪行情获取完成，共{len(all_stocks)}只")
    return all_stocks
