from __future__ import annotations

import asyncio
import base64

from investment_tracker.api.routes.transactions import upload_transaction_screenshots
from investment_tracker.api.schemas import ScreenshotUploadRequest


def test_upload_route_returns_review_summary() -> None:
    text = "招商银行 外汇买入 币种: 美元 数量: 1000 价格: 7.23 交易时间: 2026-04-26 10:30:00"
    payload = ScreenshotUploadRequest(
        files=[
            {
                "filename": "shot1.png",
                "content_base64": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
            }
        ]
    )

    result = asyncio.run(upload_transaction_screenshots(payload))

    assert result["summary"]["parsed_count"] == 1
