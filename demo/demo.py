from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import RecordStatus
from investment_tracker.data.repositories import TransactionRepository
from investment_tracker.data.services import PortfolioService
from investment_tracker.mcp_tools.exchange_rate_tool import ExchangeRateTool
from investment_tracker.mcp_tools.investment_advisor_tool import InvestmentAdvisorTool
from investment_tracker.mcp_tools.nlp_tool import NaturalLanguageTool
from investment_tracker.orchestration.screenshot_import_service import ScreenshotImportService
from investment_tracker.utils.ai_client import AIResponse

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
ARTIFACTS = ROOT / "artifacts"
DEMO_DB = ARTIFACTS / "demo.db"


@dataclass
class DemoResult:
    screenshot_preview: Dict[str, Any]
    imported_screenshot_transactions: List[int]
    natural_language_preview: List[Dict[str, Any]]
    imported_natural_language_transactions: List[int]
    positions: List[Dict[str, Any]]
    advice: Dict[str, Any]


class DemoAIClient:
    def generate(self, prompt: str, **_: Any) -> AIResponse:
        del prompt
        return AIResponse(
            content=json.dumps(
                {
                    "summary": "Portfolio remains moderately diversified with manageable FX concentration.",
                    "risk_level": "medium",
                    "actions": [
                        {"asset_code": "USD", "action": "HOLD", "rationale": "USD position is small and stable."},
                        {"asset_code": "JPY", "action": "HOLD", "rationale": "JPY allocation came from recent FX rotation."},
                    ],
                    "reasoning": "Balanced risk preference favors holding existing small positions rather than adding leverage.",
                    "warnings": ["Bond round-trip is complete, so no current bond exposure remains."],
                },
                ensure_ascii=False,
            ),
            model="demo-local-stub",
            provider="local",
            input_tokens=64,
            output_tokens=96,
            raw_response={"demo": True},
        )


def build_demo_payloads() -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    for fixture in ("bond_buy_detail_ocr.txt", "bond_sell_detail_ocr.txt", "forex_list_ocr.txt"):
        text = (FIXTURES / fixture).read_text(encoding="utf-8")
        payloads.append(
            {
                "filename": fixture.replace("_ocr.txt", ".png"),
                "content_base64": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
            }
        )
    return payloads


