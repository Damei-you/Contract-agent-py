from enum import StrEnum

from app.core.exceptions import BadRequestError


class ContractType(StrEnum):
    PROCUREMENT = "PROCUREMENT"
    SERVICE = "SERVICE"

    @classmethod
    def from_flexible(cls, value: object) -> "ContractType":
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
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @classmethod
    def from_flexible(cls, value: object) -> "RiskSeverity":
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
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONDITIONAL_APPROVED = "CONDITIONAL_APPROVED"
    RETURNED = "RETURNED"

    @classmethod
    def from_flexible(cls, value: object) -> "ApprovalDecision":
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
