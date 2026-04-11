"""
generate_building_reports.py
Generates realistic crowd reports for academic buildings
based on class schedule patterns at UMass Amherst.
"""
import random
from datetime import datetime, timedelta, time
from sqlmodel import Session, select
from db import engine
from models import Location, Report


# UMass standard class times (start hours)
# MWF: 8, 9, 10, 11, 12, 1, 2
# TuTh: 8:30, 10, 11:30, 1, 2:30, 4
# We approximate with whole hours
MWF_CLASS_HOURS = [8, 9, 10, 11, 12, 13, 14]
TUTH_CLASS_HOURS = [8, 10, 11, 13, 14, 16]

# Buildings that tend to have large lectures (more crowded)
LARGE_LECTURE_BUILDINGS = [
    "Hasbrouck Laboratory",
    "Integrated Science Building",
    "Herter Hall",
    "Machmer Hall",
    "Bartlett Hall",
    "Isenberg School of Management",
    "Integrative Learning Center",
]


def get_noise_profile(loc_type, loc_name, hour, day_of_week):
    is_weekend = day_of_week >= 5
    is_friday = day_of_week == 4
    is_mwf = day_of_week in [0, 2, 4]  # Mon, Wed, Fri
    is_tuth = day_of_week in [1, 3]     # Tue, Thu
    is_large = loc_name in LARGE_LECTURE_BUILDINGS

    if is_weekend:
        # Weekends: most academic buildings very quiet
        if loc_type in ["study_space", "library"]:
            if 10 <= hour <= 22:
                return max(1.0, min(5.0, random.gauss(2.5, 0.5)))
        return 1.0

    if loc_type == "academic":
        # Class hours = crowded hallways, between class = quieter
        class_hours = MWF_CLASS_HOURS if is_mwf else TUTH_CLASS_HOURS if is_tuth else []

        # Peak = during class end/start transitions (hallways crowded)
        # Quiet = middle of class block (everyone in class)
        if hour < 8:
            base = 1.0
        elif hour in class_hours:
            # Transition time — hallways busy
            base = 4.0 if is_large else 3.0
        elif hour in [h + 1 for h in class_hours]:
            # Mid-class — quieter in hallways
            base = 1.5
        elif hour in [15, 16, 17]:
            # Late afternoon — winding down
            base = 2.0
        elif hour >= 18:
            base = 1.0
        else:
            base = 2.0

        if is_friday and hour >= 14:
            base *= 0.6

    elif loc_type == "lounge":
        # Residence hall lounges: busy evenings and weekends
        if hour < 10:
            base = 1.0
        elif hour in [10, 11, 12, 13]:
            base = 1.5
        elif hour in [14, 15, 16]:
            base = 2.0
        elif hour in [17, 18, 19]:
            base = 3.0
        elif hour in [20, 21, 22]:
            base = 3.5
        elif hour == 23:
            base = 2.5
        else:
            base = 1.0

    elif loc_type == "study_space":
        # Study spaces: busy during day, peak evenings Sun-Thu
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
            base = 4.2
        elif hour in [22, 23]:
            base = 3.0
        else:
            base = 1.0

        if is_friday and hour >= 15:
            base *= 0.6

    else:
        base = 2.0 if 9 <= hour <= 20 else 1.0

    return max(1.0, min(5.0, base))


def generate_noise(base):
    return max(1, min(5, int(round(random.gauss(base, 0.5)))))


def generate_occupancy(noise_level, loc_type):
    if loc_type == "academic":
        scale = 30  # buildings hold more people
    elif loc_type == "study_space":
        scale = 15
    elif loc_type == "lounge":
        scale = 10
    else:
        scale = 12
    return max(0, int(round(random.gauss(noise_level * scale, 15))))


def main():
    HOURS = list(range(7, 24))
    today = datetime.now().date()
    NEW_TYPES = ["academic", "lounge", "study_space"]

    with Session(engine) as session:
        locations = session.exec(select(Location)).all()
        new_locs = [l for l in locations if l.type in NEW_TYPES]
        print(f"Generating reports for {len(new_locs)} new locations...")

        total = 0
        for loc in new_locs:
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
    print(f"Inserted {total} building reports.")


if __name__ == "__main__":
    main()
