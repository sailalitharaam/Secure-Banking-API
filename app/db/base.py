from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# Import all models to ensure they are registered on the Base.metadata
# This is required by Alembic for autogenerating migrations.
import app.models  # noqa: F401, E402
