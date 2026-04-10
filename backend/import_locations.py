import pandas as pd
from sqlmodel import Session

from db import engine, init_db
from models import Location


def main():
    init_db()

    df = pd.read_csv("../locations_seed.csv")

    with Session(engine) as session:
        for _, row in df.iterrows():
            session.add(
                Location(
                    name=str(row["name"]),
                    type=str(row["type"]),
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    source=str(row["source"]) if "source" in row and pd.notna(row["source"]) else None,
                )
            )
        session.commit()

    print("Inserted", len(df), "locations into Postgres.")


if __name__ == "__main__":
    main()
