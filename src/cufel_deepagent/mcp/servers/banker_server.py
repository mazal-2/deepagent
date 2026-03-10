"""
banker_server.py - 一个简单的银行贷款系统 MCP Server (MVP)

功能目标：
- 提供银行信息资源（存款池、贷款列表、利率）
- 支持贷款审批工具
- 支持更新每日利率工具
- 用内存存储数据（不依赖文件，先跑通再说）

启动方式：
    uvx fastmcp banker_server.py   或   python -m fastmcp banker_server.py
"""

import json
import random
from datetime import datetime
from typing import Dict, Any

from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

# =====================================
# 初始化 FastMCP
# =====================================
mcp = FastMCP(
    name="banker",
)

# =====================================
# 内存数据（MVP 阶段不依赖文件）
# =====================================
BANK_STATE: Dict[str, Any] = {
    "deposit_pool": 500000.00,          # 银行当前可用存款池
    "daily_int_rate": 0.0008,           # 日利率（0.08%）
    "loan_list": {},                    # applicant_id → 贷款记录
    "last_updated": datetime.now().isoformat()
}

def _save_state():
    """开发阶段可以打印状态，正式版可以写文件"""
    print("[BANKER] 当前银行状态：")
    print(json.dumps(BANK_STATE, indent=2, ensure_ascii=False))


# =====================================
# 数据模型
# =====================================
class LoanRequest(BaseModel):
    applicant_id: int = Field(..., description="6位数字身份标识")
    loan_amount: float = Field(..., description="申请贷款金额")
    loan_term_days: int = Field(..., description="贷款天数")
    loan_installment: int = Field(..., description="分期期数（期数越少越难批）")
    applicant_asset: float = Field(..., description="申请人资产总额")

    # 审批结果字段（由系统填写）
    status: str = Field(default="pending", description="pending / approved / rejected")
    completed: str = Field(default="not_completed", description="completed / not_completed")
    apply_time: str = Field(default_factory=lambda: datetime.now().isoformat())


# =====================================
# 资源：查看银行整体状态
# =====================================
@mcp.resource(uri="bank:status")
def check_bank_info_system():
    """
    查看当前银行状态：
    - 存款池余额
    - 当前日利率
    - 待处理/进行中贷款数量
    - 贷款列表概览（不含敏感细节）
    """
    pending = sum(1 for v in BANK_STATE["loan_list"].values() if v["status"] == "pending")
    approved_not_completed = sum(1 for v in BANK_STATE["loan_list"].values() if v["status"] == "approved" and v["completed"] == "not_completed")

    summary = {
        "deposit_pool": BANK_STATE["deposit_pool"],
        "daily_int_rate_percent": round(BANK_STATE["daily_int_rate"] * 100, 4),
        "total_loans": len(BANK_STATE["loan_list"]),
        "pending_applications": pending,
        "approved_not_completed": approved_not_completed,
        "last_updated": BANK_STATE["last_updated"],
        "loan_ids": list(BANK_STATE["loan_list"].keys())
    }
    return summary


