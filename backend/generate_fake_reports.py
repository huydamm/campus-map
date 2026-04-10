import random
from datetime import datetime, timedelta, time

from sqlmodel import Session, select

from db import engine
from models import Location, Report

HOURS = [9, 12, 15, 18, 21]


def generate_noise(hour):
    if 11 <= hour <= 16:
        base = 4
    elif 17 <= hour <= 20:
        base = 3
    else:
        base = 2
    return max(1, min(5, int(round(random.gauss(base, 0.8)))))


def generate_occupancy(noise_level):
    return max(5, int(round(random.gauss(noise_level * 12, 10))))


def main():
    # IMPORTANT: naive "local" time (Eastern) for now
    today = datetime.now().date()

    with Session(engine) as session:
        locations = session.exec(select(Location)).all()
        total = 0

        for loc in locations:
            for day_offset in range(30):
                day = today - timedelta(days=day_offset)

                for hr in HOURS:
                    # Naive timestamp with the exact hour you want
                    ts = datetime.combine(day, time(hr, 0, 0))

                    noise = generate_noise(hr)
                    occ = generate_occupancy(noise)

                    session.add(
                        Report(
                            location_id=loc.id,
                            noise_level=noise,
                            occupancy_estimate=occ,
                            created_at=ts,
                        )
                    )
                    total += 1

        session.commit()

    print("Inserted", total, "synthetic reports.")


if __name__ == "__main__":
    main()
