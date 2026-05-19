"""
选股小龙虾 - 微信推送
支持 WxPusher 和企业微信机器人
"""
import requests
import logging
import json
import os
from typing import Optional
from config.config import WXPUSHER_TOKEN, WXPUSHER_UID, WECHAT_WEBHOOK_URL

logger = logging.getLogger(__name__)


def push_via_wxpusher(content: str, file_path: str = None) -> bool:
    """
    通过 WxPusher 推送消息和文件
    
    Args:
        content: 文本内容
        file_path: docx文件路径（可选）
    
    Returns:
        是否成功
    """
    if not WXPUSHER_TOKEN:
        logger.warning("WXPUSHER_TOKEN 未配置")
        return False
    
    # 1. 发送文本
    text_url = "http://wxpush.zjiecode.com/api/send"
    text_data = {
        "token": WXPUSHER_TOKEN,
        "content": content,
        "contentType": 1,  # Markdown
    }
    if WXPUSHER_UID:
        text_data["uid"] = WXPUSHER_UID
    
    try:
        resp = requests.post(text_url, json=text_data, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"WxPusher文本发送失败: {resp.text}")
    except Exception as e:
        logger.warning(f"WxPusher请求异常: {e}")
    
    # 2. 发送文件（如有）
    if file_path and os.path.exists(file_path):
        file_url = "http://wxpush.zjiecode.com/api/sendFile"
        file_data = {
            "token": WXPUSHER_TOKEN,
            "fileType": 2,  # docx
        }
        if WXPUSHER_UID:
            file_data["uid"] = WXPUSHER_UID
        
        # 读取文件
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                resp = requests.post(file_url, data=file_data, files=files, timeout=60)
                if resp.status_code == 200:
                    logger.info(f"文件推送成功: {file_path}")
                    return True
                else:
                    logger.warning(f"文件推送失败: {resp.text}")
        except Exception as e:
            logger.warning(f"文件读取异常: {e}")
    
    return False


def push_via_wechat_bot(content: str, file_path: str = None) -> bool:
    """
    通过企业微信机器人推送
    
    Args:
        content: 文本内容
        file_path: 文件路径（需要转base64）
    
    Returns:
        是否成功
    """
    if not WECHAT_WEBHOOK_URL:
        logger.warning("WECHAT_WEBHOOK_URL 未配置")
        return False
    
    # 1. 发送文本
    text_data = {
        "msgtype": "text",
        "text": {"content": content},
    }
    
    try:
        resp = requests.post(WECHAT_WEBHOOK_URL, json=text_data, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"企业微信文本发送失败: {resp.text}")
    except Exception as e:
        logger.warning(f"企业微信请求异常: {e}")
    
    return False


def push_report(report_path: str, market_score: float = None, top_stocks: list = None) -> bool:
    """
    推送选股报告（文本摘要 + docx文件）
    
    Args:
        report_path: docx报告路径
        market_score: 大盘评分（可选）
        top_stocks: TOP20列表（可选，用于生成摘要）
    
    Returns:
        是否成功
    """
    # 构建文本摘要
    content = "📊 **选股小龙虾报告**\n"
    if market_score is not None:
        content += f"大盘评分：{market_score:.0f}分\n"
    content += "\n"
    
    # 添加TOP10摘要
    if top_stocks:
        content += "🔥 TOP10候选：\n"
        for i, stock in enumerate(top_stocks[:10]):
            code = stock.get("code", "")
            name = stock.get("name", "")
            pct = stock.get("pct_change", 0)
            score = stock.get("score_total", 0)
            content += f"{i+1}. {name}({code}) 涨{pct:.1f}% 评分{score:.0f}\n"
    else:
        content += "报告已生成，请查收附件"
    
    # 尝试两种推送方式
    success = False
    
    if WXPUSHER_TOKEN:
        success = push_via_wxpusher(content, report_path)
    
    if not success and WECHAT_WEBHOOK_URL:
        success = push_via_wechat_bot(content, report_path)
    
    return success


def push_overnight_report(report_path: str, top_stocks: list = None) -> bool:
    """
    推送隔夜套利报告（文本摘要 + docx文件）
    
    Args:
        report_path: docx报告路径
        top_stocks: TOP8列表（可选，用于生成摘要）
    
    Returns:
        是否成功
    """
    content = "🦞 **选股小龙虾 - 隔夜套利推荐**\n"
    content += "尾盘强势股，次日高开概率高\n\n"
    
    if top_stocks:
        content += "🔥 TOP8推荐：\n"
        for i, stock in enumerate(top_stocks[:8]):
            code = stock.get("code", "")
            name = stock.get("name", "")
            pct = stock.get("pct_change", 0)
            score = stock.get("overnight_total_score", 0)
            kline = stock.get("kline_direction", "-")
            trapped = stock.get("trapped_level", 0)
            content += f"{i+1}. {name}({code}) 涨{pct:.1f}% 隔夜{score:.0f}分 K线:{kline} 套牢:{trapped}级\n"
    else:
        content += "报告已生成，请查收附件"
    
    success = False
    
    if WXPUSHER_TOKEN:
        success = push_via_wxpusher(content, report_path)
    
    if not success and WECHAT_WEBHOOK_URL:
        success = push_via_wechat_bot(content, report_path)
    
    return success


def save_to_queue(queue_data: dict, queue_file: str) -> bool:
    """
    保存到推送队列（用于heartbeat兜底）
    
    Args:
        queue_data: {"type": "selection"|"overnight", "report_path": "...", "timestamp": "..."}
        queue_file: 队列文件路径
    
    Returns:
        是否成功
    """
    try:
        # 读取现有队列
        queue = []
        if os.path.exists(queue_file):
            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
        
        # 添加新项
        queue.append(queue_data)
        
        # 保存
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        with open(queue_file, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        
        return True
        
    except Exception as e:
        logger.warning(f"队列保存失败: {e}")
        return False


def load_queue(queue_file: str) -> list:
    """
    加载推送队列
    
    Args:
        queue_file: 队列文件路径
    
    Returns:
        队列列表
    """
    if not os.path.exists(queue_file):
        return []
    
    try:
        with open(queue_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"队列加载失败: {e}")
        return []
