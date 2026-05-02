"""Minimal XLSX reader based on the standard library."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, List
from xml.etree import ElementTree as ET
from zipfile import ZipFile


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "docrel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


@dataclass(frozen=True)
class WorkbookSheet:
    name: str
    rows: List[List[object]]


class XlsxReader:
    """Read workbook sheets and cell values from XLSX bytes."""

    def read(self, workbook_bytes: bytes) -> List[WorkbookSheet]:
        with ZipFile(io.BytesIO(workbook_bytes)) as archive:
            shared_strings = self._read_shared_strings(archive)
            workbook_sheet_map = self._read_workbook_sheet_map(archive)
            relationship_map = self._read_relationship_map(archive)

            sheets: List[WorkbookSheet] = []
            for sheet_name, rel_id in workbook_sheet_map:
                target = relationship_map[rel_id]
                rows = self._read_sheet_rows(archive, target, shared_strings)
                sheets.append(WorkbookSheet(name=sheet_name, rows=rows))
            return sheets

    def _read_shared_strings(self, archive: ZipFile) -> List[str]:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []

        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        values: List[str] = []
        for item in root.findall("main:si", NS):
            text_parts = [node.text or "" for node in item.findall(".//main:t", NS)]
            values.append("".join(text_parts))
        return values

    def _read_workbook_sheet_map(self, archive: ZipFile) -> List[tuple[str, str]]:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = []
        for sheet in root.findall("main:sheets/main:sheet", NS):
            sheets.append((sheet.attrib["name"], sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]))
        return sheets

    def _read_relationship_map(self, archive: ZipFile) -> Dict[str, str]:
        root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationships: Dict[str, str] = {}
        for rel in root.findall("rel:Relationship", NS):
            target = rel.attrib["Target"].lstrip("/")
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            relationships[rel.attrib["Id"]] = target
        return relationships

    def _read_sheet_rows(self, archive: ZipFile, sheet_path: str, shared_strings: List[str]) -> List[List[object]]:
        root = ET.fromstring(archive.read(sheet_path))
        rows: List[List[object]] = []

        for row_node in root.findall("main:sheetData/main:row", NS):
            cells: List[object] = []
            last_column = 0
            for cell_node in row_node.findall("main:c", NS):
                ref = cell_node.attrib.get("r", "")
                column_index = self._column_index(ref)
                while last_column < column_index - 1:
                    cells.append(None)
                    last_column += 1
                cells.append(self._parse_cell(cell_node, shared_strings))
                last_column = column_index
            rows.append(cells)
        return rows

    def _parse_cell(self, cell_node: ET.Element, shared_strings: List[str]) -> object:
        cell_type = cell_node.attrib.get("t")
        value_node = cell_node.find("main:v", NS)
        inline_text = "".join(node.text or "" for node in cell_node.findall(".//main:t", NS))

        if cell_type == "s" and value_node is not None:
            index = int(value_node.text or 0)
            return shared_strings[index]
        if cell_type == "inlineStr":
            return inline_text or None
        if value_node is None:
            return inline_text or None

        raw = value_node.text or ""
        if cell_type == "b":
            return raw == "1"
        if self._is_number(raw):
            return float(raw) if "." in raw else int(raw)
        return raw

    def _column_index(self, cell_ref: str) -> int:
        letters = "".join(character for character in cell_ref if character.isalpha())
        result = 0
        for character in letters:
            result = result * 26 + (ord(character.upper()) - ord("A") + 1)
        return result

    def _is_number(self, value: str) -> bool:
        try:
            float(value)
            return True
        except ValueError:
            return False
