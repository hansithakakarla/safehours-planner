
from pathlib import Path
from functools import lru_cache
import logging
import os
import threading
import urllib.request
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_quality import check_data_quality
from recommendation import (
    HEALTH_SENSITIVITY_GROUPS,
    cpcb_aqi_band,
    generate_recommendation,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "city_hour.csv"

app = FastAPI(title="SafeHours API")

allowed_frontend_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://safehour-planner.onrender.com",
]


def _normalise_origin(origin):
    origin = origin.strip().rstrip("/")
    if origin and "://" not in origin:
        # Render blueprints pass a bare host (e.g. safehours-web.onrender.com)
        origin = f"https://{origin}"
    return origin


allowed_frontend_origins.extend(
    _normalise_origin(origin)
    for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_frontend_origins,
    # Also accept any Render URL for this project (Render may add a suffix
    # such as safehours-web-ab12.onrender.com if the name is taken).
    allow_origin_regex=r"https://safehours?[a-z0-9-]*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_dataset():
    """Download the dataset from DATA_URL if it is not in the repo."""
    if DATA_PATH.exists():
        return
    data_url = os.getenv("DATA_URL", "").strip()
    if not data_url:
        return
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(data_url, DATA_PATH)


_load_lock = threading.Lock()


def load_data():
    """Return the checked dataset, loading it at most once.

    The lock makes concurrent callers (the startup preload plus any early
    requests) wait for the single load instead of each starting their own,
    which would multiply memory use and crash Render's 512 MB instance.
    """
    with _load_lock:
        return _load_data_once()


@lru_cache(maxsize=1)
def _load_data_once():
    try:
        _ensure_dataset()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not download dataset from DATA_URL: {exc}",
        ) from exc

    if not DATA_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Dataset not found: {DATA_PATH}",
        )

    # Only these columns are used; reading just them keeps memory low
    # enough for Render's 512 MB free tier.
    df = pd.read_csv(
        DATA_PATH,
        usecols=lambda c: str(c).strip() in {"City", "Datetime", "AQI"},
    )
    df.columns = [str(c).strip() for c in df.columns]

    required = {"City", "Datetime", "AQI"}
    missing = required - set(df.columns)

    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing dataset columns: {sorted(missing)}",
        )

    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
    df["AQI"] = pd.to_numeric(df["AQI"], errors="coerce")
    df = df.dropna(subset=["City", "Datetime"]).copy()
    supported_cities = {"bengaluru", "bangalore", "chennai", "delhi"}
    df = df[
        df["City"].astype(str).str.strip().str.casefold().isin(supported_cities)
    ].copy()

    df = check_data_quality(df, reference_time=None)

    return df


class PlanRequest(BaseModel):
    city: str
    activity_date: str
    activity_duration_minutes: int = 60
    preferred_start_hour: Optional[int] = None
    health_precautions_enabled: bool = False
    health_sensitivity_group: Optional[str] = None
    health_aqi_threshold: Optional[float] = None


@app.on_event("startup")
def warm_up_dataset():
    """Load and check the dataset in the background as soon as the server
    starts, so the first visitor doesn't have to wait for it."""
    def _load():
        try:
            load_data()
        except Exception:
            logging.exception("Failed to preload dataset during startup")

    threading.Thread(target=_load, daemon=True).start()


@app.get("/")
def root():
    return {"status": "ok", "message": "SafeHours API. See /api/health and /docs."}


@app.get("/api/health")
def health():
    return {"status": "ok", "message": "SafeHours API is running"}


