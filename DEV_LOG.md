# SafeHours — Development Log

## Project Overview

**Project:** SafeHours — AI-Powered Outdoor Activity Planner  
**Event:** NexAI Hackathon  
**Status:** Development completed; application deployed on Render.

SafeHours was developed to help users identify suitable outdoor activity times based on AQI readings. The project combines data processing, recommendation ranking, visualizations, and sensitivity-aware guidance in a Streamlit application.

## Development Timeline

### Phase 1 — Problem Identification and Planning

- Identified the difficulty of turning AQI measurements into practical outdoor activity decisions.
- Defined the goal of recommending activity windows based on city, date, and requested duration.
- Established the need for understandable recommendations rather than simply displaying raw AQI values.
- Identified students and people with respiratory sensitivities as important users of the system.

### Phase 2 — Data and AQI Processing

- Developed the AQI data-processing workflow required by the recommendation system.
- Established the use of AQI readings to compare candidate activity windows.
- Considered data availability when determining whether a recommendation could be produced.
- Ensured that recommendation results could communicate when suitable data was unavailable.

### Phase 3 — Recommendation Engine

Implemented the core recommendation logic to evaluate and rank candidate activity windows.

Key decisions:

- Support date-specific activity planning.
- Consider the requested activity duration.
- Rank candidate windows by average AQI.
- Use the lowest worst-case AQI as a tie-breaker when average AQI values are equal.
- Return a primary recommendation and additional alternatives where available.
- Provide a meaningful status when reliable readings are insufficient.

The recommendation engine focuses on comparing available activity windows rather than implementing a booking or reservation system.

### Phase 4 — Sensitivity-Aware Recommendations

- Identified that different students may have different levels of sensitivity to air pollution.
- Incorporated sensitivity-aware guidance into the project design and recommendation experience.
- Considered asthma and other respiratory sensitivities as relevant use cases.
- Used additional caution and relevant thresholds to help communicate how air-quality conditions may affect sensitive students.

The feature is intended to support more informed planning. It does not diagnose medical conditions or guarantee that an activity is safe.

### Phase 5 — User Interface and Visualizations

Developed the Streamlit interface to make recommendations and AQI information accessible to users.

Implemented the visualization experience around:

- **Line graphs:** Showing changes in AQI over time.
- **Heatmaps:** Helping users compare air-quality patterns across time periods.
- **Recommendation displays:** Presenting ranked activity windows and alternatives.
- **Interpretation of results:** Helping users connect visual patterns to practical activity-planning decisions.

The visualizations serve both as a way to understand the environmental data and as a practical aid for choosing an activity time.

### Phase 6 — Testing and Evaluation

- Added automated tests for important recommendation behavior.
- Used pytest to validate implemented functionality.
- Created and ran `evaluate_recommendation.py` to examine a configured date-specific recommendation scenario.
- Evaluated recommendation status, candidate windows, and AQI-based ranking behavior.

A development evaluation run used the following configuration:

| Parameter | Evaluation value |
|---|---|
| City | Chennai |
| Activity date | 2018-06-15 |
| Activity duration | 60 minutes |
| Reported status | `recommendation_available` |

The evaluation reported that one or more activity windows had reliable AQI readings. This was a configured historical evaluation scenario, not a claim about current Chennai air quality.

**Testing record:** A development run reported seven passing tests (`7 passed in 1.03s`). This result records that specific test run and should not be treated as a guarantee that every later version has been tested identically.

### Phase 7 — Deployment and Integration

- Prepared the application for deployment through Render.
- Configured the deployed application and its required environment settings.
- Addressed integration and deployment configuration issues during development.
- Verified the deployed application as the final delivery target.

The final public frontend URL and any associated service URLs should be recorded alongside the repository's deployment configuration.

### Phase 8 — Finalization

- Reviewed the recommendation workflow and its intended behavior.
- Consolidated the AQI ranking, visualizations, and sensitivity-aware planning features.
- Prepared the project for its final hackathon demonstration.
- Updated the project documentation to describe the implemented system and its limitations.

## Technical Decisions

### Why Rank Activity Windows?

Ranking windows by average AQI gives users a practical way to compare candidate periods. Using worst-case AQI as a tie-breaker helps distinguish windows with similar average readings but different peak pollution levels.

### Why Avoid Slot Booking?

The project's core objective is to recommend suitable activity times, not to manage reservations. Slot booking would introduce additional requirements, such as persistent storage, reservation records, conflict handling, and potentially user accounts. These features were outside the implemented recommendation workflow.

### Why Include Sensitivity-Aware Guidance?

AQI conditions can affect individuals differently. Sensitivity-aware guidance adds a practical layer to the recommendations by recognizing that some students may need more cautious decisions than the general population.

### Why Include Visualizations?

Raw AQI values can be difficult to interpret in isolation. Line graphs and heatmaps help users recognize temporal patterns and compare possible activity periods, supporting more informed decisions.

## Current Project Status

- [x] AQI-based activity-window recommendation logic
- [x] City- and date-specific evaluation workflow
- [x] Activity-duration-aware candidate evaluation
- [x] Average-AQI ranking with worst-case AQI tie-breaking
- [x] Alternative recommendation handling
- [x] Sensitivity-aware guidance
- [x] Line-graph and heatmap visualizations
- [x] Automated testing and recommendation evaluation script
- [x] Streamlit user interface
- [x] Render deployment
- [x] Project documentation

## Known Limitations

- Results depend on the quality and availability of AQI data.
- Historical evaluation results do not establish present-day air quality.
- Recommendations do not guarantee health or environmental safety.
- Sensitivity-aware guidance is not a substitute for professional medical advice.
- Database-backed booking and reservation management are not part of the completed implementation.

## Final Outcome

SafeHours delivers a data-driven approach to outdoor activity planning by translating AQI readings into ranked activity windows, supporting the results with visualizations, and incorporating sensitivity-aware guidance.

The completed project demonstrates how data processing, recommendation logic, and accessible visualization can work together to make environmental information more actionable.
