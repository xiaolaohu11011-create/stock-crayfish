"""
选股小龙虾 - 集中配置文件
所有关键参数集中管理，易于修改
"""
import os

# ==================== 数据源配置 ====================
# 东方财富API
EASTMONEY_BASE_URL = "https://push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_MIN_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
EASTMONEY_PAGE_SIZE = 500  # 每页条数（增大减少请求次数，避免限流）
EASTMONEY_TOTAL_PAGES = 12  # 12页×500条 ≈ 5181只

# akshare
AKSHARE_TIMEOUT = 60

# 腾讯行情API（备用）
TENCENT_BASE_URL = "https://qt.gtimg.cn/q="

# ==================== 筛选阈值 ====================
# 第一梯度：基础筛选（满足至少2项）
FILTER1_MIN_MARKET_CAP = 100e8        # 总市值 > 100亿
FILTER1_MIN_TURNOVER_RATE = 3.0       # 换手率 > 3%
FILTER1_MIN_RPS = 60                  # RPS > 60
FILTER1_MIN_CONDITIONS = 2            # 至少满足2项

# 第二梯度：量价筛选（满足至少1项）
FILTER2_MIN_VOLUME_RATIO = 1.5        # 量比 > 1.5
FILTER2_MIN_PCT_CHANGE = 2.0          # 涨幅 > 2%
FILTER2_MIN_CONDITIONS = 1            # 至少满足1项

# 第三梯度：资金筛选
FILTER3_CAPITAL_FLOW_POSITIVE = True   # 主力资金净流入 > 0

# ==================== 评分体系 ====================
# 资金面（35分）
SCORE_CAPITAL_MAX = 35
SCORE_CAPITAL_FORMULA = "capital_flow * 10 + 10"  # 资金流量估算值×10+10，上限35分

# 基本面（25分）- PE评分
SCORE_FUNDAMENTAL_MAX = 25
PE_THRESHOLDS = {
    15: 25,   # PE < 15: 25分
    25: 20,   # PE < 25: 20分
    40: 15,   # PE < 40: 15分
    60: 10,   # PE < 60: 10分
    99999: 5, # 其他: 5分
}

# 技术面（25分）
SCORE_TECHNICAL_MAX = 25
SCORE_TECHNICAL_FORMULA = "RPS / 4 + volume_ratio * 5"  # 上限25分

# 风控（15分）
SCORE_RISK_MAX = 15
RISK_PENALTY_PRICE_ABOVE = 100   # 股价>100扣5分
RISK_PENALTY_PRICE = -5
RISK_PENALTY_MARKET_CAP_ABOVE = 500e8  # 市值>500亿扣3分
RISK_PENALTY_MARKET_CAP = -3

# ==================== K线分析 ====================
KLINE_WINDOWS = {
    "short": 3,   # 短期3根
    "mid": 5,     # 中期5根
    "long": 8,    # 长期8根
}
KLINE_MODIFY_SCORE = 5  # ±5分修正

# 隔夜套利K线修正
OVERNIGHT_KLINE_BONUS = 15   # 方向向上+15分
OVERNIGHT_KLINE_PENALTY = -15  # 方向向下-15分

# ==================== 套牢盘分析 ====================
TRAPPED_LEVELS = {
    1: {"max_ratio": 0,    "score": 3,   "desc": "极少/无套牢", "emoji": "✨"},
    2: {"max_ratio": 20,   "score": 0,   "desc": "少量套牢",   "emoji": ""},
    3: {"max_ratio": 50,   "score": 0,   "desc": "套牢适中",   "emoji": "🟠"},
    4: {"max_ratio": 80,   "score": -5,  "desc": "套牢较重",   "emoji": "🔴"},
    5: {"max_ratio": 999,  "score": -99, "desc": "严重套牢",   "emoji": "⛔"},
}

# 隔夜套利套牢盘修正
OVERNIGHT_TRAPPED_BONUS = 10    # 1-2级+10分
OVERNIGHT_TRAPPED_PENALTY = -10  # 4-5级-10分

# ==================== 隔夜套利策略 ====================
OVERNIGHT_SCORE_CONDITIONS = {
    "pct_change_3_5": {"range": (3, 5), "score": 30, "desc": "涨幅3-5%"},
    "amplitude_above_5": {"threshold": 5, "score": 25, "desc": "振幅>5%"},
    "volume_ratio_above_2": {"threshold": 2, "score": 20, "desc": "量比>2"},
    "turnover_3_10": {"range": (3, 10), "score": 15, "desc": "换手率3-10%"},
    "tail_stand": {"score": 10, "desc": "尾盘站稳（收盘价>均价）"},
}
OVERNIGHT_TOP_N = 8  # TOP8推荐

# ==================== 大盘分析 ====================
MARKET_SCORE_THRESHOLD = 60  # >=60允许选股，<60禁止

# 国内因素（60分）
MARKET_DOMESTIC_MAX = 60
# 国际因素（40分）
MARKET_INTERNATIONAL_MAX = 40

# ==================== 推送配置 ====================
# WxPusher
WXPUSHER_TOKEN = os.environ.get("WXPUSHER_TOKEN", "")
WXPUSHER_UID = os.environ.get("WXPUSHER_UID", "")

# 企业微信机器人
WECHAT_WEBHOOK_URL = os.environ.get("WECHAT_WEBHOOK_URL", "")


# ==================== 输出配置 ====================
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
REPORT_TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "report", "template.docx")

# ==================== 运行时配置 ====================
TOP_N = 20  # 最终输出TOP20
REQUEST_TIMEOUT = 30  # API请求超时(秒)
REQUEST_RETRY = 3     # 失败重试次数
REQUEST_DELAY = 1.0   # 请求间隔(秒)，避免被封

# K线请求专用（更短的超时，避免卡住）
KLINE_TIMEOUT = 5     # K线请求超时(秒)
KLINE_RETRY = 1       # K线重试次数
KLINE_FAST_FAIL = True  # 第一个K线失败则跳过剩余（批量模式）

# 推送队列文件
PUSH_QUEUE_FILE = os.path.join(OUTPUT_DIR, "push_queue.json")
