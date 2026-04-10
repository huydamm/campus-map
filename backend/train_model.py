import pandas as pd
import joblib
from sqlmodel import Session, select
from db import engine
from models import Report, Location
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

def main():
    print("Loading data from database...")
    with Session(engine) as session:
        reports = session.exec(select(Report)).all()
        locations = session.exec(select(Location)).all()

    loc_map = {str(loc.id): loc.name for loc in locations}

    rows = []
    for r in reports:
        rows.append({
            "location_id": str(r.location_id),
            "hour": r.created_at.hour,
            "day_of_week": r.created_at.weekday(),
            "noise_level": r.noise_level,
            "occupancy_estimate": r.occupancy_estimate,
        })

    df = pd.DataFrame(rows)
    df["quiet_score"] = 100 - (df["noise_level"] * 15 + df["occupancy_estimate"] * 0.5)

    le = LabelEncoder()
    df["location_enc"] = le.fit_transform(df["location_id"])

    X = df[["location_enc", "hour", "day_of_week"]]
    y = df["quiet_score"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("Training Random Forest...")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    print(f"MAE on test set: {mae:.2f} quiet score points")

    joblib.dump(model, "model.pkl")
    joblib.dump(le, "label_encoder.pkl")
    print("Saved model.pkl and label_encoder.pkl")

if __name__ == "__main__":
    main()
