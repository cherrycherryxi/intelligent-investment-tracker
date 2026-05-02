from __future__ import annotations

from datetime import datetime

from investment_tracker.mcp_tools.nlp_tool import NaturalLanguageTool


def test_parse_chinese_trade_input() -> None:
    tool = NaturalLanguageTool()

    response = tool.execute({"text": "买入1000美元，汇率7.23，时间2026-04-26 10:30:00"})

    assert response["ok"] is True
    params = response["result"]["parameters"]
    assert params["asset_code"] == "USD"
    assert params["direction"] == "BUY"
    assert params["quantity"] == 1000.0


def test_parse_english_trade_input() -> None:
    tool = NaturalLanguageTool()

    response = tool.execute({"text": "Buy 500 USD at rate 7.10 on 2026-04-26 09:00:00"})

    assert response["ok"] is True
    params = response["result"]["parameters"]
    assert params["asset_code"] == "USD"
    assert params["direction"] == "BUY"
    assert params["quantity"] == 500.0


def test_parse_missing_fields() -> None:
    tool = NaturalLanguageTool()

    response = tool.execute({"text": "买入美元"})

    assert response["ok"] is True
    assert "quantity" in response["result"]["missing_fields"]


def test_parse_relative_date_and_cny_trade() -> None:
    tool = NaturalLanguageTool()

    response = tool.execute({"text": "我昨天购买了100刀美元，汇率是6.8136"})

    assert response["ok"] is True
    params = response["result"]["parameters"]
    assert params["asset_code"] == "USD"
    assert params["direction"] == "BUY"
    assert params["quantity"] == 100.0
    assert params["trade_currency"] == "CNY"
    assert datetime.fromisoformat(params["trade_time"]).date() < datetime.now().date()


def test_parse_cross_currency_sentence_as_buy_side() -> None:
    tool = NaturalLanguageTool()

    response = tool.execute({"text": "4月21号我卖出560.02加元，买入65254日元"})

    assert response["ok"] is True
    params = response["result"]["parameters"]
    assert params["asset_code"] == "JPY"
    assert params["direction"] == "BUY"
    assert params["quantity"] == 65254.0
    assert params["trade_currency"] == "CAD"
