"""实验废液接口：维护废液记录，覆盖登记移交、确认处置、回单归档与台账批量导入导出。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.schemas import ActionResult, EntryPayload, PageResult, WasteImportResult
from app.services.waste import (
    EXPORT_FIELDS,
    WasteImportError,
    WasteService,
    is_valid_date,
    render_csv,
)

router = APIRouter(prefix="/api/waste", tags=["实验废液"])

service = WasteService()

LIST_FIELDS = ["废液编号", "废液类别", "产生环节", "暂存容器", "产生日期", "移交日期", "处置单位", "废液状态"]
STATUSES = ["暂存中", "待移交", "已移交", "已处置"]


def _check_date(name: str, value: str | None) -> None:
    if value is not None and not is_valid_date(value):
        raise HTTPException(status_code=400, detail=f"{name}需为 YYYY-MM-DD 格式，收到：{value}")


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按废液编号检索"),
    category: str | None = Query(default=None, description="按废液类别检索"),
    transfer_start: str | None = Query(default=None, description="移交日期起，YYYY-MM-DD"),
    transfer_end: str | None = Query(default=None, description="移交日期止，YYYY-MM-DD"),
    status: str | None = Query(default=None, description="暂存中、待移交、已移交、已处置"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按废液编号、废液类别、移交日期区间与状态过滤实验废液列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    _check_date("移交日期起", transfer_start)
    _check_date("移交日期止", transfer_end)
    if transfer_start and transfer_end and transfer_start > transfer_end:
        raise HTTPException(status_code=400, detail="移交日期起不能晚于移交日期止")
    items, total = service.list_entries(
        keyword=keyword,
        category=category,
        transfer_start=transfer_start,
        transfer_end=transfer_end,
        status=status,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


# 注意：/export 与 /import 必须声明在 /{entry_id} 之前，否则会被当成废液编号参数截获。
@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按废液编号检索"),
    category: str | None = Query(default=None, description="按废液类别检索"),
    transfer_start: str | None = Query(default=None, description="移交日期起，YYYY-MM-DD"),
    transfer_end: str | None = Query(default=None, description="移交日期止，YYYY-MM-DD"),
) -> Response:
    """按当前筛选条件（废液编号、废液类别、移交日期区间）导出 CSV 台账。

    导出列与导入模板一致：utf-8 带 BOM，Excel 直接打开不乱码，且可原样再导入。
    """
    _check_date("移交日期起", transfer_start)
    _check_date("移交日期止", transfer_end)
    if transfer_start and transfer_end and transfer_start > transfer_end:
        raise HTTPException(status_code=400, detail="移交日期起不能晚于移交日期止")
    rows = service.export_rows(
        keyword=keyword,
        category=category,
        transfer_start=transfer_start,
        transfer_end=transfer_end,
    )
    content = "\ufeff" + render_csv(rows)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="waste-ledger.csv"'},
    )


@router.post("/import", response_model=WasteImportResult)
async def import_entries(request: Request) -> WasteImportResult:
    """批量导入移交台账：按废液编号对账，存在则更新移交日期与处置单位，不存在则补成暂存中。

    整份文件先解析校验、暂存全部改动，全部通过后才落库；任一处格式不合格返回 400，
    台账保持导入前状态，不会留下半份数据。废液类别或产生环节为空的行整行跳过，
    跳过行的行号与原因随结果返回。
    """
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="未收到文件内容，请选择导出的废液台账 CSV 文件")
    try:
        # utf-8-sig 可吃掉导出文件自带的 BOM，同时兼容无 BOM 的 UTF-8。
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="文件不是合法的 UTF-8 文本，请使用本页面导出的 CSV 文件"
        ) from exc
    try:
        result = service.import_rows(text)
    except WasteImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WasteImportResult(**result)


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
