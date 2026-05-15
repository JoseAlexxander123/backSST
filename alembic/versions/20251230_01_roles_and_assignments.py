"""Add module ownership, assignments and new roles

Revision ID: 20251230_01
Revises: 20251217_01
Create Date: 2025-12-30
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251230_01"
down_revision = "20251217_01"
branch_labels = None
depends_on = None


NEW_PASSWORD_HASH = "$2b$12$G0Yj.C39aF/f.WjYcyj65ONsbqhTvwFAej2FBq/sBNMhRano/Xywi"  # bcrypt for 12345678


def upgrade() -> None:
    # -------------------------
    # schema
    # -------------------------
    op.add_column("modules", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_modules_owner", "modules", "users", ["owner_id"], ["id"])

    op.create_table(
        "module_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("modules.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", "module_id", name="uq_user_module"),
    )

    # -------------------------
    # data: roles & permissions
    # -------------------------
    op.execute(
        """
        UPDATE roles SET name = 'Superadministrador', code = 'superadmin', description = 'Dueno de los modulos'
        WHERE code = 'admin';
        """
    )
    op.execute(
        """
        UPDATE roles SET name = 'Lider de Area', code = 'leader', description = 'Monitorea evaluaciones y equipos'
        WHERE code = 'supervisor';
        """
    )
    op.execute(
        """
        UPDATE roles SET name = 'Colaborador', code = 'collaborator', description = 'Completa modulos asignados'
        WHERE code = 'worker';
        """
    )
    op.execute(
        """
        INSERT INTO roles (id, name, code, description)
        VALUES (4, 'Administrador', 'admin', 'Gestiona modulos asignados')
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO permissions (id, code, module, action, description) VALUES
          (7, 'training.manage', 'training', 'manage', 'CRUD de modulos'),
          (8, 'training.assign', 'training', 'assign', 'Asignar modulos a usuarios'),
          (9, 'training.monitor', 'training', 'monitor', 'Ver progreso de colaboradores')
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute("DELETE FROM role_permissions;")
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id) VALUES
          -- superadmin (rol 1)
          (1,1),(1,2),(1,3),(1,4),(1,5),(1,6),(1,7),(1,8),(1,9),
          -- leader (rol 2)
          (2,1),(2,4),(2,9),
          -- collaborator (rol 3)
          (3,1),(3,2),(3,3),
          -- admin (rol 4)
          (4,1),(4,2),(4,3),(4,4)
        ON CONFLICT DO NOTHING;
        """
    )

    # -------------------------
    # data: users & ownership
    # -------------------------
    op.execute(
        f"""
        UPDATE users
        SET email = 'superadmin@sst.local', name = 'Super Admin', hashed_password = '{NEW_PASSWORD_HASH}'
        WHERE id = 1;
        """
    )

    op.execute(
        f"""
        INSERT INTO users (id, email, name, hashed_password, is_active, two_factor_enabled)
        VALUES
          (2, 'admin@sst.local', 'Administrador Asignaciones', '{NEW_PASSWORD_HASH}', true, true),
          (3, 'lider@sst.local', 'Lider de Area', '{NEW_PASSWORD_HASH}', true, true),
          (4, 'colaborador@sst.local', 'Colaborador', '{NEW_PASSWORD_HASH}', true, true)
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO user_roles (user_id, role_id) VALUES
          (1, 1),
          (2, 4),
          (3, 2),
          (4, 3)
        ON CONFLICT DO NOTHING;
        """
    )

    op.execute("UPDATE modules SET owner_id = 1 WHERE owner_id IS NULL;")

    op.execute(
        """
        INSERT INTO module_assignments (module_id, user_id, assigned_by)
        VALUES
          (1, 2, 1),
          (2, 2, 1),
          (1, 4, 3),
          (2, 4, 3),
          (3, 4, 3)
        ON CONFLICT (user_id, module_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_table("module_assignments")
    op.drop_constraint("fk_modules_owner", "modules", type_="foreignkey")
    op.drop_column("modules", "owner_id")

    op.execute(
        """
        UPDATE roles SET name = 'Administrador', code = 'admin', description = 'Acceso total al sistema'
        WHERE code = 'superadmin';
        """
    )
    op.execute(
        """
        UPDATE roles SET name = 'Supervisor SST', code = 'supervisor', description = 'Gestiona capacitaciones y checklist'
        WHERE code = 'leader';
        """
    )
    op.execute(
        """
        UPDATE roles SET name = 'Colaborador', code = 'worker', description = 'Consulta y completa capacitaciones'
        WHERE code = 'collaborator';
        """
    )
    op.execute("DELETE FROM roles WHERE code = 'admin';")

    op.execute("DELETE FROM permissions WHERE code IN ('training.manage', 'training.assign', 'training.monitor');")
    op.execute("DELETE FROM role_permissions;")
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id) VALUES
          (1,1),(1,2),(1,3),(1,4),(1,5),(1,6),
          (2,1),(2,2),(2,3),(2,4),
          (3,1),(3,2),(3,3)
        ON CONFLICT DO NOTHING;
        """
    )

    op.execute(
        """
        UPDATE users
        SET email = 'demo@sst.local', name = 'Demo User', hashed_password = '$2b$12$GpCCwcoiFkeI1PhhXONhXeF/qUckNEKZ5HS4edhg9x0BLSldjWFqC'
        WHERE id = 1;
        """
    )
    op.execute("DELETE FROM users WHERE id IN (2,3,4);")
    op.execute(
        """
        DELETE FROM user_roles;
        INSERT INTO user_roles (user_id, role_id) VALUES (1, 1);
        """
    )
