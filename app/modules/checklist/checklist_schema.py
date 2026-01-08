from typing import List
from pydantic import BaseModel, ConfigDict


class ChecklistSectionOut(BaseModel):
    id: int
    title: str
    items_completed: int
    items_total: int
    percentage: int
    status: str
    checklist_module_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ChecklistItemOut(BaseModel):
    id: int
    text: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class ChecklistDetail(BaseModel):
    section: ChecklistSectionOut
    items: List[ChecklistItemOut]
