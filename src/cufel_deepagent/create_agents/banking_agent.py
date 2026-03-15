
from pathlib import Path
from typing import Any, Dict, List,Optional

from mcp import ClientSession, StdioServerParameters


from langchain_mcp_adapters.tools import load_mcp_tools

from langchain.agents import create_agent   # 假设这是你项目里能用的版本
# =============================================
# 配置部分
# =============================================
SERVER_SCRIPT = r"D:\\projects\deepagent\src\\cufel_deepagent\\mcp\servers\banker_server.py"

if not Path(SERVER_SCRIPT).is_file():
    raise FileNotFoundError(f"找不到 banker_server.py: {SERVER_SCRIPT}")



# =============================================
# 系统提示词（传给 create_agent 的 system_prompt）
# =============================================


async def create_banking_agent(llm,mcp_session: ClientSession, banker_prompt:Optional[str]=None):
    """
    注入式创建 Banker Agent。
    :param mcp_session: 已经在外部 start 且 initialize 过的 MCP 会话
    :param llm: 实例化后的 LangChain 模型对象

    
    api内部能够在传入session这个参数之后读取这个session的resources以及tools, 并用create_agent来是实现这个agent
    """
    
    # 1. 从 session 中提取 MCP 端的 @mcp.tool 工具
    mcp_tools = await load_mcp_tools(mcp_session)
    
    # 2. 如果你想让 Agent 拥有读取 Resource 的能力，可以手动包装一个工具注入
    """
    async def read_bank_resource(uri: str) -> Optional[str]:
        
        读取银行内部资源（如政策文档、实时头寸明细）
        
        args: 
            uri: 可使用 'bank:status' 来查看当前的存款池、利率、贷款概览等
        
        result = await mcp_session.read_resource(uri)
        return result.contents[0] if result.contents else None
    """
    # 将 MCP 工具和自定义 Resource 访问工具合并
    combined_tools = mcp_tools # 可添加其他工具，需要在内部实现

    # 3. 创建 Agent (这里使用你的 create_deep_agent 或 create_agent)
    banker_agent = create_agent(
        model=llm,
        system_prompt=banker_prompt, # 使用你之前定义的全局变量
        tools=combined_tools,
    )
    
    return banker_agent


