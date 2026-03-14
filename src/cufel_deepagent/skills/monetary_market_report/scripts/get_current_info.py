# scripts/fetch_market_data.py
import akshare as ak
import pandas as pd
import json
from datetime import datetime

def fetch_all():
    """执行数据抓取并返回干净的 JSON 记录"""
    try:
        # 1. LPR
        lpr = ak.macro_china_lpr().tail(12)
        lpr['TRADE_DATE'] = lpr['TRADE_DATE'].astype(str)
        
        # 2. 社融
        sr = ak.macro_china_shrzgm().tail(12)
        
        # 3. CPI
        cpi = ak.macro_china_cpi_monthly().tail(12)
        cpi['日期'] = cpi['日期'].astype(str)
        
        # 4. M2 (带反转逻辑确保最新)
        ms = ak.macro_china_money_supply()
        ms = ms.iloc[::-1].head(12) if ms.index[0] < ms.index[-1] else ms.head(12)

        data = {
            "metadata": {"source": "AkShare", "timestamp": str(datetime.now())},
            "lpr": lpr.to_dict(orient='records'),
            "social_financing": sr.to_dict(orient='records'),
            "cpi": cpi.to_dict(orient='records'),
            "money_supply": ms.to_dict(orient='records')
        }
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    print(fetch_all())