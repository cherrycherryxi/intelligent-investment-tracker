"""OCR tool with pluggable engine strategies."""

from __future__ import annotations

import base64
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel

from investment_tracker.mcp_tools.base import MCPTool, ToolExecutionError
from investment_tracker.settings import AppSettings, get_settings


@dataclass
class OCRExtraction:
    text: str
    confidence: float
    engine: str
    metadata: Dict[str, Any]


class OCREngine:
    name = "base"

    def extract(
        self,
        *,
        image_bytes: Optional[bytes],
        image_path: Optional[str],
        language: str,
    ) -> OCRExtraction:
        raise NotImplementedError


class TesseractOCREngine(OCREngine):
    name = "tesseract"

    def extract(
        self,
        *,
        image_bytes: Optional[bytes],
        image_path: Optional[str],
        language: str,
    ) -> OCRExtraction:
        if image_bytes:
            try:
                text = image_bytes.decode("utf-8").strip()
                if text:
                    return OCRExtraction(
                        text=text,
                        confidence=0.99,
                        engine=self.name,
                        metadata={"source": "utf8-bytes-fallback"},
                    )
            except UnicodeDecodeError:
                pass

        if image_path:
            path = Path(image_path)
            if path.suffix.lower() == ".txt":
                return OCRExtraction(
                    text=path.read_text(encoding="utf-8").strip(),
                    confidence=0.98,
                    engine=self.name,
                    metadata={"source": "text-file-fallback"},
                )

        if image_path and shutil.which("tesseract"):
            command = ["tesseract", image_path, "stdout"]
            try:
                completed = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                text = completed.stdout.strip()
                return OCRExtraction(
                    text=text,
                    confidence=0.85 if text else 0.0,
                    engine=self.name,
                    metadata={"source": "tesseract-cli", "language": language},
                )
            except subprocess.CalledProcessError as exc:  # pragma: no cover - environment-specific
                raise ToolExecutionError(
                    "tesseract OCR failed",
                    code="ocr_engine_error",
                    details={"stderr": exc.stderr},
                    retryable=False,
                ) from exc

        raise ToolExecutionError(
            "no local OCR strategy could extract text",
            code="ocr_unavailable",
            details={"image_path": image_path, "language": language},
        )


class UnsupportedCloudOCREngine(OCREngine):
    def __init__(self, name: str, credentials_configured: bool) -> None:
        self.name = name
        self.credentials_configured = credentials_configured

    def extract(
        self,
        *,
        image_bytes: Optional[bytes],
        image_path: Optional[str],
        language: str,
    ) -> OCRExtraction:
        if not self.credentials_configured:
            raise ToolExecutionError(
                f"{self.name} OCR credentials are not configured",
                code="ocr_credentials_missing",
                retryable=False,
            )
        raise ToolExecutionError(
            f"{self.name} OCR is not available in the local Day2 implementation",
            code="ocr_provider_unavailable",
            retryable=True,
        )


class OCRToolInput(BaseModel):
    image_base64: Optional[str] = None
    image_path: Optional[str] = None
    language: str = "zh-CN"
    provider: Optional[str] = None


class OCRTool(MCPTool):
    name = "ocr_extract"
    description = "Extract text from a screenshot using a configurable OCR strategy."
    input_model = OCRToolInput

    def __init__(
        self,
        settings: Optional[AppSettings] = None,
        engines: Optional[Dict[str, OCREngine]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.engines = engines or {
            "tesseract": TesseractOCREngine(),
            "baidu": UnsupportedCloudOCREngine(
                "baidu",
                bool(self.settings.baidu_ocr_api_key and self.settings.baidu_ocr_secret_key),
            ),
            "tencent": UnsupportedCloudOCREngine(
                "tencent",
                bool(self.settings.tencent_ocr_secret_id and self.settings.tencent_ocr_secret_key),
            ),
        }

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        provider = payload.get("provider") or self.settings.ocr_provider
        try:
            engine = self.engines[provider]
        except KeyError as exc:
            raise ToolExecutionError(
                f"unsupported OCR provider: {provider}",
                code="unsupported_ocr_provider",
            ) from exc

        image_bytes = None
        if payload.get("image_base64"):
            image_bytes = base64.b64decode(payload["image_base64"])

        extraction = engine.extract(
            image_bytes=image_bytes,
            image_path=payload.get("image_path"),
            language=payload["language"],
        )
        return {
            "text": extraction.text,
            "confidence": extraction.confidence,
            "engine": extraction.engine,
            "requires_manual_review": extraction.confidence < self.settings.ocr_confidence_threshold,
            "metadata": extraction.metadata,
        }
