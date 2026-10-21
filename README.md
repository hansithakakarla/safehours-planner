# safehours-planner
A school outdoor activity planner that recommends suitable hours using historical AQI data and data-quality checks.

# SafeHours — Safe Outdoor Hours Planner for Schools

## Problem Statement
PS 3.1 — Safe Outdoor Hours Planner for Schools
Track 3: Sustainable Industry & Energy Intelligence

## Problem
Schools need to identify suitable hours for outdoor activities
based on air quality. The application must not recommend a
time window when the supporting readings are unreliable.

## Solution
SafeHours analyses historical hourly AQI data, checks data
quality, and recommends a suitable outdoor activity window.
It refuses to recommend a window when required readings are
missing or unreliable.

## Features
- City and date selection
- Activity duration selection
- Missing-data checks
- Stale-reading checks
- Stuck-sensor detection
- CPCB AQI categories
- Recommended time window and explanation
- No-advice warning when data is unreliable
- Hourly AQI visualisation

## Dataset
Air Quality Data in India (2015–2020), Kaggle.
The application uses historical data and does not provide
live air-quality measurements.

Dataset source: [Add the official Kaggle dataset page]
Licence: [Verify and add the dataset licence]

## Technology Stack
- Python
- Pandas
- Streamlit
- Plotly
- NumPy

## Installation
1. Clone this repository.
2. Install the dependencies.
3. Download the dataset.
4. Place city_hour.csv in the data directory.
5. Run the application.

## Run
streamlit run app.py

## Team Members
1. Name: Aaditi Potey
   Role: Processing Work

2. Name: Alkha Susan
   Role: Recommendation Logic

3. Name: Hansitha Kakarla
   Role: UI Integration

## Deployment
Application URL: To be added

## Limitations
The dataset contains historical observations from 2015–2020.
Recommendations are based on available historical readings
and do not guarantee that outdoor conditions are safe.