# 专门用langchain.tools 的装饰器来实现的一系列函数
from langchain.tools import tool
import akshare as ak
from datetime import datetime



REPORT_PATH = r"D:\\projects\\deepagent\\reports"

@tool(name_or_callable="市场信息获取",description="能够从东方财富上获取一些反映货币市场当前状况的信息")
def get_monetary_market_info():
    """
    获取中国宏观货币市场核心指标，包括 LPR 利率、社会融资规模、CPI 以及货币供应量(M0,M1,M2)。
    本工具用于金融分析场景，通过 AkShare 接口提取最新的经济数据，帮助 Agent 评估当前市场流动性、
    通胀压力及贷款基准成本，从而为贷款审批提供宏观政策依据。
    """
    try:
        # 1. 获取 LPR 利率 (贷款市场报价利率)
        lpr_df = ak.macro_china_lpr()
        latest_lpr = lpr_df.iloc[-12:].to_dict()

        # 2. 获取社会融资规模增量
        # 注：社融数据通常包含月份，取最后一行即为最新月份数据
        sr_df = ak.macro_china_shrzgm()
        latest_sr = sr_df.iloc[-12:].to_dict()

        # 3. 获取 CPI (居民消费价格指数) 月度同比数据
        cpi_df = ak.macro_china_cpi_monthly()
        latest_cpi = cpi_df.iloc[-12:].to_dict()

        # 4. 获取货币供应量 (M0, M1, M2)
        money_supply_df = ak.macro_china_money_supply()
        latest_ms = money_supply_df.iloc[-12:].to_dict()

        # 5. 整理成标准化字典
        result = {
            "fetch_date": datetime.now().strftime("%Y-%m-%d"),
            "data": {
                "lpr": {
                    "description": "贷款市场报价利率",
                    "value": latest_lpr
                },
                "social_financing": {
                    "description": "社会融资规模增量",
                    "value": latest_sr
                },
                "cpi": {
                    "description": "居民消费价格指数(月度同比)",
                    "value": latest_cpi
                },
                "money_supply": {
                    "description": "货币供应量(M2/M1/M0)",
                    "value": latest_ms
                }
            }
        }
        return result

    except Exception as e:
        return {"error": f"获取市场信息失败: {str(e)}", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

import os

@tool(name_or_callable="报告保存工具",description="需要补充好agent生成的文本进入content参数, 并且生成一个简单合适的报告名称以及文件格式填入到filename参数之中，比如  .../今日货币报告_1.txt")
def write_report(content: str, target_path: str = REPORT_PATH, filename: str = None) -> str:
    """
    将分析报告内容保存为物理文件。
    
    参数:
    - content: 报告的文本内容（Markdown 格式）。
    - target_path: 保存的目录或完整文件路径。
    - filename: 可选。如果 target_path 是目录，则使用此文件名。若不提供，将自动生成。
    """
    try:
        # 1. 确定最终的完整文件路径
        if target_path.endswith('/') or os.path.isdir(target_path):
            # 如果没给文件名，生成一个默认的：market_analysis_20260311_2205.md
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"market_analysis_{timestamp}.md"
            final_file_path = os.path.join(target_path, filename)
        else:
            final_file_path = target_path

        # 2. 自动创建父级目录
        directory = os.path.dirname(final_file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        # 3. 执行写入
        with open(final_file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return f"报告已成功保存！最终文件位置: {os.path.abspath(final_file_path)}"
    
    except Exception as e:
        return f"保存失败，错误原因: {str(e)}"


import os
import subprocess

SKILLS_ROOT = "D:\\projects\\deepagent\\src\\cufel_deepagent\\skills"
# 需要把monetary_market_report skill_name传给这个agent，让其学会调用

def _safe_path(skill_name, *subpaths):
    """确保路径安全，防止越权访问"""
    path = os.path.abspath(os.path.join(SKILLS_ROOT, skill_name, *subpaths))
    if not path.startswith(os.path.abspath(SKILLS_ROOT)):
        raise ValueError("非法路径访问")
    return path

@tool
def read_skill_instructions(skill_name: str):
    """
    读取技能的 SKILL.md 文件，获取该技能的核心工作流、任务蓝图及操作指南。
    这是启用任何技能的第一步，你必须通过此工具了解该技能包含哪些脚本、资源及执行顺序。

    args:
    skill_name: 你所需要查阅的技能文件夹名称（例如：'monetary_market_report','corporate_research'）。

    返回：SKILL.md 的完整文本内容，包含 YAML 元数据和 Markdown 指令。
    """
    try:
        path = _safe_path(skill_name, "SKILL.md")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"读取指令失败: {str(e)}"

import sys
@tool
def run_skill_scripts(skill_name: str, script_name: str, script_args: str = "") -> str:
    """
    运行指定技能下的 Python 脚本。
    
    args: 
    传递给脚本的命令行参数字符串。
    skill_name: 你所需要填入的技能名称,如monetary_market_report
    script_name: 你所要运行的python脚本,如get_current_info.py
    script_args: 传递给脚本的命令行参数字符串。
    
    返回脚本的标准输出(stdout)，通常是 JSON 格式的数据。
    """
    try:
        script_path = _safe_path(skill_name, "scripts", script_name)
        # 运行脚本并捕获输出
        result = subprocess.run(
            [sys.executable, script_path, script_args], 
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:  # 这里面的python
            return f"脚本运行出错: {result.stderr}"
        return result.stdout 
    except Exception as e:
        return f"执行脚本异常: {str(e)}"

@tool
def read_skill_asset(skill_name: str, asset_name: str):
    """读取技能 assets 目录下的静态资源文件。
    通常用于获取报告模板、预设的 Prompt 模板或固定格式的配置文件。

    args:
    skill_name: 你所需要填入的技能名称（例如：'monetary_market_report'）。
    asset_name: 你所要读取的资源文件名（例如：'report_template.md'）。

    返回：资源的完整文本内容。"""
    try:
        path = _safe_path(skill_name, "assets", asset_name)
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"读取资源失败: {str(e)}"

@tool
def read_skill_ref(skill_name: str, ref_name: str):
    """
    读取技能 references 目录下的参考文档。
    用于获取领域专业知识、指标定义、计算公式或业务背景逻辑。

    args:
    skill_name: 你所需要填入的技能名称（例如：'monetary_market_report'）。
    ref_name: 你所要查阅的参考文档文件名（例如：'macro_indicator.md'）。

    返回：参考文档的详细文本内容。
    """
    try:
        path = _safe_path(skill_name, "references", ref_name)
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"读取参考文档失败: {str(e)}"
    
REPORT_BASE_DIR = "D:\\projects\\deepagent\\reports"

@tool    
def save_report(content: str) -> str:
    """
    在货币市场报告撰写完成后，将报告内容持久化存储到本地磁盘。
    系统会自动根据当前日期生成文件名，并确保存储在指定的报告子目录下。

    args:
        content: Agent 撰写完成的报告文本内容（通常为 Markdown 格式）。

    returns: 
        返回保存成功的绝对路径或失败的错误提示。
    """
    try:
        # 1. 动态生成文件名：当前时间（2026年x月x日）_monetary_report.txt
        # 注意：Windows 下文件名建议不要包含特殊字符，此处使用“月”、“日”作为分隔
        now = datetime.now()
        timestamp = now.strftime("%Y年%m月%d日")
        filename = f"{timestamp}_monetary_report.txt"

        # 2. 确保目录存在
        if not os.path.exists(REPORT_BASE_DIR):
            os.makedirs(REPORT_BASE_DIR, exist_ok=True)

        # 3. 拼接完整路径
        file_path = os.path.join(REPORT_BASE_DIR, filename)

        # 4. 写入内容
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"报告保存成功！文件已存入：{file_path}"

    except Exception as e:
        return f"报告保存失败，原因：{str(e)}"

#print(read_skill_asset("monetary_market_report","report_template.md"))
#print(read_skill_ref("monetary_market_report","macro_indicator.md"))
#print(run_skill_scripts("monetary_market_report","get_current_info.py"))
#print(read_skill_instructions("monetary_market_report"))