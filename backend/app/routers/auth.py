from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import get_current_user
from app.auth.jwt import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services import users_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    u = users_service.authenticate(body.email, body.password)
    if not u:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong email or password")
    token = create_access_token(u["email"], u["role"])
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(email=user["email"], role=user["role"])
