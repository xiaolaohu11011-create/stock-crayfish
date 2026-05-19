# 选股小龙虾 🦞

面向A股全市场的量化选股与推送系统。每日收盘前自动运行，三层梯度筛选 + 100分综合评分，从5000+股票中筛出TOP20候选股，隔夜套利策略输出TOP8推荐，生成报告并通过微信推送。

## 架构

```
选股小龙虾/
├── config/          # 配置
│   ├── config.py    # 集中配置参数
│   └── __init__.py
├── data/            # 数据源
│   ├── eastmoney.py # 东方财富API（主数据源）
│   ├── akshare_data.py  # akshare资金流数据
│   ├── tencent.py   # 腾讯行情API（备用）
│   ├── cache.py     # 数据缓存层
│   └── __init__.py
├── strategy/        # 策略引擎
│   ├── screener.py  # 三层梯度筛选 + RPS排名
│   ├── scorer.py    # 100分综合评分
│   ├── kline_60min.py   # 60分钟K线方向分析
│   ├── locked_chips.py  # 套牢盘分析
│   ├── overnight.py     # 隔夜套利策略
│   ├── market_analysis.py # 大盘形势分析
│   └── __init__.py
├── report/          # 报告生成
│   ├── docx_generator.py # docx报告生成器
│   └── __init__.py
├── push/            # 推送
│   ├── wechat_pusher.py  # 微信推送（WxPusher/企业微信）
│   └── __init__.py
├── scripts/         # 定时脚本
│   ├── common.py    # 公共流程（抽取复用）
│   ├── collect_0900.py  # 09:00 早盘
│   ├── collect_0935.py  # 09:35 盘中
│   ├── collect_1425.py  # 14:25 午盘
│   ├── collect_1440.py  # 14:40 隔夜套利
│   ├── collect_1505.py  # 15:05 收盘
│   └── __init__.py
├── output/          # 报告输出
├── logs/            # 日志
├── data/.cache/     # 缓存文件
├── main.py          # 主入口
├── tests.py         # 单元测试
├── requirements.txt
├── crontab.txt      # Linux cron配置
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置推送

设置环境变量：

```bash
# WxPusher（二选一）
export WXPUSHER_TOKEN="your_token"
export WXPUSHER_UID="your_uid"

# 企业微信机器人（二选一）
export WECHAT_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
```

### 3. 运行

```bash
# 综合选股
python main.py --mode selection

# 隔夜套利
python main.py --mode overnight

# 完整流程（选股 + 隔夜）
python main.py --mode full --kline --trapped

# 不推送（测试用）
python main.py --mode selection --no-push

# 调试模式
python main.py --mode selection --debug
```

### 4. 定时运行（Linux）

```bash
# 安装crontab
crontab crontab.txt
```

### 5. 单元测试

```bash
python tests.py
```

## 核心策略

### 三层梯度筛选

| 梯度 | 条件 | 缩减效果 |
|------|------|----------|
| 第一梯度 | 市值>100亿 / 换手率>3% / 涨幅正且RPS>60（满足2项） | 5181→1300+ |
| 第二梯度 | 量比>1.5 / 涨幅>2%（满足1项） | 1300→900 |
| 第三梯度 | 主力资金流入>0 | 900→600 |

### 100分评分体系

| 维度 | 分值 | 说明 |
|------|------|------|
| 资金面 | 35分 | 主力资金流入比例分档评分 |
| 基本面 | 25分 | PE分档（<15=25, <25=20...） |
| 技术面 | 25分 | RPS排名(15分) + 量比(10分) |
| 风控 | 15分 | 高价股扣5分，大市值扣3分 |

附加修正：60分钟K线方向±5分，套牢盘等级修正±5分。

### 隔夜套利策略

14:40-14:50运行，100分制：
- 涨幅3-5% → 30分
- 振幅>5% → 25分
- 量比>2 → 20分
- 换手率3-10% → 15分
- 尾盘站稳 → 10分
- K线修正 ±15分
- 套牢盘修正 ±10分

取前8只推荐。

### 大盘形势分析

综合评分≥60分允许选股，<60分禁止。

国内因素(60分)：上证指数 + 涨跌比 + 涨停数 + 北向资金 + 成交额
国际因素(40分)：美股表现 + 恒生指数 + 汇率

## 数据源

- **主数据源**：东方财富API（实时行情、K线）
- **资金流**：akshare（主力资金净流入）
- **备用**：腾讯行情API

所有数据通过缓存层管理，同一天内避免重复请求。

## 技术栈

- Python 3.x
- requests / akshare / python-docx
- Linux cron / Windows Task Scheduler
- WxPusher / 企业微信机器人
