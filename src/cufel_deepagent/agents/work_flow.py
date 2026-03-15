from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from cufel_deepagent.create_agents.banking_agent import create_banking_agent
from cufel_deepagent.create_agents.macro_eco import create_macro_agent
from cufel_deepagent.create_agents.corp_researching import create_corp_researcher_agent
from typing import TypedDict,List
import json
from src.cufel_deepagent.agents.prompts import BANKING_SYSTEM_PROMPT,CORP_SYSTEM_RPOMPT,MACRO_ECO_SYSTEM_PROMPT
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph,END
from langgraph.checkpoint.memory import MemorySaver

class BankingState(TypedDict):
    loan_request:dict
    market_report:str
    due_diligence_report:str
    final_decision:str
    info_system:dict

async def main_banking_system():
    """
    集成整个banking_system
    """
    SERVER_SCRIPT = r"D:\\projects\deepagent\src\\cufel_deepagent\\mcp\\servers\\banker_server.py"

    params = StdioServerParameters(
        command='python',
        args=[SERVER_SCRIPT]
    )

    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            llm_banker = ChatDeepSeek(model='deepseek-chat',temperature=0.2) 
            llm_macro = ChatDeepSeek(model='deepseek-chat',temperature=0.5)
            llm_corp = ChatDeepSeek(model='deepseek-chat',temperature=0.3)

            banker_agent = await create_banking_agent(llm_banker,session,BANKING_SYSTEM_PROMPT)
            macro_researcher = create_macro_agent(llm=llm_macro,system_prompt=MACRO_ECO_SYSTEM_PROMPT)
            corp_researcher = create_corp_researcher_agent(llm=llm_corp,system_prompt=CORP_SYSTEM_RPOMPT)

            

            async def banker_start(state:BankingState) -> BankingState:
                """
                1,贷款处理：由banker接收client的贷款申请，将用户的贷款申请存入到info_system之中，由agent调用mcp里面的工具register_loan_application将信息存入
                同时这个info在state里面也会被反映出来
                2，调用这个mcp里面的检测当前银行系统的工具，将当前的info_system传入到这个state里面，后面能够在两位研究员写报告的时候提供参考
                """
                
                loan_req = state["loan_request"]
                # 让 agent 帮我们把 dict 转成正确的 tool calling 格式
                prompt = f"""
                    现在请调用 register_loan_application 工具登记这笔申请：
                    {json.dumps(loan_req, ensure_ascii=False, indent=2)}
                    登记成功后不需要做其他操作。
                    """
                
                await banker_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
                        # 不管 agent 输出什么，我们自己再读一次状态，确保拿到最新值
                status_res = await session.read_resource("bank:status") # 用这个mcp的resource工具来获取这个info_system的现状，读取并存入到这个state之中
                if status_res and status_res.contents:
                        state["info_system"] = status_res.contents[0]
                        # 早停（可选）
                        if state["info_system"].get("deposit_pool", 0) < loan_req.get("amount", 0):
                            state["final_decision"] = "Rejected: 现金池不足"
                        return state
            

            def macro_report_node(state: BankingState) -> BankingState:
                """
                能够读取这个 bankingstate 里面的 info_system 以及 loan_request 两个信息，
                传入到这个 agent 的 prompt 进行 invoke。
                在 prompt 里面还需要简单说明其工作流，如调用 macro 的工具列表
                （though this has been included in its system prompt）
                """
                loan_req = state.get("loan_request", {})
                info_sys = state.get("info_system", {})

                # 准备上下文信息
                context_info = f"""
            当前银行系统状态（来自 banker_server）：
            - 存款池余额：{info_sys.get('deposit_pool', '未知')} 元
            - 当前日利率：{info_sys.get('daily_int_rate_percent', '未知')} %
            - 待处理申请数：{info_sys.get('pending_applications', '未知')}
            - 最后更新时间：{info_sys.get('last_updated', '未知')}

            本次贷款申请概要：
            {json.dumps(loan_req, ensure_ascii=False, indent=2)}
            """

                user_prompt = f"""请为以下贷款申请生成一份专业的货币市场分析报告。

            {context_info}

            任务要求：
            1. 严格按照你系统提示中定义的工作流执行：
            - 先调用 read_skill_instructions("monetary_market_report") 确认最新执行步骤
            - 然后调用 run_skill_scripts 执行 get_current_info.py 获取最新宏观数据
            - 如有需要，调用 read_skill_ref 理解指标含义
            - 最后调用 read_skill_asset 获取 report_template.md 并填充生成报告

            2. 报告必须结合当前银行存款池情况和本次贷款金额，给出对本次贷款审批有实际参考价值的结论。
            例如：当前流动性是否宽松？利率走势是否利于大额中长期贷款？是否存在系统性风险信号？

            请开始执行。
            """

                result = macro_researcher.invoke({
                    "messages": [{"role": "user", "content": user_prompt}]
                })

                # 假设 agent 的输出结构中 "output" 是最终报告文本
                # 如果你的 agent 返回格式不同，请相应调整
                state["market_report"] = result.get("output", "（报告生成失败）")
                # 这个out_put能否得到处理？
                return state

            def corp_research_node(state: BankingState) -> BankingState:
                """corp_researcher 做尽调"""
                result = corp_researcher.invoke({
                    "messages": [{"role": "user", "content": f"Due diligence for {state['loan_request']['company']}"}]
                })
                state["due_diligence_report"] = result["output"]
                return state

            async def banker_decide_node(state: BankingState) -> BankingState:
                """banker 综合两份报告 + system_info 做最终决策"""

                prompt = f"""
                市场报告：{state['market_report']}
                尽调报告：{state['due_diligence_report']}
                当前系统信息：{state['system_info']}
                请给出最终贷款决策，并更新现金池。
                """
                result = await banker_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
                
                state["final_decision"] = result["output"]
                # 更新 system_info（现金池变动、记录保存）
                state["system_info"] = result.get("system_info", state["system_info"])
                return state
            
            workflow = StateGraph(BankingState)

            workflow.add_node('banker_start',banker_start)
            workflow.add_node('macro_report',macro_report_node)
            workflow.add_node('corp_research',corp_research_node)
            workflow.add_node('banker_decide',banker_decide_node)

            workflow.set_entry_point('banker_start')
            workflow.add_edge('banker_start','macro_report')
            workflow.add_edge('macro_report','corp_research')
            workflow.add_edge('banker_decide',END)

            app = workflow.compile(MemorySaver())

            # 准备初始状态
            initial_state: BankingState = {
                "loan_request": {"company": "比亚迪", "amount": 5000000000, "purpose": "流动资金"},
                "system_info": {},
                "market_report": "",
                "due_diligence_report": "",
                "final_decision": "",
                "history": []
            }
            
            # 运行整个流程
            final_state = await app.ainvoke(initial_state)
            print("✅ 最终决策:", final_state["final_decision"])
            print("💰 最终现金池:", final_state["system_info"].get("cash_pool"))
