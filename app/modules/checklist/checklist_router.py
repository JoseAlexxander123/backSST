from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.respository import get_db
from app.modules.auth.auth_service import require_permissions
from app.modules.checklist.checklist_schema import ChecklistDetail, ChecklistSectionOut
from app.modules.checklist.checklist_service import ChecklistService

router = APIRouter(prefix="/checklist", tags=["Checklist"])


@router.get("/", response_model=list[ChecklistSectionOut])
def list_sections(
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["checklist.view"])),
):
    service = ChecklistService(db)
    return service.list_sections()


@router.get("/{section_id}", response_model=ChecklistDetail)
def get_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["checklist.view"])),
):
    service = ChecklistService(db)
    return service.section_detail(section_id)
