#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 14:40 隔夜套利专项脚本 【核心策略】
Cron: 40 14 * * 1-5
功能：尾盘强势股筛选，次日高开概率高
14:50前必须推送微信！
"""
from datetime import datetime
from scripts.common import (
    setup_script_logging, fetch_and_prepare,
    run_overnight_pipeline, push_and_queue, log_elapsed,
)


def _is_trading_day() -> bool:
    from datetime import datetime
    return datetime.now().weekday() < 5


def main():
    logger = setup_script_logging("collect_1440")
    logger.info("=" * 60)
    logger.info("选股小龙虾 - 14:40 隔夜套利专项开始")
    
    if not _is_trading_day():
        logger.info("非交易日，跳过")
        return
    start_time = datetime.now()
    
    try:
        data = fetch_and_prepare(use_cache=False)
        if not data:
            return
        
        result = run_overnight_pipeline(data["all_stocks"], data["market"])
        
        if result:
            push_and_queue("overnight", result["report_path"], data["market"], result["top8"])
            log_elapsed(start_time, "14:40隔夜套利", len(result["top8"]))
            
            # 超时警告
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > 600:
                logger.warning("⚠️ 执行超时！可能无法在14:50前推送")
        
    except Exception as e:
        logger.exception(f"隔夜套利执行出错: {e}")
        raise


if __name__ == "__main__":
    main()
