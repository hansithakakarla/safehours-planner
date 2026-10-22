
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_quality import check_data_quality
from recommendation import generate_recommendation, cpcb_aqi_band


# ---------------- PAGE CONFIG ----------------

st.set_page_config(
    page_title="SafeHours | Outdoor Activity Planner",
    page_icon="🌿",
    layout="wide",
)

st.title("🌿 SafeHours")
st.subheader("Find the better hours for outdoor school activities")
st.caption(
    "A historical air-quality planning tool for schools. "
    "Recommendations are not live forecasts or guarantees of safety."
)

DATA_PATH = Path(__file__).parent / "data" / "city_hour.csv"


# ---------------- LOAD DATA ----------------

@st.cache_data
def load_data(path, modified_time):
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip() for c in raw.columns]

    checked = check_data_quality(raw)
    checked["Datetime"] = pd.to_datetime(
        checked["Datetime"], errors="coerce"
    )
    return checked


if not DATA_PATH.exists():
    st.error(f"Dataset not found: {DATA_PATH}")
    st.info(
        "Place city_hour.csv inside the data folder, "
        "or update DATA_PATH in app.py to match its location."
    )
    st.stop()

try:
    df = load_data(str(DATA_PATH), DATA_PATH.stat().st_mtime)
except Exception as exc:
    st.error(f"Could not load or validate the dataset: {exc}")
    st.stop()

df = df.dropna(subset=["City", "Datetime"]).copy()
df["City"] = df["City"].astype(str).str.strip()

if df.empty:
    st.error("The dataset contains no usable city and timestamp records.")
    st.stop()


# ---------------- PLANNER INPUTS ----------------

st.markdown("### Plan an outdoor activity")

city_column, date_column, duration_column = st.columns([1.3, 1.2, 1])
city_options = {
    "Bangalore": "Bengaluru",
    "Chennai": "Chennai",
    "Delhi": "Delhi",
}
city_label = city_column.selectbox("City", list(city_options))
city = city_options[city_label]

city_df = df[df["City"].str.casefold() == city.casefold()].copy()
city_df["AQI"] = pd.to_numeric(city_df["AQI"], errors="coerce")
city_df.loc[~city_df["AQI"].between(0, 500), "AQI"] = float("nan")
city_df["ActivityDate"] = city_df["Datetime"].dt.date

available_dates = sorted(
    city_df.loc[city_df["AQI"].notna(), "ActivityDate"].dropna().unique()
)
daytime_dates = sorted(
    city_df.loc[
        city_df["AQI"].notna()
        & city_df["Datetime"].dt.hour.between(6, 17),
        "ActivityDate",
    ].dropna().unique()
)

if not available_dates:
    st.error(
        f"No valid AQI readings were found for {city}. "
        "Check the dataset's AQI column and data-quality processing."
    )
    st.stop()

selected_date = date_column.date_input(
    "Date",
    value=daytime_dates[-1] if daytime_dates else available_dates[-1],
    min_value=available_dates[0],
    max_value=available_dates[-1],
    key=f"activity_date_{city}",
)

if selected_date not in available_dates:
    st.error(
        f"No valid AQI readings were found for {city_label} on "
        f"{selected_date.strftime('%d %b %Y')}. Choose another date."
    )
    st.stop()

duration = duration_column.selectbox(
    "Activity duration",
    options=[60, 120, 180],
    format_func=lambda minutes: f"{minutes // 60} hour"
    + ("" if minutes == 60 else "s"),
)

# ---------------- DATA QUALITY OVERVIEW ----------------

day_df = city_df[
    city_df["Datetime"].dt.date == selected_date
].copy()

st.markdown("---")
st.markdown("### Data overview")

m1, m2, m3 = st.columns(3)

m1.metric("Selected city", city_label)
m2.metric("Records on selected date", len(day_df))

if not day_df.empty:
    reliable_fraction = float(day_df["reliable"].fillna(False).mean())
else:
    reliable_fraction = 0.0

m3.metric("Reliable records", f"{reliable_fraction:.0%}")

if reliable_fraction < 0.70:
    st.warning(
        "Many records on this date are unreliable. "
        "The recommendation engine will decide whether there is "
        "enough reliable data to make a recommendation."
    )


# ---------------- RECOMMENDATION ----------------

st.markdown("---")
st.markdown("### Your outdoor activity plan")

try:
    result = generate_recommendation(
        df=city_df,
        city=city,
        activity_date=selected_date,
        activity_duration_minutes=duration,
    )
