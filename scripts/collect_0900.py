#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 09:00 早盘数据采集脚本
Cron: 0 9 * * 1-5
功能：开盘前准备，获取全市场数据，执行初步筛选
"""
from datetime import datetime
from scripts.common import (
    setup_script_logging, fetch_and_prepare,
    run_selection_pipeline, push_and_queue, log_elapsed,
)


def _is_trading_day() -> bool:
    from datetime import datetime
    return datetime.now().weekday() < 5  # 周一~周五


def main():
    logger = setup_script_logging("collect_0900")
    logger.info("=" * 50)
    logger.info("选股小龙虾 - 09:00 早盘数据采集开始")
    
    if not _is_trading_day():
        logger.info("非交易日，跳过")
        return
    start_time = datetime.now()
    
    try:
        # 09:00盘前数据可能不全，不使用缓存（强制刷新）
        data = fetch_and_prepare(use_cache=False)
        if not data:
            return
        
        result = run_selection_pipeline(
            data["all_stocks"], data["market"],
            kline=False,  # 盘前K线数据不全
            trapped=False,
            report_suffix="0900",
        )
        
        if result:
            push_and_queue("selection", result["report_path"], data["market"], result["top20"])
            log_elapsed(start_time, "09:00早盘采集", len(result["top20"]))
        
    except Exception as e:
        logger.exception(f"执行出错: {e}")
        raise


if __name__ == "__main__":
    main()