# =====================================
# 工具：审批或拒绝贷款申请
# =====================================
@mcp.tool(
        description="""
审批一笔贷款申请。【必须严格按照以下格式调用！】

    【重要！所有参数必须放在一个叫 "request" 的嵌套对象里面！】
    禁止把字段拍平、改名、漏掉任何一个字段！

    正确调用格式（必须一模一样）：
    {
        "request": {
            "applicant_id": 123456,                // 整数，6位申请人ID
            "loan_amount": 80000.0,                // 浮点数或整数，贷款金额（元）
            "loan_term_days": 365,                 // 整数，贷款天数
            "loan_installment": 12,                // 整数，分期期数（通常12/24/36）
            "applicant_asset": 200000.0            // 浮点数或整数，申请人总资产（元）
        }
    }

    错误示范（禁止！）：
    - {"applicant_id":123456, "amount":80000}           ← 拍平了！禁止！
    - {"request":{"applicantId":123456}}                ← 字段名错了！必须用 applicant_id
    - {"request":{"loan_amount":"80000"}}               ← 类型错了！必须是数字
    - 漏掉任何一个字段都会导致校验失败！

    审批逻辑（供参考，不需要在调用时写）：
    1. 单笔贷款金额不得超过当前存款池的 30%
    2. 申请人资产必须 ≥ 贷款金额 × 1.5
    3. 分期期数不得超过 36 期
    4. 有约 10% 的随机风险拒绝概率（模拟风控）

    返回结果示例：
    {
        "applicant_id": 123456,
        "status": "approved" 或 "rejected",
        "reasons": ["通过所有规则"] 或 ["贷款金额超过存款池30%"],
        "current_deposit_pool": 420000.0
    }

    请严格按照上面指定的 JSON 结构调用，不要添加额外字段，不要修改字段名！
""")
def approve_or_reject_loan_application(request: LoanRequest) -> dict:
    """
    审批一笔贷款申请

    简单规则（MVP 版本）：
    1. 申请金额 ≤ 存款池的 30%
    2. 申请人资产 ≥ 贷款金额 * 1.5
    3. 分期期数 ≤ 36
    4. 随机因素（模拟风险评估） 10% 拒绝概率

    返回结果会更新 BANK_STATE
    """
    applicant_id = request.applicant_id

    # 防止重复申请（同一个id只能有一笔待处理/未还清贷款）
    if applicant_id in BANK_STATE["loan_list"]:
        existing = BANK_STATE["loan_list"][applicant_id]
        if existing["status"] in ("pending", "approved") and existing["completed"] == "not_completed":
            return {
                "status": "error",
                "message": f"申请人 {applicant_id} 已有未结清/待处理贷款"
            }

    # 审批规则（非常简化）
    reject_reasons = []

    if request.loan_amount > BANK_STATE["deposit_pool"] * 0.30:
        reject_reasons.append("贷款金额超过银行存款池30%")

    if request.applicant_asset < request.loan_amount * 1.5:
        reject_reasons.append("申请人资产不足（需≥贷款金额1.5倍）")

    if request.loan_installment > 36:
        reject_reasons.append("分期期数超过36期")

    # 随机风险拒绝（模拟模型）
    if random.random() < 0.10:
        reject_reasons.append("风险评估随机拒绝（模拟风控模型）")

    status = "approved" if not reject_reasons else "rejected"

    # 记录贷款
    loan_record = request.model_dump()
    loan_record["status"] = status
    loan_record["apply_time"] = datetime.now().isoformat()

    BANK_STATE["loan_list"][applicant_id] = loan_record

    # 如果批准，扣减存款池（简化处理）
    if status == "approved":
        BANK_STATE["deposit_pool"] -= request.loan_amount

    BANK_STATE["last_updated"] = datetime.now().isoformat()

    _save_state()

    result = {
        "applicant_id": applicant_id,
        "status": status,
        "reasons": reject_reasons if reject_reasons else ["通过所有规则"],
        "current_deposit_pool": BANK_STATE["deposit_pool"]
    }

    return result


# =====================================
# 工具：更新每日利率
# =====================================
@mcp.tool(
        description="""
更新银行当前日利率，或随机生成一个合理波动的新利率。

    调用方式：
    1. 指定新利率（推荐）：
    {
        "new_rate": 0.00085     // 浮点数，例如 0.00085 表示 0.085%
    }

    2. 不传参数则随机波动（±20% 左右，限制在 0.00005 ~ 0.01 之间）：
    {}

    注意：
    - new_rate 必须是浮点数，且在 0.00005 到 0.01 之间
    - 如果传入非法值，会返回错误信息
"""
)
def update_daily_int_rate(new_rate: float = None) -> dict:
    """
    更新或随机生成新的日利率

    参数：
        new_rate: 可选，指定新利率（0.0001 ~ 0.005 合理范围）
                 如果不传，则随机生成一个新值
    """
    if new_rate is not None:
        if not 0.00005 <= new_rate <= 0.01:
            return {"error": "利率必须在 0.005% ~ 1% 之间（0.00005 ~ 0.01）"}
        BANK_STATE["daily_int_rate"] = new_rate
    else:
        # 随机波动 ±20%
        current = BANK_STATE["daily_int_rate"]
        fluctuation = random.uniform(-0.2, 0.2)
        new_rate = current * (1 + fluctuation)
        new_rate = max(0.00005, min(0.01, new_rate))
        BANK_STATE["daily_int_rate"] = new_rate

    BANK_STATE["last_updated"] = datetime.now().isoformat()
    _save_state()

    return {
        "new_daily_int_rate": BANK_STATE["daily_int_rate"],
        "new_daily_int_rate_percent": round(BANK_STATE["daily_int_rate"] * 100, 4),
        "message": "利率已更新"
    }


# =====================================
# 提示词（给主 Agent 看的内部原则）
# =====================================
@mcp.prompt(
    name="banker_redemption",
    description="银行内部贷款审批核心原则（机密）"
)
def banker_redemption_principle():
    return """
银行贷款审批核心原则（简化版）：

1. 安全第一：单笔贷款不得超过存款池的30%
2. 抵押覆盖：申请人资产必须 ≥ 贷款金额 × 1.5
3. 合理分期：分期期数不超过36期（期数越少风险越高）
4. 风险随机：即使满足规则，仍有约10%的随机拒绝概率（模拟风控模型）
5. 记录完整：每笔申请必须记录申请人ID、金额、期限、分期、资产、审批结果
6. 存款池动态：批准贷款后立即扣减存款池
"""


if __name__ == "__main__":
    print("Banker MCP Server 启动中...")
    print("可用资源： bank:status")
    print("可用工具： approve_or_reject_loan_application, update_daily_int_rate")
    print("可用提示词： banker_redemption")
    mcp.run()