except Exception as exc:
    st.error(f"Could not generate a recommendation: {exc}")
    st.stop()

if result["status"] == "recommendation_available":
    best = result["primary_recommendation"]

    st.success("A suitable historical time window was found.")

    a, b, c = st.columns(3)
    a.metric("Recommended window", f"{best['start']} – {best['end']}")
    b.metric("Mean AQI", best["mean_aqi"])
    c.metric("AQI category", best["aqi_band"])

    st.markdown("#### Why this time?")
    st.write(best["reason"])
    st.info(result["advisory"])

    alternatives = result.get("alternatives", [])
    if alternatives:
        st.markdown("#### Other eligible time windows")
        st.dataframe(
            pd.DataFrame(alternatives)[
                ["start", "end", "mean_aqi", "worst_hour_aqi", "aqi_band"]
            ].rename(
                columns={
                    "start": "Start",
                    "end": "End",
                    "mean_aqi": "Mean AQI",
                    "worst_hour_aqi": "Highest hourly AQI",
                    "aqi_band": "AQI category",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.error("No recommendation can be made for this selection.")
    st.write(result["message"])


# ---------------- HOURLY CHART ----------------

st.markdown("---")
st.markdown("### AQI through the day")
st.caption(
    "Each point is an hourly AQI reading. The horizontal lines mark CPCB category "
    "limits; gray crosses are readings excluded from the recommendation."
)

hourly = pd.DataFrame(result.get("hourly_strip", []))

if not hourly.empty:
    chart_data = hourly[["time", "aqi", "band", "reliable"]].copy()
    chart_data["aqi"] = pd.to_numeric(chart_data["aqi"], errors="coerce")
    chart_data["reliable"] = chart_data["reliable"].fillna(False).astype(bool)
    band_colors = {
        "Good": "#27805a",
        "Satisfactory": "#8b9c24",
        "Moderate": "#d49322",
        "Poor": "#d65b3c",
        "Very Poor": "#9a4d78",
        "Severe": "#6e3347",
    }
    reliable_data = chart_data[
        chart_data["reliable"] & chart_data["aqi"].notna()
    ]
    unreliable_data = chart_data[
        ~chart_data["reliable"] & chart_data["aqi"].notna()
    ]

    if not chart_data["aqi"].notna().any():
        st.warning("No AQI values are available to chart for this date.")
    else:
        observed_max = float(chart_data["aqi"].max())
        y_max = min(500, max(100, ((int(observed_max) + 49) // 50) * 50))
        figure = go.Figure()

        for threshold in [50, 100, 200, 300, 400]:
            if threshold < y_max:
                figure.add_hline(
                    y=threshold,
                    line={"color": "#aeb8b4", "width": 1, "dash": "dot"},
                )

        if not reliable_data.empty:
            reliable_data = reliable_data.copy()
            reliable_data["category"] = reliable_data["aqi"].map(
                lambda value: cpcb_aqi_band(value)["band"]
            )
            figure.add_trace(go.Scatter(
                x=reliable_data["time"],
                y=reliable_data["aqi"],
                mode="lines+markers",
                name="Reliable reading",
                connectgaps=False,
                line={"color": "#176b68", "width": 2.5},
                marker={
                    "size": 10,
                    "color": reliable_data["category"].map(band_colors),
                    "line": {"color": "#ffffff", "width": 1.5},
                },
                customdata=reliable_data[["category"]],
                hovertemplate=(
                    "%{x}<br>AQI: %{y:.1f}<br>Category: %{customdata[0]}"
                    "<extra>Reliable reading</extra>"
                ),
            ))

        if not unreliable_data.empty:
            unreliable_data = unreliable_data.copy()
            unreliable_data["category"] = unreliable_data["aqi"].map(
                lambda value: cpcb_aqi_band(value)["band"]
            )
            figure.add_trace(go.Scatter(
                x=unreliable_data["time"],
                y=unreliable_data["aqi"],
                mode="markers",
                name="Excluded reading",
                marker={"symbol": "x", "size": 11, "color": "#72808b"},
                customdata=unreliable_data[["category"]],
                hovertemplate=(
                    "%{x}<br>AQI: %{y:.1f}<br>Category: %{customdata[0]}"
                    "<extra>Excluded from recommendation</extra>"
                ),
            ))

        figure.update_layout(
            height=360,
            margin={"l": 12, "r": 12, "t": 24, "b": 12},
            hovermode="x unified",
            legend={"orientation": "h", "y": 1.15, "x": 0},
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            font={"color": "#23323a", "family": "Arial, sans-serif"},
            xaxis={"title": None, "showgrid": False},
            yaxis={
                "title": "AQI (lower is better)",
                "range": [0, y_max],
                "dtick": 50,
                "gridcolor": "#e5e9e6",
                "zeroline": False,
            },
        )
        st.plotly_chart(figure, use_container_width=True)

else:
    st.info(
        "No hourly information is available for the selected date."
    )

st.caption(
    "CPCB AQI bands: Good 0–50 · Satisfactory 51–100 · Moderate 101–200 · "
    "Poor 201–300 · Very Poor 301–400 · Severe 401–500."
)


# ---------------- MONTHLY AQI HEATMAP ----------------

st.markdown("### Daily pattern this month")
st.caption(
    "Each cell shows the median reliable AQI for that hour and date. "
    "Gray cells have no reliable reading; hover over a colored cell for its value and category."
)

month_start = pd.Timestamp(selected_date.year, selected_date.month, 1)
month_end = month_start + pd.offsets.MonthBegin(1)
month_rows = city_df[
    (city_df["Datetime"] >= month_start)
    & (city_df["Datetime"] < month_end)
    & city_df["Datetime"].dt.hour.between(6, 17)
].copy()
month_rows["ActivityDate"] = month_rows["Datetime"].dt.date
month_rows["Hour"] = month_rows["Datetime"].dt.hour
month_rows["AQI"] = pd.to_numeric(month_rows["AQI"], errors="coerce")
month_rows = month_rows[
    month_rows["reliable"].fillna(False).astype(bool)
    & month_rows["AQI"].between(0, 500)
]

days_in_month = pd.Period(month_start, freq="M").days_in_month
month_days = pd.date_range(month_start, periods=days_in_month, freq="D").date
daily_hourly = (
    month_rows.groupby(["ActivityDate", "Hour"])["AQI"]
    .median()
    .unstack("Hour")
    .reindex(index=month_days, columns=range(6, 18))
)
category_grid = daily_hourly.apply(
    lambda column: column.map(
        lambda value: cpcb_aqi_band(value)["band"] if pd.notna(value) else "No reliable data"
    )
)

month_colorscale = []
aqi_bands = [
    (0, 50, band_colors["Good"]),
    (50.01, 100, band_colors["Satisfactory"]),
    (100.01, 200, band_colors["Moderate"]),
    (200.01, 300, band_colors["Poor"]),
    (300.01, 400, band_colors["Very Poor"]),
    (400.01, 500, band_colors["Severe"]),
]
for index, (lower, upper, color) in enumerate(aqi_bands):
    month_colorscale.append([lower / 500, color])
    month_colorscale.append([upper / 500, color])
    if index < len(aqi_bands) - 1:
        next_lower, _, next_color = aqi_bands[index + 1]
        month_colorscale.append([next_lower / 500, next_color])

heatmap = go.Figure(go.Heatmap(
    z=daily_hourly.to_numpy(),
    x=[f"{hour:02d}:00" for hour in range(6, 18)],
    y=[day.strftime("%d %b") for day in month_days],
    customdata=category_grid.to_numpy(),
    colorscale=month_colorscale,
    zmin=0,
    zmax=500,
    colorbar={
        "title": {"text": "AQI category"},
        "tickvals": [25, 75, 150, 250, 350, 450],
        "ticktext": ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"],
        "len": 0.9,
    },
    xgap=2,
    ygap=2,
    hoverongaps=False,
    hovertemplate=(
        "%{y}, %{x}<br>AQI: %{z:.1f}<br>Category: %{customdata}"
        "<extra></extra>"
    ),
))
heatmap.update_layout(
    height=max(480, days_in_month * 22),
    margin={"l": 12, "r": 12, "t": 12, "b": 12},
    plot_bgcolor="#e8eceb",
    paper_bgcolor="#ffffff",
    font={"color": "#23323a", "family": "Arial, sans-serif"},
    xaxis={"title": "Hour starting", "side": "bottom", "showgrid": False},
    yaxis={"title": "Date", "autorange": "reversed", "showgrid": False},
)
st.plotly_chart(heatmap, use_container_width=True)


# ---------------- FOOTER ----------------

st.markdown("---")
st.caption(
    "SafeHours • Historical data only • "
    "Always check current local air quality before outdoor activities."
)
