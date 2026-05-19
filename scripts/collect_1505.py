#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 15:05 收盘数据采集脚本
Cron: 5 15 * * 1-5
功能：收盘后完整分析，全量K线+套牢盘，生成最终报告
"""
from datetime import datetime
from scripts.common import (
    setup_script_logging, fetch_and_prepare,
    run_selection_pipeline, push_and_queue, log_elapsed,
)


def _is_trading_day() -> bool:
    from datetime import datetime
    return datetime.now().weekday() < 5


def main():
    logger = setup_script_logging("collect_1505")
    logger.info("=" * 50)
    logger.info("选股小龙虾 - 15:05 收盘完整分析开始")
    
    if not _is_trading_day():
        logger.info("非交易日，跳过")
        return
    start_time = datetime.now()
    
    try:
        # 收盘后数据完整，强制刷新
        data = fetch_and_prepare(use_cache=False)
        if not data:
            return
        
        result = run_selection_pipeline(
            data["all_stocks"], data["market"],
            kline=True,      # 收盘后K线数据完整
            trapped=True,     # 套牢盘分析
            report_suffix="1505",
        )
        
        if result:
            push_and_queue("selection", result["report_path"], data["market"], result["top20"])
            log_elapsed(start_time, "15:05收盘分析", len(result["top20"]))
        
    except Exception as e:
        logger.exception(f"执行出错: {e}")
        raise


if __name__ == "__main__":
    main()
