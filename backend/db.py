from sqlmodel import SQLModel, create_engine
from models import Location, Report
DATABASE_URL = "postgresql+psycopg2://campus_user:campus_pass@localhost:5432/campus_db"

engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)
