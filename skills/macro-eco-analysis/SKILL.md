---
name: macro-eco-analysis
description: 当用户需要分析国家宏观经济数据（GDP、CPI、通胀等）时使用此技能。
---

## 工作流程

当需要分析宏观经济时，请按以下步骤：

1. 使用 `search-indicators` 搜索正确的指标代码
2. 使用 `get-economic-data` 获取数据（设置 years=10）
3. 解析 JSON 结果，提取年份和数值
4. 对比分析两国数据
5. 输出 Markdown 格式报告


| 工具名 | 功能 | 示例参数 |
|-------|------|---------|
| `get-country-info` | 获取国家详细信息 | `{"countryCode": "CN"}` |
| `search-indicators` | 搜索经济指标 | `{"keyword": "GDP"}` |
| `get-economic-data` | 获取经济数据 | `{"countryCode": "CN", "indicator": "GDP_GROWTH"}` |
| `get-social-data` | 获取社会数据 | `{"countryCode": "CN", "indicator": "POPULATION"}` |

**常用指标代码**：
- `GDP` - 国内生产总值（美元）
- `GDP_GROWTH` - GDP 增长率（%）
- `GDP_PER_CAPITA` - 人均 GDP（美元）
- `INFLATION` - 通胀率（%）
- `UNEMPLOYMENT` - 失业率（%）


## 注意事项

- 国家代码：中国=CN，美国=US
- 默认查询 10 年数据
- GDP 单位是美元，注意转换展示

