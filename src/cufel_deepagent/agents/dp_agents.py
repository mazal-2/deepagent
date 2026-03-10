import asyncio
from pathlib import Path

# MCP 核心库
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LangChain 相关集成
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_ollama import ChatOllama
from langchain.agents import create_agent

async def main():
    # 1. 配置 MCP 服务器参数
    # 路径指向你刚刚编写的黄金银行或数学服务器脚本
    server_script_path = r"D:\\projects\deepagent\src\\cufel_deepagent\\mcp\servers\\gold_server.py"
    
    server_params = StdioServerParameters(
        command="python",
        args=[server_script_path],
        env=None # 如果需要特定环境变量可以在此添加
    )

    # 2. 初始化 LLM (使用 Ollama)
    # 注意：确保你的 Ollama 服务已经启动并下载了 qwen3:8b
    llm = ChatOllama(model="qwen3:8b", temperature=0)

    # 3. 建立连接并运行 Agent
    print(f"正在连接到 MCP 服务器: {server_script_path}...")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化 MCP 会话
            await session.initialize()
            
            # 【关键点】利用适配器将 MCP Tools 转换为 LangChain Tools
            # 它会自动读取 MCP Server 中所有带 @mcp.tool() 装饰器的函数
            tools = await load_mcp_tools(session)
            print(f"成功加载工具: {[t.name for t in tools]}")

            # 4. 创建 React Agent
            # create_react_agent 是目前 LangChain 官方推荐的快速构建 Agent 的方法
            agent_executor = create_agent(model=llm, tools=tools)

            # 5. 执行测试指令
            # 这里你可以尝试调用你的“智能避险管家”
            query = "请查询我当前的黄金账户余额，并根据当前金价 600 美元买入 2 盎司黄金"
            
            print(f"\n用户提问: {query}")
            
            # 使用 astream 处理流式输出或直接用 ainvoke
            async for chunk in agent_executor.astream(
                {"messages": [("user", query)]},
                stream_mode="values"
            ):
                if "messages" in chunk:
                    last_msg = chunk["messages"][-1]
                    # 我们只打印 AI 的回复（忽略中间的工具调用过程）
                    if last_msg.type == "ai" and last_msg.content:
                        print(f"\n智能助手回复: {last_msg.content}")

if __name__ == "__main__":
    # Windows 环境下处理异步循环的兼容性设置
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass