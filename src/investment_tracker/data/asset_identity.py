"""Asset identity resolution for imported product names."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from investment_tracker.data.enums import AssetType


@dataclass(frozen=True)
class AssetIdentity:
    asset_code: str
    asset_name: str
    source: str
    confidence: str


@dataclass(frozen=True)
class FundRegistryEntry:
    code: str
    canonical_name: str
    aliases: tuple[str, ...]
    currencies: tuple[str, ...]
    source: str


FUND_REGISTRY: tuple[FundRegistryEntry, ...] = (
    FundRegistryEntry(
        code="019711",
        canonical_name="广发道琼斯石油指数(QDII-LOF)美元现汇E",
        aliases=(
            "广发道琼斯石油指数(QDII-LOF)美元现汇E",
            "广发道琼斯石油指数（QDII-LOF）美元现汇E",
            "广发道琼斯石油指数(QDII-LOF)美元E",
            "广发道琼斯石油指数（QDII-LOF）美元E",
            "广发道琼斯石油指数(QDII-LOF)美元",
            "广发道琼斯石油指数（QDII-LOF）美元",
        ),
        currencies=("USD",),
        source="eastmoney_fund_archive",
    ),
)


class AssetIdentityResolver:
    """Resolve imported asset names to stable product codes when confidence is high."""

    def resolve(self, *, asset_type: AssetType, name: str, currency: Optional[str]) -> Optional[AssetIdentity]:
        if asset_type != AssetType.FUND:
            return None
        normalized_name = self.normalize_name(name)
        normalized_currency = currency.upper() if currency else None
        for entry in FUND_REGISTRY:
            if normalized_currency and normalized_currency not in entry.currencies:
                continue
            if normalized_name in {self.normalize_name(alias) for alias in entry.aliases}:
                return AssetIdentity(
                    asset_code=entry.code,
                    asset_name=entry.canonical_name,
                    source=entry.source,
                    confidence="alias",
                )
        return None

    @staticmethod
    def normalize_name(value: str) -> str:
        normalized = str(value or "").strip()
        normalized = normalized.replace("（", "(").replace("）", ")")
        normalized = normalized.replace("－", "-").replace("—", "-")
        normalized = re.sub(r"\s+", "", normalized)
        return normalized.upper()
