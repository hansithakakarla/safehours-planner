
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Leaf,
  MapPin,
  Wind,
  RefreshCw,
} from "lucide-react";
import "./App.css";

function normaliseApiUrl(value) {
  const url = (value || "").trim().replace(/\/+$/, "").replace(/\/api$/, "");
  if (!url) return "";
  // Render blueprints pass a bare host (e.g. safehours-api.onrender.com).
  return /^https?:\/\//.test(url) ? url : `https://${url}`;
}

const API = normaliseApiUrl(import.meta.env.VITE_API_URL)
  || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

function apiConfigurationError() {
  return import.meta.env.DEV
    ? "Make sure FastAPI is running on port 8000."
    : "Set VITE_API_URL in the Render frontend environment to your deployed FastAPI URL, then redeploy.";
}

const AQI_BANDS = [
  { label: "Good", min: 0, max: 50, color: "#247653" },
  { label: "Satisfactory", min: 51, max: 100, color: "#8b9822" },
  { label: "Moderate", min: 101, max: 200, color: "#ce8b22" },
  { label: "Poor", min: 201, max: 300, color: "#d45f3e" },
  { label: "Very poor", min: 301, max: 400, color: "#a34f70" },
  { label: "Severe", min: 401, max: 500, color: "#71364c" },
];

const CITY_LABELS = {
  Bengaluru: "Bangalore",
  Chennai: "Chennai",
  Delhi: "Delhi",
};

function aqiColor(value) {
  if (value == null) return "#8a9690";
  return AQI_BANDS.find((band) => value <= band.max)?.color || "#71364c";
}

function bandText(band) {
  if (!band) return "Unknown";
  return typeof band === "string" ? band : band.band || "Unknown";
}

function aqiCategory(value) {
  if (value == null || Number.isNaN(Number(value))) return "No reliable reading";
  return AQI_BANDS.find((band) => Number(value) <= band.max)?.label || "Severe";
}

function displayDate(isoDate, options = { day: "numeric", month: "short", year: "numeric" }) {
  if (!isoDate) return "";
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString("en-IN", options);
}

