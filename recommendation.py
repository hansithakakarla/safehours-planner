
import pandas as pd


def generate_recommendation(
    df,
    city,
    start_date=None,
    end_date=None,
    activity_duration_hours=2,
    min_reliable_rows=24,
    min_samples_per_hour=3,
    min_reliable_fraction=0.70,
    max_alternatives=3,
):
    """
    Rank historical activity windows for SafeHours.

    Required columns:
        City, Datetime, AQI, reliable

    The primary recommendation is the eligible window with
    the lowest average of its hourly median AQI values.

    This analyses historical patterns. It does not forecast
    current AQI or guarantee that a window is safe.
    """

    # 1. Validate the inputs.
    required = {"City", "Datetime", "AQI", "reliable"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    if (
        isinstance(activity_duration_hours, bool)
        or not isinstance(activity_duration_hours, int)
        or not 1 <= activity_duration_hours <= 24
    ):
        raise ValueError(
            "Activity duration must be an integer from 1 to 24 hours."
        )

    if min_reliable_rows < 1:
        raise ValueError("min_reliable_rows must be at least 1.")

    if min_samples_per_hour < 1:
        raise ValueError("min_samples_per_hour must be at least 1.")

    if not 0 <= min_reliable_fraction <= 1:
        raise ValueError(
            "min_reliable_fraction must be between 0 and 1."
        )

    if max_alternatives < 0:
        raise ValueError("max_alternatives cannot be negative.")

    # 2. Standardise the columns we use.
    data = df.copy()

    data["City"] = data["City"].astype("string").str.strip()
    data["Datetime"] = pd.to_datetime(
        data["Datetime"], errors="coerce"
    )
    data["AQI"] = pd.to_numeric(data["AQI"], errors="coerce")

    # 3. Filter the selected city.
    data = data[
        data["City"].str.casefold()
        == str(city).strip().casefold()
    ].copy()

    # 4. Filter the requested date range.
    if start_date is not None:
        start = pd.Timestamp(start_date)
        data = data[data["Datetime"] >= start]

    if end_date is not None:
        end = pd.Timestamp(end_date)

        # Include the entire end date when only a date is supplied.
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

    # 5. Keep only records that passed data-quality checks.
    valid = (
        data["reliable"].fillna(False).astype(bool)
        & data["Datetime"].notna()
        & data["AQI"].notna()
        & data["AQI"].ge(0)
    )

    reliable = data.loc[valid].copy()

    reliable_fraction = len(reliable) / len(data)

    # 6. Refuse if the overall data quality is insufficient.
    if (
        len(reliable) < min_reliable_rows
        or reliable_fraction < min_reliable_fraction
    ):
        return {
            "status": "no_recommendation",
            "message": (
                "Insufficient reliable data to recommend "
                "an activity window."
            ),
            "city": str(city).strip(),
            "reliable_rows": len(reliable),
            "total_rows": len(data),
            "reliable_fraction": round(reliable_fraction, 3),
            "windows": [],
            "primary_recommendation": None,
            "alternatives": [],
            "hourly_scores": pd.DataFrame(),
        }

    # 7. Calculate historical AQI statistics for each clock hour.
    reliable["hour"] = reliable["Datetime"].dt.hour

    hourly = reliable.groupby("hour").agg(
        median_aqi=("AQI", "median"),
        sample_count=("AQI", "size"),
    )

    # Include all 24 clock hours, marking missing hours as ineligible.
    hourly = hourly.reindex(range(24))
    hourly.index.name = "hour"

    hourly["sample_count"] = (
        hourly["sample_count"].fillna(0).astype(int)
    )

    hourly["eligible"] = (
        hourly["sample_count"] >= min_samples_per_hour
    )

    hourly = hourly.reset_index()

    # 8. Generate every possible window of the requested duration.
    windows = []

    for start_hour in range(24 - activity_duration_hours + 1):
        end_hour = start_hour + activity_duration_hours

        window_hours = hourly[
            (hourly["hour"] >= start_hour)
            & (hourly["hour"] < end_hour)
        ]

        # Every hour in a candidate window must have enough data.
        if not window_hours["eligible"].all():
            continue

        # Compare windows using the mean of hourly median AQI.
        score = window_hours["median_aqi"].mean()

        windows.append({
            "start_hour": start_hour,
            "end_hour": end_hour,
            "start": pd.Timestamp(
                "2000-01-01"
            ).replace(hour=start_hour).strftime("%I %p").lstrip("0"),
            "end": (
                "12 AM (next day)"
                if end_hour == 24
                else pd.Timestamp(
                    "2000-01-01"
                ).replace(hour=end_hour).strftime("%I %p").lstrip("0")
            ),
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

    # 9. Refuse if no candidate window has sufficient coverage.
    if not windows:
        return {
            "status": "no_recommendation",
            "message": (
                "No window has sufficient reliable observations "
                "for every hour. Try a broader date range."
            ),
            "city": str(city).strip(),
            "reliable_rows": len(reliable),
            "total_rows": len(data),
            "reliable_fraction": round(reliable_fraction, 3),
            "windows": [],
            "primary_recommendation": None,
            "alternatives": [],
            "hourly_scores": hourly,
        }

    # 10. Rank windows: lowest AQI score first.
    # For ties, prefer the earlier window.
    windows.sort(
        key=lambda window: (
            window["score"],
            window["start_hour"],
        )
    )

    primary = windows[0]
    alternatives = windows[1:1 + max_alternatives]

    # 11. Return the result for the web app.
    return {
        "status": "recommendation_available",
        "message": (
            "Windows are ranked by historical AQI. "
            "Historical results do not establish current air quality "
            "or guarantee that outdoor activity is safe."
        ),
        "city": str(city).strip(),
        "activity_duration_hours": activity_duration_hours,
        "reliable_rows": len(reliable),
        "total_rows": len(data),
        "reliable_fraction": round(reliable_fraction, 3),
        "min_samples_per_hour": min_samples_per_hour,
        "primary_recommendation": primary,
        "alternatives": alternatives,
        "windows": windows,
        "hourly_scores": hourly,
    }
