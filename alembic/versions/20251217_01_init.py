"""init sst backend data model

Revision ID: 20251217_01
Revises:
Create Date: 2025-12-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251217_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------
    # TABLES
    # -------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("two_factor_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("permission_id", sa.Integer, sa.ForeignKey("permissions.id"), nullable=False),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "two_factor_codes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=False, server_default="login"),
        sa.Column("sent_to", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("consumed_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "checklist_sections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pendiente"),
        sa.Column("items_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("percentage", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "modules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("icon", sa.String(length=10), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
        sa.Column("due_to_checklist", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("checklist_section_id", sa.Integer, sa.ForeignKey("checklist_sections.id"), nullable=True),
        sa.Column("quiz_required", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("module_id", sa.Integer, sa.ForeignKey("modules.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("duration", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("image", sa.String(length=512), nullable=True),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_lessons_module_id", "lessons", ["module_id"])

    op.create_table(
        "checklist_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("section_id", sa.Integer, sa.ForeignKey("checklist_sections.id"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="non-compliant"),
    )

    op.create_table(
        "user_lesson_progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("lesson_id", sa.Integer, sa.ForeignKey("lessons.id"), nullable=False),
        sa.Column("completed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson"),
    )

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("module_id", sa.Integer, sa.ForeignKey("modules.id"), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="1"),
    )

    op.create_table(
        "quiz_options",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("quiz_questions.id"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("is_correct", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("module_id", sa.Integer, sa.ForeignKey("modules.id"), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("correct_answers", sa.Integer, nullable=False),
        sa.Column("total_questions", sa.Integer, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # -------------------------
    # SEED
    # -------------------------
    seed_data()


def seed_data() -> None:
    # Nota: usamos SQL literal para maxima compatibilidad con Alembic/op.execute
    # y para evitar el TypeError de "positional arguments".

    # users
    op.execute("""
    INSERT INTO users (id, email, name, hashed_password, is_active, two_factor_enabled)
    VALUES (1, 'demo@sst.local', 'Demo User', '$2b$12$GpCCwcoiFkeI1PhhXONhXeF/qUckNEKZ5HS4edhg9x0BLSldjWFqC', true, true)
    ON CONFLICT (id) DO NOTHING;
    """)

    # roles
    op.execute("""
    INSERT INTO roles (id, name, code, description) VALUES
      (1, 'Administrador', 'admin', 'Acceso total al sistema'),
      (2, 'Supervisor SST', 'supervisor', 'Gestiona capacitaciones y checklist'),
      (3, 'Colaborador', 'worker', 'Consulta y completa capacitaciones')
    ON CONFLICT (id) DO NOTHING;
    """)

    # permissions
    op.execute("""
    INSERT INTO permissions (id, code, module, action, description) VALUES
      (1, 'training.view', 'training', 'view', 'Ver modulos y lecciones'),
      (2, 'training.complete', 'training', 'complete', 'Marcar lecciones como completadas'),
      (3, 'training.quiz', 'training', 'quiz', 'Presentar y enviar quiz'),
      (4, 'checklist.view', 'checklist', 'view', 'Consultar checklist'),
      (5, 'roles.manage', 'admin', 'manage_roles', 'CRUD roles y permisos'),
      (6, 'users.manage', 'admin', 'manage_users', 'Asignar roles a usuarios')
    ON CONFLICT (id) DO NOTHING;
    """)

    # role_permissions
    op.execute("""
    INSERT INTO role_permissions (role_id, permission_id) VALUES
      (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6),
      (2, 1), (2, 2), (2, 3), (2, 4),
      (3, 1), (3, 2), (3, 3)
    ON CONFLICT DO NOTHING;
    """)

    # user_roles
    op.execute("""
    INSERT INTO user_roles (user_id, role_id) VALUES
      (1, 1)
    ON CONFLICT DO NOTHING;
    """)

    # checklist_sections
    op.execute("""
    INSERT INTO checklist_sections (id, title, status, items_completed, items_total, percentage)
    VALUES
      (1, 'Liderazgo y compromiso', 'deficiente', 2, 6, 33),
      (2, 'Participacion de trabajadores', 'deficiente', 3, 6, 50),
      (3, 'Investigacion de incidentes', 'deficiente', 1, 4, 25),
      (4, 'Capacitacion y formacion', 'aprobado', 5, 6, 83),
      (5, 'Auditorias y mejora', 'pendiente', 3, 5, 60),
      (6, 'Gestion documental', 'pendiente', 2, 4, 50)
    ON CONFLICT (id) DO NOTHING;
    """)

    # checklist_items
    op.execute("""
    INSERT INTO checklist_items (id, section_id, text, status)
    VALUES
      (1, 1, 'El empleador proporciona recursos necesarios', 'compliant'),
      (2, 1, 'Se realizan reuniones del comite de SST', 'compliant'),
      (3, 1, 'Existe liderazgo visible en seguridad', 'non-compliant'),
      (4, 2, 'Se consulta a trabajadores sobre SST', 'compliant'),
      (5, 2, 'Hay participacion activa de trabajadores', 'non-compliant'),
      (6, 3, 'Se investigan accidentes e incidentes', 'non-compliant'),
      (7, 4, 'Existe programa anual de capacitacion', 'compliant'),
      (8, 5, 'Se realizan auditorias internas', 'non-compliant')
    ON CONFLICT (id) DO NOTHING;
    """)

    # modules
    op.execute("""
    INSERT INTO modules (id, title, description, icon, color, due_to_checklist, checklist_section_id, quiz_required)
    VALUES
      (1, 'Liderazgo en SST', 'Rol de la gerencia y comunicacion efectiva en seguridad', 'S1', '#2563EB', true, 1, true),
      (2, 'Participacion de trabajadores', 'Derechos, consultas y comite de SST', 'S2', '#10B981', true, 2, true),
      (3, 'Investigacion de incidentes', 'Reporte, investigacion y acciones correctivas', 'S3', '#F97316', true, 3, true),
      (4, 'Capacitacion anual', 'Planificacion y registro de capacitaciones', 'S4', '#F59E0B', false, 4, true),
      (5, 'Auditorias internas', 'Plan, ejecucion y seguimiento de auditorias', 'S5', '#A855F7', false, 5, true),
      (6, 'Gestion documental', 'Politicas, procedimientos y registros clave', 'S6', '#4B5563', false, 6, true)
    ON CONFLICT (id) DO NOTHING;
    """)

    # lessons
    op.execute("""
    INSERT INTO lessons (id, module_id, title, duration, type, image, display_order)
    VALUES
      (1, 1, 'Introduccion al liderazgo en SST', '8 min', 'video', 'https://images.unsplash.com/photo-1520607162513-77705c0f0d4a', 1),
      (2, 1, 'Comunicacion efectiva y roles', '12 min', 'document', 'https://images.unsplash.com/photo-1498050108023-c5249f4df085', 2),
      (3, 1, 'Participacion de trabajadores', '10 min', 'interactive', 'https://images.unsplash.com/photo-1556761175-4b46a572b786', 3),
      (4, 1, 'Plan de accion y seguimiento', '9 min', 'video', 'https://images.unsplash.com/photo-1497366754035-f200968a6e72', 4),

      (5, 2, 'Derechos y deberes en SST', '10 min', 'video', NULL, 1),
      (6, 2, 'Comite y reuniones de SST', '8 min', 'document', NULL, 2),
      (7, 2, 'Consulta y participacion', '7 min', 'interactive', NULL, 3),

      (8, 3, 'Reporte de incidentes', '9 min', 'video', NULL, 1),
      (9, 3, 'Investigacion y hallazgos', '11 min', 'document', NULL, 2),
      (10, 3, 'Acciones correctivas', '6 min', 'interactive', NULL, 3),

      (11, 4, 'Plan anual de capacitacion', '10 min', 'video', NULL, 1),
      (12, 4, 'Registro y evidencias', '8 min', 'document', NULL, 2),

      (13, 5, 'Plan de auditoria', '10 min', 'video', NULL, 1),
      (14, 5, 'Informe y seguimiento', '12 min', 'document', NULL, 2),

      (15, 6, 'Politicas y procedimientos', '9 min', 'document', NULL, 1),
      (16, 6, 'Control de cambios', '7 min', 'interactive', NULL, 2)
    ON CONFLICT (id) DO NOTHING;
    """)

    # quiz_questions
    op.execute("""
    INSERT INTO quiz_questions (id, module_id, prompt, display_order)
    VALUES
      (1, 1, 'Quien es el principal responsable de garantizar la seguridad en el trabajo?', 1),
      (2, 1, 'Que debe hacer la gerencia para demostrar liderazgo en SST?', 2),
      (3, 1, 'Que documentacion es clave para evidenciar la capacitacion?', 3)
    ON CONFLICT (id) DO NOTHING;
    """)

    # quiz_options
    op.execute("""
    INSERT INTO quiz_options (id, question_id, text, is_correct)
    VALUES
      (1, 1, 'El empleador', true),
      (2, 1, 'Solo el area de seguridad', false),
      (3, 1, 'Cada trabajador individual', false),
      (4, 1, 'El comite de SST', false),

      (5, 2, 'Asignar recursos y participar activamente', true),
      (6, 2, 'Delegar todo al area de seguridad', false),
      (7, 2, 'Publicar un cartel una vez al ano', false),
      (8, 2, 'Esperar a las inspecciones', false),

      (9, 3, 'Registros de asistencia y materiales', true),
      (10, 3, 'Solo correos informales', false),
      (11, 3, 'No se necesita documentacion', false),
      (12, 3, 'Una foto de la sala de capacitacion', false)
    ON CONFLICT (id) DO NOTHING;
    """)


def downgrade() -> None:
    # Importante: borrar en orden por FKs
    op.drop_table("quiz_attempts")
    op.drop_table("quiz_options")
    op.drop_table("quiz_questions")
    op.drop_table("user_lesson_progress")
    op.drop_table("checklist_items")

    op.drop_index("ix_lessons_module_id", table_name="lessons")
    op.drop_table("lessons")

    op.drop_table("modules")
    op.drop_table("checklist_sections")
    op.drop_table("two_factor_codes")
    op.drop_table("refresh_tokens")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
