"""
generate_spire_reports.py
Converts scraped SPIRE schedule data into realistic crowd reports
for academic buildings based on actual Spring 2026 class schedules.
"""
import json
import re
import random
from datetime import datetime, timedelta, time
from collections import defaultdict
from sqlmodel import Session, select
from db import engine
from models import Location, Report

# Map SPIRE building names to our location names
BUILDING_MAP = {
    "hasbrouck": "Hasbrouck Laboratory",
    "morrill": "Morrill Science Center",
    "integrated science": "Integrated Science Building",
    "integ. learning": "Integrative Learning Center",
    "integrative learning": "Integrative Learning Center",
    "integ.learning": "Integrative Learning Center",
    "machmer": "Machmer Hall",
    "herter": "Herter Hall",
    "bartlett": "Bartlett Hall",
    "thompson": "Thompson Hall",
    "goodell": "Goodell Hall",
    "tobin": "Tobin Hall",
    "gordon": "Gordon Hall",
    "furcolo": "Furcolo Hall",
    "goessmann": "Goessmann Laboratory",
    "lederle": "Lederle Graduate Research Center",
    "computer science": "Computer Science Building",
    "isenberg": "Isenberg School of Management",
    "school of management": "Isenberg School of Management",
    "sch of management": "Isenberg School of Management",
    "fine arts": "Fine Arts Center",
    "marcus": "Marcus Hall",
    "marston": "Marston Hall",
    "engineering lab": "Elab II Engineering",
    "holdsworth": "Holdsworth Hall",
    "draper": "Draper Hall",
    "olver design": "John W. Olver Design Building",
    "mahar": "Machmer Hall",  # Mahar is near Machmer area
    "south college": "Herter Hall",  # South College is in same area
    "dickinson": "Bartlett Hall",
}


def match_building(spire_name):
    """Match a SPIRE building string to one of our location names."""
    name_lower = spire_name.lower()
    for key, loc_name in BUILDING_MAP.items():
        if key in name_lower:
            return loc_name
    return None


def parse_days(days_str):
    """Parse day string like 'MoWeFr', 'TuTh', 'MoWe' into list of weekday ints."""
    day_map = {
        "Mo": 0, "Tu": 1, "We": 2, "Th": 3, "Fr": 4, "Sa": 5, "Su": 6
    }
    days = []
    i = 0
    while i < len(days_str):
        for d, num in day_map.items():
            if days_str[i:i+len(d)] == d:
                days.append(num)
                i += len(d)
                break
        else:
            i += 1
    return days


def parse_time(time_str):
    """Parse time string like '1:00PM' or '10:10AM' into hour (float)."""
    time_str = time_str.strip()
    try:
        t = datetime.strptime(time_str, "%I:%M%p")
        return t.hour + t.minute / 60
    except:
        try:
            t = datetime.strptime(time_str, "%I:%M %p")
            return t.hour + t.minute / 60
        except:
            return None


def parse_days_time(days_time_str):
    """
    Parse 'TuTh 1:00PM - 2:15PM' into (days_list, start_hour, end_hour).
    """
    pattern = r'^([A-Za-z]+)\s+(\d+:\d+[AP]M)\s*-\s*(\d+:\d+[AP]M)$'
    match = re.match(pattern, days_time_str.strip())
    if not match:
        return None, None, None

    days_str, start_str, end_str = match.groups()
    days = parse_days(days_str)
    start_hour = parse_time(start_str)
    end_hour = parse_time(end_str)

    return days, start_hour, end_hour


def build_schedule(sections):
    """
    Build a dict: location_name -> {day_of_week -> [(start_hour, end_hour), ...]}
    """
    schedule = defaultdict(lambda: defaultdict(list))

    for s in sections:
        loc_name = match_building(s["building"])
        if not loc_name:
            continue

        days, start, end = parse_days_time(s["days_time"])
        if days is None or start is None or end is None:
            continue

        for day in days:
            schedule[loc_name][day].append((start, end))

    return schedule


def get_crowd_level(hour, day_of_week, classes_today):
    """
    Given an hour and list of (start, end) class tuples for today,
    return a base noise level 1-5.
    """
    is_weekend = day_of_week >= 5
    if is_weekend:
        return 1.0

    # Count how many classes overlap with this hour
    active = sum(1 for (s, e) in classes_today if s <= hour < e)
    # Count transition periods (30 min after class ends)
    transitioning = sum(1 for (s, e) in classes_today if e <= hour < e + 0.5)

    if active >= 3:
        base = 4.5
    elif active == 2:
        base = 4.0
    elif active == 1:
        base = 3.0
    elif transitioning >= 2:
        base = 4.0  # hallway rush
    elif transitioning == 1:
        base = 3.5
    else:
        # No classes — check if it's near class times
        upcoming = [s for (s, e) in classes_today if s > hour and s - hour < 0.5]
        if upcoming:
            base = 2.5  # students arriving
        elif 8 <= hour <= 18:
            base = 1.5  # general daytime activity
        else:
            base = 1.0

    return max(1.0, min(5.0, base))


def main():
    print("Loading SPIRE schedule...")
    with open("spire_schedule.json") as f:
        sections = json.load(f)

    print(f"Loaded {len(sections)} sections")

    schedule = build_schedule(sections)
    print(f"Matched {len(schedule)} buildings")
    for name in list(schedule.keys())[:5]:
        total = sum(len(v) for v in schedule[name].values())
        print(f"  {name}: {total} class slots")

    # Load locations from DB
    with Session(engine) as session:
        locations = {loc.name: loc for loc in session.exec(select(Location)).all()}

    HOURS = list(range(7, 23))
    today = datetime.now().date()
    total_reports = 0

    with Session(engine) as session:
        for loc_name, day_schedule in schedule.items():
            if loc_name not in locations:
                print(f"  Skipping {loc_name} - not in DB")
                continue

            loc = locations[loc_name]

            for day_offset in range(60):
                day = today - timedelta(days=day_offset)
                day_of_week = day.weekday()
                classes_today = day_schedule.get(day_of_week, [])

                for hr in HOURS:
                    base = get_crowd_level(hr, day_of_week, classes_today)
                    noise = max(1, min(5, int(round(random.gauss(base, 0.4)))))
                    occ = max(0, int(round(random.gauss(noise * 25, 15))))
                    ts = datetime.combine(day, time(hr, 0, 0))

                    session.add(Report(
                        location_id=loc.id,
                        noise_level=noise,
                        occupancy_estimate=occ,
                        created_at=ts,
                    ))
                    total_reports += 1

        session.commit()

    print(f"\nInserted {total_reports} SPIRE-based reports!")


if __name__ == "__main__":
    main()
