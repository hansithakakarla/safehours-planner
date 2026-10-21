# SafeHours — Data Quality Report

## Dataset

- Source: Air Quality Data in India (2015–2020), Kaggle
- File used: `city_hour.csv`
- Selected cities: Bengaluru, Chennai and Delhi
- Rows per city: 48,192
- Date range: January 2015 to July 2020

## Missing AQI values

| City | Missing AQI records |
|---|---:|
| Bengaluru | 2,695 |
| Chennai | 3,543 |
| Delhi | 498 |
| **Total** | **6,736** |

## Reliability results

| City | Reliable records | Reliability rate |
|---|---:|---:|
| Bengaluru | 41,223 | 85.54% |
| Chennai | 40,916 | 84.90% |
| Delhi | 46,974 | 97.47% |

These reliability rates are based on the current implementation's missing-value and stuck-reading checks. They are not official sensor-quality ratings.

## Quality checks implemented

1. Missing or invalid AQI values
2. Invalid timestamps
3. Duplicate city-hour timestamps
4. Consecutive identical AQI values as a possible stuck-reading indicator
5. Optional stale-reading checks when a reference time is provided

## Limitations and safety

- Identical AQI values do not prove that a sensor is faulty.
- Historical data must not be presented as live air quality.
- Missing hours must not be filled with invented AQI values.
- The planner must reject any activity window that lacks the required hourly observations or contains unreliable readings.
- AQI reliability alone does not establish that outdoor activity is medically safe.

## Next steps

- Integrate the data-quality function with the recommendation engine.
- Test that missing or unreliable hours cause the planner to refuse advice.
- Display data-quality warnings in the application.
