"""审批辅助 LangChain chain。

Prompt 和 JSON 解析语义对齐 `contract-agent-mvp` 的
`ContractPrompts#approvalAssistSystem/#approvalAssistUser` 与
`AiContractAssistant#parseAssistResponse`。
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
from app.domain.models import Contract

# 文本来自 contract-agent-mvp ContractPrompts.approvalAssistSystem。审批辅助返回结构被前端
# 直接消费，因此只做 Python 模板适配，不改写业务约束。
APPROVAL_ASSIST_SYSTEM_PROMPT = "\n".join(
    [
        "你是审批辅助助手。根据合同摘要、合同条款上下文、制度依据上下文与历史审批意见，"
        "为当前审批人提供「结论建议」与「核对清单」。",
        "输出 JSON，且只输出 JSON：",
        "{",
        '  "suggestion": "string",',
        '  "checklist": ["string"]',
        "}",
        "约束：",
        "- checklist 3-8 条，可操作、可核验。",
        "- 优先由命中的制度依据 requiredEvidence 派生 checklist 项；若涉及升级/会签，"
        "可在 suggestion 中点出 escalationRole。",
        "- 不引入与当前合同无关的制度通用要求；制度依据应解释或校验合同事实，"
        "而不是替代合同事实。",
        "",
    ]
)

APPROVAL_ASSIST_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=APPROVAL_ASSIST_SYSTEM_PROMPT),
        (
            "human",
            """【当前审批角色】
{approver_role}

【关注重点】
{focus}

【合同摘要】
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


def build_approval_assist_chain(chat_model: Runnable[Any, Any]) -> Runnable[dict[str, str], str]:
    """创建审批辅助生成 chain。

    模型只负责生成 suggestion/checklist 原文；命中 ID 由 graph 节点从 RAG 结果回填，
    与模型输出解耦，保持 MVP 的失败回退语义。
    """

    return APPROVAL_ASSIST_PROMPT | chat_model | StrOutputParser()


def build_approval_assist_prompt_input(
    approver_role: str,
    focus: str,
    contract: Contract,
    contract_context: Sequence[RagRetrievedDocument],
    policy_context: Sequence[RagRetrievedDocument],
    approval_digest: str,
) -> dict[str, str]:
    """组装审批辅助 prompt 入参。

    focus 为空时展示为固定占位，和参考项目 `approvalAssistUser` 保持一致。
    """

    return {
        "approver_role": approver_role,
        "focus": "（未指定）" if not focus.strip() else focus,
        "contract_summary": format_contract_summary(contract),
        "clause_rag_context": _blank_as_placeholder(build_clause_context(contract_context)),
        "policy_rag_context": _blank_as_placeholder(build_policy_context(policy_context)),
        "approval_digest": approval_digest,
    }


def parse_approval_assist_response(raw: str | None) -> tuple[str, list[str]]:
    """解析审批辅助模型输出。

    对齐参考项目：空输出返回空 suggestion/checklist；JSON 解析失败时 suggestion 返回模型原文，
    checklist 为空，RAG 命中 ID 仍由 workflow 另行保留。
    """

    if raw is None or not raw.strip():
        return "", []

    try:
        root = json.loads(_extract_json_object(raw))
        checklist = root.get("checklist", [])
        if not isinstance(checklist, list):
            checklist = []
        return str(root.get("suggestion", "")), [
            item for item in checklist if isinstance(item, str)
        ]
    except Exception:  # noqa: BLE001
        # LLM 可能输出 Markdown 围栏或非 JSON 文本；保留原文便于审批人看到模型产物。
        return raw.strip(), []


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _blank_as_placeholder(text: str | None) -> str:
    if text is None or not text.strip():
        return EMPTY_CONTEXT_PLACEHOLDER
    return text
