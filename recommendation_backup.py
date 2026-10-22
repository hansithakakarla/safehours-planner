import pandas as pd


CPCB_AQI_BANDS = [
    (0, 50, "Good", "Minimal impact expected for most people."),
    (51, 100, "Satisfactory", "Minor breathing discomfort may occur for sensitive people."),
    (101, 200, "Moderate", "Breathing discomfort may occur for people with asthma, lung or heart disease, children, and older adults."),
    (201, 300, "Poor", "Breathing discomfort may occur on prolonged exposure; sensitive groups may be affected more."),
    (301, 400, "Very Poor", "Respiratory illness may occur on prolonged exposure."),
    (401, 500, "Severe", "Health effects may occur even in healthy people; sensitive groups may experience serious effects."),
]


def cpcb_aqi_band(aqi):
    """Return the CPCB AQI band and a plain-language advisory."""
    if pd.isna(aqi) or aqi < 0:
        return {"band": "Unknown", "advisory": "AQI is unavailable."}

    for lower, upper, band, advisory in CPCB_AQI_BANDS:
        if lower <= aqi <= upper:
            return {"band": band, "advisory": advisory}

    return {
        "band": "Above scale",
        "advisory": "AQI is outside the supported 0–500 CPCB scale; verify the source data.",
    }


def _no_advice(city, activity_date, message, **extra):
    return {
        "status": "no_advice",
        "message": message,
        "city": str(city).strip(),
        "activity_date": str(activity_date),
        "primary_recommendation": None,
        "alternatives": [],
        "hourly_strip": [],
        **extra,
    }


