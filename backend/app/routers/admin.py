from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require_super_admin
from app.schemas.admin import AssignmentPutRequest, DistributeRequest, UserCreateRequest, UserOutAdmin
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
