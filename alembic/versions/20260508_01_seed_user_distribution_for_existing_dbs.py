"""Backfill seeded user distribution for existing databases

Revision ID: 20260508_01
Revises: 20260428_02
Create Date: 2026-05-08
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260508_01"
down_revision = "20260428_02"
branch_labels = None
depends_on = None


NEW_PASSWORD_HASH = "$2b$12$G0Yj.C39aF/f.WjYcyj65ONsbqhTvwFAej2FBq/sBNMhRano/Xywi"  # bcrypt for 12345678
SUPERADMIN_EMAIL = "superadmin@sst.local"
LEGACY_SEED_EMAILS = ["admin@sst.local", "lider@sst.local", "colaborador@sst.local"]


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _seed_users() -> list[tuple[str, str, str]]:
    users = [(SUPERADMIN_EMAIL, "Super Admin", "superadmin")]

    for module_id in range(1, 7):
        users.append((f"admin{module_id:02d}@sst.local", f"Administrador Modulo {module_id}", "admin"))

    for module_id in range(1, 7):
        users.append((f"lider{module_id:02d}@sst.local", f"Lider Modulo {module_id}", "leader"))

    for collaborator_number in range(1, 41):
        users.append(
            (
                f"colaborador{collaborator_number:02d}@sst.local",
                f"Colaborador {collaborator_number:02d}",
                "collaborator",
            )
        )

    return users


def _owner_specs() -> list[tuple[int, str]]:
    return [(module_id, f"admin{module_id:02d}@sst.local") for module_id in range(1, 7)]


def _assignment_specs() -> list[tuple[int, str, str]]:
    assignments: list[tuple[int, str, str]] = []

    for module_id in range(1, 7):
        assignments.append((module_id, f"admin{module_id:02d}@sst.local", SUPERADMIN_EMAIL))
        assignments.append((module_id, f"lider{module_id:02d}@sst.local", SUPERADMIN_EMAIL))

    collaborator_groups = {
        1: range(1, 8),
        2: range(8, 15),
        3: range(15, 22),
        4: range(22, 29),
        5: range(29, 35),
        6: range(35, 41),
    }

    for module_id, collaborator_numbers in collaborator_groups.items():
        leader_email = f"lider{module_id:02d}@sst.local"
        for collaborator_number in collaborator_numbers:
            assignments.append(
                (
                    module_id,
                    f"colaborador{collaborator_number:02d}@sst.local",
                    leader_email,
                )
            )

    return assignments


def upgrade() -> None:
    seed_users = _seed_users()
    managed_seed_emails = [email for email, _name, _role_code in seed_users]
    cleanup_emails = managed_seed_emails + LEGACY_SEED_EMAILS

    op.execute(
        """
        SELECT setval(
          pg_get_serial_sequence('users', 'id'),
          COALESCE((SELECT MAX(id) FROM users), 1),
          true
        );
        """
    )

    op.execute(
        f"""
        UPDATE users
        SET
          email = {_quote(SUPERADMIN_EMAIL)},
          name = 'Super Admin',
          hashed_password = {_quote(NEW_PASSWORD_HASH)},
          is_active = true,
          two_factor_enabled = true
        WHERE id = 1;
        """
    )

    legacy_renames = [
        ("admin@sst.local", "admin01@sst.local", "Administrador Modulo 1"),
        ("lider@sst.local", "lider01@sst.local", "Lider Modulo 1"),
        ("colaborador@sst.local", "colaborador01@sst.local", "Colaborador 01"),
    ]
    for old_email, new_email, new_name in legacy_renames:
        op.execute(
            f"""
            UPDATE users
            SET
              email = {_quote(new_email)},
              name = {_quote(new_name)},
              hashed_password = {_quote(NEW_PASSWORD_HASH)},
              is_active = true,
              two_factor_enabled = true
            WHERE email = {_quote(old_email)}
              AND NOT EXISTS (
                SELECT 1 FROM users existing WHERE existing.email = {_quote(new_email)}
              );
            """
        )

    user_values = ",\n          ".join(
        f"({_quote(email)}, {_quote(name)}, {_quote(NEW_PASSWORD_HASH)}, true, true)"
        for email, name, _role_code in seed_users
    )
    op.execute(
        f"""
        INSERT INTO users (email, name, hashed_password, is_active, two_factor_enabled)
        VALUES
          {user_values}
        ON CONFLICT (email) DO UPDATE SET
          name = EXCLUDED.name,
          hashed_password = EXCLUDED.hashed_password,
          is_active = EXCLUDED.is_active,
          two_factor_enabled = EXCLUDED.two_factor_enabled;
        """
    )

    cleanup_email_values = ", ".join(_quote(email) for email in cleanup_emails)
    op.execute(
        f"""
        DELETE FROM user_roles ur
        USING users u
        WHERE ur.user_id = u.id
          AND u.email IN ({cleanup_email_values});
        """
    )

    op.execute(
        """
        SELECT setval(
          pg_get_serial_sequence('user_roles', 'id'),
          COALESCE((SELECT MAX(id) FROM user_roles), 1),
          true
        );
        """
    )

    role_values = ",\n          ".join(
        f"({_quote(email)}, {_quote(role_code)})"
        for email, _name, role_code in seed_users
    )
    op.execute(
        f"""
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM (
          VALUES
            {role_values}
        ) AS desired(email, role_code)
        JOIN users u ON u.email = desired.email
        JOIN roles r ON r.code = desired.role_code
        ON CONFLICT DO NOTHING;
        """
    )

    op.execute(
        f"""
        DELETE FROM module_assignments ma
        USING users u
        WHERE ma.user_id = u.id
          AND u.email IN ({cleanup_email_values});
        """
    )

    op.execute(
        """
        SELECT setval(
          pg_get_serial_sequence('module_assignments', 'id'),
          COALESCE((SELECT MAX(id) FROM module_assignments), 1),
          true
        );
        """
    )

    assignment_values = ",\n            ".join(
        f"({module_id}, {_quote(user_email)}, {_quote(assigned_by_email)})"
        for module_id, user_email, assigned_by_email in _assignment_specs()
    )
    op.execute(
        f"""
        INSERT INTO module_assignments (module_id, user_id, assigned_by)
        SELECT desired.module_id, assignee.id, assigner.id
        FROM (
          VALUES
            {assignment_values}
        ) AS desired(module_id, user_email, assigned_by_email)
        JOIN users assignee ON assignee.email = desired.user_email
        JOIN users assigner ON assigner.email = desired.assigned_by_email
        ON CONFLICT (user_id, module_id) DO UPDATE SET
          assigned_by = EXCLUDED.assigned_by;
        """
    )

    owner_values = ",\n            ".join(
        f"({module_id}, {_quote(owner_email)})"
        for module_id, owner_email in _owner_specs()
    )
    op.execute(
        f"""
        UPDATE modules AS m
        SET owner_id = owners.user_id
        FROM (
          SELECT desired.module_id, u.id AS user_id
          FROM (
            VALUES
              {owner_values}
          ) AS desired(module_id, owner_email)
          JOIN users u ON u.email = desired.owner_email
        ) AS owners
        WHERE m.id = owners.module_id;
        """
    )

    legacy_only_email_values = ", ".join(_quote(email) for email in LEGACY_SEED_EMAILS)
    op.execute(
        f"""
        UPDATE users
        SET is_active = false
        WHERE email IN ({legacy_only_email_values});
        """
    )


def downgrade() -> None:
    # Data backfill for existing environments. No destructive downgrade.
    pass
