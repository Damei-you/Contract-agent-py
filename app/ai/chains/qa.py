"""合同问答 LangChain chain。

Prompt 文本和上下文拼接格式对齐参考项目 `contract-agent-mvp` 的
`ContractPrompts#qaSystem/#qaUser` 与 `AiContractAssistant#build*Context`。
"""

import re
from collections.abc import Sequence
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from app.ai.rag.retrievers import RagRetrievedDocument
from app.domain.enums import ContractType, RiskSeverity
from app.domain.models import Contract

RAG_CONTEXT_MAX_CHARS = 12_000
EMPTY_CONTEXT_PLACEHOLDER = "（暂无相关材料）"

CONTRACT_TYPE_DISPLAY_NAMES = {
    ContractType.PROCUREMENT: "采购合同",
    ContractType.SERVICE: "服务合同",
}
RISK_SEVERITY_DISPLAY_NAMES = {
    RiskSeverity.LOW: "低",
    RiskSeverity.MEDIUM: "中",
    RiskSeverity.HIGH: "高",
}

# 文本来自 contract-agent-mvp ContractPrompts.qaSystem，保持迁移前后的模型行为一致。
CONTRACT_QA_SYSTEM_PROMPT = (
    "你是企业财务与法务方向的合同问答助手。请仅依据提供的「合同摘要」"
    "「合同条款上下文」「制度依据上下文」作答。\n"
    "注意区分两类来源：合同条款是当前合同的事实，制度依据是公司内部规范要求。\n"
    "若问题与合同事实有关而条款上下文不足，请明确说明缺少的信息；"
    "制度依据可用于解释、校验或提示，但不要把制度要求误写成合同已约定内容。\n"
    "回答简洁、分点列出关键结论。\n"
)

CONTRACT_QA_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", CONTRACT_QA_SYSTEM_PROMPT),
        (
            "human",
            """【合同摘要】
{contract_summary}

【合同条款上下文】
{clause_rag_context}

【制度依据上下文】
{policy_rag_context}

【用户问题】
{question}""",
        ),
    ]
)


def build_contract_qa_chain(chat_model: Runnable[Any, Any]) -> Runnable[dict[str, Any], str]:
    """创建合同问答生成 chain。

    chat_model 由工厂或测试注入，便于本地单测使用 fake model，生产环境使用 OpenAI-compatible
    ChatModel。
    """

    return CONTRACT_QA_PROMPT | chat_model | StrOutputParser()


def build_qa_prompt_input(
    contract: Contract,
    question: str,
    contract_context: Sequence[RagRetrievedDocument],
    policy_context: Sequence[RagRetrievedDocument],
) -> dict[str, str]:
    """组装 prompt 入参。

    长文本集中在这里格式化，LangGraph state 只保存结构化召回结果，避免节点之间传递难以调试的
    prompt 字符串。
    """

    return {
        "contract_summary": format_contract_summary(contract),
        "clause_rag_context": _blank_as_placeholder(build_clause_context(contract_context)),
        "policy_rag_context": _blank_as_placeholder(build_policy_context(policy_context)),
        "question": question,
    }


def format_contract_summary(contract: Contract) -> str:
    """生成与 contract-agent-mvp ContractToolExecutor.contractSummary 等价的摘要。"""

    return (
        f"合同编号：{contract.id}；类型：{_contract_type_display_name(contract.contract_type)}；"
        f"甲方：{contract.party_a_name}；乙方：{contract.party_b_name}；币种：{contract.currency}；"
        f"不含税金额：{contract.amount_ex_tax}；税率(%)：{contract.tax_rate_pct}；"
        f"含税金额：{contract.amount_inc_tax}；\n"
        f"签订日：{contract.sign_date}；生效日：{contract.effective_date}；"
        f"结束日：{contract.end_date}；履约地点：{contract.performance_site}；"
        f"付款摘要：{contract.payment_terms_summary}；主办部门：{contract.business_owner_dept}；"
        f"风险分层：{_risk_severity_display_name(contract.risk_tier)}；备注：{contract.notes}"
    ).strip()


def build_clause_context(documents: Sequence[RagRetrievedDocument]) -> str:
    """按参考项目 buildClauseContext 格式拼接合同条款命中。"""

    blocks = []
    for document in documents:
        title = str(document.metadata.get("clauseTitle", ""))
        blocks.append(f"【{document.chunk_id} {title}】\n{document.page_content}\n\n")
    return _truncate("".join(blocks), RAG_CONTEXT_MAX_CHARS)


def build_policy_context(documents: Sequence[RagRetrievedDocument]) -> str:
    """按参考项目 buildPolicyContext 格式拼接制度依据命中。"""

    blocks = []
    for document in documents:
        metadata = document.metadata
        header = document.policy_id
        policy_domain = str(metadata.get("policyDomain", ""))
        control_objective = str(metadata.get("controlObjective", ""))
        severity = str(metadata.get("severity", ""))
        if policy_domain:
            header += f" {policy_domain}"
        if control_objective:
            header += f" / {control_objective}"
        if severity:
            header += f"（severity={severity}）"

        block = f"【{header}】\n{document.page_content}\n"
        required_evidence = _split_multi(metadata.get("requiredEvidence", ""))
        if required_evidence:
            block += f"requiredEvidence={_java_list(required_evidence)}\n"
        escalation_role = str(metadata.get("escalationRole", ""))
        if escalation_role:
            block += f"escalationRole={escalation_role}\n"
        blocks.append(f"{block}\n")
    return _truncate("".join(blocks), RAG_CONTEXT_MAX_CHARS)


def _blank_as_placeholder(text: str | None) -> str:
    if text is None or not text.strip():
        return EMPTY_CONTEXT_PLACEHOLDER
    return text


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}\n...[truncated]"


def _split_multi(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [token.strip() for token in re.split(r"[;；]", text) if token.strip()]


def _java_list(values: Sequence[str]) -> str:
    return "[" + ", ".join(values) + "]"


def _contract_type_display_name(contract_type: ContractType) -> str:
    return CONTRACT_TYPE_DISPLAY_NAMES.get(contract_type, contract_type.value)


def _risk_severity_display_name(severity: RiskSeverity) -> str:
    return RISK_SEVERITY_DISPLAY_NAMES.get(severity, severity.value)
