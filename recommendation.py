
import pandas as pd


CPCB_AQI_BANDS = [
    (0, 50, "Good", "Minimal impact expected for most people."),
    (51, 100, "Satisfactory", "Minor breathing discomfort may occur for sensitive people."),
    (
        101, 200, "Moderate",
        "Breathing discomfort may occur for people with asthma, lung or heart disease, children, and older adults.",
    ),
    (
        201, 300, "Poor",
        "Breathing discomfort may occur on prolonged exposure; sensitive groups may be affected more.",
    ),
    (301, 400, "Very Poor", "Respiratory illness may occur on prolonged exposure."),
    (
        401, 500, "Severe",
        "Health effects may occur even in healthy people; sensitive groups may experience serious effects.",
    ),
]

# These are configurable planning defaults, not clinical safety thresholds.
# Users can supply a different threshold when enabling health guidance.
HEALTH_SENSITIVITY_GROUPS = {
    "asthma": {
        "label": "Asthma",
        "default_aqi_threshold": 100,
    },
    "respiratory_condition": {
        "label": "Respiratory condition",
        "default_aqi_threshold": 100,
    },
    "heart_condition": {
        "label": "Heart condition",
        "default_aqi_threshold": 100,
    },
    "children": {
        "label": "Children",
        "default_aqi_threshold": 100,
    },
    "older_adults": {
        "label": "Older adults",
        "default_aqi_threshold": 100,
    },
}


def cpcb_aqi_band(aqi):
    """Return the CPCB AQI band and a plain-language advisory."""
    if pd.isna(aqi) or aqi < 0:
        return {
            "band": "Unknown",
            "advisory": "AQI is unavailable.",
        }

    for lower, upper, band, advisory in CPCB_AQI_BANDS:
        if lower <= aqi <= upper:
            return {"band": band, "advisory": advisory}

    return {
        "band": "Above scale",
        "advisory": (
            "AQI is outside the supported 0–500 CPCB scale; "
            "verify the source data."
        ),
    }


def _no_advice(city, activity_date, message, **extra):
    """Build a consistent response when no recommendation is available."""
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


def _format_hour(hour):
    """Format a whole hour as a readable time, e.g. 6 AM."""
    return (
        pd.Timestamp("2000-01-01")
        .replace(hour=int(hour))
        .strftime("%I %p")
        .lstrip("0")
    )


def _make_window(window, duration_minutes):
    """Convert hourly readings into a recommendation-window dictionary."""
    values = window["aqi"].astype(float)
    mean_aqi = float(values.mean())
    worst_aqi = float(values.max())

    mean_band = cpcb_aqi_band(mean_aqi)
    worst_band = cpcb_aqi_band(worst_aqi)

    start_hour = int(window.index[0])
    end_hour = int(window.index[-1]) + 1

    return {
        "start_hour": start_hour,
        "end_hour": end_hour,
        "start": _format_hour(start_hour),
        "end": _format_hour(end_hour),
        "duration_minutes": duration_minutes,
        "mean_aqi": round(mean_aqi, 1),
        "worst_hour_aqi": round(worst_aqi, 1),
        "aqi_band": mean_band["band"],
        "reason": (
            f"This time slot has an average AQI of {mean_aqi:.1f} "
            f"({mean_band['band']}).\n\n"
            f"The highest hourly AQI in the slot is {worst_aqi:.1f} "
            f"({worst_band['band']}). "
            "This slot was assessed using reliable readings "
            "for the selected date."
        ),
    }


