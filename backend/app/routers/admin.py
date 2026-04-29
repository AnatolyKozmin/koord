from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require_super_admin
from app.schemas.admin import AssignmentPutRequest, AssignRowRequest, DistributeCustomRequest, DistributeRequest, SetPasswordRequest, UserCreateRequest, UserOutAdmin
from app.services import assignments_service, users_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOutAdmin])
def admin_list_users(_: dict = Depends(require_super_admin)) -> list[UserOutAdmin]:
    return [UserOutAdmin(**u) for u in users_service.list_users()]


@router.post("/users", response_model=UserOutAdmin)
def admin_create_user(body: UserCreateRequest, _: dict = Depends(require_super_admin)) -> UserOutAdmin:
    try:
        users_service.create_user(body.email, body.password, body.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пользователь уже существует")
    return UserOutAdmin(email=body.email.lower(), role=body.role)


@router.patch("/users/{email}/password")
def admin_set_password(
    email: str,
    body: SetPasswordRequest,
    _: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    if not users_service.set_password(email, body.password):
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"ok": True, "email": email.lower()}


@router.get("/assignments")
def admin_list_assignments(_: dict = Depends(require_super_admin)) -> dict[str, dict[str, list[int]]]:
    return assignments_service.list_all_assignments()


@router.put("/assignments/{email}")
def admin_put_assignment(
    email: str,
    body: AssignmentPutRequest,
    _: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    assignments_service.set_assignment(email, body.rows_by_sheet)
    return {"ok": True, "email": email.lower()}


@router.delete("/assignments/{email}")
def admin_clear_assignment(
    email: str,
    _: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    """Удалить все назначения для пользователя."""
    assignments_service.set_assignment(email, {})
    return {"ok": True, "email": email.lower()}


@router.post("/assignments/distribute")
def admin_distribute(
    body: DistributeRequest,
    _: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    known = {u["email"].lower() for u in users_service.list_users()}
    for e in body.user_emails:
        if str(e).lower() not in known:
            raise HTTPException(status_code=400, detail=f"Неизвестный пользователь: {e}")
    try:
        result = assignments_service.distribute_sheet(
            body.sheet_name.strip(),
            body.per_user,
            [str(e) for e in body.user_emails],
            by_columns=body.by_columns,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "assigned_rows": result}


@router.get("/sheet-rows/{sheet_name:path}")
def admin_sheet_rows(
    sheet_name: str,
    _: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    """
    Все строки листа из кэша + словарь row_index → email проверяющего.
    Возвращает первые 5 значений каждой строки для превью.
    """
    from app.services import sheets_service

    rows = sheets_service.read_sheet_cached(sheet_name)
    if not rows:
        raise HTTPException(status_code=404, detail="Нет данных в кэше — выполните синхронизацию")
    reviewer_map = assignments_service.row_to_reviewer_map(sheet_name)
    header = [str(c) for c in rows[0]] if rows else []
    result = []
    for i, row in enumerate(rows[1:], start=1):
        result.append(
            {
                "index": i,
                "preview": [str(c) for c in row[:7]],
                "reviewer": reviewer_map.get(i),
            }
        )
    return {"sheet": sheet_name, "header": header[:7], "rows": result}


@router.post("/assignments/assign-row")
def admin_assign_row(
    body: AssignRowRequest,
    _: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    assignments_service.assign_row_to_user(
        body.sheet_name,
        body.row_index,
        str(body.email) if body.email else None,
    )
    return {"ok": True, "row_index": body.row_index, "email": str(body.email) if body.email else None}


@router.post("/assignments/distribute-custom")
def admin_distribute_custom(
    body: DistributeCustomRequest,
    _: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    known = {u["email"].lower() for u in users_service.list_users()}
    for e in body.user_counts:
        if str(e).lower() not in known:
            raise HTTPException(status_code=400, detail=f"Неизвестный пользователь: {e}")
    try:
        result = assignments_service.distribute_sheet_custom(
            body.sheet_name.strip(),
            {str(e): cnt for e, cnt in body.user_counts.items()},
            by_columns=body.by_columns,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "assigned_rows": result}
