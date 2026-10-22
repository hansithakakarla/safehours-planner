import pandas as pd

from data_quality import load_and_check_data
from recommendation import generate_recommendation


def evaluate_recommendation(
    df,
    city,
    min_training_days=30,
    activity_duration_hours=2,
    allowed_start_hour=10,
    allowed_end_hour=16,
    baseline_start_hour=10,
):
    """
    Walk-forward evaluation: each test day's recommendation uses only
    reliable data from earlier days.

    Metrics:
      - Hit rate: recommended window includes at least one of the cleanest
        observed hours within the allowed activity hours.
      - Mean AQI in recommended windows vs the mean AQI across observed
        allowed activity hours.
      - Mean AQI in recommended windows vs a fixed-window baseline
        (default 10 AM to noon).

    AQI comparisons are calculated only when the relevant test-day hours
    have reliable observations. This is historical evaluation, not a
    forecast or proof that a window is safe.
    """

    data = df.copy()
    data["Datetime"] = pd.to_datetime(data["Datetime"], errors="coerce")
    data["AQI"] = pd.to_numeric(data["AQI"], errors="coerce")
    data = data[
        data["City"].astype("string").str.strip().str.casefold()
        == city.strip().casefold()
    ].copy()

    data = data[
        data["reliable"].fillna(False).astype(bool)
        & data["Datetime"].notna()
        & data["AQI"].notna()
        & data["AQI"].ge(0)
    ].copy()

    data["day"] = data["Datetime"].dt.date
    data["hour"] = data["Datetime"].dt.hour
    days = sorted(data["day"].unique())
    results = []

    baseline_end_hour = baseline_start_hour + activity_duration_hours
    if baseline_start_hour < allowed_start_hour or baseline_end_hour > allowed_end_hour:
        raise ValueError(
            "The baseline window must fit within the allowed activity hours."
        )

    for day in days:
        training = data[data["day"] < day]
        if training["day"].nunique() < min_training_days:
            continue

        today = data[data["day"] == day]
        if today.empty:
            continue

        # Hourly medians reduce the effect of duplicate readings within an hour.
        actual_hourly = today.groupby("hour")["AQI"].median()
        allowed_actual = actual_hourly[
            (actual_hourly.index >= allowed_start_hour)
            & (actual_hourly.index < allowed_end_hour)
        ]

        if allowed_actual.empty:
            continue

        # The "cleanest hour" hit target is restricted to hours the school can use.
        lowest_aqi = allowed_actual.min()
        lowest_hours = set(
            allowed_actual[allowed_actual == lowest_aqi].index.astype(int).tolist()
        )

        recommendation = generate_recommendation(
            training,
            city=city,
            activity_duration_hours=activity_duration_hours,
            allowed_start_hour=allowed_start_hour,
            allowed_end_hour=allowed_end_hour,
        )

        row = {
            "date": str(day),
            "lowest_aqi_in_allowed_hours": float(lowest_aqi),
            "lowest_hours_in_allowed_hours": sorted(lowest_hours),
            "recommended_start_hour": None,
            "recommended_end_hour": None,
            "recommended_hours": [],
            "recommended_window_aqi": None,
            "allowed_hours_mean_aqi": float(allowed_actual.mean()),
            "baseline_start_hour": baseline_start_hour,
            "baseline_end_hour": baseline_end_hour,
            "baseline_window_aqi": None,
            "hit": None,
            "recommended_better_than_allowed_mean": None,
            "recommended_better_than_baseline": None,
            "status": "No recommendation",
        }

        if recommendation["status"] != "recommendation_available":
            results.append(row)
            continue

        primary = recommendation["primary_recommendation"]
        start_hour = primary["start_hour"]
        end_hour = primary["end_hour"]
        recommended_hours = list(range(start_hour, end_hour))
        row["recommended_start_hour"] = start_hour
        row["recommended_end_hour"] = end_hour
        row["recommended_hours"] = recommended_hours
        row["hit"] = bool(set(lowest_hours) & set(recommended_hours))
        row["status"] = "Evaluated"

        # Only score the recommended window when every hour has an observed AQI.
        if all(hour in actual_hourly.index for hour in recommended_hours):
            recommended_aqi = float(actual_hourly.loc[recommended_hours].mean())
            row["recommended_window_aqi"] = recommended_aqi
            row["recommended_better_than_allowed_mean"] = (
                recommended_aqi < float(allowed_actual.mean())
            )

        baseline_hours = list(range(baseline_start_hour, baseline_end_hour))
        if all(hour in actual_hourly.index for hour in baseline_hours):
            baseline_aqi = float(actual_hourly.loc[baseline_hours].mean())
            row["baseline_window_aqi"] = baseline_aqi
            if row["recommended_window_aqi"] is not None:
                row["recommended_better_than_baseline"] = (
                    row["recommended_window_aqi"] < baseline_aqi
                )

        results.append(row)

    results_df = pd.DataFrame(results)
    if results_df.empty:
        print("No eligible test days. Check the dataset date range.")
        return results_df

    evaluated = results_df[results_df["hit"].notna()]
    if evaluated.empty:
        print("No days produced an eligible recommendation.")
        print(results_df.to_string(index=False))
        return results_df

    hits = int(evaluated["hit"].sum())
    print(f"\nCity: {city}")
    print(f"Allowed activity hours: {allowed_start_hour:02d}:00–{allowed_end_hour:02d}:00")
    print(f"Activity duration: {activity_duration_hours} hour(s)")
    print(f"Days with recommendations evaluated for hit rate: {len(evaluated)}")
    print(f"Days matching the cleanest allowed hour: {hits}")
    print(f"Hit rate: {100 * hits / len(evaluated):.2f}%")
    print(
        "Days with no recommendation:",
        int((results_df["status"] == "No recommendation").sum()),
    )

    aq = results_df.dropna(subset=["recommended_window_aqi"])
    if not aq.empty:
        print(f"\nMean AQI in recommended windows: {aq['recommended_window_aqi'].mean():.2f}")
        print(
            "Mean AQI across observed allowed activity hours on comparable days: "
            f"{aq['allowed_hours_mean_aqi'].mean():.2f}"
        )
        print(
            "Recommended window lower than allowed-hours mean: "
            f"{100 * aq['recommended_better_than_allowed_mean'].mean():.2f}% "
            f"of scored days"
        )

    baseline = results_df.dropna(
        subset=["recommended_window_aqi", "baseline_window_aqi"]
    )
    if not baseline.empty:
        print(
            f"\nFixed baseline ({baseline_start_hour:02d}:00–{baseline_end_hour:02d}:00) "
            f"mean AQI: {baseline['baseline_window_aqi'].mean():.2f}"
        )
        print(
            "Mean AQI in recommended windows on baseline-comparable days: "
            f"{baseline['recommended_window_aqi'].mean():.2f}"
        )
        print(
            "Recommended window lower AQI than fixed baseline: "
            f"{100 * baseline['recommended_better_than_baseline'].mean():.2f}% "
            "of comparable scored days"
        )

    print("\nDaily results:")
    print(results_df.to_string(index=False))
    return results_df


if __name__ == "__main__":
    df = load_and_check_data(cities=["Chennai"])

    results = evaluate_recommendation(
        df,
        "Chennai",
        activity_duration_hours=2,
        allowed_start_hour=10,
        allowed_end_hour=16,  # Change to 17 to allow activity until 5 PM.
        baseline_start_hour=10,
    )

    if not results.empty:
        results.to_csv("evaluation_results.csv", index=False)
        print("\nSaved results to evaluation_results.csv")
