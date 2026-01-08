from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.models import ChecklistItem, ChecklistSection
from app.modules.checklist.checklist_schema import ChecklistDetail, ChecklistItemOut, ChecklistSectionOut


class ChecklistService:
    def __init__(self, db: Session):
        self.db = db

    def list_sections(self) -> List[ChecklistSectionOut]:
        sections = self.db.query(ChecklistSection).all()
        response: List[ChecklistSectionOut] = []
        for section in sections:
            linked_module_id = None
            if section.module:
                linked_module_id = section.module.id

            response.append(
                ChecklistSectionOut(
                    id=section.id,
                    title=section.title,
                    items_completed=section.items_completed,
                    items_total=section.items_total,
                    percentage=section.percentage,
                    status=section.status,
                    checklist_module_id=linked_module_id,
                )
            )
        return response

    def section_detail(self, section_id: int) -> ChecklistDetail:
        section = self.db.query(ChecklistSection).filter(ChecklistSection.id == section_id).first()
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sección no encontrada")

        items = self.db.query(ChecklistItem).filter(ChecklistItem.section_id == section_id).all()
        linked_module_id = None
        if section.module:
            linked_module_id = section.module.id

        section_out = ChecklistSectionOut(
            id=section.id,
            title=section.title,
            items_completed=section.items_completed,
            items_total=section.items_total,
            percentage=section.percentage,
            status=section.status,
            checklist_module_id=linked_module_id,
        )

        items_out = [ChecklistItemOut(id=i.id, text=i.text, status=i.status) for i in items]
        return ChecklistDetail(section=section_out, items=items_out)
