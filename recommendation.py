import pandas as pd


def generate_recommendation(
    df,
    city,
    start_date=None,
    end_date=None,
    activity_duration_hours=2,
    allowed_start_hour=9,
    allowed_end_hour=18,
    min_reliable_rows=24,
    min_samples_per_hour=3,
    min_reliable_fraction=0.70,
    max_alternatives=3,
):
    """
    Rank historical activity windows for SafeHours.

    Required columns:
        City, Datetime, AQI, reliable

    allowed_start_hour is inclusive; allowed_end_hour is exclusive.
    Defaults allow activities between 9 AM and 6 PM, so a 2-hour
    activity can start at any whole hour from 9 AM through 4 PM.

    This analyses historical patterns. It does not forecast current
    AQI or guarantee that a window is safe.
    """

    required = {"City", "Datetime", "AQI", "reliable"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if (
        isinstance(activity_duration_hours, bool)
        or not isinstance(activity_duration_hours, int)
        or not 1 <= activity_duration_hours <= 24
    ):
        raise ValueError("Activity duration must be an integer from 1 to 24 hours.")

    for name, value in (
        ("allowed_start_hour", allowed_start_hour),
        ("allowed_end_hour", allowed_end_hour),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 24:
            raise ValueError(f"{name} must be an integer from 0 to 24.")

    if allowed_start_hour >= allowed_end_hour:
        raise ValueError("allowed_start_hour must be earlier than allowed_end_hour.")

    if activity_duration_hours > allowed_end_hour - allowed_start_hour:
        raise ValueError("Activity duration does not fit inside the allowed activity hours.")

    if min_reliable_rows < 1:
        raise ValueError("min_reliable_rows must be at least 1.")
    if min_samples_per_hour < 1:
        raise ValueError("min_samples_per_hour must be at least 1.")
    if not 0 <= min_reliable_fraction <= 1:
        raise ValueError("min_reliable_fraction must be between 0 and 1.")
    if max_alternatives < 0:
        raise ValueError("max_alternatives cannot be negative.")

    data = df.copy()
    data["City"] = data["City"].astype("string").str.strip()
    data["Datetime"] = pd.to_datetime(data["Datetime"], errors="coerce")
    data["AQI"] = pd.to_numeric(data["AQI"], errors="coerce")

    data = data[
        data["City"].str.casefold() == str(city).strip().casefold()
    ].copy()

    if start_date is not None:
        start = pd.Timestamp(start_date)
        data = data[data["Datetime"] >= start]

    if end_date is not None:
        end = pd.Timestamp(end_date)
        if len(str(end_date).strip()) <= 10:
            end = end + pd.Timedelta(days=1)
        data = data[data["Datetime"] < end]

    if data.empty:
        return {
            "status": "no_recommendation",
            "message": "No data found for this city and date range.",
            "city": str(city).strip(),
            "windows": [],
            "primary_recommendation": None,
            "alternatives": [],
            "hourly_scores": pd.DataFrame(),
        }

    reliable_flag = data["reliable"].fillna(False).astype(bool)
    valid = (
        reliable_flag
        & data["Datetime"].notna()
        & data["AQI"].notna()
        & data["AQI"].ge(0)
    )
    reliable = data.loc[valid].copy()
    reliable_fraction = len(reliable) / len(data)

    common_result = {
        "city": str(city).strip(),
        "allowed_start_hour": allowed_start_hour,
        "allowed_end_hour": allowed_end_hour,
        "activity_duration_hours": activity_duration_hours,
        "reliable_rows": len(reliable),
        "total_rows": len(data),
        "reliable_fraction": round(reliable_fraction, 3),
    }

    if (
        len(reliable) < min_reliable_rows
        or reliable_fraction < min_reliable_fraction
    ):
        return {
            **common_result,
            "status": "no_recommendation",
            "message": "Insufficient reliable data to recommend an activity window.",
            "windows": [],
            "primary_recommendation": None,
            "alternatives": [],
            "hourly_scores": pd.DataFrame(),
        }

    reliable["hour"] = reliable["Datetime"].dt.hour
    hourly = reliable.groupby("hour").agg(
        median_aqi=("AQI", "median"),
        sample_count=("AQI", "size"),
    )

    hourly = hourly.reindex(range(24))
    hourly.index.name = "hour"
    hourly["sample_count"] = hourly["sample_count"].fillna(0).astype(int)
    hourly["eligible"] = hourly["sample_count"] >= min_samples_per_hour
    hourly = hourly.reset_index()

    windows = []
    latest_start = allowed_end_hour - activity_duration_hours

    for start_hour in range(allowed_start_hour, latest_start + 1):
        end_hour = start_hour + activity_duration_hours
        window_hours = hourly[
            (hourly["hour"] >= start_hour)
            & (hourly["hour"] < end_hour)
        ]

        if len(window_hours) != activity_duration_hours:
            continue
        if not window_hours["eligible"].all():
            continue

        score = window_hours["median_aqi"].mean()
        end_label = (
            "12 AM (next day)"
            if end_hour == 24
            else pd.Timestamp("2000-01-01").replace(hour=end_hour).strftime("%I %p").lstrip("0")
        )

        windows.append({
            "start_hour": start_hour,
            "end_hour": end_hour,
            "start": pd.Timestamp("2000-01-01").replace(hour=start_hour).strftime("%I %p").lstrip("0"),
            "end": end_label,
            "duration_hours": activity_duration_hours,
            "score": round(float(score), 2),
            "hourly_scores": [
                {
                    "hour": int(row.hour),
                    "median_aqi": round(float(row.median_aqi), 2),
                    "sample_count": int(row.sample_count),
                }
                for row in window_hours.itertuples(index=False)
            ],
        })

    if not windows:
        return {
            **common_result,
            "status": "no_recommendation",
            "message": (
                "No window within the allowed activity hours has enough reliable "
                "observations for every hour. Try a broader date range or review "
                "the data-quality thresholds."
            ),
            "windows": [],
            "primary_recommendation": None,
            "alternatives": [],
            "hourly_scores": hourly,
        }

    windows.sort(key=lambda window: (window["score"], window["start_hour"]))
    primary = windows[0]

    return {
        **common_result,
        "status": "recommendation_available",
        "message": (
            "Windows are ranked by historical AQI within the allowed activity hours. "
            "Historical results do not establish current air quality or guarantee safety."
        ),
        "min_samples_per_hour": min_samples_per_hour,
        "primary_recommendation": primary,
        "alternatives": windows[1:1 + max_alternatives],
        "windows": windows,
        "hourly_scores": hourly,
    }
