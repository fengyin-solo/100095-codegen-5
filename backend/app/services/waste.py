"""实验废液业务规则：状态流转、字段校验、筛选口径与台账导入导出都收在这里。"""
from __future__ import annotations

import copy
import csv
import io
import re
from datetime import date
from typing import Any

from app.store import store

MODULE = "waste"
REQUIRED_FIELDS = ["废液编号", "废液类别", "产生环节"]
STATUS_ORDER = ["暂存中", "待移交", "已移交", "已处置"]
ACTION_RULES = {"登记移交": "待移交", "确认处置": "已移交", "回单归档": "已处置"}
NEGATIVE_ACTIONS = []

EXPORT_FIELDS = ["废液编号", "废液类别", "产生环节", "暂存容器", "产生日期", "移交日期", "处置单位", "废液状态"]
IMPORT_REQUIRED_COLUMNS = ["废液编号", "废液类别", "产生环节", "移交日期", "处置单位"]
DATE_FIELDS = ["产生日期", "移交日期"]
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ImportFormatError(ValueError):
    """导入文件整体格式不合法：整份拒绝，一行都不写入。"""


def _check_date(value: str, label: str) -> str | None:
    """校验 YYYY-MM-DD 日期；空值返回 None，非法值抛出带说明的错误。"""
    text = str(value or "").strip()
    if not text:
        return None
    if not DATE_PATTERN.match(text):
        raise ValueError(f"{label}「{text}」格式不正确，应为 YYYY-MM-DD")
    try:
        date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{label}「{text}」不是真实存在的日期") from None
    return text


class WasteService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._filter_rows(
            keyword=keyword, category=category, status=status,
            date_from=date_from, date_to=date_to,
        )
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"废液记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于实验废液可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"废液记录已{action}"

    def export_csv(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> str:
        """按当前筛选条件导出 CSV；废液状态取台账里的权威状态，文件可改完再导入。"""
        rows = self._filter_rows(
            keyword=keyword, category=category, status=status,
            date_from=date_from, date_to=date_to,
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(EXPORT_FIELDS)
        for row in rows:
            writer.writerow([self._export_value(row, field) for field in EXPORT_FIELDS])
        return buffer.getvalue()

    def import_ledger(self, content: bytes) -> dict[str, Any]:
        """按废液编号对账批量补登记。

        已存在的编号只更新移交日期与处置单位；不存在的补登为暂存中。
        废液类别或产生环节为空的行整行跳过，并在结果里给出行号与原因；
        文件整体格式不合法时抛出 ImportFormatError，一行都不写入。
        """
        rows_in_file = self._parse_file(content)
        columns = self._locate_columns(rows_in_file[0])

        entries = store.rows(MODULE)
        by_number = {
            str(entry.get("废液编号") or "").strip(): entry
            for entry in entries
            if str(entry.get("废液编号") or "").strip()
        }

        plan: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        skipped: list[dict[str, Any]] = []
        next_id = max((int(entry.get("id", 0)) for entry in entries), default=0) + 1
        data_seen = False

        for line_no, record in enumerate(rows_in_file[1:], start=2):
            cells = [str(cell).strip() for cell in record]
            if not any(cells):
                continue
            data_seen = True
            values = {name: (cells[index] if index < len(cells) else "") for name, index in columns.items()}
            missing = [field for field in REQUIRED_FIELDS if not values.get(field)]
            if missing:
                skipped.append({"row": line_no, "reason": f"{'、'.join(missing)}为空"})
                continue
            try:
                dates = {field: _check_date(values.get(field, ""), field) for field in DATE_FIELDS}
            except ValueError as exc:
                skipped.append({"row": line_no, "reason": str(exc)})
                continue
            update_values = {"移交日期": dates["移交日期"], "处置单位": values.get("处置单位") or None}
            existing = by_number.get(values["废液编号"])
            if existing is not None:
                plan.append(("update", existing, update_values))
                continue
            entry = {
                "id": next_id,
                "废液编号": values["废液编号"],
                "废液类别": values["废液类别"],
                "产生环节": values["产生环节"],
                "暂存容器": values.get("暂存容器") or None,
                "产生日期": dates["产生日期"],
                "移交日期": dates["移交日期"],
                "处置单位": values.get("处置单位") or None,
                "废液状态": STATUS_ORDER[0],
                "status": STATUS_ORDER[0],
                "pending": True,
                "abnormal": False,
            }
            next_id += 1
            by_number[entry["废液编号"]] = entry
            plan.append(("create", entry, {}))

        if not data_seen:
            raise ImportFormatError("文件里没有可导入的数据行，台账未做任何改动")

        created = sum(1 for kind, _, _ in plan if kind == "create")
        updated = sum(1 for kind, _, _ in plan if kind == "update")

        snapshot = copy.deepcopy(entries)
        try:
            for kind, target, values in plan:
                if kind == "create":
                    entries.append(target)
                else:
                    target.update(values)
        except Exception:
            entries[:] = snapshot
            raise

        return {
            "message": f"导入完成：更新 {updated} 条，补登 {created} 条，跳过 {len(skipped)} 行",
            "created": created,
            "updated": updated,
            "skipped": skipped,
        }

    def _filter_rows(
        self,
        *,
        keyword: str | None,
        category: str | None,
        status: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> list[dict[str, Any]]:
        start = _check_date(date_from, "移交日期起") if date_from else None
        end = _check_date(date_to, "移交日期止") if date_to else None
        if start and end and start > end:
            raise ValueError(f"移交日期起「{start}」晚于移交日期止「{end}」，请调整区间")
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("废液编号", ""))]
        if category:
            rows = [row for row in rows if category in str(row.get("废液类别", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if start or end:
            rows = [row for row in rows if self._in_date_range(row, start, end)]
        return list(rows)

    @staticmethod
    def _in_date_range(row: dict[str, Any], start: str | None, end: str | None) -> bool:
        value = str(row.get("移交日期") or "").strip()
        if not value:
            return False
        if start and value < start:
            return False
        if end and value > end:
            return False
        return True

    @staticmethod
    def _export_value(row: dict[str, Any], field: str) -> str:
        value = row.get("status") if field == "废液状态" else row.get(field)
        return "" if value is None else str(value)

    @staticmethod
    def _parse_file(content: bytes) -> list[list[str]]:
        if not content or not content.strip():
            raise ImportFormatError("导入文件为空，没有可读取的内容")
        text = None
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ImportFormatError("文件编码无法识别，请使用 UTF-8 或 GBK 编码的 CSV 文件")
        try:
            rows = list(csv.reader(io.StringIO(text)))
        except csv.Error as exc:
            raise ImportFormatError(f"文件不是有效的 CSV：{exc}") from exc
        if not rows:
            raise ImportFormatError("导入文件为空，没有可读取的内容")
        return rows

    @staticmethod
    def _locate_columns(header: list[str]) -> dict[str, int]:
        titles = [str(cell).strip().lstrip("﻿") for cell in header]
        missing = [name for name in IMPORT_REQUIRED_COLUMNS if name not in titles]
        if missing:
            raise ImportFormatError(
                f"文件缺少必需列：{'、'.join(missing)}；表头应为：{'、'.join(EXPORT_FIELDS)}"
            )
        columns: dict[str, int] = {}
        for index, name in enumerate(titles):
            if name in EXPORT_FIELDS and name not in columns:
                columns[name] = index
        return columns
