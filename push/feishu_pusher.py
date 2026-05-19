#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 飞书 Webhook 推送
"""
import requests
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def push_to_feishu(content: str, webhook_url: str = None) -> bool:
    """
    通过飞书 Webhook 推送消息（支持 Markdown）

    Args:
        content: Markdown 格式的文本内容
        webhook_url: 飞书机器人 Webhook 地址

    Returns:
        是否成功
    """
    if not webhook_url:
        from config.config import FEISHU_WEBHOOK_URL
        webhook_url = FEISHU_WEBHOOK_URL

    if not webhook_url:
        logger.warning("FEISHU_WEBHOOK_URL 未配置，跳过飞书推送")
        return False

    # 飞书安全关键词：必须出现在消息中才能通过验证
    SAFE_KEYWORD = "小可爱"

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "text": "🦞 选股小龙虾 - 每日选股报告"},
                "template": "purple"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"**{SAFE_KEYWORD}**\n\n{content}"
                }
            ]
        }
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            logger.info("飞书推送成功")
            return True
        else:
            logger.warning(f"飞书推送失败: {result}")
            return False
    except Exception as e:
        logger.warning(f"飞书推送异常: {e}")
        return False


def push_report_feishu(stocks: list, report_path: str = None, webhook_url: str = None) -> bool:
    """
    推送综合选股报告到飞书

    Args:
        stocks: 选股结果列表
        report_path: 本地报告文件路径（飞书暂不支持文件，仅推送摘要）
        webhook_url: 可选，自定义 Webhook URL

    Returns:
        是否成功
    """
    if not stocks:
        content = "**今日无符合条件股票**\n\n大盘行情不佳，暂无推荐。"
    else:
        lines = ["**今日综合选股结果（共 {} 只）**\n".format(len(stocks))]
        for i, s in enumerate(stocks[:10], 1):
            name = s.get("name", "?")
            code = s.get("code", "?")
            pct = s.get("pct_change", 0)
            score = s.get("score", 0)
            turnover = s.get("turnover_rate", 0)
            market_cap = s.get("market_cap", 0)
            if market_cap >= 1e8:
                cap_str = f"{market_cap/1e8:.1f}亿"
            else:
                cap_str = "?"
            emoji = "🔴" if pct > 9.5 else "🟢" if pct > 0 else "⚪"
            lines.append(
                f"{i}. {emoji} **{name}({code})** 涨幅:{pct:+.2f}% 换手:{turnover:.2f}% 市值:{cap_str} "
                f"评分:{score:.0f}"
            )

        if len(stocks) > 10:
            lines.append(f"\n...还有 {len(stocks)-10} 只，详见完整报告。")

        content = "\n".join(lines)

    return push_to_feishu(content, webhook_url)
