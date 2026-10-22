
import pandas as pd

from data_quality import load_and_check_data
from recommendation import generate_recommendation


def evaluate_hit_rate(df, city, min_training_days=30):
    data = df.copy()
    data["Datetime"] = pd.to_datetime(data["Datetime"])

    data = data[
        data["City"].astype("string").str.strip().str.casefold()
        == city.strip().casefold()
    ].copy()

    data = data[data["reliable"].fillna(False)].copy()
    data = data.dropna(subset=["Datetime", "AQI"])
    data["day"] = data["Datetime"].dt.date
    data["hour"] = data["Datetime"].dt.hour

    days = sorted(data["day"].unique())
    results = []

    for day in days:
        training = data[data["day"] < day]

        # Avoid evaluating before sufficient history is available.
        if training["day"].nunique() < min_training_days:
            continue

        today = data[data["day"] == day]

        if today.empty:
            continue

        # Actual ground truth: all hour(s) tied for lowest
        # reliable observed AQI on the test day.
        lowest_aqi = today["AQI"].min()
        lowest_hours = set(
            today.loc[today["AQI"] == lowest_aqi, "hour"].tolist()
        )

        # Generate recommendations using ONLY earlier days.
        recommendation = generate_recommendation(
            training,
            city=city,
        )

        if recommendation["status"] != "recommendation_available":
            results.append({
                "date": str(day),
                "lowest_aqi": lowest_aqi,
                "lowest_hours": sorted(lowest_hours),
                "recommended_hours": [],
                "hit": None,
                "status": "No recommendation",
            })
            continue

        primary = recommendation["primary_recommendation"]

        recommended_hours = set(
            range(
                primary["start_hour"],
                primary["end_hour"]
            )
        )

        hit = bool(lowest_hours & recommended_hours)

        results.append({
            "date": str(day),
            "lowest_aqi": lowest_aqi,
            "lowest_hours": sorted(lowest_hours),
            "recommended_hours": sorted(recommended_hours),
            "hit": hit,
            "status": "Evaluated",
        })

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
    total = len(evaluated)
    hit_rate = 100 * hits / total

    print(f"\nCity: {city}")
    print(f"Days with recommendations evaluated: {total}")
    print(f"Days matching the daily minimum: {hits}")
    print(f"Hit rate: {hit_rate:.2f}%")
    print(
        "Days with no recommendation:",
        int((results_df["status"] == "No recommendation").sum()),
    )

    print("\nDaily results:")
    print(results_df.to_string(index=False))

    return results_df


if __name__ == "__main__":
    df = load_and_check_data(cities=["Chennai"])

    results = evaluate_hit_rate(df, "Chennai")

    if not results.empty:
        results.to_csv("evaluation_results.csv", index=False)
        print("\nSaved results to evaluation_results.csv")
