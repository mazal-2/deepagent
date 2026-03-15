from typing import List, Optional
from langchain.agents import create_agent
from src.cufel_deepagent.tools.tools import (
    read_skill_asset, 
    read_skill_instructions, 
    read_skill_ref, 
    run_skill_scripts, 
    save_report
)


def create_reporter_agent(llm, system_prompt:str ='none' ):
    """
    创建宏观货币研究专员 Agent。
    该 Agent 专注于通过本地 Skill 脚本获取金融数据并生成报告。
    """
    
    # 定义该 Agent 专属的工具集
    reporter_tools = [
        run_skill_scripts, 
        read_skill_ref, 
        read_skill_asset, 
        read_skill_instructions, 
        save_report
    ]
    
    # 实例化 Agent
    # 使用你项目中的 create_agent，确保它能处理 tools 和 system_prompt
    agent = create_agent(
        model=llm,
        system_prompt=system_prompt,
        tools=reporter_tools
    )
    
    return agent