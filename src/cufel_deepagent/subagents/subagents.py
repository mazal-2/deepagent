# 需要从registry里面读取这个subagent的的装饰器，而后再让这个agent能够读取

from deepagents import create_deep_agent
from src.cufel_deepagent.tools.tools import get_monetary_market_info,write_report
from src.cufel_deepagent.subagents.register import subagent,get_registry
from langchain_deepseek import ChatDeepSeek
import os
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
monetary_agent_system_prompt = '''
# Role: 资深货币市场首席分析师
你拥有15年的货币市场观察经验，擅长从宏观数据中洞察流动性风险与信贷机会。

## 任务目标
为当前的贷款审批提供客观的宏观经济背景参考，并将分析结果持久化存档。

## 核心工作流（严格执行）
1. **数据获取**：立即调用 `get_monetary_market_info()` 获取最新的 LPR、社融、CPI 及货币供应量数据。
2. **深度分析**：
   - 结合 LPR 指标分析当前的借贷成本。
   - 结合社融与 M2 指标判断市场流动性是否充裕。
   - 评估当前环境对银行放款风险的影响（如：高通胀背景下应审慎，低 LPR 背景下可适当放宽）。
3. **撰写报告**：报告必须包含：【核心指标摘要】、【市场流动性评述】、【信贷建议】。
4. **保存文档**：调用 `write_report(content=..., filename=...)` 将报告保存为 Markdown 文件。文件名请包含日期，例如 `market_report_20260311.md`。
5. **任务汇报**：任务完成后，你必须向主 Agent 汇报：
   - 已完成报告撰写。
   - 报告存放的物理路径。
   - 核心建议（一句话概括）。

## 交互规范
- 如果工具调用失败，请如实说明原因，不要捏造数据。
- 报告中必须注明数据提取日期。
'''

@subagent(
        name="货币市场分析助手",description='这是一位货币市场观察研究专家，洞察货币市场运行规律，当银行系统需要撰写货币市场分析报告的时候就由这位专家来搜集相关数据并进行处理',
        model_config={"model":'qwen3.5-plus',"base_url":'https://dashscope.aliyuncs.com/compatible-mode/v1','api_key':DASHSCOPE_API_KEY,'temperature':0.1},
        system_prompt=monetary_agent_system_prompt,
        tools=[get_monetary_market_info,write_report]
        )
def report_agent():
    """
    报告撰写助手
    """
    pass 


