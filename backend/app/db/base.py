# ======================================================================================
# DECLARATIVE BASE MODEL 
# ======================================================================================
# This is the foundational class for all SQLAlchemy ORM models in the application.
#
# Core Responsibilities:
# 1. Registry: Every model (e.g., Vehicle, Agent) must inherit from this 'Base'
#    class to automatically register itself on 'Base.metadata'.
# 2. Alembic Integration: Alembic's 'env.py' reads this metadata to detect code-level
#    changes and autogenerate database migrations accordingly.
# ======================================================================================

from sqlalchemy.orm import DeclarativeBase

# This is a SQLAlchemy component. When it "comes into the picture" (i.e., when a model inherits from it), we know that it is a table in the database.
class Base(DeclarativeBase): 
    """Base class for all SQLAlchemy models.

    Every future model, for example Agent, User, Telemetry, Alert, and Command,
    will inherit from this class.

    This lets SQLAlchemy collect all table definitions under Base.metadata.
    Alembic later reads Base.metadata to detect schema changes and generate migrations.
    """
