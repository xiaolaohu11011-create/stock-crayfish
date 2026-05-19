"""
选股小龙虾 - 数据缓存层
避免重复请求，支持TTL过期，减少API压力
"""
import os
import json
import time
import logging
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 默认缓存目录
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".cache")


class DataCache:
    """文件缓存管理器，支持TTL过期"""
    
    def __init__(self, cache_dir: str = CACHE_DIR, default_ttl: int = 3600):
        """
        Args:
            cache_dir: 缓存文件目录
            default_ttl: 默认过期时间(秒)，默认1小时
        """
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        os.makedirs(cache_dir, exist_ok=True)
    
    def _cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        # 安全化key（去除特殊字符）
        safe_key = key.replace("/", "_").replace("\\", "_").replace(":", "_")
        return os.path.join(self.cache_dir, f"{safe_key}.json")
    
    def get(self, key: str, max_age: int = None) -> Optional[Any]:
        """
        获取缓存数据
        
        Args:
            key: 缓存键
            max_age: 最大存活时间(秒)，None使用默认TTL
        
        Returns:
            缓存数据，过期或不存在返回None
        """
        path = self._cache_path(key)
        
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            
            # 检查过期
            ttl = max_age if max_age is not None else self.default_ttl
            age = time.time() - entry.get("timestamp", 0)
            
            if age > ttl:
                logger.debug(f"缓存过期: {key} (age={age:.0f}s, ttl={ttl}s)")
                return None
            
            logger.debug(f"缓存命中: {key} (age={age:.0f}s)")
            return entry["data"]
            
        except Exception as e:
            logger.warning(f"缓存读取失败: {key} - {e}")
            return None
    
    def set(self, key: str, data: Any) -> bool:
        """
        写入缓存
        
        Args:
            key: 缓存键
            data: 缓存数据（必须可JSON序列化）
        
        Returns:
            是否成功
        """
        path = self._cache_path(key)
        
        try:
            entry = {
                "timestamp": time.time(),
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data": data,
            }
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            logger.warning(f"缓存写入失败: {key} - {e}")
            return False
    
    def invalidate(self, key: str) -> bool:
        """删除指定缓存"""
        path = self._cache_path(key)
        if os.path.exists(path):
            try:
                os.remove(path)
                return True
            except Exception:
                return False
        return True
    
    def clear_all(self) -> int:
        """清空所有缓存，返回删除数量"""
        count = 0
        if os.path.exists(self.cache_dir):
            for f in os.listdir(self.cache_dir):
                if f.endswith(".json"):
                    try:
                        os.remove(os.path.join(self.cache_dir, f))
                        count += 1
                    except Exception:
                        pass
        logger.info(f"清空缓存: 删除{count}个文件")
        return count
    
    def cleanup_expired(self, max_age: int = None) -> int:
        """清理过期缓存"""
        ttl = max_age if max_age is not None else self.default_ttl
        count = 0
        
        if not os.path.exists(self.cache_dir):
            return 0
        
        now = time.time()
        for f in os.listdir(self.cache_dir):
            if not f.endswith(".json"):
                continue
            
            path = os.path.join(self.cache_dir, f)
            try:
                mtime = os.path.getmtime(path)
                if now - mtime > ttl:
                    os.remove(path)
                    count += 1
            except Exception:
                pass
        
        logger.info(f"清理过期缓存: 删除{count}个文件")
        return count


# 全局缓存实例
cache = DataCache()

# 常用缓存键
KEY_ALL_STOCKS = "all_stocks_{date}"      # 全市场行情
KEY_MONEY_FLOW = "money_flow_{date}"      # 资金流
KEY_INDEX_QUOTE = "index_quote_{date}"    # 大盘指数
KEY_KLINE_60MIN = "kline_60min_{code}"    # 60分钟K线
KEY_MARKET_ANALYSIS = "market_{date}"     # 大盘分析


def today_key(template: str) -> str:
    """生成当天日期的缓存键"""
    return template.format(date=datetime.now().strftime("%Y%m%d"))