function HourlyAqiChart({ data }) {
  const width = 720;
  const height = 270;
  const margin = { top: 16, right: 12, bottom: 38, left: 48 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const values = data.flatMap((point) => [point.reliableAqi, point.excludedAqi])
    .filter((value) => value != null);
  const minObserved = values.length ? Math.min(...values) : 0;
  const maxObserved = values.length ? Math.max(...values) : 100;
  const yMin = Math.max(0, Math.floor(Math.max(0, minObserved - 10) / 25) * 25);
  const yMax = Math.min(500, Math.max(yMin + 25, Math.ceil((maxObserved + 10) / 25) * 25));
  const y = (value) => margin.top + plotHeight - ((value - yMin) / (yMax - yMin)) * plotHeight;
  const x = (index) => margin.left + (index / Math.max(1, data.length - 1)) * plotWidth;
  const range = yMax - yMin;
  const tickSize = range <= 100 ? 25 : range <= 250 ? 50 : 100;
  const firstTick = Math.ceil(yMin / tickSize) * tickSize;
  const yTicks = Array.from(
    { length: Math.floor((yMax - firstTick) / tickSize) + 1 },
    (_, index) => firstTick + index * tickSize
  );

  const reliablePath = data.reduce((path, point, index) => {
    if (point.reliableAqi == null) return `${path} `;
    const previousIsGap = index === 0 || data[index - 1].reliableAqi == null;
    return `${path}${previousIsGap ? "M" : "L"}${x(index)},${y(point.reliableAqi)} `;
  }, "").trim();

  return (
    <svg className="aqi-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`Hourly AQI from 6 AM to 6 PM, shown on a ${yMin} to ${yMax} scale; lower values are better`}>
      <title>Hourly AQI, with CPCB category thresholds</title>
      {AQI_BANDS.map((band) => {
        const bandTop = Math.min(band.max, yMax);
        if (band.min >= yMax) return null;
        return (
          <rect
            key={band.label}
            x={margin.left}
            y={y(bandTop)}
            width={plotWidth}
            height={Math.max(0, y(band.min) - y(bandTop))}
            fill={band.color}
            opacity="0.055"
          />
        );
      })}
      <text x={width - margin.right} y={12} textAnchor="end" className="chart-scale-label">
        Zoomed scale: {yMin}–{yMax} AQI
      </text>
      {yTicks.map((tick) => (
        <g key={tick}>
          <line
            x1={margin.left}
            x2={width - margin.right}
            y1={y(tick)}
            y2={y(tick)}
            stroke={tick === 50 || tick === 100 || tick === 200 || tick === 300 || tick === 400 ? "#aab7af" : "#e5ebe6"}
            strokeDasharray={tick === 0 ? undefined : "4 5"}
          />
          <text x={margin.left - 10} y={y(tick) + 4} textAnchor="end" className="chart-axis-label">{tick}</text>
        </g>
      ))}
      <line x1={margin.left} x2={margin.left} y1={margin.top} y2={height - margin.bottom} stroke="#aeb9b1" />
      <line x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} stroke="#aeb9b1" />
      {data.map((point, index) => index % 2 === 0 || index === data.length - 1 ? (
        <text key={point.time} x={x(index)} y={height - 13} textAnchor="middle" className="chart-axis-label">{point.time.slice(0, 5)}</text>
      ) : null)}
      <path d={reliablePath} fill="none" stroke="#176c62" strokeWidth="4" strokeLinejoin="round" strokeLinecap="round" />
      {data.map((point, index) => {
        const value = point.reliableAqi ?? point.excludedAqi;
        if (value == null) return null;
        const reliable = point.reliableAqi != null;
        return (
          <circle
            key={point.time}
            cx={x(index)}
            cy={y(value)}
            r={reliable ? 5 : 6}
            fill={reliable ? aqiColor(value) : "#929c96"}
            stroke="#fff"
            strokeWidth="2"
          >
            <title>{`${point.time} · AQI ${value} · ${aqiCategory(value)} · ${reliable ? "Reliable" : "Excluded from recommendation"}`}</title>
          </circle>
        );
      })}
      <text transform={`translate(14 ${margin.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle" className="chart-axis-title">AQI</text>
    </svg>
  );
}

export default function App() {
  const [options, setOptions] = useState(null);
  const [city, setCity] = useState("");
  const [date, setDate] = useState("");
  const [duration, setDuration] = useState(60);
  const [startTime, setStartTime] = useState("");
  const [healthPrecautionsEnabled, setHealthPrecautionsEnabled] = useState(false);
  const [healthSensitivityGroup, setHealthSensitivityGroup] = useState("");
  const [healthAqiThreshold, setHealthAqiThreshold] = useState("");
  const [heatmapMode, setHeatmapMode] = useState("calendar");
  const [result, setResult] = useState(null);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadOptions() {
      try {
        setLoadingOptions(true);
        setError("");

        if (!API) {
          throw new Error(apiConfigurationError());
        }

        const response = await fetch(`${API}/api/options`);
        if (!response.ok) {
          throw new Error(`Could not load cities and dates (${response.status}).`);
        }

        const data = await response.json();
        if (cancelled) return;

        setOptions(data);
        setHealthSensitivityGroup(
          data.health_sensitivity_groups?.[0]?.value || ""
        );

        const firstCity = ["Bengaluru", "Chennai", "Delhi"].find(
          (name) => data.cities?.includes(name)
        ) || data.cities?.[0] || "";

        setCity(firstCity);

        const dates = data.dates_by_city?.[firstCity] || [];
        setDate(dates.at(-1) || "");
      } catch (err) {
        if (!cancelled) {
          setError(`${err.message} ${apiConfigurationError()}`);
        }
      } finally {
        if (!cancelled) setLoadingOptions(false);
      }
    }

    loadOptions();
    return () => {
      cancelled = true;
    };
  }, []);

  const cityDates = options?.dates_by_city?.[city] || [];
  const dateAvailable = cityDates.includes(date);
  const healthSensitivityGroups = options?.health_sensitivity_groups || [];
  const selectedHealthGroup = healthSensitivityGroups.find(
    (group) => group.value === healthSensitivityGroup
  );
  const latestStartHour = 18 - Number(duration) / 60;
  const startHours = Array.from(
    { length: latestStartHour - 5 },
    (_, index) => index + 6
  );

  const chartData = useMemo(
    () => (result?.hourly_readings || [])
      .filter((reading) => {
        const hour = Number(reading.time.slice(0, 2));
        return hour >= 6 && hour < 18;
      })
      .map((reading) => ({
        time: reading.time,
        reliableAqi: reading.reliable ? reading.aqi : null,
        excludedAqi: reading.reliable ? null : reading.aqi,
        band: bandText(reading.band),
      })),
    [result]
  );

  const heatmapDays = useMemo(() => {
    if (!date || !result?.monthly_readings) return [];

    const [year, month] = date.split("-").map(Number);
    const numberOfDays = new Date(year, month, 0).getDate();
    const buckets = new Map();

    for (const reading of result.monthly_readings) {
      if (!reading.reliable || reading.aqi == null) continue;
      const key = `${reading.date}:${reading.hour}`;
      const values = buckets.get(key) || [];
      values.push(Number(reading.aqi));
      buckets.set(key, values);
    }

    return Array.from({ length: numberOfDays }, (_, index) => {
      const day = index + 1;
      const dayDate = `${date.slice(0, 7)}-${String(day).padStart(2, "0")}`;
      const hours = Array.from({ length: 12 }, (_, hourIndex) => {
        const values = buckets.get(`${dayDate}:${hourIndex + 6}`) || [];
        values.sort((left, right) => left - right);
        const middle = Math.floor(values.length / 2);
        const value = values.length
          ? values.length % 2
            ? values[middle]
            : (values[middle - 1] + values[middle]) / 2
          : null;
        return { hour: hourIndex + 6, value };
      });
      const validValues = hours
        .map((hour) => hour.value)
        .filter((value) => value != null);
      const meanValue = validValues.length
        ? validValues.reduce((total, value) => total + value, 0) / validValues.length
        : null;
      return { date: dayDate, day, hours, meanValue, reliableHours: validValues.length };
    });
  }, [date, result]);

  const calendarCells = useMemo(() => {
    if (!date || !heatmapDays.length) return [];
    const [year, month] = date.split("-").map(Number);
    const leadingBlanks = new Date(year, month - 1, 1).getDay();
    const trailingBlanks = (7 - ((leadingBlanks + heatmapDays.length) % 7)) % 7;
    return [
      ...Array.from({ length: leadingBlanks }, (_, index) => ({ key: `leading-${index}` })),
      ...heatmapDays,
      ...Array.from({ length: trailingBlanks }, (_, index) => ({ key: `trailing-${index}` })),
    ];
  }, [date, heatmapDays]);

  async function previewPlan(requestedDate = date) {
    if (!city || !requestedDate || !cityDates.includes(requestedDate)) {
      setError("Choose a city and a date available in the historical dataset.");
      return;
    }

    try {
      setLoadingPlan(true);
      setError("");
      setResult(null);

      if (!API) {
        throw new Error(apiConfigurationError());
      }

      const response = await fetch(`${API}/api/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city,
          activity_date: requestedDate,
          activity_duration_minutes: Number(duration),
          preferred_start_hour: startTime === "" ? null : Number(startTime),
          health_precautions_enabled: healthPrecautionsEnabled,
          health_sensitivity_group: healthPrecautionsEnabled
            ? healthSensitivityGroup
            : null,
          health_aqi_threshold: healthPrecautionsEnabled && healthAqiThreshold !== ""
            ? Number(healthAqiThreshold)
            : null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : `The API returned status ${response.status}.`
        );
      }

      setResult(data);
    } catch (err) {
      setError(`${err.message} ${apiConfigurationError()}`);
    } finally {
      setLoadingPlan(false);
    }
  }

  const recommendation = result?.recommendation;
  const primary = recommendation?.primary_recommendation;
  const preferredWindow = recommendation?.preferred_window;
  const selectedWindow = preferredWindow?.status === "assessed"
    ? preferredWindow
    : null;
  const displayPrimary = selectedWindow || primary;
  const candidateAlternatives = selectedWindow
    ? [primary, ...(recommendation?.alternatives || [])]
    : recommendation?.alternatives || [];
  const alternativeWindows = candidateAlternatives.filter(
    (window, index, windows) => window
      && window.start_hour !== displayPrimary?.start_hour
      && windows.findIndex((candidate) => candidate?.start_hour === window.start_hour) === index
  );
  const status = recommendation?.status;
  const advisory =
    recommendation?.advisory ||
    recommendation?.message ||
    "No recommendation was returned.";

  const noAdvice =
    result &&
    (!primary ||
      status !== "recommendation_available");

  return (
    <div className="site-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="SafeHours home">
          <span className="brand-mark"><Wind size={20} /></span>
          <span>SafeHours</span>
        </a>
        <div className="dataset-status">
          <span className="status-light" />
          HISTORICAL AIR QUALITY · CPCB AQI
        </div>
      </header>

      <main id="top" className="dashboard">
        <section className="page-heading">
          <div>
            <p className="eyebrow"><Leaf size={14} /> SCHOOL OUTDOOR PLANNER</p>
            <h1>Make room for <span>fresh air.</span></h1>
            <p className="page-intro">
              Find a lower-AQI time window using historical readings for your city.
            </p>
          </div>
          <div className="historical-badge">
            <AlertTriangle size={16} />
            <span>Historical data, not a live forecast</span>
          </div>
        </section>

        <section className="planner-panel" aria-labelledby="planner-title">
          <div className="planner-heading">
            <div className="step-number">01</div>
            <div>
              <p className="eyebrow">START WITH YOUR PLAN</p>
              <h2 id="planner-title">Choose a city and day</h2>
            </div>
          </div>

          <div className="planner-controls">
            <label className="field city-field">
              <span className="field-label"><MapPin size={15} /> City</span>
              <select
                value={city}
                disabled={loadingOptions || !options}
                onChange={(event) => {
                  const nextCity = event.target.value;
                  const nextDates = options?.dates_by_city?.[nextCity] || [];
                  setCity(nextCity);
                  setDate(nextDates.at(-1) || "");
                  setResult(null);
                  setError("");
                }}
              >
                {options?.cities?.map((name) => (
                  <option key={name} value={name}>{CITY_LABELS[name] || name}</option>
                ))}
              </select>
            </label>

            <label className="field date-field">
              <span className="field-label"><CalendarDays size={15} /> Historical date</span>
              <input
                type="date"
                value={date}
                min={cityDates[0]}
                max={cityDates.at(-1)}
                disabled={!cityDates.length}
                onChange={(event) => {
                  setDate(event.target.value);
                  setResult(null);
                  setError("");
                }}
              />
            </label>

            <label className="field start-time-field">
              <span className="field-label"><Clock3 size={15} /> Start time</span>
              <select
                value={startTime}
                onChange={(event) => {
                  setStartTime(event.target.value);
                  setResult(null);
                }}
              >
                <option value="">Find best time</option>
                {startHours.map((hour) => (
                  <option key={hour} value={hour}>
                    {new Date(2000, 0, 1, hour).toLocaleTimeString("en-IN", {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </option>
                ))}
              </select>
            </label>

            <label className="field duration-field">
              <span className="field-label"><Clock3 size={15} /> Activity duration</span>
              <select
                value={duration}
                onChange={(event) => {
                  const nextDuration = Number(event.target.value);
                  if (startTime !== "" && Number(startTime) + nextDuration / 60 > 18) {
                    setStartTime("");
                  }
                  setDuration(nextDuration);
                  setResult(null);
                }}
              >
                <option value={60}>1 hour</option>
                <option value={120}>2 hours</option>
                <option value={180}>3 hours</option>
              </select>
            </label>

            <button
              className="primary-button"
              onClick={() => previewPlan()}
              disabled={loadingOptions || loadingPlan || !city || !dateAvailable}
            >
              {loadingPlan ? (
                <><RefreshCw size={17} className="spin" /> Finding a window</>
              ) : (
                <><Activity size={17} /> Find best hours</>
              )}
            </button>
          </div>

          <div className="health-controls">
            <label className="health-toggle">
              <input
                type="checkbox"
                checked={healthPrecautionsEnabled}
                onChange={(event) => {
                  setHealthPrecautionsEnabled(event.target.checked);
                  setResult(null);
                  setError("");
                }}
              />
              <span>Apply a health-sensitive AQI filter</span>
            </label>
            {healthPrecautionsEnabled && (
              <div className="health-fields">
                <label className="field">
                  <span className="field-label">Sensitivity group</span>
                  <select
                    value={healthSensitivityGroup}
                    onChange={(event) => {
                      setHealthSensitivityGroup(event.target.value);
                      setResult(null);
                    }}
                    disabled={!healthSensitivityGroups.length}
                  >
                    {healthSensitivityGroups.map((group) => (
                      <option key={group.value} value={group.value}>{group.label}</option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="field-label">Maximum AQI for planning</span>
                  <input
                    type="number"
                    min="0"
                    max="500"
                    step="1"
                    value={healthAqiThreshold}
                    placeholder={selectedHealthGroup ? `Default ${selectedHealthGroup.default_aqi_threshold}` : "Group default"}
                    onChange={(event) => {
                      setHealthAqiThreshold(event.target.value);
                      setResult(null);
                    }}
                  />
                </label>
                <p className="health-help">
                  {selectedHealthGroup
                    ? `Default: ${selectedHealthGroup.default_aqi_threshold} AQI for ${selectedHealthGroup.label}. `
                    : "Choose a sensitivity group. "}
                  This is a configurable planning precaution, not medical advice or a safety guarantee.
                </p>
              </div>
            )}
          </div>

          <div className="planner-foot">
            <span>
              {loadingOptions
                ? "Loading city data…"
                : options
                  ? `${displayDate(options.dataset_start)} – ${displayDate(options.dataset_end)} dataset`
                  : "Historical dataset unavailable"}
            </span>
            {!loadingOptions && date && !dateAvailable && (
              <span className="date-unavailable">No reliable daytime readings for this date</span>
            )}
          </div>

          {error && <div className="error-box" role="alert">{error}</div>}
        </section>

        <section className="results-section" aria-live="polite">
          <div className="section-heading">
            <div>
              <p className="eyebrow">YOUR PLAN</p>
              <h2>{result ? `${CITY_LABELS[result.city] || result.city} · ${displayDate(result.activity_date)}` : "Air quality at a glance"}</h2>
            </div>
            {result && <span className="result-date"><CheckCircle2 size={15} /> Analysis complete</span>}
          </div>

          <div className="metrics-grid">
            <article className="metric-card metric-city">
              <span className="metric-label">CITY</span>
              <strong>{CITY_LABELS[city] || city || "—"}</strong>
              <span className="metric-note">Historical hourly readings</span>
            </article>
            <article className="metric-card metric-aqi" style={{ "--metric-color": result ? aqiColor(result.mean_aqi) : "#8a9690" }}>
              <span className="metric-label">DAILY MEAN AQI</span>
              <strong>{result?.mean_aqi ?? "—"}</strong>
              <span className="metric-note">{result ? bandText(result.band) : "Run an analysis to see the category"}</span>
            </article>
            <article className="metric-card metric-coverage">
              <span className="metric-label">RELIABLE READINGS</span>
              <strong>{result ? `${result.reliable_count} / ${result.readings_count}` : "—"}</strong>
              <span className="metric-note">Reliable / total for selected day</span>
            </article>
          </div>

          {loadingPlan && (
            <div className="loading-panel">
              <span className="loading-ring" />
              <div><strong>Checking historical readings</strong><span>Assessing data quality and comparing activity windows.</span></div>
            </div>
          )}

          {result && displayPrimary && (
            <article className="recommendation-card">
              <div className="recommendation-main">
                <span className="recommendation-kicker"><CheckCircle2 size={15} /> {selectedWindow ? "YOUR SELECTED WINDOW · RELIABLE" : "BEST ELIGIBLE WINDOW"}</span>
                <strong>{displayPrimary.start}<span>–</span>{displayPrimary.end}</strong>
                <span>{duration / 60} {duration === 60 ? "hour" : "hours"} outdoors · {selectedWindow ? "your chosen start time" : "ranked by mean AQI"}</span>
              </div>
              <div className="recommendation-stat">
                <span>Mean AQI</span>
                <strong>{displayPrimary.mean_aqi}</strong>
                <em style={{ color: aqiColor(displayPrimary.mean_aqi) }}>{displayPrimary.aqi_band}</em>
              </div>
              <div className="recommendation-stat">
                <span>Highest hour</span>
                <strong>{displayPrimary.worst_hour_aqi}</strong>
                <em>{aqiCategory(displayPrimary.worst_hour_aqi)}</em>
              </div>
            </article>
          )}

          {result && preferredWindow?.status === "unavailable" && (
            <div className={`preferred-time-note ${preferredWindow.status === "unavailable" ? "unavailable" : "assessed"}`}>
              <Clock3 size={17} />
              <div>
                <strong>{preferredWindow.status === "assessed" ? "Your selected start time was assessed" : "No reliable readings at your selected start time"}</strong>
                <p>{preferredWindow.message}</p>
                {recommendation?.preferred_alternative && (
                  <p className="preferred-alternative">
                    Alternative: {recommendation.preferred_alternative.start}–{recommendation.preferred_alternative.end}, mean AQI {recommendation.preferred_alternative.mean_aqi} ({recommendation.preferred_alternative.aqi_band}).
                  </p>
                )}
              </div>
            </div>
          )}

          {result?.recommendation?.health_guidance_applied && (
            <div className="health-guidance-note" role="note">
              <Leaf size={17} />
              <div>
                <strong>Health-sensitive planning · {result.recommendation.health_sensitivity_label}</strong>
                <p>{result.recommendation.health_guidance_summary || `Windows were filtered using a ${result.recommendation.health_aqi_threshold} AQI planning threshold.`}</p>
                <p>This is a configurable precautionary heuristic, not medical advice or a guarantee of safety.</p>
              </div>
            </div>
          )}

          {result && noAdvice && (
            <div className="no-advice" role="status">
              <AlertTriangle size={20} />
              <div><strong>No dependable activity window found</strong><p>{advisory}</p></div>
            </div>
          )}

          {result && displayPrimary && alternativeWindows.length > 0 && (
            <details className="alternatives-panel">
              <summary>Other eligible time windows <span>{alternativeWindows.length}</span></summary>
              <div className="alternatives-list">
                {alternativeWindows.map((item) => (
                  <div className="alternative-row" key={`${item.start_hour}-${item.end_hour}`}>
                    <strong>{item.start} – {item.end}</strong>
                    <span>{item.mean_aqi} AQI · {item.aqi_band}</span>
                  </div>
                ))}
              </div>
            </details>
          )}

          <div className="visual-grid">
            <section className="visual-panel" aria-labelledby="hourly-title">
              <div className="visual-heading">
                <div><p className="eyebrow">ONE DAY</p><h3 id="hourly-title">AQI by hour</h3></div>
                {result && <span className="visual-period">{displayDate(result.activity_date)}</span>}
              </div>
              <p className="visual-description">Hourly AQI. Lower is better; the vertical scale is zoomed to show daily changes.</p>
              {chartData.length ? (
                <div className="chart-wrap">
                  <HourlyAqiChart data={chartData} />
                </div>
              ) : (
                <div className="chart-empty"><Wind size={22} /><span>{loadingPlan ? "Loading hourly readings…" : "Choose a date and find the best hours to view this chart."}</span></div>
              )}
              <div className="line-legend">
                <span className="line-legend-item"><i className="legend-reliable" /> Reliable reading</span>
                <span className="line-legend-item"><i className="legend-excluded" /> Excluded reading</span>
              </div>
              <div className="aqi-chart-key" aria-label="CPCB AQI category colors">
                {AQI_BANDS.map((band) => (
                  <span key={band.label}><i style={{ backgroundColor: band.color }} />{band.label}</span>
                ))}
              </div>
            </section>

            <section className="visual-panel heatmap-panel" aria-labelledby="heatmap-title">
              <div className="visual-heading">
                <div><p className="eyebrow">MONTH VIEW</p><h3 id="heatmap-title">AQI calendar</h3></div>
                {result && <span className="visual-period">{displayDate(date, { month: "long", year: "numeric" })}</span>}
              </div>
              <p className="visual-description">Daily color shows mean reliable daytime AQI. Choose a date to update the plan.</p>
              <div className="heatmap-view-toggle" role="group" aria-label="Heatmap view">
                <button type="button" className={heatmapMode === "calendar" ? "active" : ""} aria-pressed={heatmapMode === "calendar"} onClick={() => setHeatmapMode("calendar")}>Calendar</button>
                <button type="button" className={heatmapMode === "hours" ? "active" : ""} aria-pressed={heatmapMode === "hours"} onClick={() => setHeatmapMode("hours")}>By hour</button>
              </div>
              {heatmapDays.length ? (
                heatmapMode === "calendar" ? (
                  <div className="calendar-heatmap" role="grid" aria-label="Monthly mean AQI calendar">
                    {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((weekday) => (
                      <span className="calendar-weekday" role="columnheader" key={weekday}>{weekday}</span>
                    ))}
                    {calendarCells.map((day) => {
                      if (!day.date) return <span className="calendar-empty" role="gridcell" key={day.key} />;
                      const selectable = cityDates.includes(day.date);
                      const value = day.meanValue;
                      return (
                        <button
                          type="button"
                          role="gridcell"
                          key={day.date}
                          className={`calendar-day ${value == null ? "missing" : ""} ${value != null && value <= 100 ? "low-contrast" : ""} ${day.date === date ? "selected" : ""}`}
                          style={value == null ? undefined : { "--day-color": aqiColor(value) }}
                          disabled={!selectable}
                          title={value == null ? `${displayDate(day.date)} · No reliable daytime readings` : `${displayDate(day.date)} · Mean AQI ${value.toFixed(1)} · ${aqiCategory(value)} · ${day.reliableHours} reliable hours`}
                          aria-label={value == null ? `${displayDate(day.date)}: no reliable daytime readings` : `${displayDate(day.date)}: mean AQI ${value.toFixed(1)}, ${aqiCategory(value)}, ${day.reliableHours} reliable hours`}
                          aria-pressed={day.date === date}
                          onClick={() => {
                            setDate(day.date);
                            previewPlan(day.date);
                          }}
                        >
                          <span className="calendar-day-number">{day.day}</span>
                          <strong>{value == null ? "—" : Math.round(value)}</strong>
                          <small>{value == null ? "No data" : aqiCategory(value)}</small>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="heatmap-scroll">
                    <div className="heatmap-grid" role="grid" aria-label="AQI heatmap by day and hour">
                      <div className="heatmap-corner" />
                      {Array.from({ length: 12 }, (_, index) => (
                        <span className="heatmap-hour" key={index}>{index + 6}</span>
                      ))}
                      {heatmapDays.map((day) => (
                        <div className="heatmap-row" role="row" key={day.date}>
                          <span className={`heatmap-date ${day.date === date ? "selected" : ""}`} role="rowheader">{day.day}</span>
                          {day.hours.map(({ hour, value }) => (
                            <button
                              type="button"
                              role="gridcell"
                              className={`heat-cell ${value == null ? "missing" : ""}`}
                              key={hour}
                              style={value == null ? undefined : { "--cell-color": aqiColor(value) }}
                              title={value == null ? `${displayDate(day.date)} · ${hour}:00 · No reliable reading` : `${displayDate(day.date)} · ${hour}:00 · AQI ${value.toFixed(1)} · ${aqiCategory(value)}`}
                              aria-label={value == null ? `${displayDate(day.date)}, ${hour}:00: no reliable reading` : `${displayDate(day.date)}, ${hour}:00: AQI ${value.toFixed(1)}, ${aqiCategory(value)}`}
                              onClick={() => {
                                if (cityDates.includes(day.date)) {
                                  setDate(day.date);
                                  previewPlan(day.date);
                                }
                              }}
                            >
                              {value == null ? "" : Math.round(value)}
                            </button>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                )
              ) : (
                <div className="chart-empty"><CalendarDays size={22} /><span>Run a plan to explore this month.</span></div>
              )}
              <div className="heatmap-legend" aria-label="AQI color key">
                {AQI_BANDS.map((band) => (
                  <span key={band.label}><i style={{ backgroundColor: band.color }} />{band.label}</span>
                ))}
                <span><i className="legend-missing" />No reading</span>
              </div>
            </section>
          </div>

          {result && (
            <div className="historical-warning">
              <AlertTriangle size={17} />
              <p>{result.notice || "Historical data only; this is not a live forecast."} Always check current local air quality before outdoor activities.</p>
            </div>
          )}
        </section>

        <footer className="footer">
          <a className="brand footer-brand" href="#top"><span className="brand-mark"><Wind size={17} /></span><span>SafeHours</span></a>
          <p>Historical planning · Not a forecast · Always verify current AQI</p>
        </footer>
      </main>
    </div>
  );
}