@app.get("/api/options")
def options():
    df = load_data()

    dates_by_city = {}
    usable = df[
        df["reliable"].fillna(False).astype(bool)
        & df["AQI"].between(0, 500)
        & df["Datetime"].dt.hour.between(6, 17)
    ]
    requested_cities = ["Bengaluru", "Chennai", "Delhi"]
    for city in requested_cities:
        rows = usable[usable["City"].astype(str).str.casefold() == city.casefold()]
        dates = (
            rows["Datetime"]
            .dt.strftime("%Y-%m-%d")
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        dates_by_city[str(city)] = dates

    return {
        "cities": [city for city in requested_cities if dates_by_city[city]],
        "dates_by_city": dates_by_city,
        "durations": [60, 120, 180],
        "health_sensitivity_groups": [
            {"value": group, **details}
            for group, details in HEALTH_SENSITIVITY_GROUPS.items()
        ],
        "dataset_start": df["Datetime"].min().strftime("%Y-%m-%d"),
        "dataset_end": df["Datetime"].max().strftime("%Y-%m-%d"),
        "historical_only": True,
    }


@app.post("/api/plan")
def plan(request: PlanRequest):
    if request.activity_duration_minutes not in [60, 120, 180]:
        raise HTTPException(
            status_code=400,
            detail="Duration must be 60, 120, or 180 minutes.",
        )
    if request.preferred_start_hour is not None:
        if not 6 <= request.preferred_start_hour <= 17:
            raise HTTPException(
                status_code=400,
                detail="Start time must be between 6 AM and 5 PM.",
            )
        if request.preferred_start_hour + request.activity_duration_minutes // 60 > 18:
            raise HTTPException(
                status_code=400,
                detail="The activity must finish by 6 PM. Choose an earlier start time or shorter duration.",
            )
    if request.health_precautions_enabled:
        if request.health_sensitivity_group not in HEALTH_SENSITIVITY_GROUPS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Choose a supported health sensitivity group: "
                    + ", ".join(HEALTH_SENSITIVITY_GROUPS)
                ),
            )
        if request.health_aqi_threshold is not None and not 0 <= request.health_aqi_threshold <= 500:
            raise HTTPException(
                status_code=400,
                detail="Health AQI threshold must be between 0 and 500.",
            )

    df = load_data()

    city_rows = df[df["City"].astype(str) == request.city].copy()

    if city_rows.empty:
        raise HTTPException(status_code=404, detail="City not found.")

    selected_date = pd.to_datetime(
        request.activity_date, errors="coerce"
    )

    if pd.isna(selected_date):
        raise HTTPException(status_code=400, detail="Invalid activity date.")

    day_rows = city_rows[
        city_rows["Datetime"].dt.date == selected_date.date()
    ].copy()

    if day_rows.empty:
        raise HTTPException(
            status_code=404,
            detail="No dataset records found for this city and date.",
        )

    reliable_rows = day_rows[day_rows["reliable"] == True]
    valid_aqi = day_rows["AQI"].dropna()

    try:
        recommendation = generate_recommendation(
            df,
            city=request.city,
            activity_date=request.activity_date,
            activity_duration_minutes=request.activity_duration_minutes,
            preferred_start_hour=request.preferred_start_hour,
            health_precautions_enabled=request.health_precautions_enabled,
            health_sensitivity_group=request.health_sensitivity_group,
            health_aqi_threshold=request.health_aqi_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    hourly_readings = []
    for _, row in day_rows.sort_values("Datetime").iterrows():
        aqi = row["AQI"]
        reliable = bool(row["reliable"]) if pd.notna(row["reliable"]) else False

        hourly_readings.append({
            "time": row["Datetime"].strftime("%H:%M"),
            "aqi": float(aqi) if pd.notna(aqi) else None,
            "band": cpcb_aqi_band(float(aqi)) if pd.notna(aqi) else "Unknown",
            "reliable": reliable,
            "quality_reason": str(row.get("quality_reason", "")),
        })

    month_start = selected_date.replace(day=1)
    month_end = pd.Timestamp(month_start) + pd.offsets.MonthBegin(1)
    month_rows = city_rows[
        (city_rows["Datetime"] >= month_start)
        & (city_rows["Datetime"] < month_end)
        & city_rows["Datetime"].dt.hour.between(6, 17)
    ]
    monthly_readings = []
    for _, row in month_rows.iterrows():
        aqi = row["AQI"]
        monthly_readings.append({
            "date": row["Datetime"].strftime("%Y-%m-%d"),
            "hour": int(row["Datetime"].hour),
            "aqi": float(aqi) if pd.notna(aqi) else None,
            "reliable": bool(row["reliable"]) if pd.notna(row["reliable"]) else False,
            "quality_reason": str(row.get("quality_reason", "")),
        })

    return {
        "city": request.city,
        "activity_date": request.activity_date,
        "activity_duration_minutes": request.activity_duration_minutes,
        "mean_aqi": round(float(valid_aqi.mean()), 1) if not valid_aqi.empty else None,
        "band": cpcb_aqi_band(float(valid_aqi.mean())) if not valid_aqi.empty else "Unknown",
        "readings_count": int(len(day_rows)),
        "reliable_count": int(len(reliable_rows)),
        "hourly_readings": hourly_readings,
        "monthly_readings": monthly_readings,
        "recommendation": recommendation,
        "historical_only": True,
        "notice": (
            "Historical dataset results only. "
            "Do not treat these readings as live air-quality data."
        ),
    }
