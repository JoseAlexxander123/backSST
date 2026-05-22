from __future__ import annotations

import csv
from datetime import datetime
from io import BytesIO, StringIO
from typing import Iterable

from fastapi import HTTPException, status
from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from app.modules.models import (
    ModuleAssignment,
    SurveyAnswer,
    SurveyAssignment,
    SurveyCampaign,
    SurveyQuestion,
    SurveyResponse,
    SurveyTemplate,
    User,
)
from app.modules.surveys.survey_schema import (
    SurveyAdminResponseRowOut,
    SurveyAdminSummaryOut,
    SurveyCampaignActivationOut,
    SurveyAssignmentDetailOut,
    SurveyAssignmentSummaryOut,
    SurveyCampaignSummaryOut,
    SurveyQuestionOut,
    SurveyScaleOptionOut,
    SurveySubmissionResult,
    SurveySubmitRequest,
    SurveyTemplateSummaryOut,
)


AGREEMENT_SCALE = [
    SurveyScaleOptionOut(numeric_value=1, label="Totalmente en desacuerdo"),
    SurveyScaleOptionOut(numeric_value=2, label="En desacuerdo"),
    SurveyScaleOptionOut(numeric_value=3, label="Ni de acuerdo ni en desacuerdo"),
    SurveyScaleOptionOut(numeric_value=4, label="De acuerdo"),
    SurveyScaleOptionOut(numeric_value=5, label="Totalmente de acuerdo"),
]

PERFORMANCE_SCALE = [
    SurveyScaleOptionOut(numeric_value=1, label="No cumple"),
    SurveyScaleOptionOut(numeric_value=2, label="Cumple parcialmente"),
    SurveyScaleOptionOut(numeric_value=3, label="Cumple adecuadamente"),
    SurveyScaleOptionOut(numeric_value=4, label="Cumple completamente"),
    SurveyScaleOptionOut(numeric_value=5, label="Cumple con excelencia"),
]

COMPLIANCE_SCALE = [
    SurveyScaleOptionOut(numeric_value=1, label="No cumple"),
    SurveyScaleOptionOut(numeric_value=2, label="Si cumple"),
]

EXPORT_QUESTION_CODES = [
    "v0_i1",
    "v0_i2",
    "v0_i3",
    "v0_i4",
    "v0_i5",
    "v0_i6",
    "v0_i7",
    "v0_i8",
    "v0_i9",
    "v0_i10",
    "v0_i11",
    "v0_i12",
    "v1_i1",
    "v1_i2",
    "v1_i3",
    "v1_i4",
    "v2_i1",
    "v2_i2",
    "v2_i3",
    "v2_i4",
    "v3_i1",
    "v3_i2",
    "v3_i3",
    "v3_i4",
    "v4_i1",
    "v4_i2",
    "v4_i3",
    "v4_i4",
]

POST_TEST_PERIOD = "post_test"


