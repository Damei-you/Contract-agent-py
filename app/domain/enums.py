"""领域枚举和值解析。

枚举在数据库中按英文稳定值保存；入参解析支持中文显示名和英文别名，方便演示数据、
CSV 导入和前端表单共用同一套 API。
"""

from enum import StrEnum

from app.core.exceptions import BadRequestError


class ContractType(StrEnum):
    """合同类型。"""

    PROCUREMENT = "PROCUREMENT"
    SERVICE = "SERVICE"

    @classmethod
    def from_flexible(cls, value: object) -> "ContractType":
        """将 API/导入数据中的多种合同类型写法归一化。"""

        if isinstance(value, cls):
            return value
        normalized = str(value or "").strip().lower()
        mapping = {
            "procurement": cls.PROCUREMENT,
            "purchase": cls.PROCUREMENT,
            "采购": cls.PROCUREMENT,
            "采购合同": cls.PROCUREMENT,
            "service": cls.SERVICE,
            "服务": cls.SERVICE,
            "服务合同": cls.SERVICE,
        }
        if normalized.upper() in cls.__members__:
            return cls[normalized.upper()]
        if normalized in mapping:
            return mapping[normalized]
        raise BadRequestError(f"Unsupported contract type: {value}")


class RiskSeverity(StrEnum):
    """风险严重度。"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @classmethod
    def from_flexible(cls, value: object) -> "RiskSeverity":
        """将中文显示名或英文枚举名归一化为稳定枚举值。"""

        if isinstance(value, cls):
            return value
        normalized = str(value or "").strip().lower()
        mapping = {"低": cls.LOW, "中": cls.MEDIUM, "高": cls.HIGH}
        if normalized.upper() in cls.__members__:
            return cls[normalized.upper()]
        if normalized in mapping:
            return mapping[normalized]
        raise BadRequestError(f"Unsupported risk severity: {value}")


class ApprovalDecision(StrEnum):
    """审批结论。"""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONDITIONAL_APPROVED = "CONDITIONAL_APPROVED"
    RETURNED = "RETURNED"

    @classmethod
    def from_flexible(cls, value: object) -> "ApprovalDecision":
        """兼容历史审批数据中的中文结论。"""

        if isinstance(value, cls):
            return value
        normalized = str(value or "").strip().lower()
        mapping = {
            "通过": cls.APPROVED,
            "同意": cls.APPROVED,
            "驳回": cls.REJECTED,
            "拒绝": cls.REJECTED,
            "有条件通过": cls.CONDITIONAL_APPROVED,
            "退回": cls.RETURNED,
        }
        if normalized.upper() in cls.__members__:
            return cls[normalized.upper()]
        if normalized in mapping:
            return mapping[normalized]
        raise BadRequestError(f"Unsupported approval decision: {value}")
