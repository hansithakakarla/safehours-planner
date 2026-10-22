"""
Evaluate SafeHours' date-specific recommendation behavior.

This evaluator tests the current product requirement:
- Inputs: city, a date present in the historical dataset, activity duration.
- Search interval: 06:00 to 18:00.
- Ranking: the recommendation should be the lowest-mean-AQI eligible window
  among windows with reliable readings for every hour.
- Evaluation: compare the returned primary window with all eligible windows
  on the selected date; verify the primary is optimal and the response structure
  and CPCB AQI bands are consistent.

Important:
This tests historical recorded data for the selected date. It does not measure
future forecasting performance. The recommendation module must be named
recommendation.py and expose generate_recommendation().
"""

import argparse
import pandas as pd

from data_quality import load_and_check_data
from recommendation import generate_recommendation, cpcb_aqi_band


def _hourly_reliable_aqi(df, city, activity_date):
    data = df.copy()
    data["City"] = data["City"].astype("string").str.strip()
    data["Datetime"] = pd.to_datetime(data["Datetime"], errors="coerce")
    data["AQI"] = pd.to_numeric(data["AQI"], errors="coerce")

    selected_date = pd.Timestamp(activity_date).date()
    data = data[
        data["City"].str.casefold() == str(city).strip().casefold()
    ].copy()
    data = data[data["Datetime"].notna()].copy()
    data = data[data["Datetime"].dt.date == selected_date].copy()
    data = data[
        (data["Datetime"].dt.hour >= 6)
        & (data["Datetime"].dt.hour < 18)
    ].copy()

    reliable_flag = (
        data["reliable"].fillna(False).astype(bool)
        & data["AQI"].notna()
        & data["AQI"].between(0, 500)
    )
    data = data.loc[reliable_flag].copy()
    data["hour"] = data["Datetime"].dt.hour

    # Use the same aggregation convention as recommendation.py.
    return data.groupby("hour")["AQI"].median()


