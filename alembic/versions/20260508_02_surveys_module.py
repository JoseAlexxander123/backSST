"""Add surveys module

Revision ID: 20260508_02
Revises: 20260508_01
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260508_02"
down_revision = "20260508_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "survey_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("audience_role", sa.String(length=50), nullable=False),
        sa.Column("evaluator_role", sa.String(length=50), nullable=True),
        sa.Column("scale_type", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code", name="uq_survey_templates_code"),
    )

    op.create_table(
        "survey_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("survey_templates.id"), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("code", name="uq_survey_questions_code"),
        sa.UniqueConstraint("template_id", "display_order", name="uq_survey_question_order"),
    )

    op.create_table(
        "survey_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("period_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("start_at", sa.DateTime(), nullable=True),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code", name="uq_survey_campaigns_code"),
    )

    op.create_table(
        "survey_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("survey_campaigns.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("survey_templates.id"), nullable=False),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("respondent_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("evaluator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("modules.id"), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "campaign_id",
            "template_id",
            "target_user_id",
            "respondent_user_id",
            "module_id",
            name="uq_survey_assignment_scope",
        ),
    )
    op.create_index("ix_survey_assignments_respondent", "survey_assignments", ["respondent_user_id"])
    op.create_index("ix_survey_assignments_target", "survey_assignments", ["target_user_id"])

    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("survey_assignments.id"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("survey_campaigns.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("survey_templates.id"), nullable=False),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("respondent_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("modules.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("is_submitted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("assignment_id", name="uq_survey_response_assignment"),
    )

    op.create_table(
        "survey_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("response_id", sa.Integer(), sa.ForeignKey("survey_responses.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("survey_questions.id"), nullable=False),
        sa.Column("numeric_value", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("response_id", "question_id", name="uq_survey_answer_question"),
    )

    op.execute(
        """
        INSERT INTO permissions (id, code, module, action, description) VALUES
          (10, 'surveys.respond', 'surveys', 'respond', 'Responder encuestas asignadas'),
          (11, 'surveys.evaluate', 'surveys', 'evaluate', 'Evaluar colaboradores en encuestas'),
          (12, 'surveys.manage', 'surveys', 'manage', 'Gestionar campanas y resultados de encuestas'),
          (13, 'surveys.export', 'surveys', 'export', 'Exportar resultados de encuestas')
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON (
          (r.code = 'superadmin' AND p.code IN ('surveys.respond', 'surveys.evaluate', 'surveys.manage', 'surveys.export'))
          OR
          (r.code = 'admin' AND p.code IN ('surveys.evaluate', 'surveys.manage', 'surveys.export'))
          OR
          (r.code = 'leader' AND p.code IN ('surveys.evaluate'))
          OR
          (r.code = 'collaborator' AND p.code IN ('surveys.respond'))
        )
        ON CONFLICT DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO survey_templates (id, code, name, description, audience_role, evaluator_role, scale_type, is_active)
        VALUES
          (1, 'sst_awareness', 'Cuestionario de conciencia de SST', 'Autopercepcion del aprendizaje del colaborador', 'collaborator', NULL, 'agreement_1_5', true),
          (2, 'bidirectional_communication', 'Escala de comunicacion bidireccional', 'Percepcion del colaborador sobre mensajeria y retroalimentacion', 'collaborator', NULL, 'agreement_1_5', true),
          (3, 'usability', 'Escala de usabilidad', 'Percepcion del colaborador sobre la experiencia de uso', 'collaborator', NULL, 'agreement_1_5', true),
          (4, 'task_verification', 'Escala de verificacion de tareas normalizadas', 'Evaluacion del colaborador por un lider o admin', 'collaborator', 'leader', 'performance_1_5', true)
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO survey_questions (id, template_id, code, question_text, display_order, is_required)
        VALUES
          (1, 1, 'v1_i1', 'La informacion presentada en los modulos interactivos me resulto clara y comprensible para entender normas y procedimientos de SST.', 1, true),
          (2, 1, 'v1_i2', 'Me siento confiado(a) para aplicar lo aprendido en situaciones reales de trabajo tras revisar los contenidos interactivos.', 2, true),
          (3, 1, 'v1_i3', 'Considero que la informacion suministrada en los modulos es relevante y directamente aplicable a mis tareas diarias en la Direccion Regional Amazonas.', 3, true),
          (4, 1, 'v1_i4', 'Tras completar los modulos, percibo que tengo la capacidad necesaria para desempenar correctamente las tareas relacionadas con SST en mi puesto de trabajo.', 4, true),

          (5, 2, 'v3_i1', 'Siento que el intercambio de mensajes entre empleados y la direccion es fluido y responde rapidamente a mis consultas.', 1, true),
          (6, 2, 'v3_i2', 'Percibo que la retroalimentacion recibida a traves del aplicativo es inmediata y me permite tomar decisiones sin demora.', 2, true),
          (7, 2, 'v3_i3', 'Estoy satisfecho/a con el canal de mensajeria del aplicativo como apoyo para mis tareas de salud y seguridad en el trabajo.', 3, true),
          (8, 2, 'v3_i4', 'Confio en que la informacion que comparto y recibo por el aplicativo permanece privada y se maneja con confidencialidad.', 4, true),

          (9, 3, 'v4_i1', 'Siento que la navegacion en la interfaz del aplicativo es facil e intuitiva.', 1, true),
          (10, 3, 'v4_i2', 'Considero que los textos y botones de la aplicacion son claros y coherentes con las acciones que deseo realizar.', 2, true),
          (11, 3, 'v4_i3', 'Estoy satisfecho/a con mi experiencia de uso del aplicativo en general.', 3, true),
          (12, 3, 'v4_i4', 'Tengo la intencion de seguir utilizando esta herramienta en el futuro para mis tareas de salud y seguridad.', 4, true),

          (13, 4, 'v2_i1', 'El empleado aplica correctamente las normativas de SST establecidas en la organizacion.', 1, true),
          (14, 4, 'v2_i2', 'El empleado ejecuta los procedimientos preventivos (inspecciones, uso de equipos de proteccion) segun lo estipulado.', 2, true),
          (15, 4, 'v2_i3', 'El empleado sigue los procedimientos administrativos de SST (elaboracion de reportes, autorizaciones y registros) conforme a los estandares de la Direccion Regional.', 3, true),
          (16, 4, 'v2_i4', 'El empleado implementa los procedimientos de contingencia ante riesgos identificados de manera oportuna y efectiva.', 4, true)
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO survey_campaigns (id, code, name, period_type, status, created_by)
        VALUES
          (1, 'pre_test_2026', 'Pre test 2026', 'pre_test', 'active', 1),
          (2, 'post_test_2026', 'Post test 2026', 'post_test', 'draft', 1)
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        """
        WITH collaborator_targets AS (
          SELECT
            u.id AS collaborator_id,
            MIN(ma.module_id) AS module_id
          FROM users u
          JOIN user_roles ur ON ur.user_id = u.id
          JOIN roles r ON r.id = ur.role_id
          LEFT JOIN module_assignments ma ON ma.user_id = u.id
          WHERE r.code = 'collaborator'
            AND u.is_active = true
          GROUP BY u.id
        ),
        survey_templates_for_collaborator AS (
          SELECT id
          FROM survey_templates
          WHERE code IN ('sst_awareness', 'bidirectional_communication', 'usability')
        )
        INSERT INTO survey_assignments (
          campaign_id,
          template_id,
          target_user_id,
          respondent_user_id,
          evaluator_user_id,
          module_id,
          status
        )
        SELECT
          1,
          st.id,
          ct.collaborator_id,
          ct.collaborator_id,
          NULL,
          ct.module_id,
          'pending'
        FROM collaborator_targets ct
        CROSS JOIN survey_templates_for_collaborator st
        ON CONFLICT (campaign_id, template_id, target_user_id, respondent_user_id, module_id) DO NOTHING;
        """
    )

    op.execute(
        """
        WITH evaluator_assignments AS (
          SELECT
            ma.user_id AS collaborator_id,
            ma.module_id,
            ma.assigned_by AS evaluator_id
          FROM module_assignments ma
          JOIN users evaluator ON evaluator.id = ma.assigned_by
          JOIN user_roles eur ON eur.user_id = evaluator.id
          JOIN roles er ON er.id = eur.role_id
          JOIN users collaborator ON collaborator.id = ma.user_id
          JOIN user_roles cur ON cur.user_id = collaborator.id
          JOIN roles cr ON cr.id = cur.role_id
          WHERE ma.assigned_by IS NOT NULL
            AND er.code IN ('leader', 'admin', 'superadmin')
            AND cr.code = 'collaborator'
            AND collaborator.is_active = true
        )
        INSERT INTO survey_assignments (
          campaign_id,
          template_id,
          target_user_id,
          respondent_user_id,
          evaluator_user_id,
          module_id,
          status
        )
        SELECT
          1,
          4,
          ea.collaborator_id,
          ea.evaluator_id,
          ea.evaluator_id,
          ea.module_id,
          'pending'
        FROM evaluator_assignments ea
        ON CONFLICT (campaign_id, template_id, target_user_id, respondent_user_id, module_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (10, 11, 12, 13);")
    op.execute("DELETE FROM permissions WHERE id IN (10, 11, 12, 13);")

    op.drop_table("survey_answers")
    op.drop_table("survey_responses")
    op.drop_index("ix_survey_assignments_target", table_name="survey_assignments")
    op.drop_index("ix_survey_assignments_respondent", table_name="survey_assignments")
    op.drop_table("survey_assignments")
    op.drop_table("survey_campaigns")
    op.drop_table("survey_questions")
    op.drop_table("survey_templates")
