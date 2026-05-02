"""Batch screenshot import preview workflow."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from investment_tracker.mcp_tools.ocr_tool import OCRTool
from investment_tracker.mcp_tools.transaction_parser_tool import TransactionParserTool


class ScreenshotImportService:
    """Run OCR + transaction parsing across a batch of uploaded screenshots."""

    def __init__(
        self,
        *,
        ocr_tool: Optional[OCRTool] = None,
        parser_tool: Optional[TransactionParserTool] = None,
    ) -> None:
        self.ocr_tool = ocr_tool or OCRTool()
        self.parser_tool = parser_tool or TransactionParserTool()

    def preview_batch(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not files:
            return {
                "summary": {"total_files": 0, "parsed_count": 0, "pending_count": 0, "failed_count": 1},
                "parsed_transactions": [],
                "pending_review": [],
                "failed": [{"filename": None, "errors": ["no files provided"]}],
            }
        if len(files) > 50:
            return {
                "summary": {"total_files": len(files), "parsed_count": 0, "pending_count": 0, "failed_count": len(files)},
                "parsed_transactions": [],
                "pending_review": [],
                "failed": [{"filename": None, "errors": ["file count exceeds maximum of 50"]}],
            }

        parsed_transactions: List[Dict[str, Any]] = []
        pending_review: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        for item in files:
            filename = item.get("filename")
            ocr_response = self.ocr_tool.execute(
                {
                    "image_base64": item["content_base64"],
                    "language": item.get("language", "zh-CN"),
                    "provider": item.get("provider"),
                }
            )
            if not ocr_response["ok"]:
                failed.append(
                    {
                        "filename": filename,
                        "errors": [ocr_response["error"]["message"]],
                        "stage": "ocr",
                    }
                )
                continue

            parse_response = self.parser_tool.execute({"ocr_text": ocr_response["result"]["text"]})
            if not parse_response["ok"]:
                failed.append(
                    {
                        "filename": filename,
                        "ocr_text": ocr_response["result"]["text"],
                        "errors": [parse_response["error"]["message"]],
                        "stage": "parse",
                    }
                )
                continue

            result_row = {
                "filename": filename,
                "ocr": ocr_response["result"],
                "transaction_summary": parse_response["result"],
            }
            requires_review = (
                ocr_response["result"]["requires_manual_review"]
                or bool(parse_response["result"]["missing_fields"])
            )
            if requires_review:
                pending_review.append(result_row)
            else:
                parsed_transactions.append(result_row)

        return {
            "summary": {
                "total_files": len(files),
                "parsed_count": len(parsed_transactions),
                "pending_count": len(pending_review),
                "failed_count": len(failed),
            },
            "parsed_transactions": parsed_transactions,
            "pending_review": pending_review,
            "failed": failed,
        }
