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
    UserAdminOut,
    UserCreateRequest,
    UserPasswordResetRequest,
    UserPasswordResetResult,
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


@router.get(
    "/users",
    response_model=List[UserAdminOut],
    dependencies=[Depends(require_permissions(["users.manage"]))],
)
def list_users(db: Session = Depends(get_db)):
    service = AuthService(db)
    return [service._serialize_user_admin(user) for user in service.list_users()]


@router.post(
    "/users",
    response_model=UserAdminOut,
    dependencies=[Depends(require_permissions(["users.manage"]))],
)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = AuthService(db)
    user = service.create_user(payload, current_user)
    return service._serialize_user_admin(user)


@router.post(
    "/users/{user_id}/reset-password",
    response_model=UserPasswordResetResult,
    dependencies=[Depends(require_permissions(["users.manage"]))],
)
def reset_user_password(
    user_id: int,
    payload: UserPasswordResetRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = AuthService(db)
    return service.reset_user_password(user_id, payload, current_user)


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
