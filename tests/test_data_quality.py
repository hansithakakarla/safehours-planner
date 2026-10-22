
import pandas as pd

from data_quality import check_data_quality


def make_df(rows):
    return pd.DataFrame(
        rows,
        columns=["City", "Datetime", "AQI"],
    )


def test_missing_aqi_is_unreliable():
    df = make_df([
        ["Delhi", "2020-01-01 06:00", None],
    ])

    result = check_data_quality(df)

    assert not result.loc[0, "reliable"]
    assert "Missing or invalid AQI" in result.loc[0, "quality_reason"]


def test_six_identical_hourly_readings_are_flagged():
    df = make_df([
        ["Delhi", f"2020-01-01 {hour:02d}:00", 100]
        for hour in range(6, 12)
    ])

    result = check_data_quality(df, stuck_threshold=6)

    assert not result["reliable"].any()
    assert result["quality_reason"].str.contains(
        "Potentially stuck AQI"
    ).all()


def test_short_repeated_run_is_not_flagged():
    df = make_df([
        ["Delhi", "2020-01-01 06:00", 100],
        ["Delhi", "2020-01-01 07:00", 100],
        ["Delhi", "2020-01-01 08:00", 100],
    ])

    result = check_data_quality(df, stuck_threshold=6)

    assert result["reliable"].all()


def test_time_gap_breaks_stuck_run():
    df = make_df([
        ["Delhi", "2020-01-01 06:00", 100],
        ["Delhi", "2020-01-01 07:00", 100],
        ["Delhi", "2020-01-01 09:00", 100],
        ["Delhi", "2020-01-01 10:00", 100],
    ])

    result = check_data_quality(df, stuck_threshold=4)

    # The original readings should remain reliable because
    # the repeated readings are separated by a missing hour.
    original_times = pd.to_datetime(df["Datetime"])
    checked_original = result[
        result["Datetime"].isin(original_times)
    ]

    assert len(checked_original) == 4
    assert checked_original["reliable"].all()

    # The missing 08:00 hour should be flagged as unreliable.
    missing_hour = result[
        result["Datetime"] == pd.Timestamp("2020-01-01 08:00")
    ]

    assert len(missing_hour) == 1
    assert not missing_hour.iloc[0]["reliable"]


def test_stale_check_is_optional():
    df = make_df([
        ["Delhi", "2020-01-01 06:00", 100],
    ])

    historical = check_data_quality(df)

    checked_for_freshness = check_data_quality(
        df,
        reference_time="2020-01-01 10:00",
        max_age_hours=3,
    )

    assert historical.loc[0, "reliable"]
    assert not checked_for_freshness.loc[0, "reliable"]
    assert "Stale reading" in checked_for_freshness.loc[
        0, "quality_reason"
    ]


def test_negative_aqi_is_unreliable():
    df = make_df([
        ["Delhi", "2020-01-01 06:00", -1],
    ])

    result = check_data_quality(df)

    assert not result.loc[0, "reliable"]
    assert "outside the valid" in result.loc[0, "quality_reason"]



def test_duplicate_city_hour_is_flagged():
    df = make_df([
        ["Delhi", "2020-01-01 06:00", 100],
        ["Delhi", "2020-01-01 06:00", 101],
    ])

    result = check_data_quality(df)

    assert not result["reliable"].any()
    assert result["quality_reason"].str.contains(
        "Duplicate city-hour"
    ).all()
