#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 09:35 盘中更新脚本
Cron: 35 9 * * 1-5
功能：开盘5分钟后快速更新，验证盘前选股
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
    logger = setup_script_logging("collect_0935")
    logger.info("=" * 50)
    logger.info("选股小龙虾 - 09:35 盘中更新开始")
    
    if not _is_trading_day():
        logger.info("非交易日，跳过")
        return
    start_time = datetime.now()
    
    try:
        # 强制刷新数据（开盘后行情已更新）
        data = fetch_and_prepare(use_cache=False)
        if not data:
            return
        
        result = run_selection_pipeline(
            data["all_stocks"], data["market"],
            kline=True,   # 开盘后K线数据可用
            trapped=False,
            report_suffix="0935",
        )
        
        if result:
            push_and_queue("selection", result["report_path"], data["market"], result["top20"])
            log_elapsed(start_time, "09:35盘中更新", len(result["top20"]))
        
    except Exception as e:
        logger.exception(f"执行出错: {e}")
        raise


if __name__ == "__main__":
    main()