def generate_recommendation(
    df,
    city,
    activity_date,
    activity_duration_minutes=60,
    min_reliable_fraction=0.70,
    min_reliable_rows=6,
    max_alternatives=3,
    preferred_start_hour=None,
    health_precautions_enabled=False,
    health_sensitivity_group=None,
    health_aqi_threshold=None,
):
    """
    Recommend a historical outdoor-activity window for one city and date.

    Required columns: City, Datetime, AQI, reliable

    Candidate start times are whole hours from 06:00. Every hourly
    bucket touched by an activity must have reliable AQI data.

    Activity durations must be whole numbers of hours because the
    source data is hourly.

    Preferred start time is optional. Health guidance is also optional.
    When enabled, candidate windows must meet the selected AQI threshold.

    Health thresholds are configurable planning heuristics, not
    medical advice or guarantees of safety.

    This is a historical planner, not a current AQI forecast.
    """

    required = {"City", "Datetime", "AQI", "reliable"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    if (
        isinstance(activity_duration_minutes, bool)
        or not isinstance(activity_duration_minutes, int)
        or activity_duration_minutes < 60
        or activity_duration_minutes % 60 != 0
    ):
        raise ValueError(
            "With hourly source data, activity_duration_minutes must "
            "be a positive whole number of hours "
            "(for example, 60, 120, or 180)."
        )

    if not 0 <= min_reliable_fraction <= 1:
        raise ValueError(
            "min_reliable_fraction must be between 0 and 1."
        )

    if min_reliable_rows < 1:
        raise ValueError("min_reliable_rows must be at least 1.")

    if max_alternatives < 0:
        raise ValueError("max_alternatives cannot be negative.")

    if not isinstance(health_precautions_enabled, bool):
        raise ValueError(
            "health_precautions_enabled must be True or False."
        )

    if health_precautions_enabled:
        if health_sensitivity_group not in HEALTH_SENSITIVITY_GROUPS:
            raise ValueError(
                "Choose a supported health_sensitivity_group: "
                + ", ".join(HEALTH_SENSITIVITY_GROUPS)
            )

        if health_aqi_threshold is None:
            health_aqi_threshold = HEALTH_SENSITIVITY_GROUPS[
                health_sensitivity_group
            ]["default_aqi_threshold"]

    if health_aqi_threshold is not None:
        if (
            isinstance(health_aqi_threshold, bool)
            or not isinstance(health_aqi_threshold, (int, float))
            or not 0 <= health_aqi_threshold <= 500
        ):
            raise ValueError(
                "health_aqi_threshold must be a number between 0 and 500."
            )

        health_aqi_threshold = float(health_aqi_threshold)

    if preferred_start_hour is not None:
        if (
            isinstance(preferred_start_hour, bool)
            or not isinstance(preferred_start_hour, int)
            or not 6 <= preferred_start_hour <= 17
        ):
            raise ValueError(
                "Preferred start time must be a whole hour from "
                "6 AM to 5 PM, or None."
            )

        if (
            preferred_start_hour
            + activity_duration_minutes // 60
            > 18
        ):
            raise ValueError(
                "The preferred activity must finish by 6 PM. "
                "Choose an earlier start time or shorter duration."
            )

    try:
        selected_date = pd.Timestamp(activity_date).date()
    except (TypeError, ValueError):
        raise ValueError(
            "activity_date must be a valid date, e.g. '2018-06-15'."
        )

    data = df.copy()
    data["City"] = data["City"].astype("string").str.strip()
    data["Datetime"] = pd.to_datetime(
        data["Datetime"], errors="coerce"
    )
    data["AQI"] = pd.to_numeric(data["AQI"], errors="coerce")

    city_rows = data[
        data["City"].str.casefold()
        == str(city).strip().casefold()
    ].copy()

    city_rows = city_rows[city_rows["Datetime"].notna()].copy()
    city_rows["date"] = city_rows["Datetime"].dt.date
    day_rows = city_rows[
        city_rows["date"] == selected_date
    ].copy()

    if day_rows.empty:
        return _no_advice(
            city,
            selected_date,
            f"We could not find AQI records for {str(city).strip()} "
            f"on {selected_date}. Please try another date or city.",
        )

    # Only use observations from 06:00 through 17:59.
    day_rows = day_rows[
        (day_rows["Datetime"].dt.hour >= 6)
        & (day_rows["Datetime"].dt.hour < 18)
    ].copy()

    if day_rows.empty:
        return _no_advice(
            city,
            selected_date,
            "We could not find readings between 6 AM and 6 PM "
            "for this date. Please try another date.",
        )

    day_rows["reliable_flag"] = (
        day_rows["reliable"].fillna(False).astype(bool)
        & day_rows["AQI"].notna()
        & day_rows["AQI"].between(0, 500)
    )

    total_rows = len(day_rows)
    reliable_rows = day_rows[
        day_rows["reliable_flag"]
    ].copy()

    reliable_fraction = (
        len(reliable_rows) / total_rows if total_rows else 0.0
    )

    # Aggregate duplicate observations by hour. An hour is reliable
    # only when every row in that hour is marked reliable.
    hourly_all = day_rows.groupby(
        day_rows["Datetime"].dt.hour
    ).agg(
        total_samples=("AQI", "size"),
        reliable_samples=("reliable_flag", "sum"),
    )

    hourly_good = reliable_rows.groupby(
        reliable_rows["Datetime"].dt.hour
    )["AQI"].median()

    hourly = pd.DataFrame(index=range(6, 18))
    hourly.index.name = "hour"

    hourly["aqi"] = hourly_good.reindex(hourly.index)

    hourly["total_samples"] = (
        hourly_all["total_samples"]
        .reindex(hourly.index)
        .fillna(0)
        .astype(int)
    )

    hourly["reliable_samples"] = (
        hourly_all["reliable_samples"]
        .reindex(hourly.index)
        .fillna(0)
        .astype(int)
    )

    hourly["reliable"] = (
        hourly["total_samples"].gt(0)
        & hourly["reliable_samples"].eq(
            hourly["total_samples"]
        )
        & hourly["aqi"].notna()
    )

    hourly_strip = []

    for hour, row in hourly.iterrows():
        band = cpcb_aqi_band(row["aqi"])
        is_reliable = bool(row["reliable"])

        hourly_strip.append({
            "hour": int(hour),
            "time": f"{int(hour):02d}:00–{int(hour) + 1:02d}:00",
            "aqi": (
                None
                if pd.isna(row["aqi"])
                else round(float(row["aqi"]), 1)
            ),
            "band": (
                band["band"] if is_reliable
                else "No reliable data"
            ),
            "advisory": (
                band["advisory"] if is_reliable
                else "No reliable AQI reading for this hour."
            ),
            "reliable": is_reliable,
        })

    base_metadata = {
        "reliable_rows": int(len(reliable_rows)),
        "total_rows": int(total_rows),
        "reliable_fraction": round(
            float(reliable_fraction), 3
        ),
        "hourly_strip": hourly_strip,
    }

    health_group_label = (
        HEALTH_SENSITIVITY_GROUPS[health_sensitivity_group]["label"]
        if health_precautions_enabled
        else None
    )

    health_metadata = {
        "health_guidance_applied": bool(
            health_precautions_enabled
        ),
        "health_sensitivity_group": (
            health_sensitivity_group
            if health_precautions_enabled
            else None
        ),
        "health_sensitivity_label": health_group_label,
        "health_aqi_threshold": (
            health_aqi_threshold
            if health_precautions_enabled
            else None
        ),
    }

    if (
        len(reliable_rows) < min_reliable_rows
        or reliable_fraction < min_reliable_fraction
    ):
        return _no_advice(
            city,
            selected_date,
            "We do not have enough reliable AQI readings to suggest "
            "an outdoor activity time for this date.\n\n"
            "Please try another date. The hourly strip shows which "
            "hours have missing or unreliable data.",
            **base_metadata,
            **health_metadata,
        )

    duration_hours = activity_duration_minutes // 60
    last_start = 18 - duration_hours
    candidates = []

    for start_hour in range(6, last_start + 1):
        end_hour = start_hour + duration_hours
        window = hourly.loc[start_hour:end_hour - 1]

        if (
            len(window) != duration_hours
            or not window["reliable"].all()
        ):
            continue

        candidates.append(
            _make_window(window, activity_duration_minutes)
        )

    if not candidates:
        return _no_advice(
            city,
            selected_date,
            "We could not find a complete activity window with "
            "reliable AQI readings for every hour between 6 AM "
            "and 6 PM.\n\nPlease try another date or choose a "
            "different activity duration.",
            **base_metadata,
            **health_metadata,
        )

    # Rank by average AQI, then worst hourly AQI, then earlier start.
    candidates.sort(
        key=lambda window: (
            window["mean_aqi"],
            window["worst_hour_aqi"],
            window["start_hour"],
        )
    )

    eligible_candidates = candidates

    if health_precautions_enabled:
        eligible_candidates = [
            window for window in candidates
            if window["worst_hour_aqi"] <= health_aqi_threshold
        ]

    health_metadata["eligible_window_count"] = len(
        eligible_candidates
    )

    if health_precautions_enabled:
        health_metadata["health_guidance_summary"] = (
            f"Windows were filtered to require every hourly AQI "
            f"reading to be at or below {health_aqi_threshold:g} "
            f"for the selected group: {health_group_label}. "
            "This is a configurable planning heuristic, not "
            "medical advice or a guarantee of safety."
        )
    else:
        health_metadata["health_guidance_summary"] = None

    if not eligible_candidates:
        return _no_advice(
            city,
            selected_date,
            (
                "Reliable activity windows were found, but none "
                "met the selected health AQI threshold. Consider "
                "a different date or check current local air "
                "quality before planning an outdoor activity."
            ),
            reason_code="no_health_eligible_window",
            reliable_window_count=len(candidates),
            alternatives=[],
            preferred_window=None,
            preferred_alternative=None,
            **base_metadata,
            **health_metadata,
        )

    primary = eligible_candidates[0]
    alternatives = eligible_candidates[
        1:1 + max_alternatives
    ]

    advisory = (
        f"For {str(city).strip()} on {selected_date}, the best "
        f"eligible time in the available historical data is "
        f"{primary['start']}–{primary['end']} for your "
        f"{activity_duration_minutes}-minute activity.\n\n"
        f"The average AQI for this window is "
        f"{primary['mean_aqi']:.1f} ({primary['aqi_band']}). "
        f"{cpcb_aqi_band(primary['mean_aqi'])['advisory']}\n\n"
        "This result is based on historical readings, not a live "
        "AQI forecast. Please check current local conditions "
        "before the activity."
    )

    if health_precautions_enabled:
        advisory += (
            f"\n\nHealth planning filter: the worst hourly AQI "
            f"in the recommended window is "
            f"{primary['worst_hour_aqi']:.1f}, within the "
            f"configured threshold of {health_aqi_threshold:g} "
            f"for {health_group_label}. This threshold is a "
            "planning preference, not a medical safety guarantee."
        )

    preferred_window = None
    preferred_alternative = None

    if preferred_start_hour is not None:
        preferred_end_hour = (
            preferred_start_hour + duration_hours
        )
        preferred_hours = hourly.loc[
            preferred_start_hour:preferred_end_hour - 1
        ]

        preferred_is_reliable = (
            len(preferred_hours) == duration_hours
            and bool(preferred_hours["reliable"].all())
        )

        preferred_start = _format_hour(preferred_start_hour)
        preferred_end = _format_hour(preferred_end_hour)

        if not preferred_is_reliable:
            preferred_window = {
                "start_hour": preferred_start_hour,
                "end_hour": preferred_end_hour,
                "start": preferred_start,
                "end": preferred_end,
                "status": "unavailable",
                "mean_aqi": None,
                "worst_hour_aqi": None,
                "aqi_band": "No reliable data",
                "message": (
                    f"We cannot assess your preferred time because "
                    f"at least one hour between "
                    f"{preferred_start_hour}:00 and "
                    f"{preferred_end_hour}:00 is missing or "
                    "unreliable.\n\nWe have looked for another "
                    "time with reliable readings instead."
                ),
            }
            preferred_alternative = primary

        else:
            preferred_candidate = next(
                (
                    window for window in candidates
                    if window["start_hour"] == preferred_start_hour
                ),
                None,
            )

            if preferred_candidate is None:
                # A fully reliable preferred window should normally
                # be present among the candidates.
                preferred_window = {
                    "start_hour": preferred_start_hour,
                    "end_hour": preferred_end_hour,
                    "start": preferred_start,
                    "end": preferred_end,
                    "status": "unavailable",
                    "mean_aqi": None,
                    "worst_hour_aqi": None,
                    "aqi_band": "Unavailable",
                    "message": "The preferred time could not be assessed.",
                }
                preferred_alternative = primary

            else:
                is_health_eligible = (
                    preferred_candidate in eligible_candidates
                )

                if (
                    health_precautions_enabled
                    and not is_health_eligible
                ):
                    preferred_window = {
                        **preferred_candidate,
                        "status": "above_health_threshold",
                        "message": (
                            f"Your preferred time, "
                            f"{preferred_candidate['start']}–"
                            f"{preferred_candidate['end']}, has "
                            f"a worst hourly AQI of "
                            f"{preferred_candidate['worst_hour_aqi']:.1f}, "
                            f"above the configured threshold of "
                            f"{health_aqi_threshold:g}.\n\n"
                            "It does not meet your selected health "
                            "planning preference."
                        ),
                    }
                    preferred_alternative = primary

                else:
                    preferred_window = {
                        **preferred_candidate,
                        "status": "assessed",
                        "message": (
                            f"Your preferred time, "
                            f"{preferred_candidate['start']}–"
                            f"{preferred_candidate['end']}, has "
                            f"an average AQI of "
                            f"{preferred_candidate['mean_aqi']:.1f} "
                            f"({preferred_candidate['aqi_band']}).\n\n"
                            f"{cpcb_aqi_band(preferred_candidate['mean_aqi'])['advisory']}"
                        ),
                    }

                    better_options = [
                        window for window in eligible_candidates
                        if (
                            window["start_hour"] != preferred_start_hour
                            and window["mean_aqi"]
                            < preferred_candidate["mean_aqi"]
                        )
                    ]

                    if better_options:
                        preferred_alternative = better_options[0]
                        preferred_window["message"] += (
                            f"\n\nA lower-AQI option is "
                            f"{preferred_alternative['start']}–"
                            f"{preferred_alternative['end']}, "
                            f"with an average AQI of "
                            f"{preferred_alternative['mean_aqi']:.1f}."
                        )
                    else:
                        preferred_window["message"] += (
                            "\n\nWe did not find another eligible "
                            "time slot with a lower average AQI "
                            "in the available data."
                        )

    return {
        "status": "recommendation_available",
        "message": (
            "We found one or more activity times with reliable "
            "AQI readings.\n\n"
            "Times are ranked by average AQI. If two windows have "
            "the same average, we prefer the one with the lower "
            "worst-hour AQI, then the earlier start time."
        ),
        "city": str(city).strip(),
        "activity_date": str(selected_date),
        "activity_duration_minutes": activity_duration_minutes,
        "search_start_hour": 6,
        "search_end_hour": 18,
        "reliable_rows": int(len(reliable_rows)),
        "total_rows": int(total_rows),
        "reliable_fraction": round(
            float(reliable_fraction), 3
        ),
        "hourly_strip": hourly_strip,
        "primary_recommendation": primary,
        "alternatives": alternatives,
        "advisory": advisory,
        "preferred_window": preferred_window,
        "preferred_alternative": preferred_alternative,
        **health_metadata,
    }
