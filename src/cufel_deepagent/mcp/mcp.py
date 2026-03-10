MCP_SERVERS_CONFIG = {
    # ...其他配置
    "worldbank":{
        'command':'npx',
        'args':['worldbank-mcp'],
        'transport':'stdio'
    },

    "dp_goldbank":{
        "command":"python",
        'args':["-m",'cufel_deepagent.mcp.servers.gold_server.py'],
        'transport':'stdio'
    }
}


