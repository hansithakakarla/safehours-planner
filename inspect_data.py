
import pandas as pd
from data_quality import load_and_check_data

df = load_and_check_data("data/city_hour.csv")

# 1. Missing AQI values by city and year
df["Year"] = df["Datetime"].dt.year

print("\nMissing AQI by city and year:")
print(
    df.groupby(["City", "Year"])["AQI"]
    .apply(lambda values: values.isna().sum())
)

# 2. First valid AQI observation per city
print("\nFirst valid AQI record per city:")

for city, group in df.groupby("City"):
    valid = group.dropna(subset=["AQI"]).sort_values("Datetime")

    if valid.empty:
        print(f"{city}: No valid AQI readings")
    else:
        first = valid.iloc[0]
        print(
            f"{city}: {first['Datetime']} "
            f"(AQI {first['AQI']})"
        )

# 3. Missing timestamps within each city's date range
print("\nMissing hourly timestamps by city:")

for city, group in df.groupby("City"):
    timestamps = pd.DatetimeIndex(
        group["Datetime"].dropna().unique()
    ).sort_values()

    if len(timestamps) == 0:
        print(f"{city}: Cannot check; no valid timestamps")
        continue

    expected = pd.date_range(
        start=timestamps.min(),
        end=timestamps.max(),
        freq="h",
    )

    missing = expected.difference(timestamps)

    print(f"{city}: {len(missing)} missing timestamps")
