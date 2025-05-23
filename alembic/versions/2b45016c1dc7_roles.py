"""roles

Revision ID: 2b45016c1dc7
Revises: 3e1b3668729b
Create Date: 2025-05-11 14:04:00.698599

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "2b45016c1dc7"
down_revision = "3e1b3668729b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "user_tracker_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tracker_id", sa.Integer(), nullable=False),
        sa.Column(
            "role", sa.Enum("manager", "employee", name="roleenum"), nullable=False
        ),
        sa.Column("is_current", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(
            ["tracker_id"],
            ["trackers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("user_id", "tracker_id"),
    )
    op.drop_constraint("users_current_tracker_id_fkey", "users", type_="foreignkey")
    op.drop_column("users", "current_tracker_id")
    op.drop_column("users", "org_id")
    op.drop_column("users", "cloud_id")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "users",
        sa.Column(
            "cloud_id", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "users",
        sa.Column("org_id", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "current_tracker_id", sa.INTEGER(), autoincrement=False, nullable=True
        ),
    )
    op.create_foreign_key(
        "users_current_tracker_id_fkey",
        "users",
        "trackers",
        ["current_tracker_id"],
        ["id"],
    )
    op.drop_table("user_tracker_roles")
    # ### end Alembic commands ###
