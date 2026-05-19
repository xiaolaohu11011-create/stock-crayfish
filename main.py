#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 主入口
支持命令行参数和交互式运行
"""
import sys
import os
import argparse
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.common import (
    setup_script_logging, fetch_and_prepare,
    run_selection_pipeline, run_overnight_pipeline,
    push_and_queue, log_elapsed,
)
from config.config import OUTPUT_DIR


def _save_json(stocks, market, report_path=""):
    """将选股结果保存为JSON（供Web Dashboard读取）"""
    import json as _json
    json_dir = os.path.join(OUTPUT_DIR, "_json")
    os.makedirs(json_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(json_dir, f"result_{ts}.json")
    data = {
        "timestamp": datetime.now().isoformat(),
        "market": market,
        "report_path": report_path,
        "stocks": stocks,
    }
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)
    logger = logging.getLogger(__name__)
    logger.info(f"JSON结果已保存: {path}")


def main():
    parser = argparse.ArgumentParser(description="选股小龙虾 - 量化选股系统")
    parser.add_argument(
        "--mode", 
        choices=["selection", "overnight", "full"],
        default="selection",
        help="运行模式：selection=综合选股, overnight=隔夜套利, full=完整流程"
    )
    parser.add_argument(
        "--kline", 
        action="store_true",
        help="启用60分钟K线分析（较慢）"
    )
    parser.add_argument(
        "--trapped",
        action="store_true",
        help="启用套牢盘分析"
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="不推送微信"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="不使用缓存，强制刷新数据"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="自定义输出文件路径"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="调试模式"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="模拟模式（非交易时段用模拟数据跑完整流程，用于测试）"
    )
    parser.add_argument(
        "--check-position",
        action="store_true",
        help="持仓健康检查（不选股，只检查现有持仓）"
    )
    parser.add_argument(
        "--position-report",
        action="store_true",
        help="生成持仓检查报告（配合--check-position使用）"
    )
    
    args = parser.parse_args()
    
    # 日志
    logger = setup_script_logging("main")
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    start_time = datetime.now()
    
    # 持仓检查模式
    if args.check_position:
        from position_check import check_positions, generate_position_report
        
        logger.info("=" * 50)
        logger.info("选股小龙虾 - 持仓健康检查")
        
        result = check_positions()
        
        if args.position_report:
            report_path = generate_position_report(result)
            logger.info(f"持仓报告: {report_path}")
        
        log_elapsed(start_time, "持仓检查", len(result.get("position_signals", [])))
        return
    
    # 获取数据
    data = fetch_and_prepare(use_cache=not args.no_cache, mock=args.mock)
    if not data:
        logger.error("数据获取失败，退出")
        return
    
    all_stocks = data["all_stocks"]
    market = data["market"]
    
    if args.mode in ("selection", "full"):
        logger.info("=" * 50)
        logger.info("选股小龙虾 - 综合选股模式")
        
        result = run_selection_pipeline(
            all_stocks, market,
            kline=args.kline,
            trapped=args.trapped,
        )
        
        if result:
            # 保存JSON结果（供Web Dashboard读取）
            _save_json(result["top20"], market, result["report_path"])
            if not args.no_push:
                push_and_queue("selection", result["report_path"], market, result["top20"])
            log_elapsed(start_time, "综合选股", len(result["top20"]))
    
    if args.mode in ("overnight", "full"):
        logger.info("=" * 50)
        logger.info("选股小龙虾 - 隔夜套利模式")
        
        result = run_overnight_pipeline(all_stocks, market)
        
        if result:
            _save_json(result["top8"], market, result["report_path"])
            if not args.no_push:
                push_and_queue("overnight", result["report_path"], market, result["top8"])
            log_elapsed(start_time, "隔夜套利", len(result["top8"]))


if __name__ == "__main__":
    main()