def evaluate_date(df, city, activity_date, activity_duration_minutes=60):
    """Return (summary dictionary, candidate-window DataFrame)."""
    result = generate_recommendation(
        df,
        city=city,
        activity_date=activity_date,
        activity_duration_minutes=activity_duration_minutes,
    )

    hourly = _hourly_reliable_aqi(df, city, activity_date)
    duration_hours = activity_duration_minutes // 60
    candidates = []

    for start_hour in range(6, 18 - duration_hours + 1):
        end_hour = start_hour + duration_hours
        hours = list(range(start_hour, end_hour))

        if not all(hour in hourly.index for hour in hours):
            continue

        values = hourly.loc[hours].astype(float)
        mean_aqi = float(values.mean())
        worst_aqi = float(values.max())
        candidates.append({
            "start_hour": start_hour,
            "end_hour": end_hour,
            "window": (
                f"{pd.Timestamp('2000-01-01').replace(hour=start_hour).strftime('%I %p').lstrip('0')}"
                f"–{pd.Timestamp('2000-01-01').replace(hour=end_hour).strftime('%I %p').lstrip('0')}"
            ),
            "mean_aqi": round(mean_aqi, 1),
            "worst_hour_aqi": round(worst_aqi, 1),
            "aqi_band": cpcb_aqi_band(mean_aqi)["band"],
        })

    candidates_df = pd.DataFrame(candidates)
    if not candidates_df.empty:
        candidates_df = candidates_df.sort_values(
            ["mean_aqi", "worst_hour_aqi", "start_hour"],
            ascending=True,
            kind="stable",
        ).reset_index(drop=True)

    summary = {
        "city": city,
        "activity_date": str(pd.Timestamp(activity_date).date()),
        "duration_minutes": activity_duration_minutes,
        "status": result.get("status"),
        "message": result.get("message"),
        "candidate_windows_with_reliable_data": len(candidates_df),
        "primary_window": None,
        "primary_mean_aqi": None,
        "primary_band": None,
        "primary_is_best_eligible_window": None,
        "hourly_strip_hours": len(result.get("hourly_strip", [])),
        "hourly_strip_has_12_slots": len(result.get("hourly_strip", [])) == 12,
        "all_hourly_slots_between_6_and_18": all(
            6 <= slot.get("hour", -1) < 18
            for slot in result.get("hourly_strip", [])
        ),
        "cpcb_band_consistent": None,
        "alternatives_within_daytime": None,
        "checks_passed": [],
        "checks_failed": [],
    }

    if result.get("status") != "recommendation_available":
        # A no-advice response is valid when there are no candidate windows
        # or the module refuses due to its quality thresholds.
        summary["checks_passed"].append("No-advice response has no primary recommendation")
        if result.get("primary_recommendation") is not None:
            summary["checks_failed"].append(
                "No-advice response unexpectedly includes a primary recommendation"
            )
        if result.get("primary_recommendation") is None:
            summary["checks_passed"].append("Primary recommendation is None for no-advice")
        return summary, candidates_df

    primary = result.get("primary_recommendation") or {}
    start_hour = primary.get("start_hour")
    end_hour = primary.get("end_hour")
    summary["primary_window"] = f"{start_hour}:00–{end_hour}:00"
    summary["primary_mean_aqi"] = primary.get("mean_aqi")
    summary["primary_band"] = primary.get("aqi_band")

    # Check primary window boundaries and duration.
    if (
        isinstance(start_hour, int)
        and isinstance(end_hour, int)
        and 6 <= start_hour < end_hour <= 18
        and (end_hour - start_hour) * 60 == activity_duration_minutes
    ):
        summary["checks_passed"].append("Primary window is within 06:00–18:00 and has requested duration")
    else:
        summary["checks_failed"].append("Primary window violates daytime bounds or requested duration")

    # Verify the recommended window is the best among observed eligible windows.
    if candidates_df.empty:
        summary["primary_is_best_eligible_window"] = False
        summary["checks_failed"].append(
            "Recommendation returned, but evaluator found no complete reliable candidate windows"
        )
    else:
        expected = candidates_df.iloc[0]
        is_best = (
            start_hour == int(expected["start_hour"])
            and end_hour == int(expected["end_hour"])
            and abs(float(primary.get("mean_aqi", float("nan"))) - float(expected["mean_aqi"])) < 0.11
        )
        summary["primary_is_best_eligible_window"] = bool(is_best)
        if is_best:
            summary["checks_passed"].append("Primary recommendation is the best eligible window by ranking")
        else:
            summary["checks_failed"].append("Primary recommendation does not match the best eligible window")

    expected_band = cpcb_aqi_band(primary.get("mean_aqi"))
    band_ok = primary.get("aqi_band") == expected_band["band"]
    summary["cpcb_band_consistent"] = bool(band_ok)
    if band_ok:
        summary["checks_passed"].append("Primary CPCB AQI band matches its mean AQI")
    else:
        summary["checks_failed"].append("Primary CPCB AQI band does not match its mean AQI")

    # Alternatives must also be valid daytime windows of the requested duration.
    alternatives = result.get("alternatives", [])
    alternatives_ok = all(
        isinstance(w.get("start_hour"), int)
        and isinstance(w.get("end_hour"), int)
        and 6 <= w["start_hour"] < w["end_hour"] <= 18
        and (w["end_hour"] - w["start_hour"]) * 60 == activity_duration_minutes
        for w in alternatives
    )
    summary["alternatives_within_daytime"] = bool(alternatives_ok)
    if alternatives_ok:
        summary["checks_passed"].append("All alternatives respect daytime bounds and duration")
    else:
        summary["checks_failed"].append("An alternative violates daytime bounds or duration")

    if summary["hourly_strip_has_12_slots"] and summary["all_hourly_slots_between_6_and_18"]:
        summary["checks_passed"].append("Hourly strip has 12 slots covering 06:00–18:00")
    else:
        summary["checks_failed"].append("Hourly strip does not correctly cover 06:00–18:00")

    return summary, candidates_df


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate one city/date/duration for SafeHours."
    )
    parser.add_argument("--city", default="Chennai", help="City name (default: Chennai)")
    parser.add_argument(
        "--date",
        default="2018-06-15",
        help="Historical date to test (default: 2018-06-15)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Activity duration in whole hours as minutes, e.g. 60 or 120 (default: 60)",
    )
    args = parser.parse_args()

    df = load_and_check_data(cities=[args.city])
    summary, candidates = evaluate_date(
        df,
        city=args.city,
        activity_date=args.date,
        activity_duration_minutes=args.duration,
    )

    print("\nSafeHours date-specific evaluation")
    print("=" * 36)
    for key in (
        "city",
        "activity_date",
        "duration_minutes",
        "status",
        "message",
        "candidate_windows_with_reliable_data",
        "primary_window",
        "primary_mean_aqi",
        "primary_band",
        "primary_is_best_eligible_window",
        "hourly_strip_hours",
        "hourly_strip_has_12_slots",
        "all_hourly_slots_between_6_and_18",
        "cpcb_band_consistent",
        "alternatives_within_daytime",
    ):
        print(f"{key}: {summary.get(key)}")

    print("\nChecks passed:")
    for item in summary["checks_passed"]:
        print(f"  PASS: {item}")

    print("\nChecks failed:")
    if summary["checks_failed"]:
        for item in summary["checks_failed"]:
            print(f"  FAIL: {item}")
    else:
        print("  None")

    if not candidates.empty:
        print("\nBest eligible windows for this date:")
        print(candidates.head(10).to_string(index=False))

    # Save machine-readable results for later inspection.
    pd.DataFrame([summary]).to_csv("date_evaluation_summary.csv", index=False)
    candidates.to_csv("date_evaluation_candidates.csv", index=False)
    print("\nSaved date_evaluation_summary.csv and date_evaluation_candidates.csv")


if __name__ == "__main__":
    main()
