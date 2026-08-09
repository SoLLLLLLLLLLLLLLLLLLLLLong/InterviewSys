"""Create the platform schema from SQLAlchemy metadata."""

from alembic import op

from infrastructure.database import Base

revision = "0001_platform_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
