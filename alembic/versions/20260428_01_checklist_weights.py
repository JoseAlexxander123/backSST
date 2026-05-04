"""Add checklist weights and complete seeded items

Revision ID: 20260428_01
Revises: 20260330_01
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260428_01"
down_revision = "20260330_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "checklist_items",
        sa.Column("weight", sa.Integer(), nullable=False, server_default="10"),
    )

    op.execute(
        """
        UPDATE checklist_items SET weight = CASE id
          WHEN 1 THEN 20
          WHEN 2 THEN 15
          WHEN 3 THEN 15
          WHEN 4 THEN 20
          WHEN 5 THEN 15
          WHEN 6 THEN 20
          WHEN 7 THEN 20
          WHEN 8 THEN 20
          ELSE weight
        END;
        """
    )

    op.execute(
        """
        INSERT INTO checklist_items (id, section_id, text, status, weight)
        VALUES
          (9, 1, 'La politica SST esta difundida y disponible para todos los trabajadores', 'non-compliant', 20),
          (10, 1, 'La direccion revisa periodicamente los indicadores de SST', 'non-compliant', 15),
          (11, 1, 'Los responsables de SST tienen funciones documentadas', 'non-compliant', 15),

          (12, 2, 'Existe comite o supervisor SST formalmente designado', 'compliant', 15),
          (13, 2, 'Se registran acuerdos y compromisos de reuniones SST', 'non-compliant', 20),
          (14, 2, 'Los trabajadores conocen canales de consulta y reporte', 'non-compliant', 15),
          (15, 2, 'Las recomendaciones de los trabajadores reciben seguimiento', 'non-compliant', 15),

          (16, 3, 'Existe procedimiento para reporte inmediato de incidentes', 'compliant', 15),
          (17, 3, 'Las investigaciones identifican causas raiz y acciones correctivas', 'non-compliant', 15),
          (18, 3, 'Se registran evidencias de acciones correctivas cerradas', 'non-compliant', 20),
          (19, 3, 'Los incidentes se comunican al personal involucrado', 'non-compliant', 15),
          (20, 3, 'Se revisa la eficacia de las medidas correctivas', 'non-compliant', 15),

          (21, 4, 'El plan anual de capacitacion esta aprobado', 'compliant', 15),
          (22, 4, 'Las capacitaciones obligatorias se asignan segun brechas detectadas', 'compliant', 20),
          (23, 4, 'Se conservan evidencias de asistencia y participacion', 'compliant', 15),
          (24, 4, 'Las evaluaciones de aprendizaje quedan registradas', 'compliant', 15),
          (25, 4, 'Se reprograman capacitaciones pendientes o desaprobadas', 'non-compliant', 15),

          (26, 5, 'Existe programa de auditorias internas SST', 'compliant', 15),
          (27, 5, 'Los hallazgos de auditoria tienen responsables asignados', 'compliant', 15),
          (28, 5, 'Se realiza seguimiento a planes de accion de auditoria', 'compliant', 20),
          (29, 5, 'La direccion revisa resultados de auditorias', 'non-compliant', 15),
          (30, 5, 'Las mejoras se documentan y comunican oportunamente', 'non-compliant', 15),

          (31, 6, 'La matriz documental SST esta actualizada', 'compliant', 20),
          (32, 6, 'Los procedimientos criticos tienen version vigente', 'compliant', 15),
          (33, 6, 'Los registros obligatorios son accesibles para auditoria', 'non-compliant', 15),
          (34, 6, 'Existe control de cambios para documentos SST', 'non-compliant', 20),
          (35, 6, 'Los documentos obsoletos se retiran de uso operativo', 'non-compliant', 15),
          (36, 6, 'Las evidencias se organizan por modulo o requisito', 'non-compliant', 15)
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        """
        WITH scores AS (
          SELECT
            section_id,
            COUNT(*) AS items_total,
            COUNT(*) FILTER (WHERE status = 'compliant') AS items_completed,
            COALESCE(SUM(weight), 0) AS total_weight,
            COALESCE(SUM(CASE WHEN status = 'compliant' THEN weight ELSE 0 END), 0) AS earned_score
          FROM checklist_items
          GROUP BY section_id
        )
        UPDATE checklist_sections s
        SET
          items_total = scores.items_total,
          items_completed = scores.items_completed,
          percentage = CASE
            WHEN scores.total_weight = 0 THEN 0
            ELSE ROUND((scores.earned_score::numeric / scores.total_weight::numeric) * 100)::integer
          END,
          status = CASE
            WHEN scores.total_weight = 0 THEN 'pendiente'
            WHEN ROUND((scores.earned_score::numeric / scores.total_weight::numeric) * 100)::integer >= 80 THEN 'aprobado'
            WHEN ROUND((scores.earned_score::numeric / scores.total_weight::numeric) * 100)::integer >= 50 THEN 'pendiente'
            ELSE 'deficiente'
          END
        FROM scores
        WHERE s.id = scores.section_id;
        """
    )

    op.alter_column("checklist_items", "weight", server_default=None)


def downgrade() -> None:
    op.execute("DELETE FROM checklist_items WHERE id BETWEEN 9 AND 36;")
    op.drop_column("checklist_items", "weight")
    op.execute(
        """
        UPDATE checklist_sections SET
          items_completed = CASE id
            WHEN 1 THEN 2
            WHEN 2 THEN 3
            WHEN 3 THEN 1
            WHEN 4 THEN 5
            WHEN 5 THEN 3
            WHEN 6 THEN 2
            ELSE items_completed
          END,
          items_total = CASE id
            WHEN 1 THEN 6
            WHEN 2 THEN 6
            WHEN 3 THEN 4
            WHEN 4 THEN 6
            WHEN 5 THEN 5
            WHEN 6 THEN 4
            ELSE items_total
          END,
          percentage = CASE id
            WHEN 1 THEN 33
            WHEN 2 THEN 50
            WHEN 3 THEN 25
            WHEN 4 THEN 83
            WHEN 5 THEN 60
            WHEN 6 THEN 50
            ELSE percentage
          END,
          status = CASE id
            WHEN 1 THEN 'deficiente'
            WHEN 2 THEN 'deficiente'
            WHEN 3 THEN 'deficiente'
            WHEN 4 THEN 'aprobado'
            WHEN 5 THEN 'pendiente'
            WHEN 6 THEN 'pendiente'
            ELSE status
          END;
        """
    )
