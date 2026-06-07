# ======================================================================================
# ALEMBIC MIGRATION TEMPLATE (script.py.mako)
# ======================================================================================
# This is a blueprint/template file used automatically by Alembic.
# Whenever you run 'alembic revision', Alembic copies this file, replaces the ${} 
# placeholders with real data (dates, IDs), and creates a new script in 'versions/'.
# Do NOT modify the syntax of this file unless you want to change the global structure 
# of all future migration files.
# ======================================================================================

"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}


# Unique ID of this migration.
revision: str = ${repr(up_revision)}

# Previous migration ID.
# This creates the migration chain/order.
down_revision: Union[str, None] = ${repr(down_revision)}

# Advanced Alembic feature for branching migrations.
# Usually not used in this project.
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}

# Advanced Alembic feature for migration dependencies.
# Usually not used in this project.
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    # Forward change: create/update database schema.
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    # Rollback change: undo what upgrade() did.
    ${downgrades if downgrades else "pass"}