def create_session() -> Session:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    if DEMO_DB.exists():
        DEMO_DB.unlink()
    engine = create_engine(f"sqlite:///{DEMO_DB}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def normalize_screenshot_transaction(item: Dict[str, Any]) -> Dict[str, Any]:
    parsed = item["transaction_summary"]["parsed_transaction"]
    raw_text = item["ocr"]["text"]
    total_cost = _extract_amount(raw_text, r"交易金额\s*([0-9,]+(?:\.[0-9]+)?)元")
    trade_currency = "CNY"
    return {
        "asset_type": parsed["asset_type"],
        "asset_code": parsed["asset_code"],
        "asset_name": parsed.get("asset_name") or parsed["asset_code"],
        "direction": parsed["direction"],
        "quantity": parsed["quantity"],
        "unit_price": parsed["unit_price"],
        "trade_currency": trade_currency,
        "trade_time": parsed["trade_time"],
        "exchange_rate_to_cny": 1.0,
        "total_cost_cny": total_cost or round(float(parsed["quantity"]) * float(parsed["unit_price"]), 2),
        "source": "screenshot_demo",
        "status": RecordStatus.CONFIRMED.value,
        "raw_text": raw_text,
        "notes": item["filename"],
    }


def sort_transactions_by_time(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(transactions, key=lambda item: item["trade_time"])


def create_transactions_sequentially(
    repository: TransactionRepository,
    *,
    user_id: int,
    transactions: List[Dict[str, Any]],
) -> List[int]:
    created_ids: List[int] = []
    for item in sort_transactions_by_time(transactions):
        created = repository.create_transactions(user_id=user_id, transactions=[item])
        created_ids.extend(row.id for row in created)
    return created_ids


def normalize_natural_language_transaction(
    text: str,
    parsed: Dict[str, Any],
    *,
    exchange_rate_tool: ExchangeRateTool,
) -> Dict[str, Any]:
    params = parsed["parameters"]
    asset_type = params["asset_type"]
    quantity = float(params["quantity"])
    unit_price = float(params["unit_price"])
    trade_currency = params.get("trade_currency") or ("CNY" if asset_type == "BOND" else "CNY")
    trade_time = params["trade_time"]

    exchange_rate_to_cny = 1.0
    total_cost_cny = round(quantity * unit_price, 2)
    if trade_currency != "CNY":
        response = exchange_rate_tool.execute({"base_currency": trade_currency, "quote_currency": "CNY"})
        if response["ok"]:
            exchange_rate_to_cny = float(response["result"]["rate"])
            total_cost_cny = round(quantity * unit_price * exchange_rate_to_cny, 2)

    return {
        "asset_type": asset_type,
        "asset_code": params["asset_code"],
        "asset_name": params["asset_code"],
        "direction": params["direction"],
        "quantity": quantity,
        "unit_price": unit_price,
        "trade_currency": trade_currency,
        "trade_time": trade_time,
        "exchange_rate_to_cny": exchange_rate_to_cny,
        "total_cost_cny": total_cost_cny,
        "source": "nl_demo",
        "status": RecordStatus.CONFIRMED.value,
        "raw_text": text,
        "notes": "demo natural language input",
    }


def run_demo() -> DemoResult:
    screenshot_service = ScreenshotImportService()
    nl_tool = NaturalLanguageTool()
    exchange_rate_tool = ExchangeRateTool()

    screenshot_preview = screenshot_service.preview_batch(build_demo_payloads())
    fixture_inputs = json.loads((FIXTURES / "natural_language_inputs.json").read_text(encoding="utf-8"))

    session = create_session()
    try:
        repository = TransactionRepository(session)

        screenshot_transactions = [
            normalize_screenshot_transaction(item) for item in screenshot_preview["parsed_transactions"]
        ]
        created_from_screenshots = create_transactions_sequentially(
            repository,
            user_id=1,
            transactions=screenshot_transactions,
        )

        nl_preview: List[Dict[str, Any]] = []
        nl_transactions: List[Dict[str, Any]] = []
        for text in fixture_inputs["inputs"]:
            response = nl_tool.execute({"text": text})
            result = response["result"]
            nl_preview.append({"input": text, "result": result})
            if result["missing_fields"]:
                continue
            nl_transactions.append(
                normalize_natural_language_transaction(
                    text,
                    result,
                    exchange_rate_tool=exchange_rate_tool,
                )
            )

        created_from_nl = create_transactions_sequentially(
            repository,
            user_id=1,
            transactions=nl_transactions,
        )

        portfolio_service = PortfolioService(session, exchange_rate_tool=exchange_rate_tool)
        positions = portfolio_service.build_positions(user_id=1)
        advice_tool = InvestmentAdvisorTool(ai_client=DemoAIClient())
        advice = advice_tool.execute(
            {
                "positions": positions,
                "market_data": {"mode": "demo", "generated_from": "local fixtures"},
                "risk_preference": fixture_inputs["risk_preference"],
            }
        )
    finally:
        session.close()

    return DemoResult(
        screenshot_preview=screenshot_preview,
        imported_screenshot_transactions=created_from_screenshots,
        natural_language_preview=nl_preview,
        imported_natural_language_transactions=created_from_nl,
        positions=positions,
        advice=advice,
    )


def print_demo(result: DemoResult) -> None:
    print("== Screenshot Preview ==")
    print(json.dumps(result.screenshot_preview["summary"], ensure_ascii=False, indent=2))
    print(f"imported screenshot transaction ids: {result.imported_screenshot_transactions}")

    print("\n== Natural Language Preview ==")
    for item in result.natural_language_preview:
        print(json.dumps(item, ensure_ascii=False, indent=2))
    print(f"imported natural-language transaction ids: {result.imported_natural_language_transactions}")

    print("\n== Positions ==")
    print(json.dumps(result.positions, ensure_ascii=False, indent=2))

    print("\n== Advice ==")
    print(json.dumps(result.advice, ensure_ascii=False, indent=2))
    print(f"\ndemo database: {DEMO_DB}")


def _extract_amount(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


if __name__ == "__main__":
    print_demo(run_demo())
