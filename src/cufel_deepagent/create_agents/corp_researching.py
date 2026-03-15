from typing import List, Optional
from langchain.agents import create_agent
from src.cufel_deepagent.tools.corp_researcher_tool import rag_retrieve
from src.cufel_deepagent.tools.tools import read_skill_instructions

def create_corp_researcher_agent(llm, system_prompt: str = 'none', extra_tools: Optional[list] = None):
    """
    创建企业背调专员 Agent (Corporate Researcher)。
    
    :param llm: 外部注入的模型实例 (建议使用 DeepSeek 或 GPT-4 以处理复杂的逻辑判断)
    :param system_prompt: 注入的系统提示词，定义了其“技能驱动”的工作模式
    :param extra_tools: 可选。如果未来有新的 RAG 工具或征信 API，可以动态注入
    """
    
    # 基础工具集：包括核心的 RAG 检索和技能说明读取
    base_tools = [rag_retrieve, read_skill_instructions]
    
    if extra_tools:
        base_tools.extend(extra_tools)
        
    # 实例化 Agent
    # 使用项目标准的 create_agent，该 Agent 具备思考循环（Thought/Action）能力
    agent = create_agent(
        model=llm,
        tools=base_tools,
        system_prompt=system_prompt
    )
    
    return agent