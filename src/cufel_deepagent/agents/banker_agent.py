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
# =============================================
# 配置部分
# =============================================
SERVER_SCRIPT = r"D:\\projects\deepagent\src\\cufel_deepagent\\mcp\servers\banker_server.py"

if not Path(SERVER_SCRIPT).is_file():
    raise FileNotFoundError(f"找不到 banker_server.py: {SERVER_SCRIPT}")

LLM_MODEL = "qwen3:8b"  # 根据你本地 Ollama 实际情况调整

# =============================================
# 系统提示词（传给 create_agent 的 system_prompt）
# =============================================
SYSTEM_PROMPT = """
你是银行贷款Agent。当用户提供贷款申请信息时，必须一步提取并转换为JSON格式调用工具。

【提取规则 - 必须严格执行】
1. 扫描用户输入，提取以下字段（忽略单位如“元”“天”，转换为数字）：
   - applicant_id: 整数，从“申请人ID:”或类似提取
   - loan_amount: 浮点数，从“贷款金额:”提取
   - loan_term_days: 整数，从“贷款天数:”提取
   - loan_installment: 整数，从“分期期数:”提取
   - applicant_asset: 浮点数，从“申请人资产:”提取
2. 如果5个字段全齐 → 立即构造{"request": {...}}并调用approve_or_reject_loan_application
3. 如果缺少字段 → 只回复“缺少[字段名]，请补充”
4. 不要改值、不要默认、严格数字类型

示例输入："申请人ID: 123456\n贷款金额: 80000 元\n贷款天数: 20 天\n分期期数: 12 期\n申请人资产: 200000 元"
提取输出：
Thought: 所有字段齐全，提取并调用。
Action: approve_or_reject_loan_application
Action Input: {"request": {"applicant_id": 123456, "loan_amount": 80000.0, "loan_term_days": 20, "loan_installment": 12, "applicant_asset": 200000.0}}

现在处理用户请求。
"""

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
            tools = await load_mcp_tools(session)
            print(f"\n成功加载 {len(tools)} 个工具：")
            for t in tools:
                print(f"  - {t.name:<30} : {t.description[:60]}...")

            if not tools:
                print("警告：没有加载到任何工具！")
                return

            # 3. 创建 LLM
            llm = ChatOllama(
                model=LLM_MODEL,
                temperature=0.3,
            )

            llm_dp = ChatDeepSeek(
                model = "deepseek-reasoner",
            )
            # 4. 创建 Agent（使用项目里的 create_agent）
            banker_agent = create_agent(
                model=llm,
                system_prompt=SYSTEM_PROMPT,
                tools=tools
            )

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