"""Investment advice API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Optional

from fastapi import APIRouter, Request

from investment_tracker.data.db import get_db_session
from investment_tracker.data.models import PortfolioEvent
from investment_tracker.api.routes.positions import _build_asset_positions, _build_cash_positions, _build_position_totals
from investment_tracker.mcp_tools.nlp_tool import NaturalLanguageTool
from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.utils.ai_client import AIClient
from investment_tracker.utils.agent_run_logger import log_agent_event, start_agent_run
from investment_tracker.utils.logger import get_logger


router = APIRouter(prefix="/api/advice", tags=["advice"])
logger = get_logger(__name__)


def _local_advice(*, positions: list[dict], risk_preference: str) -> dict:
    totals = _build_position_totals(positions)
    total_value = totals.get("total_value_cny") or 0
    sorted_positions = sorted(
        positions,
        key=lambda item: abs(float(item.get("current_value_cny") or 0)),
        reverse=True,
    )
    actions = []
    warnings = []
    for item in sorted_positions[:5]:
        value = float(item.get("current_value_cny") or 0)
        weight = (value / total_value * 100) if total_value else 0
        action = "HOLD"
        rationale = f"当前权重约 {weight:.2f}%，收益率 {item.get('return_pct')}%。"
        if risk_preference == "conservative" and weight > 35:
            action = "REVIEW"
            rationale = f"当前权重约 {weight:.2f}%，保守偏好下建议复核集中度。"
        if item.get("valuation_status") not in (None, "OK"):
            warnings.append(f"{item.get('asset_code')} 估值状态为 {item.get('valuation_status')}。")
        actions.append({"asset_code": item["asset_code"], "action": action, "rationale": rationale})

    if not warnings and totals.get("missing_rates"):
        warnings.append(f"存在缺失汇率：{', '.join(totals['missing_rates'])}")

    return {
        "portfolio_summary": {
            "total_cost_cny": totals.get("total_cost_cny"),
            "total_value_cny": totals.get("total_value_cny"),
            "total_pnl_cny": totals.get("total_pnl_cny"),
            "total_return_pct": totals.get("total_return_pct"),
            "exposure_pct": {
                item["asset_code"]: round(((item.get("current_value_cny") or 0) / total_value * 100), 2)
                if total_value
                else 0
                for item in positions
                if item.get("current_value_cny") is not None
            },
            "positions_count": len(positions),
        },
        "advice": {
            "summary": "本地规则建议",
            "risk_level": risk_preference,
            "actions": actions,
            "reasoning": "AI 服务不可用或未配置时，系统根据当前持仓权重、收益率和数据质量生成基础建议。",
            "warnings": warnings,
        },
        "ai_provider": "local",
        "model": "rule-based-fallback",
        "token_usage": {"input_tokens": 0, "output_tokens": 0},
    }


def _positions_for_user(user_id: int) -> tuple[list[dict], dict, list[dict]]:
    with get_db_session() as session:
        cutoff = datetime.now(timezone.utc)
        positions = [
            *_build_cash_positions(session, user_id=user_id, cutoff=cutoff),
            *_build_asset_positions(session, user_id=user_id, cutoff=cutoff),
        ]
        totals = _build_position_totals(positions)
        transactions = _recent_transactions(session, user_id=user_id)
    return positions, totals, transactions


def _recent_transactions(session, *, user_id: int, limit: int = 80) -> list[dict]:
    rows = (
        session.query(PortfolioEvent)
        .filter(PortfolioEvent.user_id == user_id)
        .order_by(PortfolioEvent.event_time.desc(), PortfolioEvent.id.desc())
        .limit(limit)
        .all()
    )
    transactions = []
    for event in rows:
        asset_entries = []
        for entry in event.asset_ledger_entries:
            asset_entries.append(
                {
                    "asset_code": entry.asset.asset_code if entry.asset else None,
                    "asset_name": entry.asset.asset_name if entry.asset else None,
                    "asset_type": entry.asset.asset_type.value if entry.asset else None,
                    "currency": entry.asset.currency if entry.asset else entry.cash_currency,
                    "quantity_delta": float(entry.quantity_delta),
                    "cash_amount": float(entry.cash_amount) if entry.cash_amount is not None else None,
                    "cash_currency": entry.cash_currency,
                    "unit_price": float(entry.unit_price) if entry.unit_price is not None else None,
                }
            )
        cash_entries = [
            {
                "currency": entry.currency,
                "amount_delta": float(entry.amount_delta),
                "rmb_amount": float(entry.rmb_amount) if entry.rmb_amount is not None else None,
                "fx_rate_to_cny": float(entry.fx_rate_to_cny) if entry.fx_rate_to_cny is not None else None,
            }
            for entry in event.cash_ledger_entries
        ]
        transactions.append(
            {
                "id": event.id,
                "event_type": event.event_type.value,
                "event_time": event.event_time.isoformat(),
                "source": event.source,
                "notes": event.notes,
                "asset_entries": asset_entries,
                "cash_entries": cash_entries,
            }
        )
    return transactions


def _compact_positions(positions: list[dict], *, limit: int = 40) -> list[dict]:
    sorted_positions = sorted(
        positions,
        key=lambda item: abs(float(item.get("current_value_cny") or 0)),
        reverse=True,
    )
    compact = []
    for item in sorted_positions[:limit]:
        compact.append(
            {
                "asset_code": item.get("asset_code"),
                "asset_name": item.get("asset_name"),
                "asset_type": item.get("asset_type"),
                "currency": item.get("currency"),
                "quantity": item.get("quantity"),
                "current_value_cny": item.get("current_value_cny"),
                "current_value_native": item.get("current_value_native"),
                "cost_basis_cny": item.get("cost_basis_cny"),
                "investment_pnl_cny": item.get("investment_pnl_cny"),
                "fx_pnl_cny": item.get("fx_pnl_cny"),
                "unrealized_pnl_cny": item.get("unrealized_pnl_cny"),
                "return_pct": item.get("return_pct"),
                "valuation_status": item.get("valuation_status"),
            }
        )
    return compact


def _compact_transactions(transactions: list[dict], *, limit: int = 40) -> list[dict]:
    compact = []
    for item in transactions[:limit]:
        compact.append(
            {
                "id": item.get("id"),
                "event_type": item.get("event_type"),
                "event_time": item.get("event_time"),
                "notes": item.get("notes"),
                "asset_entries": item.get("asset_entries"),
                "cash_entries": item.get("cash_entries"),
            }
        )
    return compact


def _round_money(value) -> Optional[float]:  # type: ignore[no-untyped-def]
    if value is None:
        return None
    return round(float(value), 2)


def _group_exposure(positions: list[dict], *, key: str, total_value: float) -> list[dict]:
    grouped: dict[str, dict] = {}
    for item in positions:
        group_key = str(item.get(key) or "UNKNOWN")
        current_value = float(item.get("current_value_cny") or 0)
        cost_basis = float(item.get("cost_basis_cny") or 0)
        investment_pnl = float(item.get("investment_pnl_cny") or 0)
        fx_pnl = float(item.get("fx_pnl_cny") or 0)
        bucket = grouped.setdefault(
            group_key,
            {"name": group_key, "current_value_cny": 0.0, "cost_basis_cny": 0.0, "investment_pnl_cny": 0.0, "fx_pnl_cny": 0.0},
        )
        bucket["current_value_cny"] += current_value
        bucket["cost_basis_cny"] += cost_basis
        bucket["investment_pnl_cny"] += investment_pnl
        bucket["fx_pnl_cny"] += fx_pnl

    rows = []
    for bucket in grouped.values():
        current_value = bucket["current_value_cny"]
        rows.append(
            {
                **bucket,
                "current_value_cny": round(current_value, 2),
                "cost_basis_cny": round(bucket["cost_basis_cny"], 2),
                "investment_pnl_cny": round(bucket["investment_pnl_cny"], 2),
                "fx_pnl_cny": round(bucket["fx_pnl_cny"], 2),
                "weight_pct": round(current_value / total_value * 100, 2) if total_value else 0,
            }
        )
    return sorted(rows, key=lambda row: abs(row["current_value_cny"]), reverse=True)


def _summarize_recent_activity(transactions: list[dict], *, limit: int = 40) -> dict:
    event_counts: dict[str, int] = {}
    currency_flows: dict[str, float] = {}
    asset_trade_counts: dict[str, int] = {}
    notable_events = []
    for item in transactions[:limit]:
        event_type = str(item.get("event_type") or "UNKNOWN")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        for entry in item.get("cash_entries") or []:
            currency = str(entry.get("currency") or "UNKNOWN")
            currency_flows[currency] = currency_flows.get(currency, 0.0) + float(entry.get("amount_delta") or 0)
        for entry in item.get("asset_entries") or []:
            asset_code = str(entry.get("asset_code") or "UNKNOWN")
            asset_trade_counts[asset_code] = asset_trade_counts.get(asset_code, 0) + 1
        if len(notable_events) < 12:
            notable_events.append(
                {
                    "id": item.get("id"),
                    "event_type": event_type,
                    "event_time": item.get("event_time"),
                    "notes": item.get("notes"),
                    "asset_entries": item.get("asset_entries"),
                    "cash_entries": item.get("cash_entries"),
                }
            )

    return {
        "window": f"latest_{min(len(transactions), limit)}_events",
        "event_counts": dict(sorted(event_counts.items())),
        "net_cash_flows_by_currency": {currency: round(amount, 2) for currency, amount in sorted(currency_flows.items())},
        "asset_trade_counts": dict(sorted(asset_trade_counts.items(), key=lambda item: item[1], reverse=True)[:10]),
        "notable_recent_events": notable_events,
    }


def _build_agent_analysis_context(
    *,
    positions: list[dict],
    totals: dict,
    transactions: list[dict],
    risk_preference: str,
    user_message: str,
) -> dict:
    total_value = float(totals.get("total_value_cny") or 0)
    compact_positions = _compact_positions(positions, limit=20)
    return {
        "task": {
            "user_message": user_message,
            "risk_preference": risk_preference,
            "base_currency": "CNY",
            "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "field_glossary": {
            "current_value_cny": "当前估值折人民币，来自最新估值和汇率。",
            "cost_basis_cny": "按资金来源和买入/换汇成本追踪出的人民币成本。",
            "investment_pnl_cny": "资产本身投资盈亏，不含外汇影响；现金该字段为 0。",
            "fx_pnl_cny": "外币资金相对人民币的汇率盈亏。",
            "unrealized_pnl_cny": "当前未实现总盈亏，通常等于 investment_pnl_cny + fx_pnl_cny。",
            "return_pct": "基于当前口径计算的收益率百分比。",
            "valuation_status": "OK 表示估值和汇率数据完整；缺失时必须提示核对。",
        },
        "portfolio_summary": {
            "total_cost_cny": _round_money(totals.get("total_cost_cny")),
            "total_value_cny": _round_money(totals.get("total_value_cny")),
            "total_pnl_cny": _round_money(totals.get("total_pnl_cny")),
            "total_investment_pnl_cny": _round_money(totals.get("total_investment_pnl_cny")),
            "total_fx_pnl_cny": _round_money(totals.get("total_fx_pnl_cny")),
            "total_return_pct": totals.get("total_return_pct"),
            "positions_count": len(positions),
            "missing_rates": totals.get("missing_rates") or [],
            "missing_valuations": totals.get("missing_valuations") or [],
        },
        "exposure_by_currency": _group_exposure(positions, key="currency", total_value=total_value),
        "exposure_by_asset_type": _group_exposure(positions, key="asset_type", total_value=total_value),
        "top_positions": compact_positions,
        "recent_activity": _summarize_recent_activity(transactions),
        "analysis_rules": [
            "先判断组合层面：总收益、投资收益与外汇收益分别贡献了什么。",
            "再判断集中度：币种、资产类型、单一产品权重是否过高。",
            "现金不是投资资产，现金的盈亏主要看 fx_pnl_cny；不要把现金 investment_pnl_cny=0 解读成没有风险。",
            "基金和理财要分开看：基金更偏市场波动，理财产品更偏流动性、币种和收益稳定性。",
            "近期交易只作为行为线索，不要用近期交易覆盖当前持仓事实。",
            "如果发现数据口径矛盾或估值缺失，输出 warning，不要编造市场行情。",
        ],
        "output_contract": {
            "summary": "一句中文组合结论，直接说明是否需要行动。",
            "actions": "最多 8 条。每条包含 asset_name、action、rationale。action 只能是 HOLD/REVIEW/REDUCE/ADD。",
            "reasoning": "3 到 5 条中文依据，必须引用上方字段名或数值。",
            "warnings": "数据质量、集中度、汇率、流动性等风险提示列表。",
        },
    }


def _ai_error_response(*, mode: str, error: Exception) -> dict:
    if isinstance(error, ToolExecutionError):
        message = str(error)
        code = error.code
        details = error.details
    else:
        message = str(error)
        code = "ai_execution_failed"
        details = {}
    return {"ok": False, "mode": mode, "error": {"message": message, "code": code, "details": details}}


def _ai_parse_fallback(*, mode: str, error: ToolExecutionError) -> dict:
    content = str(error.details.get("content") or "").strip()
    answer = content or "AI 已返回内容，但系统暂时无法解析为结构化结果。请查看后端日志中的原始响应片段。"
    return {
        "answer": answer,
        "warnings": [
            "AI 返回内容不是合法结构化 JSON，系统已展示原始文本。",
            "后端日志已记录原始响应片段，可用于继续优化解析规则。",
        ],
        "parse_error": {"mode": mode, "code": error.code, "message": str(error)},
    }


@router.get("")
async def get_advice(
    request: Request,
    user_id: int = 1,
    risk_preference: str = "balanced",
    use_ai: bool = True,
) -> dict:
    positions, _, _ = _positions_for_user(user_id)

    result = request.app.state.orchestration.skill_runner.run(
        "investment_advice_skill",
        {
            "positions": positions,
            "market_data": {"generated_at": "local"},
            "risk_preference": risk_preference,
        },
    )
    return {"ok": True, "result": result}


@router.post("/chat")
async def chat_advice(request: Request, payload: dict) -> dict:
    started = perf_counter()
    user_id = int(payload.get("user_id") or 1)
    mode = str(payload.get("mode") or "chat")
    message = str(payload.get("message") or "").strip()
    risk_preference = str(payload.get("risk_preference") or "balanced")
    with start_agent_run(
        mode=mode,
        user_id=user_id,
        metadata={"risk_preference": risk_preference, "message": message, "message_length": len(message)},
    ):
        positions, totals, transactions = _positions_for_user(user_id)
        skill_runner = request.app.state.orchestration.skill_runner
        ai_client = AIClient(max_retries=1, token_budget=30000)
        context = _build_agent_analysis_context(
            positions=positions,
            totals=totals,
            transactions=transactions,
            risk_preference=risk_preference,
            user_message=message,
        )
        compact_positions = context["top_positions"]
        compact_transactions = _compact_transactions(transactions, limit=12)
        log_agent_event(
            "Agent orchestration prepared",
            data={
                "mode": mode,
                "user_id": user_id,
                "risk_preference": risk_preference,
                "positions_count": len(positions),
                "compact_positions_count": len(compact_positions),
                "transactions_count": len(transactions),
                "compact_transactions_count": len(compact_transactions),
                "context": context,
            },
        )
        logger.info(
            "advice_ai_request_started",
            extra={
                "agent_mode": mode,
                "user_id": user_id,
                "risk_preference": risk_preference,
                "positions_count": len(positions),
                "compact_positions_count": len(compact_positions),
                "transactions_count": len(transactions),
                "compact_transactions_count": len(compact_transactions),
                "message_length": len(message),
            },
        )
        try:
            if mode == "generate_advice":
                log_agent_event("Agent mode selected", data={"mode": mode, "skill": "investment_advice_skill"})
                result = skill_runner.run(
                    "investment_advice_skill",
                    {
                        "positions": compact_positions,
                        "market_data": {"portfolio_summary": context["portfolio_summary"], "recent_activity": context["recent_activity"]},
                        "risk_preference": risk_preference,
                    },
                )
            elif mode == "position_analysis":
                log_agent_event("Agent mode selected", data={"mode": mode, "skill": "risk_assessment_skill"})
                result = skill_runner.run(
                    "risk_assessment_skill",
                    {"positions": compact_positions, "volatility_data": {"portfolio_summary": context["portfolio_summary"]}},
                )
            elif mode == "transaction_analysis":
                log_agent_event("Agent mode selected", data={"mode": mode, "skill": "transaction_analysis_skill"})
                result = skill_runner.run(
                    "transaction_analysis_skill",
                    {"transactions": compact_transactions},
                )
            else:
                log_agent_event("Agent mode selected", data={"mode": mode, "path": "direct_chat"})
                ai_response = ai_client.generate(
                    (
                        "请基于以下投资组合数据回答用户问题。必须使用中文，先给结论，再列关键依据和需要补充的数据。"
                        "不要编造不存在的交易或行情。\n"
                        f"用户问题: {message}\n"
                        f"上下文: {context}"
                    ),
                    system_prompt="You are an AI portfolio assistant for a personal investment ledger. Be precise and data-grounded.",
                    temperature=0.2,
                    max_tokens=5000,
                )
                result = {
                    "answer": ai_response.content,
                    "ai_provider": ai_response.provider,
                    "model": ai_response.model,
                    "token_usage": {"input_tokens": ai_response.input_tokens, "output_tokens": ai_response.output_tokens},
                }
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            logger.info(
                "advice_ai_request_succeeded",
                extra={
                    "agent_mode": mode,
                    "user_id": user_id,
                    "elapsed_ms": elapsed_ms,
                    "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
                },
            )
            response_payload = {
                "ok": True,
                "mode": mode,
                "result": result,
                "portfolio_summary": totals,
            }
            log_agent_event("Endpoint response prepared", data={"elapsed_ms": elapsed_ms, "response": response_payload})
            return response_payload
        except Exception as exc:  # AI provider errors should be returned to the chat UI.
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            if isinstance(exc, ToolExecutionError) and exc.code == "invalid_skill_response":
                raw_content = str(exc.details.get("content") or "")
                logger.warning(
                    "advice_ai_parse_failed",
                    extra={
                        "agent_mode": mode,
                        "user_id": user_id,
                        "elapsed_ms": elapsed_ms,
                        "error_code": exc.code,
                        "error_message": str(exc),
                        "raw_response_excerpt": raw_content[:2000],
                        "raw_response_length": len(raw_content),
                    },
                )
                response_payload = {
                    "ok": True,
                    "mode": mode,
                    "result": _ai_parse_fallback(mode=mode, error=exc),
                    "portfolio_summary": totals,
                }
                log_agent_event(
                    "Endpoint parse fallback prepared",
                    data={"elapsed_ms": elapsed_ms, "response": response_payload},
                    content=raw_content,
                )
                return response_payload
            logger.exception(
                "advice_ai_request_failed",
                extra={
                    "agent_mode": mode,
                    "user_id": user_id,
                    "elapsed_ms": elapsed_ms,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            response_payload = _ai_error_response(mode=mode, error=exc)
            log_agent_event(
                "Endpoint error response prepared",
                data={"elapsed_ms": elapsed_ms, "error_type": type(exc).__name__, "error": str(exc), "response": response_payload},
            )
            return response_payload


@router.post("/parse-transaction")
async def parse_transaction(payload: dict) -> dict:
    text = str(payload.get("text") or "").strip()
    return NaturalLanguageTool().execute({"text": text})


@router.get("/risk-assessment")
async def get_risk_assessment(user_id: int = 1) -> dict:
    with get_db_session() as session:
        cutoff = datetime.now(timezone.utc)
        positions = [
            *_build_cash_positions(session, user_id=user_id, cutoff=cutoff),
            *_build_asset_positions(session, user_id=user_id, cutoff=cutoff),
        ]
    totals = _build_position_totals(positions)
    total_value = totals.get("total_value_cny") or 0
    exposures = sorted(
        [
            {
                "asset_code": item["asset_code"],
                "asset_name": item.get("asset_name"),
                "asset_type": item.get("asset_type"),
                "weight_pct": round(((item.get("current_value_cny") or 0) / total_value * 100), 2) if total_value else 0,
            }
            for item in positions
            if item.get("current_value_cny") is not None
        ],
        key=lambda item: item["weight_pct"],
        reverse=True,
    )
    top_weight = exposures[0]["weight_pct"] if exposures else 0
    risk_level = "high" if top_weight >= 40 else "medium" if top_weight >= 25 else "low"
    factors = []
    if top_weight:
        factors.append(f"最大单一持仓权重约 {top_weight:.2f}%。")
    if totals.get("missing_rates") or totals.get("missing_valuations"):
        factors.append("存在缺失汇率或估值数据。")
    if not factors:
        factors.append("当前持仓数据完整，未发现明显集中度风险。")
    return {
        "ok": True,
        "result": {
            "risk_level": risk_level,
            "factors": factors,
            "diversification_suggestions": [
                "优先复核高权重资产是否符合风险偏好。",
                "结合银行 APP 当前持仓收益与系统全生命周期收益进行交叉核对。",
            ],
            "exposures": exposures[:10],
        },
    }
