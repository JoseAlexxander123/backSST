from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class LoginRequest(BaseModel):
    # Usamos str para permitir dominios internos (.local) usados en los seeds
    email: str
    password: str


class LoginChallenge(BaseModel):
    pending_token: str
    otp_expires_in: int
    masked_email: str


class OTPVerifyRequest(BaseModel):
    pending_token: str
    code: str = Field(min_length=4, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class PermissionOut(BaseModel):
    code: str
    module: str
    action: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RoleOut(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    permissions: List[PermissionOut] = []

    model_config = ConfigDict(from_attributes=True)


class RoleCreateRequest(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    permission_codes: List[str] = []


class RoleUpdateRequest(RoleCreateRequest):
    pass


class PermissionCreateRequest(BaseModel):
    code: str
    module: str
    action: str
    description: Optional[str] = None


class AssignPermissionsRequest(BaseModel):
    permission_codes: List[str]


class AssignUserRolesRequest(BaseModel):
    role_codes: List[str]


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    first_name: str
    last_name: str
    roles: List[str]
    permissions: List[str]


class UserAdminOut(UserOut):
    is_active: bool
    two_factor_enabled: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    module_assignments_count: int = 0
    lesson_assignments_count: int = 0
    survey_assignments_count: int = 0
    pending_survey_assignments_count: int = 0


class UserCreateRequest(BaseModel):
    email: str
    first_name: str
    last_name: str
    password: str
    role_codes: List[str]
    is_active: bool = True
    two_factor_enabled: bool = True


class UserPasswordResetRequest(BaseModel):
    new_password: str
    notify_user: bool = False


class UserPasswordResetResult(BaseModel):
    user_id: int
    email: str
    sessions_revoked: int
    otp_codes_revoked: int
    notified_by_email: bool


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenResponse


class RefreshRequest(BaseModel):
    refresh_token: str
