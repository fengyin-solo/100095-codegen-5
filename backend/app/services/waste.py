"""实验废液业务规则：状态流转、字段校验、筛选口径与台账导入导出都收在这里。"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

from app.store import store

MODULE = "waste"
REQUIRED_FIELDS = ["废液编号", "废液类别", "产生环节"]
# 导出列固定为这 8 列，导入时表头必须与它逐列一致，保证导出文件可无损再导入。
EXPORT_FIELDS = ["废液编号", "废液类别", "产生环节", "暂存容器", "产生日期", "移交日期", "处置单位", "废液状态"]
STATUS_ORDER = ["暂存中", "待移交", "已移交", "已处置"]
ACTION_RULES = {"登记移交": "待移交", "确认处置": "已移交", "回单归档": "已处置"}
NEGATIVE_ACTIONS = []

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class WasteImportError(ValueError):
    """导入文件整体不合格（编码、表头、列数、重复编号、日期格式等），整份文件不得写入。"""


def is_valid_date(value: str) -> bool:
    """移交日期只接受 YYYY-MM-DD，避免 2026.9.1 这类写法进台账后对不上账。"""
    if not _DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


class WasteService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        transfer_start: str | None = None,
        transfer_end: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._filter_rows(
            keyword=keyword,
            category=category,
            transfer_start=transfer_start,
            transfer_end=transfer_end,
            status=status,
        )
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def export_rows(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        transfer_start: str | None = None,
        transfer_end: str | None = None,
    ) -> list[dict[str, Any]]:
        """导出与列表同一套筛选口径下的全量记录（不走分页）。"""
        return self._filter_rows(
            keyword=keyword,
            category=category,
            transfer_start=transfer_start,
            transfer_end=transfer_end,
        )

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

    # ------------------------------------------------------------------
    # 导入：先整份解析、逐行校验并把改动暂存起来，全部通过后才一次性落库，
    # 任何一处不合格都直接抛 WasteImportError，台账保持导入前的状态。
    # ------------------------------------------------------------------
    def import_rows(self, text: str) -> dict[str, Any]:
        staged, skipped, scanned = self._plan_import(text)
        # 校验阶段全部通过后才提交：这里之后只做内存赋值，不能再抛错，避免半份数据。
        for entry, values in staged:
            if entry is None:
                store.rows(MODULE).append(values)
            else:
                entry["移交日期"] = values["移交日期"]
                entry["处置单位"] = values["处置单位"]
        updated = sum(1 for entry, _ in staged if entry is not None)
        created = len(staged) - updated
        return {
            "scanned": scanned,
            "updated": updated,
            "created": created,
            "skipped": skipped,
        }

    def _plan_import(
        self, text: str
    ) -> tuple[list[tuple[dict[str, Any] | None, dict[str, Any]]], list[dict[str, int | str]], int]:
        if not text or not text.strip():
            raise WasteImportError("文件内容为空，请使用导出的废液台账 CSV 文件")
        reader = csv.reader(io.StringIO(text))
        staged: list[tuple[dict[str, Any] | None, dict[str, Any]]] = []
        skipped: list[dict[str, int | str]] = []
        seen_codes: dict[str, int] = {}
        existing = {str(row.get("废液编号", "")).strip(): row for row in store.rows(MODULE)}
        next_id = max((int(row.get("id", 0)) for row in store.rows(MODULE)), default=0)
        scanned = 0

        try:
            try:
                header = next(reader)
            except StopIteration as exc:
                raise WasteImportError("文件内容为空，请使用导出的废液台账 CSV 文件") from exc
            header = [cell.strip() for cell in header]
            if header != EXPORT_FIELDS:
                raise WasteImportError(
                    "文件表头与废液台账模板不一致，期望列：" + "、".join(EXPORT_FIELDS)
                )

            for row in reader:
                line_no = reader.line_num
                # 整行为空多半是编辑器留下的空行，不算台账记录，静默跳过。
                if not any(cell.strip() for cell in row):
                    continue
                scanned += 1
                if len(row) > len(EXPORT_FIELDS):
                    raise WasteImportError(
                        f"第 {line_no} 行列数多于表头（{len(EXPORT_FIELDS)} 列），文件格式不正确，整份文件未导入"
                    )
                cells = [cell.strip() for cell in row] + [""] * (len(EXPORT_FIELDS) - len(row))
                record = dict(zip(EXPORT_FIELDS, cells))

                code = record["废液编号"]
                # 编号无法对账、或关键业务列为空时整行跳过，并在结果里标明行号与原因。
                if not code:
                    skipped.append({"line": line_no, "reason": "废液编号为空，无法对账"})
                    continue
                if not record["废液类别"]:
                    skipped.append({"line": line_no, "reason": "废液类别为空"})
                    continue
                if not record["产生环节"]:
                    skipped.append({"line": line_no, "reason": "产生环节为空"})
                    continue
                transfer_date = record["移交日期"]
                if transfer_date and not is_valid_date(transfer_date):
                    raise WasteImportError(
                        f"第 {line_no} 行移交日期「{transfer_date}」不是 YYYY-MM-DD 格式，整份文件未导入"
                    )
                if code in seen_codes:
                    raise WasteImportError(
                        f"废液编号「{code}」在第 {seen_codes[code]} 行与第 {line_no} 行重复，"
                        "无法按编号对账，整份文件未导入"
                    )
                seen_codes[code] = line_no

                entry = existing.get(code)
                if entry is not None:
                    # 已存在：只更新移交日期与处置单位，其余字段与状态保持不动。
                    staged.append((entry, {"移交日期": transfer_date, "处置单位": record["处置单位"]}))
                else:
                    # 不存在：按暂存中补登记，内部状态与展示状态都置为暂存中。
                    next_id += 1
                    new_entry: dict[str, Any] = {"id": next_id}
                    new_entry.update({field: record[field] for field in EXPORT_FIELDS})
                    new_entry["废液状态"] = STATUS_ORDER[0]
                    new_entry["status"] = STATUS_ORDER[0]
                    new_entry["pending"] = True
                    new_entry["abnormal"] = False
                    staged.append((None, new_entry))
        except csv.Error as exc:
            raise WasteImportError(f"文件不是合法的 CSV 格式（{exc}），整份文件未导入") from exc

        return staged, skipped, scanned

    def _filter_rows(
        self,
        *,
        keyword: str | None,
        category: str | None,
        transfer_start: str | None,
        transfer_end: str | None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = list(store.rows(MODULE))
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("废液编号", ""))]
        if category:
            rows = [row for row in rows if category in str(row.get("废液类别", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if transfer_start or transfer_end:
            # 日期统一为 YYYY-MM-DD，字符串比较与时间先后一致；未填移交日期的记录不进区间。
            rows = [
                row
                for row in rows
                if (date := str(row.get("移交日期") or "").strip())
                and (not transfer_start or date >= transfer_start)
                and (not transfer_end or date <= transfer_end)
            ]
        return rows


def render_csv(rows: list[dict[str, Any]]) -> str:
    """把台账记录渲染成导出 CSV：列顺序固定，缺字段补空，保证再导入能对上表头。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_FIELDS)
    for row in rows:
        writer.writerow(["" if row.get(field) is None else str(row.get(field)) for field in EXPORT_FIELDS])
    return buffer.getvalue()
