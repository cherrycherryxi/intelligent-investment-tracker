from __future__ import annotations

import time

from investment_tracker.mcp_tools import ExchangeRateTool, OCRTool, TransactionParserTool


def test_ocr_smoke_performance() -> None:
    tool = OCRTool()
    payload = {
        "image_base64": "5oub5ZWG6ZO26KGMIOWklumGkuS5sOWFpQ==",  # utf-8 fallback text
    }

    start = time.perf_counter()
    result = tool.execute(payload)
    duration = time.perf_counter() - start

    assert result["ok"] is True
    assert duration < 5


def test_exchange_rate_smoke_performance() -> None:
    tool = ExchangeRateTool()

    start = time.perf_counter()
    result = tool.execute({"base_currency": "USD", "quote_currency": "CNY"})
    duration = time.perf_counter() - start

    assert result["ok"] is True
    assert duration < 3


def test_batch_parse_smoke_performance() -> None:
    tool = TransactionParserTool()
    payload = {
        "ocr_text": "招商银行 外汇买入 币种: 美元 数量: 1000 价格: 7.23 交易时间: 2026-04-26 10:30:00"
    }

    start = time.perf_counter()
    for _ in range(50):
        result = tool.execute(payload)
        assert result["ok"] is True
    duration = time.perf_counter() - start

    assert duration < 30
