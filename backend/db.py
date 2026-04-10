import os
from sqlmodel import SQLModel, create_engine
from models import Location, Report

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://campus_user:campus_pass@localhost:5432/campus_db"
)

# Render uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif not DATABASE_URL.startswith("postgresql+psycopg2"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)
