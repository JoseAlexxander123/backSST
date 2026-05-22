"""Add functionality checklist survey for collaborators

Revision ID: 20260519_01
Revises: 20260508_02
Create Date: 2026-05-19
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260519_01"
down_revision = "20260508_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO survey_templates (
          id,
          code,
          name,
          description,
          audience_role,
          evaluator_role,
          scale_type,
          is_active
        )
        VALUES (
          5,
          'functionality_checklist',
          'Lista de cotejo de funcionalidad del aplicativo movil',
          'Validacion funcional del aplicativo movil mediante respuestas de Si cumple y No cumple por parte del colaborador.',
          'collaborator',
          NULL,
          'compliance_1_2',
          true
        )
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO survey_questions (id, template_id, code, question_text, display_order, is_required)
        VALUES
          (17, 5, 'v0_i1', '1.1.1. Login con usuario y contrasena.', 1, true),
          (18, 5, 'v0_i2', '1.1.2. Autenticacion multifactor (SMS, email, 2FA).', 2, true),
          (19, 5, 'v0_i3', '1.1.3. Politicas de complejidad y expiracion de contrasena.', 3, true),
          (20, 5, 'v0_i4', '2.1.1. Tiempo medio de carga del formulario (segundos).', 4, true),
          (21, 5, 'v0_i5', '2.1.2. Validacion en tiempo real de campos obligatorios y formato.', 5, true),
          (22, 5, 'v0_i6', '2.1.3. Manejo de errores claros y sugerencias de correccion en pantalla.', 6, true),
          (23, 5, 'v0_i7', '3.1.1. Sincronizacion automatica bidireccional de datos.', 7, true),
          (24, 5, 'v0_i8', '3.1.2. Compatibilidad con APIs REST/SOAP del sistema legado.', 8, true),
          (25, 5, 'v0_i9', '3.1.3. Consistencia de datos tras operacion de CRUD en ambos sistemas.', 9, true),
          (26, 5, 'v0_i10', '4.1.1. Personalizacion de flujos de trabajo segun roles y permisos.', 10, true),
          (27, 5, 'v0_i11', '4.1.2. Flexibilidad para agregar nuevos modulos o campos sin desarrollo.', 11, true),
          (28, 5, 'v0_i12', '4.1.3. Escalabilidad: rendimiento estable al aumentar usuarios o datos.', 12, true)
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        """
        WITH active_campaigns AS (
          SELECT id
          FROM survey_campaigns
          WHERE status = 'active'
        ),
        collaborator_targets AS (
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
          ac.id,
          5,
          ct.collaborator_id,
          ct.collaborator_id,
          NULL,
          ct.module_id,
          'pending'
        FROM active_campaigns ac
        CROSS JOIN collaborator_targets ct
        ON CONFLICT (campaign_id, template_id, target_user_id, respondent_user_id, module_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM survey_answers sa
        USING survey_responses sr
        WHERE sa.response_id = sr.id
          AND sr.template_id = 5;
        """
    )
    op.execute("DELETE FROM survey_responses WHERE template_id = 5;")
    op.execute("DELETE FROM survey_assignments WHERE template_id = 5;")
    op.execute("DELETE FROM survey_questions WHERE template_id = 5;")
    op.execute("DELETE FROM survey_templates WHERE id = 5;")
