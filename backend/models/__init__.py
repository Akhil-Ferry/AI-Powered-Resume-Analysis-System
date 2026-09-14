from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.database import Resume, JobCache  # noqa: E402,F401
