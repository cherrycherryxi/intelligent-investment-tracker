from __future__ import annotations

import base64

from investment_tracker.orchestration.screenshot_import_service import ScreenshotImportService


def test_screenshot_import_preview_parses_batch() -> None:
    text = "招商银行 外汇买入 币种: 美元 数量: 1000 价格: 7.23 交易时间: 2026-04-26 10:30:00"
    payload = {
        "files": [
            {
                "filename": "shot1.png",
                "content_base64": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
            }
        ]
    }

    result = ScreenshotImportService().preview_batch(payload["files"])

    assert result["summary"]["parsed_count"] == 1
    assert result["parsed_transactions"][0]["transaction_summary"]["parsed_transaction"]["asset_code"] == "USD"


def test_screenshot_import_limits_batch_size() -> None:
    files = [{"filename": f"{i}.png", "content_base64": base64.b64encode(b"x").decode("utf-8")} for i in range(51)]

    result = ScreenshotImportService().preview_batch(files)

    assert result["summary"]["failed_count"] == 51

