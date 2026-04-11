from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from datetime import datetime, timedelta
from sqlalchemy import func
from db import engine
from models import Location
from typing import Optional
from fastapi import Query

from pydantic import BaseModel
from uuid import UUID
from models import Report

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://campus-map-frontend.vercel.app", "https://umassquite.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/locations")
def get_locations(
    type: Optional[str] = None,
    limit: int = Query(100, le=500)
):
    with Session(engine) as session:
        stmt = select(Location)

        if type:
            stmt = stmt.where(Location.type == type)

        stmt = stmt.limit(limit)

        results = session.exec(stmt).all()
        return results

class ReportCreate(BaseModel):
    location_id: UUID
    noise_level: int
    occupancy_estimate: int


@app.post("/report")
def create_report(report: ReportCreate):
    with Session(engine) as session:
        db_report = Report(
            location_id=report.location_id,
            noise_level=report.noise_level,
            occupancy_estimate=report.occupancy_estimate,
        )
        session.add(db_report)
        session.commit()
        session.refresh(db_report)
        return db_report
@app.get("/locations/{location_id}/quiet")
def location_quiet_score(location_id: UUID):
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    with Session(engine) as session:
        stmt = select(
            func.avg(Report.noise_level),
            func.avg(Report.occupancy_estimate),
            func.count(Report.id)
        ).where(
            Report.location_id == location_id,
            Report.created_at >= seven_days_ago
        )

        result = session.exec(stmt).first()

        if not result or result[2] == 0:
            return {"error": "No recent data"}

        avg_noise = float(result[0])
        avg_occupancy = float(result[1])
        report_count = result[2]

        quiet_score = max(
            0,
            100 - (avg_noise * 15 + avg_occupancy * 0.5)
        )

        return {
            "location_id": location_id,
            "avg_noise_last_7d": avg_noise,
            "avg_occupancy_last_7d": avg_occupancy,
            "report_count": report_count,
            "quiet_score": round(quiet_score, 2)
        }
@app.get("/rankings")
def quiet_rankings(hour: Optional[int] = None):
    """
    If hour is provided (0-23), rank locations using only reports
    whose created_at hour matches that hour (across last 30 days).
    If not provided, use last 7 days all hours.
    """
    now = datetime.utcnow()

    if hour is None:
        start_time = now - timedelta(days=7)
    else:
        # wider window so we have enough samples for that hour
        start_time = now - timedelta(days=30)

    with Session(engine) as session:
        locations = session.exec(select(Location)).all()
        rankings = []

        for loc in locations:
            stmt = select(
                func.avg(Report.noise_level),
                func.avg(Report.occupancy_estimate),
                func.count(Report.id)
            ).where(
                Report.location_id == loc.id,
                Report.created_at >= start_time
            )

            # Filter by hour-of-day if requested
            if hour is not None:
                stmt = stmt.where(func.extract("hour", Report.created_at) == hour)

            avg_noise, avg_occ, n = session.exec(stmt).first()

            if not avg_noise or n == 0:
                continue

            avg_noise = float(avg_noise)
            avg_occ = float(avg_occ)

            quiet_score = max(0, 100 - (avg_noise * 15 + avg_occ * 0.5))

            rankings.append({
                "location_id": loc.id,
                "name": loc.name,
                "quiet_score": round(quiet_score, 2),
                "report_count": int(n)
            })

        rankings.sort(key=lambda x: x["quiet_score"], reverse=True)
        return rankings

# --- ML Forecast ---
import joblib
import numpy as np

_model = joblib.load("model_new.pkl")
_le = joblib.load("label_encoder_new.pkl")

@app.get("/forecast")
def forecast(location_id: UUID, hours_ahead: int = Query(1, ge=0, le=12)):
    target_hour = (datetime.now().hour + hours_ahead) % 24
    day_of_week = datetime.now().weekday()

    loc_id_str = str(location_id)
    if loc_id_str not in _le.classes_:
        return {"error": "Unknown location_id"}

    loc_enc = _le.transform([loc_id_str])[0]
    features = np.array([[loc_enc, target_hour, day_of_week]])
    predicted_score = float(_model.predict(features)[0])

    return {
        "location_id": location_id,
        "hours_ahead": hours_ahead,
        "predicted_at_hour": target_hour,
        "predicted_quiet_score": round(predicted_score, 2)
    }

@app.get("/quiet-now")
def quiet_now():
    current_hour = datetime.now().hour
    day_of_week = datetime.now().weekday()

    results = []
    for loc_id_str in _le.classes_:
        loc_enc = _le.transform([loc_id_str])[0]
        features = np.array([[loc_enc, current_hour, day_of_week]])
        predicted_score = float(_model.predict(features)[0])

        with Session(engine) as session:
            loc = session.exec(select(Location).where(Location.id == loc_id_str)).first()
            if not loc:
                continue

        results.append({
            "location_id": loc_id_str,
            "name": loc.name,
            "predicted_quiet_score": round(predicted_score, 2),
            "current_hour": current_hour,
            "latitude": loc.latitude,
            "longitude": loc.longitude
        })

    results.sort(key=lambda x: x["predicted_quiet_score"], reverse=True)
    return results
