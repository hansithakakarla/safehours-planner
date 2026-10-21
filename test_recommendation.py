# checks if the code works

from data_quality import load_and_check_data
from recommendation import generate_recommendation

# Load the dataset and run Member 1's quality checks.
df = load_and_check_data(cities=["Chennai"])

# Analyse historical data for Chennai.
result = generate_recommendation(
    df,
    city="Chennai",
    start_date="2018-01-01",
    end_date="2019-12-31",
)

print("\nStatus:", result["status"])
print(result["message"])

if result["status"] == "recommendation_available":
    print("\nRecommended windows:")

    for window in result["windows"]:
        print(
            f'{window["start"]} – {window["end"]} | '
            f'Median AQI summary: '
            f'{window["average_of_hourly_medians"]}'
        )

print("\nHourly statistics:")
print(result["hourly_scores"].to_string(index=False))
