import akshare as ak
from datetime import datetime

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


result = get_monetary_market_info()

print(result)