
from data_quality import load_and_check_data
from recommendation import generate_recommendation


df = load_and_check_data(cities=["Chennai"])

result = generate_recommendation(
    df,
    city="Chennai",
    start_date="2018-01-01",
    end_date="2019-12-31",
    activity_duration_hours=2,
)

print("\nStatus:", result["status"])
print(result["message"])

if result["status"] == "recommendation_available":
    primary = result["primary_recommendation"]

    print("\nPRIMARY RECOMMENDATION")
    print(f'{primary["start"]} – {primary["end"]}')
    print(f'AQI score: {primary["score"]}')

    print("\nALTERNATIVES")
    for window in result["alternatives"]:
        print(
            f'{window["start"]} – {window["end"]} | '
            f'AQI score: {window["score"]}'
        )

    print("\nData coverage:")
    print("Reliable rows:", result["reliable_rows"])
    print("Total rows:", result["total_rows"])
    print("Reliable fraction:", result["reliable_fraction"])

print("\nHourly statistics:")
print(result["hourly_scores"].to_string(index=False))
