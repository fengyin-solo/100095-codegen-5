"""实验废液接口：维护废液记录，覆盖登记移交、确认处置、回单归档与台账导入导出。"""
from __future__ import annotations

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.schemas import ActionResult, EntryPayload, ImportResult, PageResult
from app.services.waste import ImportFormatError, WasteService

router = APIRouter(prefix="/api/waste", tags=["实验废液"])

service = WasteService()

STATUSES = ["暂存中", "待移交", "已移交", "已处置"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按废液编号检索"),
    category: str | None = Query(default=None, description="按废液类别检索"),
    status: str | None = Query(default=None, description="暂存中、待移交、已移交、已处置"),
    date_from: str | None = Query(default=None, description="移交日期起，YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="移交日期止，YYYY-MM-DD"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按编号、类别、状态与移交日期区间过滤实验废液列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    try:
        items, total = service.list_entries(
            keyword=keyword, category=category, status=status,
            date_from=date_from, date_to=date_to, page=page, size=size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按废液编号检索"),
    category: str | None = Query(default=None, description="按废液类别检索"),
    status: str | None = Query(default=None, description="暂存中、待移交、已移交、已处置"),
    date_from: str | None = Query(default=None, description="移交日期起，YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="移交日期止，YYYY-MM-DD"),
) -> Response:
    """按当前筛选条件导出移交台账 CSV；导出的文件改完后可直接再导入。"""
    try:
        csv_text = service.export_csv(
            keyword=keyword, category=category, status=status,
            date_from=date_from, date_to=date_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    stamp = f"{date.today():%Y%m%d}"
    disposition = (
        f"attachment; filename=\"waste_ledger_{stamp}.csv\"; "
        f"filename*=UTF-8''{quote(f'废液移交台账_{stamp}.csv')}"
    )
    return Response(
        content=csv_text.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )


@router.post("/import", response_model=ImportResult)
async def import_entries(file: UploadFile) -> ImportResult:
    """批量补登记：按废液编号对账，已存在的更新移交日期与处置单位，不存在的补成暂存中。

    废液类别或产生环节为空的行整行跳过并在结果里列出行号与原因；
    文件整体格式不合法时整份拒绝，不会留下写了一半的台账。
    """
    content = await file.read()
    try:
        result = service.import_ledger(content)
    except ImportFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportResult(ok=True, **result)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条废液记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"废液记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条废液记录，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="废液记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条废液记录执行登记移交、确认处置、回单归档；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
