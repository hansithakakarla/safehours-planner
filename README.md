# SafeHours — Safe Outdoor Hours Planner for Schools

## Problem Statement

Schools need to schedule outdoor activities without knowing which hours have the safest air quality. SafeHours helps teachers identify suitable outdoor activity windows using historical hourly air-quality data.

**Problem statement:** NexAI Hack 2026 — PS 3.1, Track 3: Sustainable Industry & Energy Intelligence.

## Our Solution

SafeHours analyses hourly AQI readings for a selected city and date, then recommends the best available window for an outdoor activity between 6:00 AM and 6:00 PM.

The planner uses CPCB AQI bands to explain air-quality conditions. When the data is insufficient or unreliable, it should return “No advice” rather than make an unsupported recommendation.

The application uses historical data, not live measurements or future AQI predictions. The dataset covers 2015–2020.

## Current Features

- [x] Date-specific recommendation logic implemented.
- [x] CPCB AQI band classification implemented.
- [x] Recommendation ranking based on mean AQI, with worst-hour AQI and start time as tie-breakers.
- [x] Evaluation script checks recommendation ranking, daytime bounds, activity duration, AQI bands, and hourly-strip structure.
- [ ] Data-quality checks verified for missing, stale, and stuck readings.
- [ ] Hour-by-hour AQI strip coloured by AQI band.
- [ ] Teacher-friendly advisory paragraph.
- [ ] Deployed application and public URL.

*Update this checklist as features are implemented and tested. Do not mark a feature complete until it has been verified.*

## How It Works

1. Load hourly air-quality records from the dataset.
2. Select the city and date requested by the user.
3. assess the quality and availability of the selected day's hourly readings.
4. Generate candidate activity windows within 6 AM–6 PM.
5. Rank eligible windows using their AQI readings and select the best one.
6. Return a recommendation with its AQI band and explanation, or “No advice” if reliability requirements are not met.

## Technology Stack

- Python
- Pandas
- [Streamlit / chosen web framework]
- [Plotly / chosen visualisation library]

## Dataset

**Air Quality Data in India (2015–2020)** — Kaggle.

The dataset contains historical air-quality records originally sourced from the Central Pollution Control Board (CPCB). The project uses `city_hour.csv`.

Dataset source: [Add the Kaggle dataset URL]

Licence: [Verify and state the licence shown on the dataset page.]

AQI classification: CPCB National Air Quality Index bands. [Add an official CPCB source URL.]

Because the dataset ends in 2020, recommendations are based on historical replay data and must not be interpreted as current air-quality conditions.

## Setup and Execution

1. Clone this repository.
2. Create and activate a Python virtual environment.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Place the downloaded `city_hour.csv` in the expected data directory.
5. Run the data-quality checks and recommendation evaluation:

   ```bash
   python data_quality.py
   python evaluate_recommendation.py
   ```

6. Run the application:

   ```bash
   streamlit run app.py
   ```

   Replace the final command with the actual entry point and framework used by the project.

## Evaluation

A date-specific evaluation was run for Chennai on 15 June 2018, for a 60-minute activity.

- Recommendation: 10:00–11:00 AM
- Mean AQI: 92
- CPCB band: Satisfactory
- Candidate windows with reliable data: 12
- Evaluator checks: all passed for this test case

These results validate the tested recommendation logic only. They do not establish performance across all cities and dates or prove that all data-quality failure cases are handled correctly.

## Architecture

Dataset → Data-quality checks → City/date filtering → Candidate window ranking → Recommendation and AQI explanation → Web interface

## Team

- Member 1 — Aaditi Potey, responsible for data cleaning and processing
- Member 2 — Alkha Susan, responsible for recommendation logic and backend
- Member 3 — Hansitha Kakarla, responsible for UI integration

## Development Log

See [DEV_LOG.md](DEV_LOG.md) for development decisions, experiments, test results, and AI-tool assistance.

## Demo and Deployment

- Live application: [Add public URL when deployed]
- Demo video: [Add URL]

### Render Deployment

Deploy the React frontend as a Static Site and the FastAPI backend as a separate Web Service.

**Frontend Static Site**

- Root directory: `frontend`
- Build command: `npm install && npm run build`
- Publish directory: `dist`
- Environment variable: `VITE_API_URL=https://<your-api-service>.onrender.com`

**Backend Web Service**

- Root directory: repository root
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Environment variable: `FRONTEND_ORIGINS=https://<your-frontend-site>.onrender.com`

`VITE_API_URL` is embedded into the frontend at build time, so redeploy the Static Site after changing it. Do not use `127.0.0.1` for the deployed frontend; that address points to each visitor's own computer. `FRONTEND_ORIGINS` accepts comma-separated browser origins and should contain the exact frontend origin, without a path.
