#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股小龙虾 - 持仓跟踪器
管理持仓记录的增删改查，JSON持久化存储
"""
import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config.config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# 持仓数据文件
POSITION_FILE = os.path.join(OUTPUT_DIR, "positions.json")


def _load_positions() -> List[Dict]:
    """加载持仓数据"""
    if not os.path.exists(POSITION_FILE):
        return []
    try:
        with open(POSITION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载持仓数据失败: {e}")
        return []


def _save_positions(positions: List[Dict]) -> bool:
    """保存持仓数据"""
    try:
        os.makedirs(os.path.dirname(POSITION_FILE), exist_ok=True)
        with open(POSITION_FILE, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存持仓数据失败: {e}")
        return False


def add_position(
    code: str,
    name: str,
    buy_price: float,
    shares: int,
    strategy: str = "selection",
    buy_date: str = None,
    stop_loss: float = None,
    take_profit: float = None,
    notes: str = "",
) -> Dict:
    """
    添加新持仓
    
    Args:
        code: 股票代码
        name: 股票名称
        buy_price: 买入价格
        shares: 持股数量
        strategy: 策略类型 (selection/overnight)
        buy_date: 买入日期 (YYYY-MM-DD)，默认今天
        stop_loss: 止损价，默认买入价-5%
        take_profit: 止盈价，默认买入价+10%
        notes: 备注
    
    Returns:
        持仓记录字典
    """
    positions = _load_positions()
    
    # 检查是否已存在
    for p in positions:
        if p["code"] == code and p["status"] == "holding":
            logger.warning(f"股票 {code} 已有持仓，请先卖出或更新")
            return p
    
    if buy_date is None:
        buy_date = datetime.now().strftime("%Y-%m-%d")
    
    if stop_loss is None:
        stop_loss = round(buy_price * 0.95, 2)  # 默认-5%止损
    
    if take_profit is None:
        take_profit = round(buy_price * 1.10, 2)  # 默认+10%止盈
    
    position = {
        "id": f"{code}_{buy_date}_{int(datetime.now().timestamp())}",
        "code": code,
        "name": name,
        "buy_price": round(buy_price, 2),
        "shares": shares,
        "strategy": strategy,
        "buy_date": buy_date,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "notes": notes,
        "status": "holding",  # holding/sold
        "sell_price": None,
        "sell_date": None,
        "sell_reason": None,
        "profit_pct": None,
        "hold_days": 0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    
    positions.append(position)
    _save_positions(positions)
    
    logger.info(f"添加持仓: {name}({code}) {shares}股 @ {buy_price}")
    return position


def sell_position(
    code: str,
    sell_price: float,
    sell_reason: str = "manual",
    sell_date: str = None,
) -> Optional[Dict]:
    """
    卖出持仓
    
    Args:
        code: 股票代码
        sell_price: 卖出价格
        sell_reason: 卖出原因 (manual/score_drop/stop_loss/take_profit/time_stop/kline_down/trapped)
        sell_date: 卖出日期，默认今天
    
    Returns:
        更新后的持仓记录，未找到返回None
    """
    positions = _load_positions()
    
    for p in positions:
        if p["code"] == code and p["status"] == "holding":
            if sell_date is None:
                sell_date = datetime.now().strftime("%Y-%m-%d")
            
            buy_date = datetime.strptime(p["buy_date"], "%Y-%m-%d")
            sell_dt = datetime.strptime(sell_date, "%Y-%m-%d")
            hold_days = (sell_dt - buy_date).days
            
            profit_pct = round((sell_price - p["buy_price"]) / p["buy_price"] * 100, 2)
            
            p["status"] = "sold"
            p["sell_price"] = round(sell_price, 2)
            p["sell_date"] = sell_date
            p["sell_reason"] = sell_reason
            p["profit_pct"] = profit_pct
            p["hold_days"] = hold_days
            p["updated_at"] = datetime.now().isoformat()
            
            _save_positions(positions)
            
            logger.info(f"卖出持仓: {p['name']}({code}) @ {sell_price}, 盈亏: {profit_pct}%")
            return p
    
    logger.warning(f"未找到持仓: {code}")
    return None


def update_position(code: str, **kwargs) -> Optional[Dict]:
    """
    更新持仓字段
    
    Args:
        code: 股票代码
        **kwargs: 要更新的字段
    
    Returns:
        更新后的持仓记录，未找到返回None
    """
    positions = _load_positions()
    
    for p in positions:
        if p["code"] == code and p["status"] == "holding":
            for key, value in kwargs.items():
                if key in p:
                    p[key] = value
            p["updated_at"] = datetime.now().isoformat()
            _save_positions(positions)
            return p
    
    return None


def get_positions(status: str = "holding") -> List[Dict]:
    """
    获取持仓列表
    
    Args:
        status: "holding" 或 "sold" 或 "all"
    
    Returns:
        持仓记录列表
    """
    positions = _load_positions()
    
    if status == "all":
        return positions
    
    return [p for p in positions if p["status"] == status]


def get_position(code: str) -> Optional[Dict]:
    """获取单只股票持仓"""
    positions = _load_positions()
    for p in positions:
        if p["code"] == code:
            return p
    return None


def delete_position(code: str) -> bool:
    """删除持仓记录（慎用）"""
    positions = _load_positions()
    positions = [p for p in positions if p["code"] != code]
    return _save_positions(positions)


def clear_all_positions() -> bool:
    """清空所有持仓（慎用）"""
    if os.path.exists(POSITION_FILE):
        os.remove(POSITION_FILE)
    logger.warning("所有持仓记录已清空")
    return True


def calculate_position_value(current_prices: Dict[str, float]) -> Dict:
    """
    计算持仓市值和盈亏
    
    Args:
        current_prices: {code: price} 当前价格字典
    
    Returns:
        {
            "total_cost": 总成本,
            "total_value": 总市值,
            "total_profit": 总盈亏,
            "total_profit_pct": 总盈亏率%,
            "positions": [{...}, ...]
        }
    """
    positions = get_positions("holding")
    
    total_cost = 0
    total_value = 0
    detailed = []
    
    for p in positions:
        code = p["code"]
        buy_price = p["buy_price"]
        shares = p["shares"]
        current_price = current_prices.get(code, buy_price)
        
        cost = buy_price * shares
        value = current_price * shares
        profit = value - cost
        profit_pct = round((current_price - buy_price) / buy_price * 100, 2)
        
        total_cost += cost
        total_value += value
        
        detailed.append({
            **p,
            "current_price": current_price,
            "market_value": round(value, 2),
            "unrealized_profit": round(profit, 2),
            "unrealized_profit_pct": profit_pct,
        })
    
    total_profit = total_value - total_cost
    total_profit_pct = round(total_profit / total_cost * 100, 2) if total_cost > 0 else 0
    
    return {
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_profit": round(total_profit, 2),
        "total_profit_pct": total_profit_pct,
        "position_count": len(positions),
        "positions": detailed,
    }


# ============ CLI 接口 ============

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="持仓管理工具")
    parser.add_argument("action", choices=["add", "sell", "list", "clear"], help="操作")
    parser.add_argument("--code", help="股票代码")
    parser.add_argument("--name", help="股票名称")
    parser.add_argument("--price", type=float, help="价格")
    parser.add_argument("--shares", type=int, help="股数")
    parser.add_argument("--reason", default="manual", help="卖出原因")
    parser.add_argument("--strategy", default="selection", help="策略类型")
    
    args = parser.parse_args()
    
    if args.action == "add":
        if not all([args.code, args.name, args.price, args.shares]):
            print("添加持仓需要: --code --name --price --shares")
            exit(1)
        pos = add_position(args.code, args.name, args.price, args.shares, args.strategy)
        print(f"已添加: {pos['name']}({pos['code']}) {pos['shares']}股")
    
    elif args.action == "sell":
        if not all([args.code, args.price]):
            print("卖出需要: --code --price")
            exit(1)
        pos = sell_position(args.code, args.price, args.reason)
        if pos:
            print(f"已卖出: {pos['name']}({pos['code']}) 盈亏: {pos['profit_pct']}%")
        else:
            print(f"未找到持仓: {args.code}")
    
    elif args.action == "list":
        positions = get_positions("all")
        print(f"共 {len(positions)} 条记录")
        for p in positions:
            status = "持有" if p["status"] == "holding" else "已卖"
            print(f"[{status}] {p['name']}({p['code']}) {p['shares']}股 @ {p['buy_price']}")
    
    elif args.action == "clear":
        clear_all_positions()
        print("已清空所有持仓")
