from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from src.cufel_deepagent.create_agents.banking_agent import create_banking_agent
from src.cufel_deepagent.create_agents.macro_eco import create_macro_agent
from src.cufel_deepagent.create_agents.corp_researching import create_corp_researcher_agent
from typing import TypedDict,List,Any
import json
from src.cufel_deepagent.agents.prompts import BANKING_SYSTEM_PROMPT,CORP_SYSTEM_RPOMPT,MACRO_ECO_SYSTEM_PROMPT
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph,END
from langgraph.checkpoint.memory import MemorySaver

class BankingState(TypedDict):
    loan_request:dict
    market_report:str
    due_diligence_report:str
    final_decision:Any
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
            print("\n🚀 [System] MCP Session 建立成功，Agent 初始化完成。")
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
                print("\n🟦 [Node: banker_start] 正在处理贷款登记...")
                loan_req = state["loan_request"]
                print('当前贷款信息为：\n',loan_req)
                # 让 agent 帮我们把 dict 转成正确的 tool calling 格式
                prompt = f"""
                    现在请调用 register_loan_application 工具登记这笔申请：
                    {json.dumps(loan_req, ensure_ascii=False, indent=2)}
                    登记成功后不需要做其他操作。
                    """
                
                result = await banker_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
                        # 不管 agent 输出什么，我们自己再读一次状态，确保拿到最新值
                print(f"✅ [banker_start] 已成功登记 {loan_req.get('company')} 的贷款申请。")
                print(f"banker_start 节点输出结果：{result['messages'][-1].content}")
                status_res = await session.read_resource("bank:status") # 用这个mcp的resource工具来获取这个info_system的现状，读取并存入到这个state之中
                if status_res and status_res.contents:
                        
                    # 1. 从 TextResourceContents 对象中提取 text 字符串
                    raw_text = status_res.contents[0].text 
                    
                    # 2. 将 JSON 字符串解析为字典
                    try:
                        info_dict = json.loads(raw_text)
                        state["info_system"] = info_dict
                    except json.JSONDecodeError:
                        print(f"❌ [banker_start] 无法解析资源内容: {raw_text}")
                        state["info_system"] = {}
                    pool = state["info_system"].get("deposit_pool", 0)
                    print(f"📊 [banker_start] 当前银行存款池: {pool} 元")
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
                print("\n🟧 [Node: macro_report] 宏观研究员正在分析市场动态...")
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
                state["market_report"] = result['messages'][-1].content
                print("📝 [macro_report] 货币市场分析报告生成完毕: \n")
                print(state["market_report"])
                # 这个out_put能否得到处理？
                return state

            def corp_research_node(state: BankingState) -> BankingState:
                """
                能够读取这个 bankingstate 里面的 info_system 以及 loan_request 两个信息，
                传入到这个 agent 的 prompt 进行 invoke。
                在 prompt 里面还需要简单说明其工作流，如调用 rag_retrieve 的工具列表,以及获取skill之后能够读取内容以及follow its instruction
                （though this has been included in its system prompt）
                """
                print("\n🟪 [Node: corp_research] 企业研究员正在执行尽职调查...")
                loan_req = state.get("loan_request", {})
                info_sys = state.get("info_system", {})    

                context_info = f"""
                    本次贷款申请信息：
                    {json.dumps(loan_req, ensure_ascii=False, indent=2)}


                    当前银行系统状态（参考）：
                    - 存款池余额：{info_sys.get('deposit_pool', 'N/A')} 元
                    - 日利率：{info_sys.get('daily_int_rate_percent', 'N/A')} %
                    - 待处理申请数：{info_sys.get('pending_applications', 'N/A')}
                    """
                # 核心用户提示词（重点强化工作流）
                user_prompt = f"""请为以下企业贷款申请执行**企业财务背调分析**（corporate_research 技能）。
                    {context_info}
                    ### 任务要求（严格执行）：
                    1. **立即**先调用工具 `read_skill_instructions("corporate_research")` 获取最新 SKILL.md 指引（这是你的第一步，必做！）。
                    2. 阅读完技能指引后，**严格按照技能中的「研究方法论」** 执行：
                    3. 最后严格使用技能提供的**报告模板**，输出 400–500 字的**三段式**信贷风险简评报告。
                    - 所有关键数据必须标注 `chunk_id` 或页码+类型
                    - 结尾必须给出明确的信贷建议（可适度支持 / 需严格控制 / 暂不宜介入 等）

                    请现在开始执行背调分析，直接输出最终报告（不要输出中间思考过程）。
                    """
                
                result = corp_researcher.invoke({
                    "messages": [{"role": "user", "content": user_prompt}]
                    })
                # 提取报告（根据你 create_agent 的返回结构调整）
                state["due_diligence_report"] = result['messages'][-1].content
                print("📑 [corp_research] 企业财务背调报告生成完毕:\n")
                print(state['due_diligence_report'])
                # 这个result的ouput参数是否可行
                return state

            async def banker_decide_node(state: BankingState) -> BankingState:
                """
                在前面这个工作流程走下来之后，能够让banker读取两篇报告，按照mcp里面的prompt指导，综合决定是否发放贷款，完成贷款审批
                """
                print("\n⚖️ [Node: banker_decide] Banker 正在进行最终综合评审...")
                prompt = f"""
                市场报告：
                {state['market_report']}
                尽调报告：
                {state['due_diligence_report']}
                贷款申请：
                {state['loan_request']}
                当前系统信息：
                {json.dumps(state.get('info_system', {}), ensure_ascii=False, indent=2)}

                请综合以上信息，给出最终贷款决策。
                **必须**使用 submit_loan_decision 工具提交结构化结果，不要直接写文本结论，并返回这个submit_loan_decision的返回结果
                决策理由请控制在50字以内。
                """
                result = await banker_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}) # 这里应该进行一次结构化的输出？
                #对结果进行读取
                # 尝试从结果中提取工具调用返回值

                # 获取最后一条消息
                last_msg = result["messages"][-1]
                print(f"返回最终决策结果：\n{last_msg}")
                # 路径 A: 如果 Agent 刚发出了 Tool Call 指令 (AIMessage)
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                    for call in last_msg.tool_calls:
                        if call["name"] == "submit_loan_decision":
                            # 直接拿 Agent 想传入的参数，这通常就是我们要的决策
                            state["final_decision"] = call["args"]
                            print("🏁 [banker_decide] 已通过工具提交结构化决策。")
                            return state

                # 路径 B: 如果工具已经执行完，最后一项是 ToolMessage
                # 这种情况通常发生在你的 Node 内部运行了完整的 ReAct 循环
                for msg in reversed(result["messages"]):
                    if msg.type == "tool" and msg.name == "submit_loan_decision":
                        # msg.content 通常是工具返回的字符串，需要 json.loads
                        try:
                            state["final_decision"] = json.loads(msg.content)
                            print("🏁 [banker_decide] 已提取到工具返回的决策结果。")
                        except:
                            state["final_decision"] = msg.content
                        return state

                # 兜底
                state["final_decision"] = {"approve": False, "simple_reason_within_50_words": "未能提取到结构化决策"}
                print("❌ [banker_decide] 未能正确提取到决策。")
                return state
            
            print("\n⚙️ [System] 正在编译工作流图形...")
            workflow = StateGraph(BankingState)

            workflow.add_node('banker_start',banker_start)
            workflow.add_node('macro_report',macro_report_node)
            workflow.add_node('corp_research',corp_research_node)
            workflow.add_node('banker_decide',banker_decide_node)

            workflow.set_entry_point('banker_start')
            workflow.add_edge('banker_start','macro_report')
            workflow.add_edge('macro_report','corp_research')
            workflow.add_edge('corp_research','banker_decide')
            workflow.add_edge('banker_decide',END)

            app = workflow.compile(MemorySaver())

            # 准备初始状态
            
            initial_state: BankingState = {
        "loan_request": {
            "company": "比亚迪", 
            "amount": 500000000, 
            "purpose": "用于固态电池生产线建设",
            'applicant_id':100234,
            'loan_term_days':30,
            'loan_installment':24,
            'applicant_asset':50000000000
        },
        "info_system": {},          # 与 TypedDict 对齐
        "market_report": "",
        "due_diligence_report": "",
        "final_decision": ""
    }
            
            # 运行整个流程
            print("\n🏃 [System] 开始执行 AInvoke 流程...")
            final_state = await app.ainvoke(initial_state,config={'configurable':{'thread_id':'loan_process_001'}})
            
            print("\n" + "—"*50)
            print("✨ 【任务流结束】 ✨")
            print(f"✅ 最终决策结果: {json.dumps(final_state['final_decision'], ensure_ascii=False, indent=2)}")
            # 注意：这里改为 final_state.get('info_system') 确保不报错
            print(f"💰 最终银行快照: {final_state.get('info_system')}")
            print("—"*50 + "\n")

import asyncio
asyncio.run(main_banking_system())