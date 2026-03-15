from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from cufel_deepagent.create_agents.banking_agent import create_banking_agent
from cufel_deepagent.create_agents.macro_eco import create_macro_agent
from cufel_deepagent.create_agents.corp_researching import create_corp_researcher_agent


from src.cufel_deepagent.agents.prompts import BANKING_SYSTEM_PROMPT,CORP_SYSTEM_RPOMPT,MACRO_ECO_SYSTEM_PROMPT
from langchain_deepseek import ChatDeepSeek

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

            banker = await create_banking_agent(llm_banker,session,BANKING_SYSTEM_PROMPT)
            macro_researcher = create_macro_agent(llm=llm_macro,system_prompt=MACRO_ECO_SYSTEM_PROMPT)
            corp_researcher = create_corp_researcher_agent(llm=llm_corp,system_prompt=CORP_SYSTEM_RPOMPT)