class SurveyService:
    def __init__(self, db: Session):
        self.db = db

    def list_my_assignments(self, current_user: User, include_completed: bool = True) -> list[SurveyAssignmentSummaryOut]:
        query = (
            self.db.query(SurveyAssignment)
            .join(SurveyAssignment.campaign)
            .options(
                joinedload(SurveyAssignment.campaign),
                joinedload(SurveyAssignment.template),
                joinedload(SurveyAssignment.target_user),
                joinedload(SurveyAssignment.respondent_user),
                joinedload(SurveyAssignment.module),
            )
            .filter(SurveyAssignment.respondent_user_id == current_user.id)
            .filter(SurveyCampaign.period_type == POST_TEST_PERIOD)
            .order_by(SurveyAssignment.completed_at.is_(None).desc(), SurveyAssignment.assigned_at.asc())
        )
        if not include_completed:
            query = query.filter(SurveyAssignment.status != "completed")
        return [self._build_assignment_summary(assignment) for assignment in query.all()]

    def get_assignment_detail(self, assignment_id: int, current_user: User) -> SurveyAssignmentDetailOut:
        assignment = self._get_assignment(assignment_id)
        self._ensure_assignment_visibility(assignment, current_user)

        scale_options = self._scale_options_for_template(assignment.template)
        questions = [
            SurveyQuestionOut.model_validate(question)
            for question in sorted(assignment.template.questions, key=lambda item: item.display_order)
        ]
        return SurveyAssignmentDetailOut(
            assignment=self._build_assignment_summary(assignment),
            description=assignment.template.description,
            scale_type=assignment.template.scale_type,
            scale_options=scale_options,
            questions=questions,
        )

    def submit_assignment(
        self,
        assignment_id: int,
        payload: SurveySubmitRequest,
        current_user: User,
    ) -> SurveySubmissionResult:
        assignment = self._get_assignment(assignment_id)
        if assignment.respondent_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La encuesta no pertenece al usuario actual")
        if assignment.status == "completed":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La encuesta ya fue enviada")

        questions = sorted(assignment.template.questions, key=lambda item: item.display_order)
        required_ids = {question.id for question in questions if question.is_required}
        submitted_ids = {answer.question_id for answer in payload.answers}
        if required_ids != submitted_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes responder todas las preguntas obligatorias antes de enviar",
            )

        valid_range = {option.numeric_value for option in self._scale_options_for_template(assignment.template)}
        for answer in payload.answers:
            if answer.numeric_value not in valid_range:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La escala enviada es invalida")

        response = assignment.response
        if response is None:
            response = SurveyResponse(
                assignment_id=assignment.id,
                campaign_id=assignment.campaign_id,
                template_id=assignment.template_id,
                target_user_id=assignment.target_user_id,
                respondent_user_id=assignment.respondent_user_id,
                module_id=assignment.module_id,
                started_at=datetime.utcnow(),
            )
            self.db.add(response)
            self.db.flush()
        else:
            self.db.query(SurveyAnswer).filter(SurveyAnswer.response_id == response.id).delete(synchronize_session=False)

        for answer in payload.answers:
            self.db.add(
                SurveyAnswer(
                    response_id=response.id,
                    question_id=answer.question_id,
                    numeric_value=answer.numeric_value,
                )
            )

        now = datetime.utcnow()
        response.submitted_at = now
        response.is_submitted = True
        assignment.status = "completed"
        assignment.completed_at = now

        self.db.commit()
        self.db.refresh(response)
        self.db.refresh(assignment)
        return SurveySubmissionResult(
            assignment_id=assignment.id,
            response_id=response.id,
            submitted_at=now,
            status=assignment.status,
        )

    def admin_summary(self, current_user: User) -> SurveyAdminSummaryOut:
        self._ensure_manage_permission(current_user)
        assignments = self._base_assignment_query().all()
        responses = self._base_response_query().all()

        templates: list[SurveyTemplateSummaryOut] = []
        template_map = {}
        for assignment in assignments:
            key = assignment.template.code
            if key not in template_map:
                template_map[key] = {
                    "name": assignment.template.name,
                    "pending": 0,
                    "completed": 0,
                    "scores": [],
                }
            bucket = template_map[key]
            if assignment.status == "completed":
                bucket["completed"] += 1
            else:
                bucket["pending"] += 1
        for response in responses:
            if response.answers:
                template_map[response.template.code]["scores"].append(
                    sum(answer.numeric_value for answer in response.answers) / len(response.answers)
                )
        for code, data in sorted(template_map.items()):
            scores = data["scores"]
            templates.append(
                SurveyTemplateSummaryOut(
                    template_code=code,
                    template_name=data["name"],
                    pending=data["pending"],
                    completed=data["completed"],
                    average_score=round(sum(scores) / len(scores), 2) if scores else None,
                )
            )

        campaigns: list[SurveyCampaignSummaryOut] = []
        campaign_map = {
            campaign.code: {
                "id": campaign.id,
                "name": campaign.name,
                "period_type": campaign.period_type,
                "status": campaign.status,
                "start_at": campaign.start_at,
                "end_at": campaign.end_at,
                "pending": 0,
                "completed": 0,
            }
            for campaign in self.db.query(SurveyCampaign).order_by(SurveyCampaign.id.asc()).all()
            if campaign.period_type == POST_TEST_PERIOD
        }
        for assignment in assignments:
            bucket = campaign_map[assignment.campaign.code]
            if assignment.status == "completed":
                bucket["completed"] += 1
            else:
                bucket["pending"] += 1
        for code, data in sorted(campaign_map.items()):
            campaigns.append(
                SurveyCampaignSummaryOut(
                    campaign_id=data["id"],
                    campaign_code=code,
                    campaign_name=data["name"],
                    period_type=data["period_type"],
                    status=data["status"],
                    start_at=data["start_at"],
                    end_at=data["end_at"],
                    pending=data["pending"],
                    completed=data["completed"],
                )
            )

        total_assignments = len(assignments)
        completed_assignments = sum(1 for assignment in assignments if assignment.status == "completed")
        pending_assignments = total_assignments - completed_assignments
        return SurveyAdminSummaryOut(
            total_assignments=total_assignments,
            pending_assignments=pending_assignments,
            completed_assignments=completed_assignments,
            templates=templates,
            campaigns=campaigns,
        )

    def activate_campaign(self, campaign_id: int, current_user: User) -> SurveyCampaignActivationOut:
        self._ensure_manage_permission(current_user)
        campaign = self.db.query(SurveyCampaign).filter(SurveyCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campana no encontrada")
        if campaign.period_type != POST_TEST_PERIOD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden activar campanas de post test",
            )

        generated_assignments = self._generate_assignments_for_campaign(campaign.id)
        now = datetime.utcnow()
        campaign.status = "active"
        if campaign.start_at is None:
            campaign.start_at = now
        self.db.commit()
        self.db.refresh(campaign)
        return SurveyCampaignActivationOut(
            campaign_id=campaign.id,
            campaign_code=campaign.code,
            campaign_name=campaign.name,
            period_type=campaign.period_type,
            status=campaign.status,
            generated_assignments=generated_assignments,
            started_at=campaign.start_at,
        )

    def admin_responses(self, current_user: User, limit: int = 100) -> list[SurveyAdminResponseRowOut]:
        self._ensure_manage_permission(current_user)
        rows: list[SurveyAdminResponseRowOut] = []
        responses = self._base_response_query().order_by(SurveyResponse.submitted_at.desc()).limit(limit).all()
        for response in responses:
            average = None
            if response.answers:
                average = round(sum(answer.numeric_value for answer in response.answers) / len(response.answers), 2)
            rows.append(
                SurveyAdminResponseRowOut(
                    response_id=response.id,
                    period_type=response.campaign.period_type,
                    campaign_name=response.campaign.name,
                    template_code=response.template.code,
                    template_name=response.template.name,
                    target_user_name=response.target_user.name,
                    respondent_user_name=response.respondent_user.name,
                    module_title=response.module.title if response.module else None,
                    submitted_at=response.submitted_at or response.started_at,
                    average_score=average,
                )
            )
        return rows

    def export_xlsx(self, current_user: User) -> tuple[bytes, str]:
        self._ensure_export_permission(current_user)
        workbook = Workbook()
        post_sheet = workbook.active
        post_sheet.title = POST_TEST_PERIOD

        post_rows = self._build_consolidated_export_rows()
        headers = ["No", "colaborador", "email", "leader", "module", *EXPORT_QUESTION_CODES]
        self._write_export_sheet(post_sheet, headers, post_rows)

        output = BytesIO()
        workbook.save(output)
        filename = f"survey_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return output.getvalue(), filename

    def export_csv(self, current_user: User) -> tuple[bytes, str]:
        self._ensure_export_permission(current_user)
        post_rows = self._build_consolidated_export_rows()
        output = StringIO()
        writer = csv.writer(output)
        headers = ["No", "colaborador", "email", "leader", "module", *EXPORT_QUESTION_CODES]
        writer.writerow(headers)
        for row in post_rows:
            writer.writerow(row)
        filename = f"survey_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        return output.getvalue().encode("utf-8"), filename

    def _build_consolidated_export_rows(self) -> list[list[object]]:
        responses = self._base_response_query().all()
        grouped: dict[int, dict[str, object]] = {}
        for response in responses:
            key = response.target_user_id
            row = grouped.setdefault(
                key,
                {
                    "colaborador": response.target_user.name,
                    "email": response.target_user.email,
                    "leader": "",
                    "module": response.module.title if response.module else "",
                    "answers": {},
                },
            )
            if response.module and not row["module"]:
                row["module"] = response.module.title
            if response.template.code == "task_verification":
                row["leader"] = response.respondent_user.name
            for answer in response.answers:
                row["answers"][answer.question.code] = self._answer_label_for_template(
                    response.template,
                    answer.numeric_value,
                )

        rows: list[list[object]] = []
        for index, item in enumerate(sorted(grouped.values(), key=lambda record: str(record["email"])), start=1):
            row = [
                index,
                item["colaborador"],
                item["email"],
                item["leader"],
                item["module"],
            ]
            answers = item["answers"]
            for code in EXPORT_QUESTION_CODES:
                row.append(answers.get(code, ""))
            rows.append(row)
        return rows

    def _write_export_sheet(self, sheet, headers: list[str], rows: Iterable[list[object]]) -> None:
        sheet.append(headers)
        for row in rows:
            sheet.append(row)

    def _base_assignment_query(self):
        return (
            self.db.query(SurveyAssignment)
            .join(SurveyAssignment.campaign)
            .options(
                joinedload(SurveyAssignment.campaign),
                joinedload(SurveyAssignment.template),
                joinedload(SurveyAssignment.target_user),
                joinedload(SurveyAssignment.respondent_user),
                joinedload(SurveyAssignment.module),
            )
            .filter(SurveyCampaign.period_type == POST_TEST_PERIOD)
        )

    def _generate_assignments_for_campaign(self, campaign_id: int) -> int:
        collaborator_templates = (
            self.db.query(SurveyTemplate)
            .filter(
                SurveyTemplate.code.in_(
                    [
                        "functionality_checklist",
                        "sst_awareness",
                        "bidirectional_communication",
                        "usability",
                    ]
                )
            )
            .all()
        )
        task_verification_template = (
            self.db.query(SurveyTemplate).filter(SurveyTemplate.code == "task_verification").first()
        )

        collaborators = (
            self.db.query(User)
            .options(joinedload(User.roles), joinedload(User.module_assignments))
            .all()
        )
        generated = 0
        for collaborator in collaborators:
            role_codes = {role.code for role in collaborator.roles}
            if "collaborator" not in role_codes or not collaborator.is_active:
                continue
            module_id = min((assignment.module_id for assignment in collaborator.module_assignments), default=None)
            for template in collaborator_templates:
                created = self._ensure_assignment(
                    campaign_id=campaign_id,
                    template_id=template.id,
                    target_user_id=collaborator.id,
                    respondent_user_id=collaborator.id,
                    evaluator_user_id=None,
                    module_id=module_id,
                )
                generated += 1 if created else 0

        learning_assignments = (
            self.db.query(ModuleAssignment)
            .options(
                joinedload(ModuleAssignment.user).joinedload(User.roles),
                joinedload(ModuleAssignment.assigned_by_user).joinedload(User.roles),
            )
            .filter(ModuleAssignment.assigned_by.isnot(None))
            .all()
        )
        if task_verification_template is not None:
            for module_assignment in learning_assignments:
                collaborator_role_codes = {role.code for role in module_assignment.user.roles}
                evaluator = module_assignment.assigned_by_user
                if evaluator is None:
                    continue
                evaluator_role_codes = {role.code for role in evaluator.roles}
                if "collaborator" not in collaborator_role_codes:
                    continue
                if not evaluator_role_codes.intersection({"leader", "admin", "superadmin"}):
                    continue
                created = self._ensure_assignment(
                    campaign_id=campaign_id,
                    template_id=task_verification_template.id,
                    target_user_id=module_assignment.user_id,
                    respondent_user_id=evaluator.id,
                    evaluator_user_id=evaluator.id,
                    module_id=module_assignment.module_id,
                )
                generated += 1 if created else 0
        return generated

    def _ensure_assignment(
        self,
        campaign_id: int,
        template_id: int,
        target_user_id: int,
        respondent_user_id: int,
        evaluator_user_id: int | None,
        module_id: int | None,
    ) -> bool:
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
        if existing:
            return False
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
        self.db.flush()
        return True

    def _base_response_query(self):
        return (
            self.db.query(SurveyResponse)
            .join(SurveyResponse.campaign)
            .options(
                joinedload(SurveyResponse.campaign),
                joinedload(SurveyResponse.template),
                joinedload(SurveyResponse.target_user),
                joinedload(SurveyResponse.respondent_user),
                joinedload(SurveyResponse.module),
                joinedload(SurveyResponse.answers).joinedload(SurveyAnswer.question),
            )
            .filter(SurveyResponse.is_submitted.is_(True))
            .filter(SurveyCampaign.period_type == POST_TEST_PERIOD)
        )

    def _get_assignment(self, assignment_id: int) -> SurveyAssignment:
        assignment = (
            self.db.query(SurveyAssignment)
            .join(SurveyAssignment.campaign)
            .options(
                joinedload(SurveyAssignment.campaign),
                joinedload(SurveyAssignment.template).joinedload(SurveyTemplate.questions),
                joinedload(SurveyAssignment.target_user),
                joinedload(SurveyAssignment.respondent_user),
                joinedload(SurveyAssignment.evaluator_user),
                joinedload(SurveyAssignment.module),
                joinedload(SurveyAssignment.response).joinedload(SurveyResponse.answers),
            )
            .filter(SurveyAssignment.id == assignment_id)
            .filter(SurveyCampaign.period_type == POST_TEST_PERIOD)
            .first()
        )
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encuesta no encontrada")
        return assignment

    def _ensure_assignment_visibility(self, assignment: SurveyAssignment, current_user: User) -> None:
        permission_codes = {permission.code for role in current_user.roles for permission in role.permissions}
        if assignment.respondent_user_id == current_user.id:
            return
        if "surveys.manage" in permission_codes or "surveys.export" in permission_codes:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver esta encuesta")

    def _ensure_manage_permission(self, current_user: User) -> None:
        permission_codes = {permission.code for role in current_user.roles for permission in role.permissions}
        if "surveys.manage" not in permission_codes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes administrar encuestas")

    def _ensure_export_permission(self, current_user: User) -> None:
        permission_codes = {permission.code for role in current_user.roles for permission in role.permissions}
        if "surveys.export" not in permission_codes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes exportar encuestas")

    def _scale_options_for_template(self, template: SurveyTemplate) -> list[SurveyScaleOptionOut]:
        if template.scale_type == "compliance_1_2":
            return COMPLIANCE_SCALE
        if template.scale_type == "performance_1_5":
            return PERFORMANCE_SCALE
        return AGREEMENT_SCALE

    def _answer_label_for_template(self, template: SurveyTemplate, numeric_value: int) -> str:
        for option in self._scale_options_for_template(template):
            if option.numeric_value == numeric_value:
                return option.label
        return str(numeric_value)

    def _build_assignment_summary(self, assignment: SurveyAssignment) -> SurveyAssignmentSummaryOut:
        pending_kind = "respond"
        if assignment.template.code == "task_verification":
            pending_kind = "evaluate"
        return SurveyAssignmentSummaryOut(
            id=assignment.id,
            campaign_id=assignment.campaign_id,
            campaign_code=assignment.campaign.code,
            campaign_name=assignment.campaign.name,
            period_type=assignment.campaign.period_type,
            template_code=assignment.template.code,
            template_name=assignment.template.name,
            target_user_id=assignment.target_user_id,
            target_user_name=assignment.target_user.name,
            respondent_user_id=assignment.respondent_user_id,
            respondent_user_name=assignment.respondent_user.name,
            module_id=assignment.module_id,
            module_title=assignment.module.title if assignment.module else None,
            status=assignment.status,
            assigned_at=assignment.assigned_at,
            completed_at=assignment.completed_at,
            pending_kind=pending_kind,
        )
