from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Every future model, for example Agent, User, Telemetry, Alert, and Command,
    will inherit from this class.

    This lets SQLAlchemy collect all table definitions under Base.metadata.
    Alembic later reads Base.metadata to detect schema changes and generate migrations.
    """
