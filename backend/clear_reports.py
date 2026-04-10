from sqlmodel import Session
from sqlalchemy import text
from db import engine

def main():
    with Session(engine) as session:
        session.exec(text("DELETE FROM report;"))
        session.commit()
    print("Deleted all reports.")

if __name__ == "__main__":
    main()