def generate_recommendation(
    df,
    city,
    activity_date,
    activity_duration_minutes=60,
    min_reliable_fraction=0.70,
    min_reliable_rows=6,
    max_alternatives=3,
):
    """
    Recommend a historical outdoor-activity window for one city and date.

    Required columns: City, Datetime, AQI, reliable

    The dataset is historical hourly AQI. Candidate start times are whole hours
    from 06:00, and every hourly bucket touched by an activity must have reliable
    AQI data. For now, duration must be a whole number of hours because the
    source data is hourly; this avoids pretending to know sub-hour conditions.

    This is a historical planner, not a forecast of current conditions.
    """

    required = {"City", "Datetime", "AQI", "reliable"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if (
        isinstance(activity_duration_minutes, bool)
        or not isinstance(activity_duration_minutes, int)
        or activity_duration_minutes < 60
        or activity_duration_minutes % 60 != 0
    ):
        raise ValueError(
            "With hourly source data, activity_duration_minutes must be a "
            "positive whole number of hours (for example, 60, 120, or 180)."
        )

    if not 0 <= min_reliable_fraction <= 1:
        raise ValueError("min_reliable_fraction must be between 0 and 1.")
    if min_reliable_rows < 1:
        raise ValueError("min_reliable_rows must be at least 1.")
    if max_alternatives < 0:
        raise ValueError("max_alternatives cannot be negative.")

    try:
        selected_date = pd.Timestamp(activity_date).date()
    except (TypeError, ValueError):
        raise ValueError("activity_date must be a valid date, e.g. '2018-06-15'.")

    data = df.copy()
    data["City"] = data["City"].astype("string").str.strip()
    data["Datetime"] = pd.to_datetime(data["Datetime"], errors="coerce")
    data["AQI"] = pd.to_numeric(data["AQI"], errors="coerce")

    city_rows = data[
        data["City"].str.casefold() == str(city).strip().casefold()
    ].copy()
    city_rows = city_rows[city_rows["Datetime"].notna()].copy()
    city_rows["date"] = city_rows["Datetime"].dt.date
    day_rows = city_rows[city_rows["date"] == selected_date].copy()

    if day_rows.empty:
        return _no_advice(
            city, selected_date,
            "No data is available for this city on the selected date.",
        )

    # AQI records outside 06:00–18:00 are not used for the planner's hourly strip.
    day_rows = day_rows[
        (day_rows["Datetime"].dt.hour >= 6)
        & (day_rows["Datetime"].dt.hour < 18)
    ].copy()

    if day_rows.empty:
        return _no_advice(
            city, selected_date,
            "No readings are available between 6 AM and 6 PM on the selected date.",
        )

    day_rows["reliable_flag"] = (
        day_rows["reliable"].fillna(False).astype(bool)
        & day_rows["AQI"].notna()
        & day_rows["AQI"].between(0, 500)
    )

    total_rows = len(day_rows)
    reliable_rows = day_rows[day_rows["reliable_flag"]].copy()
    reliable_fraction = len(reliable_rows) / total_rows if total_rows else 0.0

    # Aggregate duplicate observations in an hour using the median, but mark an
    # hour reliable only when its rows have adequate reliability coverage.
    hourly_all = day_rows.groupby(day_rows["Datetime"].dt.hour).agg(
        total_samples=("AQI", "size"),
        reliable_samples=("reliable_flag", "sum"),
    )
    hourly_good = reliable_rows.groupby(
        reliable_rows["Datetime"].dt.hour
    )["AQI"].median()

    hourly = pd.DataFrame(index=range(6, 18))
    hourly.index.name = "hour"
    hourly["aqi"] = hourly_good.reindex(hourly.index)
    hourly["total_samples"] = hourly_all["total_samples"].reindex(
        hourly.index
    ).fillna(0).astype(int)
    hourly["reliable_samples"] = hourly_all["reliable_samples"].reindex(
        hourly.index
    ).fillna(0).astype(int)
    hourly["reliable"] = (
        hourly["total_samples"].gt(0)
        & hourly["reliable_samples"].eq(hourly["total_samples"])
        & hourly["aqi"].notna()
    )

    hourly_strip = []
    for hour, row in hourly.iterrows():
        band = cpcb_aqi_band(row["aqi"])
        hourly_strip.append({
            "hour": int(hour),
            "time": f"{int(hour):02d}:00–{int(hour) + 1:02d}:00",
            "aqi": None if pd.isna(row["aqi"]) else round(float(row["aqi"]), 1),
            "band": band["band"] if row["reliable"] else "No reliable data",
            "advisory": band["advisory"] if row["reliable"] else "No reliable AQI reading for this hour.",
            "reliable": bool(row["reliable"]),
        })

    if len(reliable_rows) < min_reliable_rows or reliable_fraction < min_reliable_fraction:
        return _no_advice(
            city, selected_date,
            "No advice: the selected date does not have enough reliable AQI data.",
            reliable_rows=int(len(reliable_rows)),
            total_rows=int(total_rows),
            reliable_fraction=round(float(reliable_fraction), 3),
            hourly_strip=hourly_strip,
        )

    duration_hours = activity_duration_minutes // 60
    # End time is exclusive: the activity must finish by 18:00.
    last_start = 18 - duration_hours
    candidates = []

    for start_hour in range(6, last_start + 1):
        end_hour = start_hour + duration_hours
        window = hourly.loc[start_hour:end_hour - 1]

        if len(window) != duration_hours or not window["reliable"].all():
            continue

        values = window["aqi"].astype(float)
        mean_aqi = float(values.mean())
        worst_aqi = float(values.max())
        mean_band = cpcb_aqi_band(mean_aqi)
        worst_band = cpcb_aqi_band(worst_aqi)

        candidates.append({
            "start_hour": int(start_hour),
            "end_hour": int(end_hour),
            "start": pd.Timestamp("2000-01-01").replace(hour=start_hour).strftime("%I %p").lstrip("0"),
            "end": pd.Timestamp("2000-01-01").replace(hour=end_hour).strftime("%I %p").lstrip("0"),
            "duration_minutes": activity_duration_minutes,
            "mean_aqi": round(mean_aqi, 1),
            "worst_hour_aqi": round(worst_aqi, 1),
            "aqi_band": mean_band["band"],
            "reason": (
                f"Mean AQI {mean_aqi:.1f} ({mean_band['band']}); "
                f"highest hourly AQI in this window is {worst_aqi:.1f} "
                f"({worst_band['band']}). Ranked using reliable readings "
                "for the selected date."
            ),
        })

    if not candidates:
        return _no_advice(
            city, selected_date,
            "No advice: no complete activity window between 6 AM and 6 PM "
            "has reliable readings for every hour.",
            reliable_rows=int(len(reliable_rows)),
            total_rows=int(total_rows),
            reliable_fraction=round(float(reliable_fraction), 3),
            hourly_strip=hourly_strip,
        )

    candidates.sort(key=lambda w: (w["mean_aqi"], w["worst_hour_aqi"], w["start_hour"]))
    primary = candidates[0]
    alternatives = candidates[1:1 + max_alternatives]

    # Do not describe any AQI band as an unconditional guarantee of safety.
    advisory = (
        f"For {str(city).strip()} on {selected_date}, the lowest-scoring "
        f"eligible {activity_duration_minutes}-minute window in the available "
        f"historical readings is {primary['start']}–{primary['end']}. "
        f"Its mean AQI is {primary['mean_aqi']:.1f} ({primary['aqi_band']}). "
        f"{cpcb_aqi_band(primary['mean_aqi'])['advisory']} "
        "This is a historical-data recommendation, not a live AQI forecast; "
        "check current local conditions before the activity."
    )

    return {
        "status": "recommendation_available",
        "message": (
            "The window is ranked by mean hourly AQI among eligible windows "
            "with reliable observations. Historical data does not guarantee "
            "conditions on another day."
        ),
        "city": str(city).strip(),
        "activity_date": str(selected_date),
        "activity_duration_minutes": activity_duration_minutes,
        "search_start_hour": 6,
        "search_end_hour": 18,
        "reliable_rows": int(len(reliable_rows)),
        "total_rows": int(total_rows),
        "reliable_fraction": round(float(reliable_fraction), 3),
        "hourly_strip": hourly_strip,
        "primary_recommendation": primary,
        "alternatives": alternatives,
        "advisory": advisory,
    }
