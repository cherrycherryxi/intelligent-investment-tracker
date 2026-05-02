from __future__ import annotations

from pathlib import Path
import re

from investment_tracker.utils.xlsx_reader import XlsxReader


def test_xlsx_reader_extracts_sheet_names_and_rows() -> None:
    workbook_bytes = Path("investment_tracker_v5.xlsx").read_bytes()

    sheets = XlsxReader().read(workbook_bytes)

    assert [sheet.name for sheet in sheets] == ["资产总览", "外汇交易记录", "柜台债持仓"]
    assert sheets[1].rows[0][0] == "交易ID"
    trade_ids = [str(row[0]) for row in sheets[1].rows[1:] if row and re.fullmatch(r"FX\d{3}", str(row[0]))]
    assert trade_ids
