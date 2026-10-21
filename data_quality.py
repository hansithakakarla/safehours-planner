
from pathlib import Path

import pandas as pd


DEFAULT_CITIES = ["Delhi", "Bengaluru", "Chennai"]


def check_data_quality(
    df,
    stuck_threshold=6,
    reference_time=None,
    max_age_hours=3,
):
    """
    Clean and check AQI data.

    Required input columns:
        City, Datetime, AQI

    Adds:
        reliable: True/False
        quality_reason: explanation of the result

    reference_time:
        Leave None for historical dataset replay.
        Supply a timestamp for freshness checks on current/live data.
    """
    df = df.copy()

    # Standardise column names, ignoring case and surrounding spaces.
    df.columns = [str(col).strip() for col in df.columns]
    lookup = {col.lower(): col for col in df.columns}

    required = ["City", "Datetime", "AQI"]
    rename = {}

    for col in required:
        if col.lower() not in lookup:
            raise ValueError(
                f"Missing required column '{col}'. "
                f"Found columns: {list(df.columns)}"
            )

        original_name = lookup[col.lower()]
        if original_name != col:
            rename[original_name] = col

    df = df.rename(columns=rename)

    # Clean values.
    df["City"] = df["City"].astype("string").str.strip()
    df["Datetime"] = pd.to_datetime(
        df["Datetime"], errors="coerce"
    )
    df["AQI"] = pd.to_numeric(df["AQI"], errors="coerce")

    reasons = {idx: [] for idx in df.index}

    # 1. Missing or invalid values.
    for idx, row in df.iterrows():
        if pd.isna(row["City"]) or not str(row["City"]).strip():
            reasons[idx].append("Missing city")

        if pd.isna(row["Datetime"]):
            reasons[idx].append("Invalid or missing timestamp")

        if pd.isna(row["AQI"]):
            reasons[idx].append("Missing or invalid AQI")
        elif row["AQI"] < 0:
            reasons[idx].append("Invalid negative AQI")

    # 2. Duplicate city-hour records.
    duplicate_mask = df.duplicated(
        subset=["City", "Datetime"], keep=False
    )

    for idx in df.index[duplicate_mask]:
        reasons[idx].append("Duplicate city-hour timestamp")

    # 3. Optional freshness check.
    # Do not enable this for historical replay data.
    if reference_time is not None:
        reference_time = pd.Timestamp(reference_time)

        # Make timezone handling consistent with this dataset's timestamps.
        if reference_time.tzinfo is not None:
            reference_time = reference_time.tz_localize(None)

        if max_age_hours < 0:
            raise ValueError("max_age_hours cannot be negative")

        for idx, timestamp in df["Datetime"].items():
            if pd.isna(timestamp):
                continue

            age_hours = (
                reference_time - timestamp
            ).total_seconds() / 3600

            if age_hours > max_age_hours:
                reasons[idx].append("Stale reading")
            elif age_hours < 0:
                reasons[idx].append("Timestamp is in the future")

    # 4. Detect consecutive identical hourly AQI readings.
    # A missing hour or invalid reading breaks the sequence.
    if stuck_threshold < 2:
        raise ValueError("stuck_threshold must be at least 2")

    for _, city_rows in df.groupby("City", dropna=False):
        city_rows = city_rows.sort_values(
            "Datetime", kind="stable"
        )

        run_indices = []
        previous_time = None
        previous_aqi = None

        def mark_stuck(indices):
            if len(indices) >= stuck_threshold:
                for row_idx in indices:
                    reasons[row_idx].append(
                        "Potentially stuck AQI: unchanged for "
                        f"{stuck_threshold}+ consecutive hourly readings"
                    )

        for idx, row in city_rows.iterrows():
            timestamp = row["Datetime"]
            aqi = row["AQI"]

            valid = pd.notna(timestamp) and pd.notna(aqi)

            consecutive_same = (
                valid
                and previous_time is not None
                and timestamp - previous_time == pd.Timedelta(hours=1)
                and aqi == previous_aqi
            )

            if not valid:
                mark_stuck(run_indices)
                run_indices = []
                previous_time = None
                previous_aqi = None
                continue

            if not consecutive_same:
                mark_stuck(run_indices)
                run_indices = [idx]
            else:
                run_indices.append(idx)

            previous_time = timestamp
            previous_aqi = aqi

        mark_stuck(run_indices)

    # 5. Add the output columns.
    df["quality_reason"] = [
        "; ".join(reasons[idx]) if reasons[idx] else "OK"
        for idx in df.index
    ]

    df["reliable"] = df["quality_reason"].eq("OK")

    return df.sort_values(
        ["City", "Datetime"],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)


def load_and_check_data(
    csv_path="data/city_hour.csv",
    cities=None,
    stuck_threshold=6,
    reference_time=None,
    max_age_hours=3,
):
    """
    Load the Kaggle CSV, optionally filter cities, and check quality.

    Example:
        df = load_and_check_data()
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Cannot find {csv_path}. "
            "Check that city_hour.csv is inside the data folder."
        )

    df = pd.read_csv(csv_path)

    # Standardise column names for filtering.
    df.columns = [str(col).strip() for col in df.columns]
    lookup = {col.lower(): col for col in df.columns}

    if "city" not in lookup:
        raise ValueError(
            "Could not find a City column. "
            f"Available columns: {list(df.columns)}"
        )

    city_column = lookup["city"]

    if cities is None:
        cities = DEFAULT_CITIES

    requested = {str(city).strip().casefold() for city in cities}

    city_values = df[city_column].astype("string").str.strip()
    available = set(city_values.dropna().str.casefold())

    missing_cities = requested - available

    if missing_cities:
        print(
            "Warning: these requested cities were not found:",
            sorted(missing_cities),
        )

    df = df[
        city_values.str.casefold().isin(requested)
    ].copy()

    if df.empty:
        raise ValueError(
            "No rows found for the selected cities. "
            "Check the city names in the dataset."
        )

    return check_data_quality(
        df,
        stuck_threshold=stuck_threshold,
        reference_time=reference_time,
        max_age_hours=max_age_hours,
    )


if __name__ == "__main__":
    # Run this file directly to inspect the dataset.
    df = load_and_check_data()

    print("\nRows per city:")
    print(df.groupby("City").size())

    print("\nDate range:")
    print(df["Datetime"].min(), "to", df["Datetime"].max())

    print("\nReliability summary:")
    print(
        df.groupby("City")["reliable"].agg(
            total_rows="count",
            reliable_rows="sum",
            reliable_fraction="mean",
        )
    )

    print("\nQuality reasons:")
    print(df["quality_reason"].value_counts().head(10))

    print("\nSample rows:")
    print(
        df[
            ["City", "Datetime", "AQI", "reliable", "quality_reason"]
        ].head(15).to_string(index=False)
    )
