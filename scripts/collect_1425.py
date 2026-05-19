#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 14:25 午盘更新脚本
Cron: 25 14 * * 1-5
功能：午后盘更新，K线+套牢盘全量分析
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
    logger = setup_script_logging("collect_1425")
    logger.info("=" * 50)
    logger.info("选股小龙虾 - 14:25 午盘更新开始")
    
    if not _is_trading_day():
        logger.info("非交易日，跳过")
        return
    start_time = datetime.now()
    
    try:
        # 午盘数据，强制刷新
        data = fetch_and_prepare(use_cache=False)
        if not data:
            return
        
        result = run_selection_pipeline(
            data["all_stocks"], data["market"],
            kline=True,
            trapped=True,
            report_suffix="1425",
        )
        
        if result:
            push_and_queue("selection", result["report_path"], data["market"], result["top20"])
            log_elapsed(start_time, "14:25午盘更新", len(result["top20"]))
        
    except Exception as e:
        logger.exception(f"执行出错: {e}")
        raise


if __name__ == "__main__":
    main()
