from __future__ import annotations

import base64

from investment_tracker.mcp_tools.ocr_tool import OCRTool, OCRExtraction, OCREngine
from investment_tracker.settings import AppSettings


class StubEngine(OCREngine):
    name = "stub"

    def __init__(self, text: str, confidence: float) -> None:
        self.text = text
        self.confidence = confidence

    def extract(self, *, image_bytes, image_path, language):
        return OCRExtraction(
            text=self.text,
            confidence=self.confidence,
            engine=self.name,
            metadata={"language": language},
        )


def test_ocr_tool_extracts_text_from_base64() -> None:
    tool = OCRTool(
        settings=AppSettings(ocr_provider="tesseract"),
        engines={"tesseract": StubEngine("招商银行 外汇买入", 0.95)},
    )
    payload = {"image_base64": base64.b64encode("ignored".encode("utf-8")).decode("utf-8")}

    response = tool.execute(payload)

    assert response["ok"] is True
    assert response["result"]["text"] == "招商银行 外汇买入"
    assert response["result"]["requires_manual_review"] is False


def test_ocr_tool_flags_low_confidence_review() -> None:
    tool = OCRTool(
        settings=AppSettings(ocr_provider="tesseract", ocr_confidence_threshold=0.8),
        engines={"tesseract": StubEngine("uncertain text", 0.5)},
    )

    response = tool.execute({"image_base64": base64.b64encode(b"text").decode("utf-8")})

    assert response["ok"] is True
    assert response["result"]["requires_manual_review"] is True
