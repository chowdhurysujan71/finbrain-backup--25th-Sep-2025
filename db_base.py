"""
Lightweight Database Base Module
Provides Base and db objects without Flask application side effects.
Safe for import by Alembic migrations and main application.
"""

from sqlalchemy.orm import DeclarativeBase
from flask_sqlalchemy import SQLAlchemy

class Base(DeclarativeBase):
    """SQLAlchemy declarative base class"""
    pass

# Create db instance without Flask app - will be initialized later
db = SQLAlchemy(model_class=Base)