from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.infrastructure.respository import get_db
from app.modules.auth.auth_service import get_current_user
from app.modules.surveys.survey_schema import (
    SurveyAdminResponseRowOut,
    SurveyAdminSummaryOut,
    SurveyCampaignActivationOut,
    SurveyAssignmentDetailOut,
    SurveyAssignmentSummaryOut,
    SurveySubmissionResult,
    SurveySubmitRequest,
)
from app.modules.surveys.survey_service import SurveyService

router = APIRouter(prefix="/surveys", tags=["Surveys"])


@router.get("/my-assignments", response_model=list[SurveyAssignmentSummaryOut])
def list_my_assignments(
    include_completed: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return SurveyService(db).list_my_assignments(current_user, include_completed=include_completed)


@router.get("/assignments/{assignment_id}", response_model=SurveyAssignmentDetailOut)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return SurveyService(db).get_assignment_detail(assignment_id, current_user)


@router.post("/assignments/{assignment_id}/submit", response_model=SurveySubmissionResult)
def submit_assignment(
    assignment_id: int,
    payload: SurveySubmitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return SurveyService(db).submit_assignment(assignment_id, payload, current_user)


@router.get("/admin/summary", response_model=SurveyAdminSummaryOut)
def admin_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return SurveyService(db).admin_summary(current_user)


@router.post("/admin/campaigns/{campaign_id}/activate", response_model=SurveyCampaignActivationOut)
def activate_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return SurveyService(db).activate_campaign(campaign_id, current_user)


@router.get("/admin/responses", response_model=list[SurveyAdminResponseRowOut])
def admin_responses(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return SurveyService(db).admin_responses(current_user, limit=limit)


@router.get("/admin/export.xlsx")
def export_xlsx(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    content, filename = SurveyService(db).export_xlsx(current_user)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/export.csv")
def export_csv(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    content, filename = SurveyService(db).export_csv(current_user)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
