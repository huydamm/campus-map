import random
from datetime import datetime, timedelta, time
from sqlmodel import Session, select, delete
from db import engine
from models import Location, Report


def get_noise_profile(loc_type, loc_name, hour, day_of_week):
    is_weekend = day_of_week >= 5
    is_friday = day_of_week == 4
    is_dining = "Dining" in loc_name or "Commons" in loc_name

    if is_dining:
        if hour in [7, 8]:
            base = 4.5
        elif hour in [11, 12, 13]:
            base = 5.0
        elif hour in [17, 18, 19]:
            base = 4.8
        elif hour in [9, 10, 14, 15, 16]:
            base = 2.0
        elif hour in [20, 21]:
            base = 1.5
        else:
            base = 1.0
    elif loc_type == "library":
        if hour < 8:
            base = 1.0
        elif hour in [8, 9]:
            base = 2.0
        elif hour in [10, 11, 12]:
            base = 3.0
        elif hour in [13, 14, 15]:
            base = 3.5
        elif hour in [16, 17, 18]:
            base = 3.8
        elif hour in [19, 20, 21]:
            base = 4.2 if not is_weekend else 2.5
        elif hour in [22, 23]:
            base = 3.0 if not is_weekend else 1.5
        else:
            base = 1.0
    elif loc_type == "cafe":
        if hour < 8:
            base = 1.0
        elif hour in [8, 9]:
            base = 3.0
        elif hour in [10, 11]:
            base = 3.5
        elif hour in [12, 13]:
            base = 4.0
        elif hour in [14, 15]:
            base = 3.0
        elif hour in [16, 17]:
            base = 2.5
        elif hour in [18, 19]:
            base = 2.0
        elif hour in [20, 21]:
            base = 1.5
        else:
            base = 1.0
    elif loc_type == "fast_food":
        if hour < 10:
            base = 1.0
        elif hour in [10, 11]:
            base = 2.5
        elif hour in [12, 13, 14]:
            base = 4.5
        elif hour in [15, 16]:
            base = 2.0
        elif hour in [17, 18, 19]:
            base = 4.0
        elif hour in [20, 21]:
            base = 2.5
        else:
            base = 1.0
    else:
        if 9 <= hour <= 20:
            base = 2.5
        else:
            base = 1.0

    if is_weekend:
        base *= 0.5
    elif is_friday and hour >= 14:
        base *= 0.7

    return max(1.0, min(5.0, base))


def generate_noise(base):
    return max(1, min(5, int(round(random.gauss(base, 0.5)))))


def generate_occupancy(noise_level, loc_type):
    if loc_type == "library":
        scale = 20
    else:
        scale = 12
    return max(0, int(round(random.gauss(noise_level * scale, 10))))


def main():
    HOURS = list(range(7, 24))
    today = datetime.now().date()

    with Session(engine) as session:
        cutoff = datetime.combine(today, time(0, 0, 0))
        session.exec(delete(Report).where(Report.created_at < cutoff))
        session.commit()
        print("Cleared old reports.")

        locations = session.exec(select(Location)).all()
        total = 0

        for loc in locations:
            for day_offset in range(60):
                day = today - timedelta(days=day_offset)
                day_of_week = day.weekday()
                for hr in HOURS:
                    ts = datetime.combine(day, time(hr, 0, 0))
                    base = get_noise_profile(loc.type, loc.name, hr, day_of_week)
                    noise = generate_noise(base)
                    occ = generate_occupancy(noise, loc.type)
                    session.add(Report(
                        location_id=loc.id,
                        noise_level=noise,
                        occupancy_estimate=occ,
                        created_at=ts,
                    ))
                    total += 1

        session.commit()
    print(f"Inserted {total} realistic reports.")


if __name__ == "__main__":
    main()
