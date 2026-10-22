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
    Check hourly AQI data and add:
      - reliable: True/False
      - quality_reason: explanation

    Detects missing/invalid AQI, missing hourly timestamps within each city's
    observed range, duplicate city-hour records, optional stale readings, and
    suspicious runs of identical AQI values.

    Leave reference_time=None for historical replay. Historical dates should
    not be marked stale just because they are old today.
    """
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]

    lookup = {str(col).lower(): col for col in df.columns}
    rename = {}
    for required_col in ["City", "Datetime", "AQI"]:
        if required_col.lower() not in lookup:
            raise ValueError(
                f"Missing required column '{required_col}'. "
                f"Found columns: {list(df.columns)}"
            )
        original_col = lookup[required_col.lower()]
        if original_col != required_col:
            rename[original_col] = required_col
    df = df.rename(columns=rename)

    df["City"] = df["City"].astype("string").str.strip()
    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
    df["AQI"] = pd.to_numeric(df["AQI"], errors="coerce")

    # Remember which rows are inserted to represent missing timestamps.
    df["_inserted_missing_hour"] = False
    inserted_rows = []

    # Add a placeholder for each absent hour between the first and last
    # observed hour for each city. Never copy/fill an earlier AQI into it.
    for city, city_rows in df.groupby("City", dropna=False, sort=False):
        valid_times = city_rows["Datetime"].dropna()
        if valid_times.empty:
            continue

        expected_hours = pd.date_range(
            start=valid_times.min().floor("h"),
            end=valid_times.max().floor("h"),
            freq="h",
        )
        actual_hours = pd.DatetimeIndex(valid_times.dt.floor("h").unique())

        for missing_hour in expected_hours.difference(actual_hours):
            row = {column: pd.NA for column in df.columns}
            row["City"] = city
            row["Datetime"] = missing_hour
            row["AQI"] = float("nan")
            row["_inserted_missing_hour"] = True
            inserted_rows.append(row)

    if inserted_rows:
        df = pd.concat(
            [df, pd.DataFrame(inserted_rows, columns=df.columns)],
            ignore_index=True,
        )

    # Initialise reasons only after adding all placeholder rows.
    df = df.reset_index(drop=True)
    reasons = {idx: [] for idx in df.index}

    # 1. Missing/invalid values and inserted missing-hour placeholders.
    for idx, row in df.iterrows():
        if pd.isna(row["City"]) or not str(row["City"]).strip():
            reasons[idx].append("Missing city")

        if pd.isna(row["Datetime"]):
            reasons[idx].append("Invalid or missing timestamp")

        if bool(row["_inserted_missing_hour"]):
            reasons[idx].append("Missing hourly timestamp")

        if pd.isna(row["AQI"]):
            reasons[idx].append("Missing or invalid AQI")
        elif not 0 <= row["AQI"] <= 500:
            reasons[idx].append("AQI outside the valid 0–500 range")

    # 2. Duplicate city-hour records (all duplicates are marked unreliable).
    valid_timestamp_mask = df["Datetime"].notna()
    duplicate_keys = pd.DataFrame({
        "City": df["City"],
        "hour": df["Datetime"].dt.floor("h"),
    })
    duplicate_mask = (
        valid_timestamp_mask
        & duplicate_keys.duplicated(
            subset=["City", "hour"], keep=False
        )
    )
    for idx in df.index[duplicate_mask]:
        reasons[idx].append("Duplicate city-hour timestamp")

    # 3. Optional freshness check for live/current data.
    if reference_time is not None:
        reference_time = pd.Timestamp(reference_time)
        if reference_time.tzinfo is not None:
            reference_time = reference_time.tz_localize(None)
        if max_age_hours < 0:
            raise ValueError("max_age_hours cannot be negative")

        for idx, timestamp in df["Datetime"].items():
            if pd.isna(timestamp):
                continue
            age_hours = (reference_time - timestamp).total_seconds() / 3600
            if age_hours > max_age_hours:
                reasons[idx].append("Stale reading")
            elif age_hours < 0:
                reasons[idx].append("Timestamp is in the future")

    # 4. Detect runs of identical AQI over consecutive hourly timestamps.
    if stuck_threshold < 2:
        raise ValueError("stuck_threshold must be at least 2")

    for _, city_rows in df.groupby("City", dropna=False, sort=False):
        city_rows = city_rows.sort_values(
            "Datetime", kind="stable", na_position="last"
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
            valid = (
                pd.notna(timestamp)
                and pd.notna(aqi)
                and 0 <= aqi <= 500
            )
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

    df["quality_reason"] = [
        "; ".join(reasons[idx]) if reasons[idx] else "OK"
        for idx in df.index
    ]
    df["reliable"] = df["quality_reason"].eq("OK")
    df = df.drop(columns=["_inserted_missing_hour"])

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
    """Load city_hour.csv, optionally filter cities, and check data quality."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Cannot find {csv_path}. "
            "Check that city_hour.csv is inside the data folder."
        )

    df = pd.read_csv(csv_path)
    df.columns = [str(col).strip() for col in df.columns]
    lookup = {str(col).lower(): col for col in df.columns}
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

    df = df[city_values.str.casefold().isin(requested)].copy()
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
        df[["City", "Datetime", "AQI", "reliable", "quality_reason"]]
        .head(15).to_string(index=False)
    )
