from mcp.server.fastmcp import FastMCP
import json
import os

mcp = FastMCP("智能避险管家")

# 定义数据路径
DATA_PATH = "my_gold_data.json"

def load_data():
    """读取银行账户信息，若不存在则初始化"""
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    # 默认初始资金：10000美元，5盎司黄金
    return {"usd": 10000.0, "gold": 5.0}

def save_data(data):
    """持久化保存账户数据"""
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ============ Tool: 买入与卖出 ============

@mcp.tool()
def buy_gold(ounces: float, current_price: float) -> str:
    """
    买入黄金工具。
    参数:
        ounces: 拟购买的数量（盎司）
        current_price: 当前市场实时金价（美元/盎司）
    """
    data = load_data()
    total_cost = ounces * current_price
    
    if data["usd"] < total_cost:
        return f"交易失败：余额不足。需 ${total_cost:.2f}，当前仅有 ${data['usd']:.2f}"
    
    data["usd"] -= total_cost
    data["gold"] += ounces
    save_data(data)
    
    return f"交易成功！以 ${current_price}/盎司 买入 {ounces} 盎司。当前余额: ${data['usd']:.2f}, 持仓: {data['gold']} 盎司。"

@mcp.tool()
def sell_gold(ounces: float, current_price: float) -> str:
    """
    卖出黄金工具。
    参数:
        ounces: 拟卖出的数量（盎司）
        current_price: 当前市场实时金价
    """
    data = load_data()
    
    if data["gold"] < ounces:
        return f"交易失败：持仓不足。当前仅有 {data['gold']} 盎司。"
    
    earnings = ounces * current_price
    data["gold"] -= ounces
    data["usd"] += earnings
    save_data(data)
    
    return f"交易成功！以 ${current_price}/盎司 卖出 {ounces} 盎司。获得 ${earnings:.2f}。当前持仓: {data['gold']} 盎司。"

# ============ Resource: 账户看板 ============

@mcp.resource("bank://account/dashboard")
def my_gold_data_json() -> str:
    """让 Agent 随时调取并查看当前最新的账户资产负债表"""
    data = load_data()
    # 计算总资产（假设一个参考价）
    total_value = data["usd"] + (data["gold"] * 500.0) 
    return f"""
    ### 深智银行资产看板
    - 现金余额: ${data['usd']:.2f}
    - 黄金持仓: {data['gold']:.2f} 盎司
    - 预估总资产: ${total_value:.2f} (基于参考价 $500/oz)
    """

# ============ Prompt: 交易策略 ============

@mcp.prompt()
def gold_trading_strategy(market_sentiment: str = "中性") -> str:
    """教导 Agent 如何进行黄金避险交易的思维模板"""
    return f"""
    你现在是深智银行的首席风险官。
    当前市场情绪：{market_sentiment}。
    
    请按以下逻辑执行：
    1. 首先通过 `bank://account/dashboard` 确认用户资产。
    2. 如果用户提到的外部通胀率 > 3%，优先考虑 `buy_gold` 进行避险。
    3. 如果金价相比买入成本已有 20% 涨幅，提示用户可以使用 `sell_gold` 获利了结。
    4. 始终保持账户中至少有 20% 的现金储备。
    """

if __name__ == "__main__":
    mcp.run()