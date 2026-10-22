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

- FastAPI and Pydantic for the API
- Pandas for dataset loading and processing
- React and Vite for the frontend

## Dataset

**Air Quality Data in India (2015–2020)** — Kaggle.

The dataset contains historical air-quality records originally sourced from the Central Pollution Control Board (CPCB). The project uses `city_hour.csv`.

Dataset source: [Add the Kaggle dataset URL]

Licence: [Verify and state the licence shown on the dataset page.]

AQI classification: CPCB National Air Quality Index bands. [Add an official CPCB source URL.]

Because the dataset ends in 2020, recommendations are based on historical replay data and must not be interpreted as current air-quality conditions.

## Local Setup and Execution

1. Install the Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Prepare the small dataset used by the API from the full Kaggle `city_hour.csv`:

   ```bash
   python prepare_data.py path/to/full/city_hour.csv
   ```

   This writes `data/city_hour.csv`, containing only Bengaluru, Chennai, Delhi, and the `City`, `Datetime`, and `AQI` columns. Alternatively, set `DATA_URL` on the API to a publicly accessible copy of the dataset.

3. Start the API in one terminal:

   ```bash
   uvicorn api:app --reload
   ```

4. In another terminal, install and start the frontend:

   ```bash
   cd frontend
   npm ci
   npm run dev
   ```

   The Vite development server uses `http://127.0.0.1:8000` for the API by default. Set `VITE_API_URL` if the API is running elsewhere.

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

**1. Add the dataset (one time).** Render can only use files that are in the repo. Make the small 3-city file and commit it:

```bash
python prepare_data.py path/to/full/city_hour.csv   # writes data/city_hour.csv
git add data/city_hour.csv
```

`.gitignore` allows `data/city_hour.csv` but still ignores other CSVs. As an alternative, host the CSV somewhere public and set a `DATA_URL` environment variable on the API service; it is downloaded on first request.

**2. Deploy with the Blueprint (recommended).** In Render, go to **New + → Blueprint**, pick this repo and click **Apply**. `render.yaml` creates both services and wires their URLs together automatically:

- `safehours-api`: Python web service (FastAPI, `uvicorn api:app`), health check `/api/health`
- `safehours-web`: static site built from `frontend/` (`npm ci && npm run build`, publish `dist`)

**Manual setup (if you don't use the Blueprint).**

Backend Web Service: root directory blank, build `pip install -r requirements.txt`, start `uvicorn api:app --host 0.0.0.0 --port $PORT`, env vars `PYTHON_VERSION=3.12.8` and `FRONTEND_ORIGINS=https://<your-frontend>.onrender.com`.

Frontend Static Site: root directory `frontend`, build `npm ci && npm run build`, publish directory `dist`, env var `VITE_API_URL=https://<your-api>.onrender.com`.

`VITE_API_URL` is embedded at build time, so redeploy the static site after changing it. Any `https://safehours*.onrender.com` origin is accepted by the API's CORS settings, plus anything listed in `FRONTEND_ORIGINS`.

On the free plan the API sleeps after ~15 minutes idle; open `/api/health` once before a demo to wake it.
