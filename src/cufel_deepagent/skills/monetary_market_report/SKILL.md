---
name: monetary_market_report
description: 专业分析中国宏观货币市场核心指标（LPR、社融、CPI、M0/M1/M2）。当用户需要了解贷款基准成本、市场流动性、通胀走势，或要求撰写正式的金融市场分析报告时，应调用此技能。
---

# 货币市场报告技能指南 (Monetary Market Report)

你现在拥有撰写专业中国货币市场报告的能力。请遵循以下资源结构和执行流程。

## 1. 资源目录
本技能包含以下核心资源，你可以通过元工具（Meta-tools）访问：

- **Scripts (执行程序)**:
    - `fetch_market_data.py`: 核心抓取程序。运行后返回包含 LPR、社融增量、CPI、货币供应量的 JSON 数据。
- **References (知识库)**:
    - `indicators_guide.md`: 详细解释了 M1-M2 剪刀差、LPR 期限利差等专业指标的金融含义，辅助你进行深度解读。
- **Assets (输出模板)**:
    - `report_template.md`: 规定了标准金融报告的 Markdown 结构（摘要、利率分析、流动性分析、结论）。

## 2. 任务执行流程 (Workflow)

当你被触发执行此任务时，请按顺序执行以下步骤：

### 第一步：获取原始数据
调用 `run_skill_scripts(skill_name="monetary_market_report", script_name="get_current_info.py")`。
> **注意**: 检查返回的 JSON 数据中是否存在错误信息（如 SSL 报错或空值）。

### 第二步：研读指标含义 (按需)
如果你对数据中的某个指标变动（如社融大幅下降）感到不确定，请调用 `read_skill_ref(skill_name="monetary_market_report", ref_name="macro_indicator.md")` 来获取专业解释，确保分析不失准。

### 第三步：加载报告结构
调用 `read_skill_asset(skill_name="monetary_market_report", asset_name="report_template.md")` 获取官方要求的报告格式。

### 第四步：合成与撰写
将第一步获取的 **真实数据** 与第二步理解的 **专业逻辑** 相结合，填充到第三步的 **模板** 中。
- 确保所有的百分比（%）和单位（亿元）准确无误。
- 保持客观、专业、中立的分析口吻。

## 3. 约束要求
- 禁止编造数据。如果脚本运行失败，请如实告知用户网络状况。
- 报告必须包含数据来源（AkShare）和抓取日期（fetch_date）。