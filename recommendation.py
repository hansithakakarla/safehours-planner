import pandas as pd


def generate_recommendation(
    df,
    city,
    start_date=None,
    end_date=None,
    max_aqi=100,
    min_reliable_rows=24,
    min_samples_per_hour=3,
    min_reliable_fraction=0.70,
    min_window_hours=2,
):

    required = {"City", "Datetime", "AQI", "reliable"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    if max_aqi < 0 or min_reliable_rows < 1:
        raise ValueError("Invalid AQI or minimum row setting.")

    if min_samples_per_hour < 1 or min_window_hours < 1:
        raise ValueError("Minimum counts must be at least 1.")

    if not 0 <= min_reliable_fraction <= 1:
        raise ValueError("Reliable fraction must be between 0 and 1.")

    data = df.copy()
    data["Datetime"] = pd.to_datetime(
        data["Datetime"], errors="coerce"
    )
    data["AQI"] = pd.to_numeric(data["AQI"], errors="coerce")
    data["City"] = data["City"].astype("string").str.strip()

    # Select the requested city.
    data = data[
        data["City"].str.casefold() == str(city).strip().casefold()
    ].copy()

    if start_date is not None:
        data = data[data["Datetime"] >= pd.Timestamp(start_date)]

    if end_date is not None:
        # Include the entire end date if a date alone is supplied.
        end = pd.Timestamp(end_date)
        if len(str(end_date).strip()) <= 10:
            end = end + pd.Timedelta(days=1)
        data = data[data["Datetime"] < end]

    if data.empty:
        return {
            "status": "no_recommendation",
            "message": "No data found for this city and date range.",
            "windows": [],
            "hourly_scores": pd.DataFrame(),
        }

    # Remove records that cannot be used for scoring.
    valid = (
        data["reliable"].fillna(False).astype(bool)
        & data["Datetime"].notna()
        & data["AQI"].notna()
        & data["AQI"].ge(0)
    )

    reliable = data.loc[valid].copy()

    reliable_fraction = len(reliable) / len(data)

    # Refuse when the overall data quality is insufficient.
    if (
        len(reliable) < min_reliable_rows
        or reliable_fraction < min_reliable_fraction
    ):
        return {
            "status": "no_recommendation",
            "message": (
                "Insufficient reliable data to recommend "
                "outdoor activity hours."
            ),
            "reliable_rows": len(reliable),
            "total_rows": len(data),
            "reliable_fraction": round(reliable_fraction, 3),
            "windows": [],
            "hourly_scores": pd.DataFrame(),
        }

    # Summarise each hour using reliable observations only.
    reliable["hour"] = reliable["Datetime"].dt.hour

    hourly = reliable.groupby("hour").agg(
        median_aqi=("AQI", "median"),
        sample_count=("AQI", "size"),
    )

    # An hour is eligible only when it has sufficient observations.
    hourly["eligible"] = (
        hourly["sample_count"] >= min_samples_per_hour
    )

    hourly["recommended"] = (
        hourly["eligible"]
        & (hourly["median_aqi"] <= max_aqi)
    )

    hourly = hourly.reset_index().sort_values("hour")

    eligible = hourly[hourly["recommended"]].copy()

    if eligible.empty:
        return {
            "status": "no_recommendation",
            "message": (
                "No hour met the data-coverage and AQI criteria. "
                "The app will not recommend an activity window."
            ),
            "reliable_rows": len(reliable),
            "total_rows": len(data),
            "reliable_fraction": round(reliable_fraction, 3),
            "windows": [],
            "hourly_scores": hourly,
        }

    # Group consecutive qualifying hours into activity windows.
    windows = []
    current = []

    for row in eligible.itertuples(index=False):
        hour = int(row.hour)

        if current and hour != current[-1]["hour"] + 1:
            if len(current) >= min_window_hours:
                windows.append(current)
            current = []

        current.append({
            "hour": hour,
            "median_aqi": round(float(row.median_aqi), 1),
            "sample_count": int(row.sample_count),
        })

    if len(current) >= min_window_hours:
        windows.append(current)

    # Prefer lower median AQI; break ties by longer windows.
    windows.sort(
        key=lambda w: (
            sum(h["median_aqi"] for h in w) / len(w),
            -len(w),
        )
    )

    if not windows:
        return {
            "status": "no_recommendation",
            "message": (
                "No sufficiently long consecutive window met "
                "the criteria. Try a broader date range."
            ),
            "reliable_rows": len(reliable),
            "total_rows": len(data),
            "reliable_fraction": round(reliable_fraction, 3),
            "windows": [],
            "hourly_scores": hourly,
        }

    def format_hour(hour):
        return pd.Timestamp("2000-01-01") + pd.Timedelta(hours=hour)

    formatted_windows = []

    for window in windows:
        start_hour = window[0]["hour"]
        end_hour = window[-1]["hour"] + 1

        formatted_windows.append({
            "start": format_hour(start_hour).strftime("%I %p").lstrip("0"),
            "end": format_hour(end_hour % 24).strftime("%I %p").lstrip("0"),
            "average_of_hourly_medians": round(
                sum(h["median_aqi"] for h in window) / len(window), 1
            ),
            "hours": window,
        })

    return {
        "status": "recommendation_available",
        "message": (
            "These are historically lower-AQI hours in the selected "
            "data. They do not confirm current air quality or guarantee safety."
        ),
        "city": str(city).strip(),
        "reliable_rows": len(reliable),
        "total_rows": len(data),
        "reliable_fraction": round(reliable_fraction, 3),
        "max_aqi_threshold": max_aqi,
        "windows": formatted_windows,
        "hourly_scores": hourly,
    }
