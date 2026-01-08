from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.respository import get_db
from app.modules.auth.auth_schema import (
    AssignPermissionsRequest,
    AssignUserRolesRequest,
    AuthResponse,
    LoginChallenge,
    LoginRequest,
    OTPVerifyRequest,
    PermissionCreateRequest,
    PermissionOut,
    RefreshRequest,
    RoleCreateRequest,
    RoleOut,
    RoleUpdateRequest,
    UserOut,
)
from app.modules.auth.auth_service import AuthService, get_current_user, require_permissions

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginChallenge | AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.login(payload.email, payload.password)


@router.post("/verify-otp", response_model=AuthResponse)
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.verify_otp(payload.pending_token, payload.code)


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.refresh_session(payload.refresh_token)


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return AuthService(db)._serialize_user(current_user)  # type: ignore


@router.get(
    "/roles",
    response_model=List[RoleOut],
    dependencies=[Depends(require_permissions(["roles.manage"]))],
)
def list_roles(db: Session = Depends(get_db)):
    return AuthService(db).list_roles()


@router.post(
    "/roles",
    response_model=RoleOut,
    dependencies=[Depends(require_permissions(["roles.manage"]))],
)
def create_role(payload: RoleCreateRequest, db: Session = Depends(get_db)):
    return AuthService(db).create_role(payload)


@router.put(
    "/roles/{role_id}",
    response_model=RoleOut,
    dependencies=[Depends(require_permissions(["roles.manage"]))],
)
def update_role(role_id: int, payload: RoleUpdateRequest, db: Session = Depends(get_db)):
    return AuthService(db).update_role(role_id, payload)


@router.post(
    "/roles/{role_id}/permissions",
    response_model=RoleOut,
    dependencies=[Depends(require_permissions(["roles.manage"]))],
)
def assign_role_permissions(role_id: int, payload: AssignPermissionsRequest, db: Session = Depends(get_db)):
    return AuthService(db).assign_permissions(role_id, payload)


@router.get(
    "/permissions",
    response_model=List[PermissionOut],
    dependencies=[Depends(require_permissions(["roles.manage"]))],
)
def list_permissions(db: Session = Depends(get_db)):
    return AuthService(db).list_permissions()


@router.post(
    "/permissions",
    response_model=PermissionOut,
    dependencies=[Depends(require_permissions(["roles.manage"]))],
)
def create_permission(payload: PermissionCreateRequest, db: Session = Depends(get_db)):
    return AuthService(db).create_permission(payload)


@router.post(
    "/users/{user_id}/roles",
    response_model=UserOut,
    dependencies=[Depends(require_permissions(["users.manage"]))],
)
def assign_roles_to_user(user_id: int, payload: AssignUserRolesRequest, db: Session = Depends(get_db)):
    user = AuthService(db).assign_roles_to_user(user_id, payload)
    return AuthService(db)._serialize_user(user)  # type: ignore
