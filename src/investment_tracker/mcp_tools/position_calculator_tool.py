"""Position calculator using weighted average cost."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from investment_tracker.data.enums import AssetType, TransactionDirection
from investment_tracker.mcp_tools.base import MCPTool, ToolExecutionError


class PositionTransactionInput(BaseModel):
    asset_type: AssetType
    asset_code: str
    direction: TransactionDirection
    quantity: Decimal
    unit_price: Decimal
    trade_currency: str = "CNY"
    exchange_rate_to_cny: Optional[Decimal] = None


class PositionCalculatorInput(BaseModel):
    transactions: List[PositionTransactionInput]
    current_price: Decimal


class PositionCalculatorTool(MCPTool):
    name = "calculate_position"
    description = "Calculate current position, average cost, and unrealized PnL."
    input_model = PositionCalculatorInput

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        transactions = payload["transactions"]
        if not transactions:
            raise ToolExecutionError("at least one transaction is required", code="no_transactions")

        first = transactions[0]
        asset_code = first["asset_code"]
        asset_type = first["asset_type"]
        if any(txn["asset_code"] != asset_code or txn["asset_type"] != asset_type for txn in transactions):
            raise ToolExecutionError(
                "all transactions must refer to the same asset",
                code="mixed_asset_transactions",
            )

        quantity = Decimal("0")
        cost_basis = Decimal("0")
        average_cost = Decimal("0")

        for txn in transactions:
            txn_qty = Decimal(str(txn["quantity"]))
            unit_price = Decimal(str(txn["unit_price"]))
            fx_rate = Decimal(str(txn["exchange_rate_to_cny"] or 1))
            if txn["asset_type"] == AssetType.FOREX and txn["trade_currency"].upper() == "CNY":
                fx_rate = Decimal("1")

            transaction_cost_cny = txn_qty * unit_price * fx_rate
            if txn["asset_type"] == AssetType.FOREX and txn["trade_currency"].upper() == "CNY":
                transaction_cost_cny = txn_qty * unit_price

            if txn["direction"] == TransactionDirection.BUY:
                quantity += txn_qty
                cost_basis += transaction_cost_cny
            else:
                if txn_qty > quantity:
                    raise ToolExecutionError(
                        "sell quantity exceeds current position",
                        code="insufficient_position",
                    )
                average_cost = cost_basis / quantity if quantity else Decimal("0")
                quantity -= txn_qty
                cost_basis -= average_cost * txn_qty

            average_cost = cost_basis / quantity if quantity else Decimal("0")

        current_price = Decimal(str(payload["current_price"]))
        if asset_type == AssetType.FOREX:
            current_value = quantity * current_price
        else:
            current_value = quantity * current_price

        unrealized_pnl = current_value - cost_basis
        return_pct = Decimal("0")
        if cost_basis > 0:
            return_pct = (unrealized_pnl / cost_basis) * Decimal("100")

        return {
            "asset_type": asset_type.value,
            "asset_code": asset_code,
            "quantity": self._quantize(quantity, "0.000001"),
            "average_cost_cny": self._quantize(average_cost, "0.000001"),
            "cost_basis_cny": self._quantize(cost_basis, "0.01"),
            "current_value_cny": self._quantize(current_value, "0.01"),
            "unrealized_pnl_cny": self._quantize(unrealized_pnl, "0.01"),
            "return_pct": self._quantize(return_pct, "0.0001"),
        }

    def _quantize(self, value: Decimal, pattern: str) -> float:
        return float(value.quantize(Decimal(pattern), rounding=ROUND_HALF_UP))
