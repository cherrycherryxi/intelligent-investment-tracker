from __future__ import annotations

from investment_tracker.mcp_tools.transaction_parser_tool import TransactionParserTool


def test_parse_forex_transaction() -> None:
    tool = TransactionParserTool()
    text = "招商银行 外汇买入 币种: 美元 数量: 1000 价格: 7.23 交易时间: 2026-04-26 10:30:00"

    response = tool.execute({"ocr_text": text})

    assert response["ok"] is True
    parsed = response["result"]["parsed_transaction"]
    assert response["result"]["transaction_type"] == "FOREX"
    assert parsed["asset_code"] == "USD"
    assert parsed["direction"] == "BUY"
    assert parsed["quantity"] == 1000.0


def test_parse_bond_transaction() -> None:
    tool = TransactionParserTool()
    text = "招商银行 柜台债 买入 债券代码: 123456 数量: 10 价格: 99.80 交易时间: 2026-04-26 10:30:00"

    response = tool.execute({"ocr_text": text})

    assert response["ok"] is True
    parsed = response["result"]["parsed_transaction"]
    assert response["result"]["transaction_type"] == "BOND"
    assert parsed["asset_code"] == "123456"


def test_parse_bond_detail_screenshot_text() -> None:
    tool = TransactionParserTool()
    text = (
        "招商银行 交易详情 买入 24特别国债04 交易产品 24特别国债04 "
        "买入全价 102.9762元 买入份数 10份 交易时间 2026-01-28 14:52:23"
    )

    response = tool.execute({"ocr_text": text})

    assert response["ok"] is True
    parsed = response["result"]["parsed_transaction"]
    assert parsed["asset_code"] == "24特别国债04"
    assert parsed["asset_name"] == "24特别国债04"
    assert parsed["quantity"] == 10.0
    assert parsed["unit_price"] == 102.9762


def test_parse_transaction_missing_fields() -> None:
    tool = TransactionParserTool()
    text = "招商银行 美元 买入"

    response = tool.execute({"ocr_text": text})

    assert response["ok"] is True
    assert "quantity" in response["result"]["missing_fields"]
    assert "unit_price" in response["result"]["missing_fields"]
