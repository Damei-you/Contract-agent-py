"""结构化风险检查 LangChain chain。

Prompt、JSON schema 和解析失败语义对齐 `contract-agent-mvp` 的
`ContractPrompts#riskCheckSystem/#riskCheckUser` 与 `AiContractAssistant#parseRiskResponse`。
"""

import json
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from app.ai.chains.qa import (
    EMPTY_CONTEXT_PLACEHOLDER,
    build_clause_context,
    build_policy_context,
    format_contract_summary,
)
from app.ai.rag.retrievers import RagRetrievedDocument
from app.domain.enums import RiskSeverity
from app.domain.models import Contract, RiskItem

# 文本来自 contract-agent-mvp ContractPrompts.riskCheckSystem；结构化输出约束不能随意改写，
# 否则前端和审批历史中保存的 riskItems 字段会出现兼容性问题。
RISK_CHECK_SYSTEM_PROMPT = "\n".join(
    [
        "你是合同风险审查助手。请结合「合同摘要」「合同条款上下文」「制度依据上下文」"
        "「历史审批摘要」输出 JSON，且只输出 JSON，不要 Markdown 围栏。",
        "JSON Schema:",
        "{",
        '  "summary": "string",',
        '  "riskItems": [',
        "    {",
        '      "code": "string",',
        '      "severity": "LOW|MEDIUM|HIGH",',
        '      "detail": "string",',
        '      "relatedClauseChunkIds": ["string"],',
        '      "relatedPolicyIds": ["string"],',
        '      "requiredEvidence": ["string"],',
        '      "escalationRole": "string"',
        "    }",
        "  ]",
        "}",
        "约束：",
        "- severity 必须为大写枚举。",
        "- 风险项必须由合同条款触发；relatedClauseChunkIds 应为当前合同的条款 id；"
        "若仅依赖制度无合同条款命中，请将该风险标注为「需人工复核」并尽量给出 "
        "relatedPolicyIds。",
        "- 若命中制度依据，relatedPolicyIds、requiredEvidence、escalationRole "
        "应尽量回填来自制度通道的稳定值；无依据时返回空数组或空字符串。",
        "- 若无风险点，riskItems 可为空数组。",
        "",
    ]
)

RISK_CHECK_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=RISK_CHECK_SYSTEM_PROMPT),
        (
            "human",
            """【合同摘要】
{contract_summary}

【合同条款上下文】
{clause_rag_context}

【制度依据上下文】
{policy_rag_context}

【历史审批摘要】
{approval_digest}""",
        ),
    ]
)


def build_risk_check_chain(chat_model: Runnable[Any, Any]) -> Runnable[dict[str, str], str]:
    """创建风险检查生成 chain。

    模型被要求只输出 JSON；解析和失败兜底放在 validate 节点，便于 LangGraph trace 定位。
    """

    return RISK_CHECK_PROMPT | chat_model | StrOutputParser()


def build_risk_check_prompt_input(
    contract: Contract,
    contract_context: Sequence[RagRetrievedDocument],
    policy_context: Sequence[RagRetrievedDocument],
    approval_digest: str,
) -> dict[str, str]:
    """组装风险检查 prompt 入参。

    合同条款与制度依据沿用 QA 阶段已对齐 MVP 的上下文拼接规则；审批摘要来自业务表，
    不使用向量检索，避免历史审批事实被 RAG 索引状态影响。
    """

    return {
        "contract_summary": format_contract_summary(contract),
        "clause_rag_context": _blank_as_placeholder(build_clause_context(contract_context)),
        "policy_rag_context": _blank_as_placeholder(build_policy_context(policy_context)),
        "approval_digest": approval_digest,
    }


def parse_risk_response(raw: str | None) -> tuple[str, list[RiskItem]]:
    """解析模型输出的风险 JSON。

    对齐参考项目：空输出返回空 summary/空列表；JSON 解析或枚举解析失败时不抛错，
    而是把模型原文作为 summary 返回，riskItems 置空，方便人工看到失败原文。
    """

    if raw is None or not raw.strip():
        return "", []

    try:
        root = json.loads(_extract_json_object(raw))
        risk_items = root.get("riskItems", [])
        if not isinstance(risk_items, list):
            risk_items = []
        return str(root.get("summary", "")), [_to_risk_item(item) for item in risk_items]
    except Exception:  # noqa: BLE001
        # LLM 输出可能夹杂说明文字、Markdown 或非法枚举；MVP 选择保留原文而不是让接口 500。
        return raw.strip(), []


def _to_risk_item(value: Any) -> RiskItem:
    if not isinstance(value, dict):
        raise ValueError("risk item must be an object")
    return RiskItem(
        code=str(value.get("code") or "UNKNOWN"),
        severity=RiskSeverity.from_flexible(value.get("severity") or RiskSeverity.MEDIUM.value),
        detail=str(value.get("detail") or ""),
        related_clause_chunk_ids=_read_string_array(value, "relatedClauseChunkIds"),
        related_policy_ids=_read_string_array(value, "relatedPolicyIds"),
        required_evidence=_read_string_array(value, "requiredEvidence"),
        escalation_role=str(value.get("escalationRole") or ""),
    )


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _read_string_array(value: dict[str, Any], field: str) -> list[str]:
    values = value.get(field)
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, str)]


def _blank_as_placeholder(text: str | None) -> str:
    if text is None or not text.strip():
        return EMPTY_CONTEXT_PLACEHOLDER
    return text
