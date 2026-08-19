# WeatherAnalysis

This project includes:

- A Python CLI for live weather analysis, charts, alerts, classification, and anomaly detection.
- A Netlify-ready frontend that fetches weather through a serverless function.

## CLI features

The terminal app in `weather_reporter.py` now supports:

- Weather alerts for extreme temperature, wind, and humidity.
- City favorites/watchlist stored in `config.json`.
- A weather condition classifier trained on labels generated from fetched weather history.
- Anomaly detection using Z-scores against previously logged observations.
- Historical logging in `output/weather_history.csv`.

Run it with:

```bash
python weather_reporter.py
```

If `scikit-learn` is not installed, the classifier falls back to rule-based labels until the dependency is available.

## Netlify deployment

1. Push this project to GitHub.
2. In Netlify, choose `Add new site` -> `Import an existing project`.
3. Select your repository and keep these settings:
   - Build command: leave blank
   - Publish directory: `.`
4. Add an environment variable in Netlify:
   - `OWM_API_KEY` = your OpenWeatherMap API key
5. Trigger the deploy.

The frontend loads from `index.html`, and live weather requests are routed through `/.netlify/functions/weather`.
