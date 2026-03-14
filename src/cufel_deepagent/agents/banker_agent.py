import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List
import os
# MCP 核心库
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_deepseek import ChatDeepSeek
# LangChain 相关
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_ollama import ChatOllama
# 你项目里的 create_agent（model, system_prompt, tools）
from langchain.agents import create_agent   # 假设这是你项目里能用的版本
from langchain_core.messages import HumanMessage,AIMessage
from langchain_community.chat_models import ChatTongyi
from deepagents import create_deep_agent
from src.cufel_deepagent.subagents.register import get_all_subagents
from src.cufel_deepagent.subagents.subagents import monetary_agent_system_prompt

from src.cufel_deepagent.tools.tools import get_monetary_market_info,write_report
# =============================================
# 配置部分
# =============================================
SERVER_SCRIPT = r"D:\\projects\deepagent\src\\cufel_deepagent\\mcp\servers\banker_server.py"

if not Path(SERVER_SCRIPT).is_file():
    raise FileNotFoundError(f"找不到 banker_server.py: {SERVER_SCRIPT}")

LLM_MODEL = "qwen3:8b"  # 根据你本地 Ollama 实际情况调整

sub_model = ChatDeepSeek(model='deepseek-chat')

report_agent_dict = {
    "name": "货币市场分析助手",
    "description": "专业分析货币市场 LPR、社融数据并撰写报告的专家",
    "model": sub_model, # 必须是实例化的对象
    "system_prompt": monetary_agent_system_prompt,
    "tools": [get_monetary_market_info, write_report] # 真正的工具函数列表
}


# =============================================
# 系统提示词（传给 create_agent 的 system_prompt）
# =============================================
SYSTEM_PROMPT = """
你是智能银行贷款经理（DeepAgent）。你负责处理客户贷款申请，并结合宏观市场分析做出最终决策。

### 【标准工作流】
1. **信息提取**：从用户输入中提取 5 个关键字段：applicant_id, loan_amount, loan_term_days, loan_installment, applicant_asset。
2. **市场咨询（调用子代理）**：在执行具体审批前，你应该先调用 `货币市场分析助手`（SubAgent）获取当前市场报告。
3. **贷款审批（调用 MCP 工具）**：
   - 使用 MCP 工具 `approve_or_reject_loan_application` 进行技术性审批。
   - **结合子代理的报告建议**：如果子代理报告显示市场流动性紧缩，你应在回复中对贷款要求更严苛；如果流动性宽松，则可更积极放款。
4. **最终回复**：告知客户审批结果，并同步说明当前的宏观市场背景（引用子代理生成的报告路径）。

### 【约束条件】
- 必须先确认用户信息齐全。
- 必须调用 SubAgent 撰写分析报告以作为审批附件。
- 提取 JSON 调用 MCP 工具时，确保数字类型严格准确。

示例交互：
Thought: 用户提供了完整的申请信息。我需要先让“货币市场分析助手”生成分析报告，再进行贷款审批。
Action: 货币市场分析助手
Action Input: "请生成当前货币市场分析报告，并给出贷款审批建议。"
"""
from src.cufel_deepagent.subagents.subagents import report_agent

registered_subagents = get_all_subagents()

# =============================================
# 主逻辑
# =============================================
async def run_banker_agent():
    print("=== banker MCP Agent 测试（使用 create_agent + messages 流） ===")

    # 1. 启动 MCP stdio 服务器
    params = StdioServerParameters(
        command="python",
        args=[SERVER_SCRIPT],
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            print("MCP 会话已建立，正在初始化...")
            await session.initialize()
            print("MCP 会话初始化完成")

            # 2. 加载工具
            mcp_tools = await load_mcp_tools(session)
            print(f"\n成功加载 {len(mcp_tools)} 个工具：")
            for t in mcp_tools:
                print(f"  - {t.name:<30} : {t.description[:60]}...")

            if not mcp_tools:
                print("警告：没有加载到任何工具！")
                return

            # 3. 创建 LLM
            llm = ChatOllama(
                model=LLM_MODEL,
                temperature=0.3,
            )
            #llm_qw = ChatTongyi(
            #    model='qwen-plus',
            #s)

            
            # 4. 创建 Agent（使用项目里的 create_agent）
            """
            banker_agent = create_agent(
                model=llm_qw,
                system_prompt=SYSTEM_PROMPT,
                tools=tools
            )
            """

            banker_agent = create_deep_agent(model=llm,system_prompt=SYSTEM_PROMPT,tools=mcp_tools,subagents=[report_agent_dict])
            # 5. 用 messages 列表管理对话历史
            # 格式：[{"role": "user"|"assistant", "content": "..."}]
            messages: List[Dict[str, str]] = []

            # =====================================
            # 第一轮：提交贷款申请
            # =====================================
            first_input = """
请帮我提交一笔贷款申请：
申请人ID: 123456
贷款金额: 80000 元
贷款天数: 20 天
分期期数: 12 期
申请人资产: 200000 元

并且告诉我当前货币市场的局势如何了？有相关报告吗？
            """.strip()

            print("\n" + "="*70)
            print("第一轮用户输入：")
            print(first_input)
            print("="*70 + "\n")

            # 记录用户输入
            messages.append(HumanMessage(content=first_input))
           
            # 调用 agent
            result1 = await banker_agent.ainvoke(input={
                "messages": messages  # 把完整历史传给 input
            })
            # 处理输出（兼容不同返回格式）
            ai_msg1 = result1['messages'][-1]
            messages.append(ai_msg1)


            print("第一轮 AI 回复：")
            print(ai_msg1.content)
            print("-"*70 + "\n")

            # =====================================
            # 第二轮：查询银行状态
            # =====================================
            second_input = "请告诉我现在的银行存款池还有多少？贷款审批情况如何？"

            print("\n" + "="*70)
            print("第二轮用户输入：")
            print(second_input)
            print("="*70 + "\n")

            messages.append(HumanMessage(content=second_input))

            # 再次构建完整上下文

            result2 = await banker_agent.ainvoke({
                "messages":messages 
            })

            ai_msg2 = result2['messages'][-1]
            messages.append(ai_msg2)

            print("第二轮 AI 回复：")
            print(ai_msg2.content)
            print("-"*70 + "\n")


            # 你可以继续加第三轮、第四轮...


# =============================================
# 运行入口
# =============================================
if __name__ == "__main__":
    try:
        asyncio.run(run_banker_agent())
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n发生错误：{str(e)}")
# =============================================
# 运行入口
# =============================================
if __name__ == "__main__":
    try:
        asyncio.run(run_banker_agent())
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n发生错误：{str(e)}")