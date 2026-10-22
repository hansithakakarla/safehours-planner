
from data_quality import load_and_check_data
from recommendation import generate_recommendation


def main():
    df = load_and_check_data(cities=["Chennai"])

    result = generate_recommendation(
        df,
        city="Chennai",
        activity_date="2018-01-01",
        activity_duration_minutes=120,
    )

    print("\nStatus:", result["status"])
    print(result["message"])

    if result["status"] == "recommendation_available":
        primary = result["primary_recommendation"]

        print("\nPRIMARY RECOMMENDATION")
        print(f'{primary["start"]} – {primary["end"]}')
        print(f'Mean AQI: {primary["mean_aqi"]}')
        print(f'Worst-hour AQI: {primary["worst_hour_aqi"]}')
        print(f'AQI category: {primary["aqi_band"]}')
        print(f'Reason: {primary["reason"]}')

        print("\nALTERNATIVES")
        for window in result["alternatives"]:
            print(
                f'{window["start"]} – {window["end"]} | '
                f'Mean AQI: {window["mean_aqi"]} | '
                f'Category: {window["aqi_band"]}'
            )

    print("\nData coverage:")
    print("Reliable rows:", result["reliable_rows"])
    print("Total rows:", result["total_rows"])
    print("Reliable fraction:", result["reliable_fraction"])


if __name__ == "__main__":
    main()
