from datetime import datetime, timedelta
import random
from typing import Iterable, List, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session, joinedload

from app.config.settings import settings
from app.core.security import (
    create_access_token,
    create_pending_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.infrastructure.respository import get_db
from app.modules.auth.auth_schema import (
    AssignPermissionsRequest,
    AssignUserRolesRequest,
    PermissionCreateRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
    TokenResponse,
    UserAdminOut,
    UserCreateRequest,
    UserPasswordResetRequest,
    UserPasswordResetResult,
    UserOut,
)
from app.modules.models import (
    Lesson,
    Module,
    ModuleAssignment,
    Permission,
    RefreshToken,
    Role,
    SurveyAssignment,
    SurveyCampaign,
    SurveyTemplate,
    TwoFactorCode,
    User,
    UserLessonProgress,
)
from app.shared.email import send_email

bearer_scheme = HTTPBearer(auto_error=False)


def validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 8 caracteres",
        )
    if not any(c.isupper() for c in password) or not any(c.islower() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe incluir mayusculas y minusculas",
        )
    if not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe incluir al menos un numero",
        )


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def login(self, email: str, password: str) -> dict:
        user = self._get_user_with_relations(email=email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

        # Solo se omite OTP cuando 2FA esta desactivado o el usuario no lo requiere.
        if settings.DISABLE_2FA or not user.two_factor_enabled:
            return self._build_auth_response(user)

        otp, _raw_code = self._create_otp(user)
        pending_token = create_pending_token(user.id, otp.id, settings.OTP_EXPIRE_MINUTES)
        return {
            "pending_token": pending_token,
            "otp_expires_in": settings.OTP_EXPIRE_MINUTES * 60,
            "masked_email": self._mask_email(user.email),
        }

    def verify_otp(self, pending_token: str, code: str) -> dict:
        payload = decode_token(pending_token, expected_type="pending")
        user_id = int(payload.get("sub"))
        otp_id = int(payload.get("otp_id"))

        otp = (
            self.db.query(TwoFactorCode)
            .filter(TwoFactorCode.id == otp_id, TwoFactorCode.user_id == user_id, TwoFactorCode.purpose == "login")
            .first()
        )
        if not otp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP no encontrado")
        if otp.consumed_at or otp.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP expirado")
        if otp.code != hash_token(code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codigo incorrecto")

        otp.consumed_at = datetime.utcnow()
        user = self._get_user_with_relations(user_id=user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
        user.last_login_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)

        return self._build_auth_response(user)

    def refresh_session(self, refresh_token: str) -> dict:
        hashed = hash_token(refresh_token)
        token_row = (
            self.db.query(RefreshToken)
            .options(joinedload(RefreshToken.user).joinedload(User.roles).joinedload(Role.permissions))
            .filter(RefreshToken.token == hashed, RefreshToken.revoked.is_(False))
            .first()
        )
        if not token_row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")
        if token_row.expires_at < datetime.utcnow():
            token_row.revoked = True
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expirado")

        user = token_row.user
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")

        token_row.revoked = True
        self.db.commit()
        return self._build_auth_response(user)

    def me(self, user: User) -> dict:
        return {"user": self._serialize_user(user)}

    def list_roles(self) -> List[Role]:
        return self.db.query(Role).options(joinedload(Role.permissions)).all()

    def list_permissions(self) -> List[Permission]:
        return self.db.query(Permission).all()

    def list_users(self) -> List[User]:
        return (
            self.db.query(User)
            .options(
                joinedload(User.roles).joinedload(Role.permissions),
                joinedload(User.module_assignments),
                joinedload(User.lesson_progress),
                joinedload(User.survey_targets),
                joinedload(User.survey_respondent_assignments),
                joinedload(User.survey_evaluator_assignments),
            )
            .order_by(User.created_at.desc(), User.id.desc())
            .all()
        )

    def create_user(self, payload: UserCreateRequest, current_user: User) -> User:
        validate_password_policy(payload.password)
        email = payload.email.strip().lower()
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El correo es obligatorio")
        if self.db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe un usuario con ese correo")

        role_codes = sorted({code.strip() for code in payload.role_codes if code.strip()})
        if not role_codes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes seleccionar al menos un rol")
        self._validate_role_combination(role_codes)

        roles = self.db.query(Role).filter(Role.code.in_(role_codes)).all()
        found_codes = {role.code for role in roles}
        missing_codes = sorted(set(role_codes) - found_codes)
        if missing_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Roles no encontrados: {', '.join(missing_codes)}",
            )

        first_name = payload.first_name.strip()
        last_name = payload.last_name.strip()
        if not first_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nombre es obligatorio")
        if not last_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El apellido es obligatorio")

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            hashed_password=hash_password(payload.password),
            is_active=payload.is_active,
            two_factor_enabled=payload.two_factor_enabled,
        )
        user.roles = roles
        self.db.add(user)
        self.db.flush()

        if self._is_collaborator_role_set(role_codes):
            self._provision_collaborator(user, current_user)

        self.db.commit()
        return self._get_user_with_admin_relations(user.id)

    def reset_user_password(
        self,
        user_id: int,
        payload: UserPasswordResetRequest,
        current_user: User,
    ) -> UserPasswordResetResult:
        validate_password_policy(payload.new_password)
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        user.hashed_password = hash_password(payload.new_password)
        sessions_revoked = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
            .update({"revoked": True}, synchronize_session=False)
        )
        otp_codes_revoked = (
            self.db.query(TwoFactorCode)
            .filter(TwoFactorCode.user_id == user.id, TwoFactorCode.consumed_at.is_(None))
            .delete(synchronize_session=False)
        )

        if payload.notify_user:
            try:
                send_email(
                    recipient=user.email,
                    subject="Recuperacion de contrasena SST",
                    body=(
                        f"Hola {user.name or user.email},\n\n"
                        "Un superadministrador ha restablecido tu acceso al sistema SST.\n"
                        f"Tu nueva contrasena temporal es: {payload.new_password}\n\n"
                        "Por seguridad, ingresa nuevamente al sistema con esta clave."
                    ),
                )
            except Exception as exc:  # pragma: no cover - SMTP depende de entorno
                self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"No se pudo enviar el correo de recuperacion: {exc}",
                )

        self.db.commit()
        return UserPasswordResetResult(
            user_id=user.id,
            email=user.email,
            sessions_revoked=sessions_revoked,
            otp_codes_revoked=otp_codes_revoked,
            notified_by_email=payload.notify_user,
        )

    def create_role(self, payload: RoleCreateRequest) -> Role:
        role = Role(name=payload.name, code=payload.code, description=payload.description)
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        if payload.permission_codes:
            self._sync_role_permissions(role, payload.permission_codes)
        return self._get_role_with_permissions(role.id)

    def update_role(self, role_id: int, payload: RoleUpdateRequest) -> Role:
        role = self._get_role_with_permissions(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
        role.name = payload.name
        role.code = payload.code
        role.description = payload.description
        self.db.commit()
        if payload.permission_codes is not None:
            self._sync_role_permissions(role, payload.permission_codes)
        return self._get_role_with_permissions(role_id)

    def create_permission(self, payload: PermissionCreateRequest) -> Permission:
        perm = Permission(code=payload.code, module=payload.module, action=payload.action, description=payload.description)
        self.db.add(perm)
        self.db.commit()
        self.db.refresh(perm)
        return perm

    def assign_permissions(self, role_id: int, payload: AssignPermissionsRequest) -> Role:
        role = self._get_role_with_permissions(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
        self._sync_role_permissions(role, payload.permission_codes)
        return self._get_role_with_permissions(role_id)

    def assign_roles_to_user(self, user_id: int, payload: AssignUserRolesRequest) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        roles = self.db.query(Role).filter(Role.code.in_(payload.role_codes)).all()
        if not roles:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Roles no encontrados")
        user.roles = roles
        self.db.commit()
        self.db.refresh(user)
        return self._get_user_with_relations(user_id=user.id)

    # -------------------------
    # Helpers
    # -------------------------
    def _create_otp(self, user: User) -> tuple[TwoFactorCode, str]:
        # limpiar tokens vencidos previos
        self.db.query(TwoFactorCode).filter(
            TwoFactorCode.user_id == user.id,
            TwoFactorCode.purpose == "login",
            TwoFactorCode.expires_at < datetime.utcnow(),
        ).delete()
        code = f"{random.randint(0, 999999):06d}"
        hashed_code = hash_token(code)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        otp = TwoFactorCode(
            user_id=user.id,
            code=hashed_code,
            purpose="login",
            sent_to=user.email,
            expires_at=expires_at,
        )
        self.db.add(otp)
        self.db.commit()
        self.db.refresh(otp)
        try:
            send_email(
                recipient=user.email,
                subject="Codigo de acceso SST",
                body=f"Tu codigo OTP es: {code}. Expira en {settings.OTP_EXPIRE_MINUTES} minutos.",
            )
        except Exception as exc:  # pragma: no cover - SMTP depende de entorno
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"No se pudo enviar el correo OTP: {exc}",
            )
        return otp, code

    def _build_auth_response(self, user: User) -> dict:
        profile = self._serialize_user(user)
        access_payload = {
            "sub": str(user.id),
            "roles": profile.roles,
            "permissions": profile.permissions,
            "name": user.name,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
        access_token = create_access_token(access_payload, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_raw, refresh_exp = create_refresh_token(user.id, settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_record = RefreshToken(
            user_id=user.id,
            token=hash_token(refresh_raw),
            expires_at=refresh_exp,
            revoked=False,
        )
        self.db.add(refresh_record)
        self.db.commit()
        expires_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return {
            "user": profile,
            "tokens": TokenResponse(
                access_token=access_token,
                refresh_token=refresh_raw,
                expires_in=expires_seconds,
            ),
        }

    def _serialize_user(self, user: User) -> UserOut:
        roles = [r.code for r in user.roles]
        permissions: Set[str] = set()
        for role in user.roles:
            for perm in role.permissions:
                permissions.add(perm.code)
        return UserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            first_name=user.first_name,
            last_name=user.last_name,
            roles=roles,
            permissions=sorted(list(permissions)),
        )

    def _serialize_user_admin(self, user: User) -> UserAdminOut:
        profile = self._serialize_user(user)
        survey_ids = {
            assignment.id
            for assignment in [
                *user.survey_targets,
                *user.survey_respondent_assignments,
                *user.survey_evaluator_assignments,
            ]
        }
        pending_survey_ids = {
            assignment.id
            for assignment in [
                *user.survey_targets,
                *user.survey_respondent_assignments,
                *user.survey_evaluator_assignments,
            ]
            if assignment.status != "completed"
        }
        return UserAdminOut(
            id=profile.id,
            email=profile.email,
            name=profile.name,
            first_name=profile.first_name,
            last_name=profile.last_name,
            roles=profile.roles,
            permissions=profile.permissions,
            is_active=user.is_active,
            two_factor_enabled=user.two_factor_enabled,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            module_assignments_count=len(user.module_assignments),
            lesson_assignments_count=len(user.lesson_progress),
            survey_assignments_count=len(survey_ids),
            pending_survey_assignments_count=len(pending_survey_ids),
        )

    def _mask_email(self, email: str) -> str:
        name, _, domain = email.partition("@")
        if len(name) <= 2:
            return "***@" + domain
        return f"{name[0]}***{name[-1]}@{domain}"

    def _sync_role_permissions(self, role: Role, permission_codes: Iterable[str]) -> None:
        perms = self.db.query(Permission).filter(Permission.code.in_(list(permission_codes))).all()
        role.permissions = perms
        self.db.commit()
        self.db.refresh(role)

    def _validate_role_combination(self, role_codes: list[str]) -> None:
        management_roles = {"superadmin", "admin", "leader", "supervisor"}
        role_set = set(role_codes)
        if "collaborator" in role_set and role_set.intersection(management_roles):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede mezclar collaborator con roles de gestion en el registro inicial",
            )

    def _is_collaborator_role_set(self, role_codes: list[str]) -> bool:
        return "collaborator" in set(role_codes)

    def _provision_collaborator(self, user: User, current_user: User) -> None:
        modules = (
            self.db.query(Module)
            .options(joinedload(Module.owner).joinedload(User.roles))
            .order_by(Module.id.asc())
            .all()
        )
        for module in modules:
            assigner_id = self._resolve_assigner_for_module(module, current_user)
            existing_assignment = (
                self.db.query(ModuleAssignment)
                .filter(ModuleAssignment.user_id == user.id, ModuleAssignment.module_id == module.id)
                .first()
            )
            if existing_assignment is None:
                self.db.add(
                    ModuleAssignment(
                        module_id=module.id,
                        user_id=user.id,
                        assigned_by=assigner_id,
                    )
                )

        self.db.flush()
        self._ensure_lesson_progress_rows(user.id)
        self._ensure_collaborator_survey_assignments(user.id, created_by=current_user.id)

    def _resolve_assigner_for_module(self, module: Module, current_user: User) -> int:
        owner = module.owner
        if owner and owner.is_active and self._has_management_role({role.code for role in owner.roles}):
            return owner.id
        return current_user.id

    def _ensure_lesson_progress_rows(self, user_id: int) -> None:
        existing_lesson_ids = {
            row.lesson_id
            for row in self.db.query(UserLessonProgress).filter(UserLessonProgress.user_id == user_id).all()
        }
        lessons = self.db.query(Lesson).order_by(Lesson.id.asc()).all()
        for lesson in lessons:
            if lesson.id in existing_lesson_ids:
                continue
            self.db.add(
                UserLessonProgress(
                    user_id=user_id,
                    lesson_id=lesson.id,
                    completed=False,
                    completed_at=None,
                )
            )

    def _ensure_collaborator_survey_assignments(self, user_id: int, created_by: int) -> None:
        campaign = self._ensure_post_test_campaign(created_by)
        templates = (
            self.db.query(SurveyTemplate)
            .filter(
                SurveyTemplate.code.in_(
                    [
                        "functionality_checklist",
                        "sst_awareness",
                        "bidirectional_communication",
                        "usability",
                    ]
                ),
                SurveyTemplate.is_active.is_(True),
            )
            .all()
        )
        module_assignments = (
            self.db.query(ModuleAssignment)
            .join(ModuleAssignment.user)
            .options(
                joinedload(ModuleAssignment.user).joinedload(User.roles),
                joinedload(ModuleAssignment.assigned_by_user).joinedload(User.roles),
            )
            .filter(ModuleAssignment.user_id == user_id)
            .order_by(ModuleAssignment.module_id.asc())
            .all()
        )
        primary_module_id = min((assignment.module_id for assignment in module_assignments), default=None)

        for template in templates:
            self._ensure_survey_assignment(
                campaign_id=campaign.id,
                template_id=template.id,
                target_user_id=user_id,
                respondent_user_id=user_id,
                evaluator_user_id=None,
                module_id=primary_module_id,
            )

        task_verification_template = (
            self.db.query(SurveyTemplate)
            .filter(SurveyTemplate.code == "task_verification", SurveyTemplate.is_active.is_(True))
            .first()
        )
        if task_verification_template is None:
            return

        for assignment in module_assignments:
            evaluator = assignment.assigned_by_user
            if evaluator is None or not evaluator.is_active:
                continue
            evaluator_role_codes = {role.code for role in evaluator.roles}
            if not evaluator_role_codes.intersection({"leader", "admin", "superadmin"}):
                continue
            self._ensure_survey_assignment(
                campaign_id=campaign.id,
                template_id=task_verification_template.id,
                target_user_id=user_id,
                respondent_user_id=evaluator.id,
                evaluator_user_id=evaluator.id,
                module_id=assignment.module_id,
            )

    def _ensure_post_test_campaign(self, created_by: int) -> SurveyCampaign:
        campaign = (
            self.db.query(SurveyCampaign)
            .filter(SurveyCampaign.period_type == "post_test")
            .order_by(SurveyCampaign.status.asc(), SurveyCampaign.id.desc())
            .first()
        )
        if campaign is not None:
            return campaign

        now = datetime.utcnow()
        campaign = SurveyCampaign(
            code=f"post_test_auto_{now.strftime('%Y%m%d_%H%M%S')}",
            name=f"Post test auto {now.strftime('%Y-%m-%d')}",
            period_type="post_test",
            status="active",
            created_by=created_by,
            start_at=now,
        )
        self.db.add(campaign)
        self.db.flush()
        return campaign

    def _ensure_survey_assignment(
        self,
        campaign_id: int,
        template_id: int,
        target_user_id: int,
        respondent_user_id: int,
        evaluator_user_id: int | None,
        module_id: int | None,
    ) -> None:
        existing = (
            self.db.query(SurveyAssignment)
            .filter(
                SurveyAssignment.campaign_id == campaign_id,
                SurveyAssignment.template_id == template_id,
                SurveyAssignment.target_user_id == target_user_id,
                SurveyAssignment.respondent_user_id == respondent_user_id,
                SurveyAssignment.module_id == module_id,
            )
            .first()
        )
        if existing is not None:
            return
        self.db.add(
            SurveyAssignment(
                campaign_id=campaign_id,
                template_id=template_id,
                target_user_id=target_user_id,
                respondent_user_id=respondent_user_id,
                evaluator_user_id=evaluator_user_id,
                module_id=module_id,
                status="pending",
            )
        )

    def _has_management_role(self, role_codes: set[str]) -> bool:
        return bool(role_codes.intersection({"superadmin", "admin", "leader", "supervisor"}))

    def _get_user_with_relations(self, user_id: int | None = None, email: str | None = None) -> User | None:
        query = self.db.query(User).options(joinedload(User.roles).joinedload(Role.permissions))
        if user_id is not None:
            return query.filter(User.id == user_id).first()
        if email is not None:
            return query.filter(User.email == email).first()
        return None

    def _get_user_with_admin_relations(self, user_id: int) -> User:
        user = (
            self.db.query(User)
            .options(
                joinedload(User.roles).joinedload(Role.permissions),
                joinedload(User.module_assignments),
                joinedload(User.lesson_progress),
                joinedload(User.survey_targets),
                joinedload(User.survey_respondent_assignments),
                joinedload(User.survey_evaluator_assignments),
            )
            .filter(User.id == user_id)
            .first()
        )
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        return user

    def _get_role_with_permissions(self, role_id: int) -> Role | None:
        return (
            self.db.query(Role)
            .options(joinedload(Role.permissions))
            .filter(Role.id == role_id)
            .first()
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falta token")

    token = credentials.credentials
    try:
        payload = decode_token(token, expected_type="access")
    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    service = AuthService(db)
    user = service._get_user_with_relations(user_id=int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user


def require_roles(roles: List[str]):
    def wrapper(user: User = Depends(get_current_user)) -> User:
        user_roles = {r.code for r in user.roles}
        if not user_roles.intersection(set(roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado")
        return user

    return wrapper


def require_permissions(permissions: List[str]):
    def wrapper(user: User = Depends(get_current_user)) -> User:
        user_perms = {p.code for r in user.roles for p in r.permissions}
        if not set(permissions).issubset(user_perms):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")
        return user

    return wrapper
