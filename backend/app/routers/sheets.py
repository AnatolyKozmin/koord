from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import get_current_user, require_super_admin
from app.config import get_settings
from app.schemas.sheets import WriteBatchQueueRequest, WriteQueueRequest
from app.services import sheet_filter, sheets_queue_status, sheets_service

router = APIRouter(prefix="/sheets", tags=["sheets"])


@router.get("/queue/status/{job_id}")
def queue_job_status(job_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    """Статус задачи записи в Google (queued / finished / failed)."""
    _ = user
    try:
        return sheets_queue_status.get_job_payload(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Задача не найдена") from None


@router.post("/sync")
def sync_sheets(_: dict = Depends(require_super_admin)) -> dict[str, Any]:
    """Полное чтение листов из Google и запись снимка в Redis."""
    data = sheets_service.fetch_and_cache_all()
    return {"ok": True, "sheets": list(data.keys()), "rows": {k: len(v) for k, v in data.items()}}


@router.get("/{sheet_name}")
def get_sheet(sheet_name: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    """Данные листа из кэша Redis (после /sync). Для user — только назначенные строки (Polls/Domashki/Enquiries)."""
    rows = sheets_service.read_sheet_cached(sheet_name)
    if rows is None:
        return {
            "sheet": sheet_name,
            "values": [],
            "note": (
                "Данные из Google ещё не подгружены или вкладка с таким именем не попала в кэш. "
                "Супер-админ: откройте «Дашборд» и нажмите «Синхронизировать с Google». "
                f"Имя вкладки в таблице должно совпадать с настройкой (для сабов: {get_settings().sheet_name_subs})."
            ),
        }
    filtered = sheet_filter.filter_sheet_values(sheet_name, rows, user)
    _, indexed_rows = sheet_filter.filter_sheet_rows_with_indices(sheet_name, rows, user)
    data_row_indices = [idx for idx, _ in indexed_rows]
    return {
        "sheet": sheet_name,
        "values": filtered,
        "data_row_indices": data_row_indices,
    }


@router.post("/write-queue")
def queue_write(
    body: WriteQueueRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """Постановка записи в очередь Redis; фактический вызов Sheets API — в воркере (с лимитами и повторами)."""
    _ = user
    job_id = sheets_service.enqueue_cells_update(body.range_a1, body.values)
    return {"job_id": job_id, "status": "queued", "poll_url": f"/api/sheets/queue/status/{job_id}"}


@router.post("/write-queue-batch")
def queue_write_batch(
    body: WriteBatchQueueRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """Несколько ячеек/диапазонов за одну задачу воркера (batchUpdate)."""
    _ = user
    payload = [u.model_dump() for u in body.updates]
    job_id = sheets_service.enqueue_batch_values_update(payload)
    return {"job_id": job_id, "status": "queued", "poll_url": f"/api/sheets/queue/status/{job_id}"}
