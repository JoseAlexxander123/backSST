from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.auth.auth_schema import UserOut


class SurveyScaleOptionOut(BaseModel):
    numeric_value: int
    label: str


class SurveyQuestionOut(BaseModel):
    id: int
    code: str
    question_text: str
    display_order: int
    is_required: bool

    model_config = ConfigDict(from_attributes=True)


class SurveyAssignmentSummaryOut(BaseModel):
    id: int
    campaign_id: int
    campaign_code: str
    campaign_name: str
    period_type: str
    template_code: str
    template_name: str
    target_user_id: int
    target_user_name: str
    respondent_user_id: int
    respondent_user_name: str
    module_id: Optional[int] = None
    module_title: Optional[str] = None
    status: str
    assigned_at: datetime
    completed_at: Optional[datetime] = None
    pending_kind: str


class SurveyAssignmentDetailOut(BaseModel):
    assignment: SurveyAssignmentSummaryOut
    description: Optional[str] = None
    scale_type: str
    scale_options: List[SurveyScaleOptionOut]
    questions: List[SurveyQuestionOut]


class SurveyAnswerInput(BaseModel):
    question_id: int
    numeric_value: int = Field(ge=1, le=5)


class SurveySubmitRequest(BaseModel):
    answers: List[SurveyAnswerInput]

    @field_validator("answers")
    @classmethod
    def validate_answers_not_empty(cls, value: List[SurveyAnswerInput]) -> List[SurveyAnswerInput]:
        if not value:
            raise ValueError("Debes responder la encuesta antes de enviarla")
        ids = [answer.question_id for answer in value]
        if len(ids) != len(set(ids)):
            raise ValueError("No se permiten respuestas duplicadas para la misma pregunta")
        return value


class SurveySubmissionResult(BaseModel):
    assignment_id: int
    response_id: int
    submitted_at: datetime
    status: str


class SurveyTemplateSummaryOut(BaseModel):
    template_code: str
    template_name: str
    pending: int
    completed: int
    average_score: Optional[float] = None


class SurveyCampaignSummaryOut(BaseModel):
    campaign_id: int
    campaign_code: str
    campaign_name: str
    period_type: str
    status: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    pending: int
    completed: int


class SurveyAdminSummaryOut(BaseModel):
    total_assignments: int
    pending_assignments: int
    completed_assignments: int
    templates: List[SurveyTemplateSummaryOut]
    campaigns: List[SurveyCampaignSummaryOut]


class SurveyAdminResponseRowOut(BaseModel):
    response_id: int
    period_type: str
    campaign_name: str
    template_code: str
    template_name: str
    target_user_name: str
    respondent_user_name: str
    module_title: Optional[str] = None
    submitted_at: datetime
    average_score: Optional[float] = None


class SurveyCampaignActivationOut(BaseModel):
    campaign_id: int
    campaign_code: str
    campaign_name: str
    period_type: str
    status: str
    generated_assignments: int
    started_at: Optional[datetime] = None


class SurveyExportResultOut(BaseModel):
    filename: str
    rows_post_test: int
