import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("证券持仓管理系统")
DATA_FILE = Path(__file__).parent / "stock_portfolio.json"

def load_portfolio():
    """从 JSON 文件加载持仓数据"""
    if not DATA_FILE.exists():
        initial_data = {
            "portfolio_id": "PORTFOLIO-001",
            "account_name": "主账户",
            "positions": [
                {"name": "深空智能", "symbol": "688588", "quantity": 500,
                 "avg_cost": 85.0, "current_price": 72.5,
                 "take_profit": 102.0, "stop_loss": 76.5},
                {"name": "虚研科技", "symbol": "300789", "quantity": 300,
                 "avg_cost": 45.0, "current_price": 58.5,
                 "take_profit": 54.0, "stop_loss": 36.0}
            ]
        }
        save_portfolio(initial_data)
        return initial_data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_portfolio(data):
    """保存持仓数据到 JSON 文件"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def find_position(data, name):
    """根据名称查找持仓"""
    for pos in data["positions"]:
        if pos["name"] == name:
            return pos
    return None

@mcp.resource("portfolio://overview")
def get_portfolio_overview() -> str:
    """查看当前证券持仓状态"""
    pf = load_portfolio() # 能够在python里面导入这个数据，而后再用这个resource的组件，能够输出给agent查看
    lines = [f"--- 证券持仓 [{pf['portfolio_id']}] ---", "当前持仓:"]
    for pos in pf["positions"]:
        change = ((pos["current_price"] - pos["avg_cost"]) / pos["avg_cost"]) * 100
        status = "🔴 需清仓" if pos["current_price"] >= pos["take_profit"] or pos["current_price"] <= pos["stop_loss"] else "🟢 正常"
        lines.append(f"  {pos['name']}({pos['symbol']}): {pos['current_price']}元 | 盈亏:{change:+.1f}% | {status}")
    return "\n".join(lines)

@mcp.tool()
def update_price(item_name: str, new_price: float) -> str:
    """更新股票价格并检查止盈止损"""
    pos = find_position(load_portfolio(), item_name)
    if not pos:
        return f"股票不存在"
    # 寻找仓位，并且里面的现价会被调整成新价格，而后再储存，并且判断是否达到止盈止损的条件
    pos["current_price"] = new_price
    save_portfolio(load_portfolio())

    # 检查是否触发止盈止损
    if new_price >= pos["take_profit"]:
        return f"🔴 【止盈触发】{item_name} 当前价 {new_price}元 >= 止盈价 {pos['take_profit']}元，建议清仓！"
    elif new_price <= pos["stop_loss"]:
        return f"🔴 【止损触发】{item_name} 当前价 {new_price}元 <= 止损价 {pos['stop_loss']}元，建议清仓！"
    return f"🟢 {item_name} 当前价 {new_price}元，在正常范围内"

@mcp.prompt()
def stock_strategy() -> str:
    """证券投资策略指导"""
    return """
    你是证券投资专家。请按以下规则操作：

    1. 使用 portfolio://overview 查看持仓
    2. 价格更新后调用 update_price 检查止盈止损
    3. 止盈条件：当前价 >= 止盈价 → 清仓锁定收益
    4. 止损条件：当前价 <= 止损价 → 清仓控制风险
    5. 正常持有：止损价 < 当前价 < 止盈价 → 不操作

    示例：股票成本100元，止盈120元，止损80元
    - 涨到125元 → 触发止盈 → 清仓
    - 跌到75元 → 触发止损 → 清仓
    """