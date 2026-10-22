# SafeHours — Development Log

## Project Information

- **Hackathon:** NexAI Hack 2026
- **Problem statement:** PS 3.1 — Safe Outdoor Hours Planner for Schools
- **Development period:** 21–22 October 2026
- **Team:** [Add all team members]

## 21 October 2026 — Initial Implementation and Evaluation

### Data Processing

- Worked with the Air Quality Data in India dataset, specifically `city_hour.csv`.
- Used Python and Pandas for data loading and processing.
- Worked on `data_quality.py` for loading and checking the dataset.

### Recommendation Logic

- Implemented date-specific recommendation logic in `recommendation.py`.
- The function accepts a city, activity date, and activity duration.
- Candidate windows are restricted to 6:00 AM–6:00 PM.
- Eligible windows are ranked by mean hourly AQI, then worst-hour AQI, then earliest start time.
- CPCB AQI bands are used to describe the selected window.
- The implementation includes a “no advice” outcome when its reliability requirements are not met.

### Evaluation

Test command:

```bash
python evaluate_recommendation.py
```

Test configuration:

- City: Chennai
- Date: 2018-06-15
- Activity duration: 60 minutes

Observed result:

- Status: `recommendation_available`
- Recommended window: 10:00–11:00 AM
- Mean AQI: 92
- AQI band: Satisfactory
- Eligible candidate windows: 12
- All reported evaluator checks passed.

The evaluator checked daytime bounds, activity duration, ranking, CPCB band consistency, alternatives, and the 12-slot hourly-strip structure.

### Evaluation Limitations

- The successful test covers one city, date, and activity duration.
- It does not prove that every city/date combination works correctly.
- Separate tests are still needed for missing dates, insufficient readings, stale readings, and sensors stuck at the same value.
- The dataset is historical and ends in 2020; it cannot provide current AQI conditions.

### Decisions

- Keep generated evaluation CSVs separate from source data.
- Ignore generated evaluation outputs in Git where appropriate.
- Retain the evaluation scripts and document representative test results.

### AI Assistance

- Used AI assistance to help design and review recommendation logic, evaluation checks, and documentation.

---
