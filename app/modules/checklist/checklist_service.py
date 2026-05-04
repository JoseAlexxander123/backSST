from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.models import ChecklistItem, ChecklistSection
from app.modules.checklist.checklist_schema import (
    ChecklistDetail,
    ChecklistItemOut,
    ChecklistSectionOut,
)


class ChecklistService:
    def __init__(self, db: Session):
        self.db = db

    def list_sections(self) -> List[ChecklistSectionOut]:
        sections = self.db.query(ChecklistSection).all()
        return [self._build_section_out(section) for section in sections]

    def section_detail(self, section_id: int) -> ChecklistDetail:
        section = (
            self.db.query(ChecklistSection)
            .filter(ChecklistSection.id == section_id)
            .first()
        )
        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Seccion no encontrada",
            )

        items = (
            self.db.query(ChecklistItem)
            .filter(ChecklistItem.section_id == section_id)
            .all()
        )
        section_out = self._build_section_out(section, items)
        items_out = [self._build_item_out(item) for item in items]
        return ChecklistDetail(section=section_out, items=items_out)

    def _build_section_out(
        self,
        section: ChecklistSection,
        items: List[ChecklistItem] | None = None,
    ) -> ChecklistSectionOut:
        section_items = list(items if items is not None else section.items)
        linked_module_id = section.module.id if section.module else None

        items_completed = sum(
            1 for item in section_items if item.status == "compliant"
        )
        items_total = len(section_items)
        total_weight = sum(item.weight or 0 for item in section_items)
        earned_score = sum(
            (item.weight or 0)
            for item in section_items
            if item.status == "compliant"
        )
        percentage = (
            round((earned_score / total_weight) * 100)
            if total_weight
            else 0
        )

        return ChecklistSectionOut(
            id=section.id,
            title=section.title,
            items_completed=items_completed,
            items_total=items_total,
            percentage=percentage,
            status=section.status,
            earned_score=earned_score,
            total_weight=total_weight,
            checklist_module_id=linked_module_id,
        )

    def _build_item_out(self, item: ChecklistItem) -> ChecklistItemOut:
        weight = item.weight or 0
        score = weight if item.status == "compliant" else 0
        return ChecklistItemOut(
            id=item.id,
            text=item.text,
            status=item.status,
            weight=weight,
            score=score,
        )
