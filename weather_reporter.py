import json
import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import requests


API_KEY = "fe8b56bc86011acbef988a7664f5288b"
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
UNITS = "metric"
OUTPUT_DIR = "output"
CONFIG_FILE = "config.json"
HISTORY_FILE = os.path.join(OUTPUT_DIR, "weather_history.csv")

TEMP_ALERT_THRESHOLD = 40
WIND_ALERT_THRESHOLD = 15
HUMIDITY_ALERT_THRESHOLD = 90
ANOMALY_ZSCORE_THRESHOLD = 2.0

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"


def color_text(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def load_config(config_path: str = CONFIG_FILE) -> dict:
    default_config = {"favorites": []}

    if not os.path.exists(config_path):
        save_config(default_config, config_path)
        return default_config

    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config = json.load(file)
    except (json.JSONDecodeError, OSError):
        save_config(default_config, config_path)
        return default_config

    favorites = config.get("favorites", [])
    if not isinstance(favorites, list):
        favorites = []
    config["favorites"] = [str(city).strip() for city in favorites if str(city).strip()]
    return config


def save_config(config: dict, config_path: str = CONFIG_FILE) -> None:
    with open(config_path, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)


def normalize_cities(cities: list[str]) -> list[str]:
    unique_cities = []
    seen = set()

    for city in cities:
        cleaned = city.strip()
        if not cleaned:
            continue

        key = cleaned.casefold()
        if key not in seen:
            seen.add(key)
            unique_cities.append(cleaned)

    return unique_cities


def get_city_input(config: dict) -> list[str]:
    favorites = normalize_cities(config.get("favorites", []))

    print("\n" + "=" * 60)
    print("  Live Weather Reporting System")
    print("=" * 60)

    if favorites:
        print(f"Saved favorites: {', '.join(favorites)}")
        prompt = "\nEnter city name(s) [comma-separated, blank uses favorites]: "
    else:
        prompt = "\nEnter city name(s) [comma-separated for multiple]: "

    raw = input(prompt).strip()

    if raw:
        cities = normalize_cities(raw.split(","))
    elif favorites:
        cities = favorites
        print("Using saved favorites.")
    else:
        raise ValueError("No city name provided and favorites list is empty.")

    if not cities:
        raise ValueError("No valid city names were provided.")

    print(f"\nCities queued: {', '.join(cities)}")
    return cities


def maybe_update_favorites(config: dict, cities: list[str], config_path: str = CONFIG_FILE) -> None:
    favorites = normalize_cities(config.get("favorites", []))
    prompt = "Save these cities as your favorites/watchlist? [y/n]: "

    if favorites:
        prompt = "Replace saved favorites with these cities? [y/n]: "

    choice = input(prompt).strip().lower()
    if choice == "y":
        config["favorites"] = normalize_cities(cities)
        save_config(config, config_path)
        print(color_text("Favorites updated in config.json", CYAN))


def fetch_weather(city: str) -> dict:
    params = {
        "q": city,
        "appid": API_KEY,
        "units": UNITS,
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        raise ConnectionError("Network error: Could not reach the weather API. Check your internet connection.")
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Request timed out for '{city}'. Try again later.")
    except requests.exceptions.HTTPError as error:
        status = response.status_code
        if status == 401:
            raise PermissionError("Invalid API key. Please check your OpenWeatherMap API key.")
        if status == 404:
            raise ValueError(f"City '{city}' not found. Please check the spelling and try again.")
        if status == 429:
            raise RuntimeError("API rate limit exceeded. Wait a moment and retry.")
        raise RuntimeError(f"HTTP {status} error for '{city}': {error}")


def detect_alerts(record: dict) -> tuple[str, str]:
    alerts = []

    if record["Temperature"] is not None and record["Temperature"] > TEMP_ALERT_THRESHOLD:
        alerts.append(f"High temperature ({record['Temperature']:.1f}{record['Unit']})")
    if record["Wind_Speed"] is not None and record["Wind_Speed"] > WIND_ALERT_THRESHOLD:
        alerts.append(f"Strong wind ({record['Wind_Speed']:.1f} m/s)")
    if record["Humidity"] is not None and record["Humidity"] > HUMIDITY_ALERT_THRESHOLD:
        alerts.append(f"Very high humidity ({record['Humidity']:.0f}%)")

    if not alerts:
        return "Normal", "None"

    if len(alerts) >= 2:
        return " | ".join(alerts), "High"

    return alerts[0], "Moderate"


def parse_weather(data: dict) -> dict:
    unit_symbol = "C" if UNITS == "metric" else "F"

    parsed = {
        "City": data.get("name", "Unknown"),
        "Country": data.get("sys", {}).get("country", "N/A"),
        "Temperature": data.get("main", {}).get("temp"),
        "Feels_Like": data.get("main", {}).get("feels_like"),
        "Temp_Min": data.get("main", {}).get("temp_min"),
        "Temp_Max": data.get("main", {}).get("temp_max"),
        "Humidity": data.get("main", {}).get("humidity"),
        "Weather_Condition": data.get("weather", [{}])[0].get("description", "N/A").title(),
        "Wind_Speed": data.get("wind", {}).get("speed"),
        "Visibility_km": round(data.get("visibility", 0) / 1000, 1),
        "Unit": unit_symbol,
        "Timestamp": datetime.utcfromtimestamp(data.get("dt", 0)).strftime("%Y-%m-%d %H:%M UTC"),
        "Fetched_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    alerts, alert_level = detect_alerts(parsed)
    parsed["Weather_Alerts"] = alerts
    parsed["Alert_Level"] = alert_level
    return parsed


def build_dataframe(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df.set_index("City", inplace=True)
    return df


def load_history(history_path: str = HISTORY_FILE) -> pd.DataFrame:
    if not os.path.exists(history_path):
        return pd.DataFrame()

    try:
        history_df = pd.read_csv(history_path)
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()

    return history_df


def append_history(df: pd.DataFrame, history_path: str = HISTORY_FILE) -> None:
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    history_df = df.reset_index().copy()
    history_df.to_csv(
        history_path,
        mode="a",
        header=not os.path.exists(history_path),
        index=False,
    )


def derive_weather_label(temperature: float, humidity: float, wind_speed: float) -> str:
    if wind_speed is not None and wind_speed > 12:
        return "Windy"
    if humidity is not None and humidity >= 75:
        return "Humid"
    if temperature is not None and temperature >= 32:
        return "Hot"
    if temperature is not None and temperature <= 18:
        return "Cold"
    return "Pleasant"


def classify_weather(current_df: pd.DataFrame, history_df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    feature_cols = ["Temperature", "Humidity", "Wind_Speed"]

    combined_frames = []
    if not history_df.empty:
        available_history_cols = [col for col in feature_cols + ["City"] if col in history_df.columns]
        combined_frames.append(history_df[available_history_cols].copy())

    current_training = current_df.reset_index()[["City"] + feature_cols].copy()
    combined_frames.append(current_training)

    training_df = pd.concat(combined_frames, ignore_index=True)
    training_df = training_df.dropna(subset=feature_cols)
    training_df["Generated_Label"] = training_df.apply(
        lambda row: derive_weather_label(row["Temperature"], row["Humidity"], row["Wind_Speed"]),
        axis=1,
    )

    if len(training_df) < 5 or training_df["Generated_Label"].nunique() < 2:
        fallback_df = current_df.copy()
        fallback_df["Weather_Class"] = fallback_df.apply(
            lambda row: derive_weather_label(row["Temperature"], row["Humidity"], row["Wind_Speed"]),
            axis=1,
        )
        return fallback_df, "Rule-based fallback (not enough historical variety to train a model)"

    try:
        from sklearn.tree import DecisionTreeClassifier
    except ImportError:
        fallback_df = current_df.copy()
        fallback_df["Weather_Class"] = fallback_df.apply(
            lambda row: derive_weather_label(row["Temperature"], row["Humidity"], row["Wind_Speed"]),
            axis=1,
        )
        return fallback_df, "Rule-based fallback (scikit-learn not installed)"

    model = DecisionTreeClassifier(max_depth=4, min_samples_leaf=2, random_state=42)
    model.fit(training_df[feature_cols], training_df["Generated_Label"])

    classified_df = current_df.copy()
    classified_df["Weather_Class"] = model.predict(classified_df[feature_cols])
    return classified_df, f"DecisionTree trained on {len(training_df)} generated weather samples"


def detect_anomalies(current_df: pd.DataFrame, history_df: pd.DataFrame) -> list[dict]:
    if history_df.empty:
        return []

    metrics = {
        "Temperature": ("temperature", current_df["Unit"].iloc[0]),
        "Humidity": ("humidity", "%"),
        "Wind_Speed": ("wind speed", "m/s"),
    }
    anomalies = []

    for city, row in current_df.iterrows():
        if "City" not in history_df.columns:
            break

        city_history = history_df[
            history_df["City"].astype(str).str.casefold() == city.casefold()
        ].copy()
        if len(city_history) < 3:
            continue

        strongest = None
        for column, (label, unit) in metrics.items():
            if column not in city_history.columns:
                continue

            series = pd.to_numeric(city_history[column], errors="coerce").dropna()
            if len(series) < 3:
                continue

            std = series.std(ddof=0)
            if std == 0 or pd.isna(std):
                continue

            current_value = row[column]
            z_score = (current_value - series.mean()) / std

            candidate = {
                "city": city,
                "metric": label,
                "current": current_value,
                "mean": series.mean(),
                "unit": unit,
                "z_score": z_score,
            }

            if strongest is None or abs(candidate["z_score"]) > abs(strongest["z_score"]):
                strongest = candidate

        if strongest and abs(strongest["z_score"]) >= ANOMALY_ZSCORE_THRESHOLD:
            direction = "above" if strongest["z_score"] > 0 else "below"
            strongest["message"] = (
                f"{city}'s {strongest['metric']} today is "
                f"{abs(strongest['z_score']):.1f} standard deviations {direction} normal "
                f"(current {strongest['current']:.1f}{strongest['unit']}, "
                f"avg {strongest['mean']:.1f}{strongest['unit']})."
            )
            anomalies.append(strongest)

    return anomalies


def analyze(df: pd.DataFrame) -> dict:
    numeric_cols = ["Temperature", "Feels_Like", "Humidity", "Wind_Speed"]
    df_num = df[numeric_cols].copy()

    return {
        "city_count": len(df),
        "hottest_city": df["Temperature"].idxmax() if len(df) > 1 else df.index[0],
        "coldest_city": df["Temperature"].idxmin() if len(df) > 1 else df.index[0],
        "avg_temp": round(df["Temperature"].mean(), 2),
        "max_temp": round(df["Temperature"].max(), 2),
        "min_temp": round(df["Temperature"].min(), 2),
        "avg_humidity": round(df["Humidity"].mean(), 2),
        "max_wind": round(df["Wind_Speed"].max(), 2),
        "windiest_city": df["Wind_Speed"].idxmax(),
        "most_humid_city": df["Humidity"].idxmax(),
        "stats_table": df_num.describe().round(2),
    }


def visualize(df: pd.DataFrame, save_path: str | None = None) -> None:
    cities = df.index.tolist()
    n = len(cities)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Live Weather Report", fontsize=16, fontweight="bold", y=1.02)

    colors = plt.cm.coolwarm([i / max(n - 1, 1) for i in range(n)])

    ax1 = axes[0]
    bars = ax1.bar(cities, df["Temperature"], color=colors, edgecolor="white", linewidth=1.2)
    ax1.set_title("Temperature", fontsize=13, fontweight="bold")
    ax1.set_ylabel(f"Temp ({df['Unit'].iloc[0]})")
    ax1.set_xlabel("City")
    for bar, val in zip(bars, df["Temperature"]):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.3,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )
    ax1.tick_params(axis="x", rotation=30)
    ax1.grid(axis="y", alpha=0.3)

    ax2 = axes[1]
    bars2 = ax2.bar(cities, df["Humidity"], color="#5b9bd5", edgecolor="white", linewidth=1.2)
    ax2.set_title("Humidity", fontsize=13, fontweight="bold")
    ax2.set_ylabel("Humidity (%)")
    ax2.set_xlabel("City")
    ax2.set_ylim(0, 110)
    for bar, val in zip(bars2, df["Humidity"]):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val:.0f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )
    ax2.tick_params(axis="x", rotation=30)
    ax2.grid(axis="y", alpha=0.3)

    ax3 = axes[2]
    bars3 = ax3.bar(cities, df["Wind_Speed"], color="#70ad47", edgecolor="white", linewidth=1.2)
    ax3.set_title("Wind Speed", fontsize=13, fontweight="bold")
    ax3.set_ylabel("Wind Speed (m/s)")
    ax3.set_xlabel("City")
    for bar, val in zip(bars3, df["Wind_Speed"]):
        ax3.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )
    ax3.tick_params(axis="x", rotation=30)
    ax3.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"\nChart saved -> {save_path}")

    plt.show()


def safe_fetch_and_parse(city: str) -> dict | None:
    try:
        raw = fetch_weather(city)
        parsed = parse_weather(raw)

        summary = f"  OK {city} -> {parsed['Temperature']:.1f}{parsed['Unit']}, {parsed['Weather_Condition']}"
        if parsed["Alert_Level"] == "High":
            summary = color_text(summary + f" | ALERT: {parsed['Weather_Alerts']}", RED)
        elif parsed["Alert_Level"] == "Moderate":
            summary = color_text(summary + f" | Warning: {parsed['Weather_Alerts']}", YELLOW)
        else:
            summary = color_text(summary, GREEN)

        print(summary)
        return parsed

    except ValueError as error:
        print(color_text(f"  ERROR {city} -> City not found: {error}", RED))
    except PermissionError as error:
        print(color_text(f"  ERROR {city} -> Auth error: {error}", RED))
    except (ConnectionError, TimeoutError) as error:
        print(color_text(f"  ERROR {city} -> Network error: {error}", RED))
    except RuntimeError as error:
        print(color_text(f"  ERROR {city} -> Runtime error: {error}", RED))
    except Exception as error:
        print(color_text(f"  ERROR {city} -> Unexpected error: {type(error).__name__}: {error}", RED))

    return None


def print_alert_section(df: pd.DataFrame) -> None:
    print("\n" + "-" * 60)
    print("  Weather Alerts")
    print("-" * 60)

    alert_rows = df[df["Alert_Level"] != "None"]
    if alert_rows.empty:
        print(color_text("  No extreme-condition alerts detected.", GREEN))
        return

    for city, row in alert_rows.iterrows():
        color = RED if row["Alert_Level"] == "High" else YELLOW
        print(color_text(f"  {city}: {row['Weather_Alerts']}", color))


def print_classifier_section(df: pd.DataFrame, classifier_note: str) -> None:
    print("\n" + "-" * 60)
    print("  Weather Condition Classifier")
    print("-" * 60)
    print(f"  Model status: {classifier_note}")
    print(df[["Weather_Class", "Temperature", "Humidity", "Wind_Speed"]].to_string())


def print_anomaly_section(anomalies: list[dict], history_df: pd.DataFrame) -> None:
    print("\n" + "-" * 60)
    print("  Anomaly Detection")
    print("-" * 60)

    if history_df.empty:
        print("  No historical data yet. Run the script a few times to build anomaly baselines.")
        return

    if not anomalies:
        print(color_text("  No strong weather anomalies detected against historical averages.", GREEN))
        return

    for anomaly in anomalies:
        color = RED if abs(anomaly["z_score"]) >= 3 else YELLOW
        print(color_text(f"  {anomaly['message']}", color))


def print_report(df: pd.DataFrame, analysis: dict, classifier_note: str, anomalies: list[dict], history_df: pd.DataFrame) -> None:
    unit = df["Unit"].iloc[0]

    print("\n" + "=" * 60)
    print("  WEATHER ANALYSIS REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\nCity-wise Summary\n")
    display_cols = [
        "Country",
        "Temperature",
        "Feels_Like",
        "Humidity",
        "Weather_Condition",
        "Wind_Speed",
        "Weather_Class",
        "Weather_Alerts",
        "Timestamp",
    ]
    print(df[display_cols].to_string())

    print("\n" + "-" * 60)
    print("  Key Insights")
    print("-" * 60)
    print(f"  Cities Analyzed : {analysis['city_count']}")
    print(f"  Avg Temperature : {analysis['avg_temp']} {unit}")
    print(f"  Max Temperature : {analysis['max_temp']} {unit} ({analysis['hottest_city']})")
    print(f"  Min Temperature : {analysis['min_temp']} {unit} ({analysis['coldest_city']})")
    print(f"  Avg Humidity    : {analysis['avg_humidity']} %")
    print(f"  Most Humid      : {analysis['most_humid_city']}")
    print(f"  Highest Wind    : {analysis['max_wind']} m/s ({analysis['windiest_city']})")

    print_alert_section(df)
    print_classifier_section(df, classifier_note)
    print_anomaly_section(anomalies, history_df)

    print("\n" + "-" * 60)
    print("  Descriptive Statistics")
    print("-" * 60)
    print(analysis["stats_table"].to_string())

    print("\n" + "=" * 60)
    print("  Report Complete")
    print("=" * 60 + "\n")


def save_outputs(df: pd.DataFrame, output_dir: str) -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(output_dir, f"weather_report_{timestamp}.csv")
    chart_path = os.path.join(output_dir, f"weather_chart_{timestamp}.png")

    df.to_csv(csv_path)
    print(f"CSV saved -> {csv_path}")

    visualize(df, save_path=chart_path)
    return csv_path, chart_path


def main() -> None:
    config = load_config()

    try:
        cities = get_city_input(config)
    except ValueError as error:
        print(f"\nInput Error: {error}")
        return

    maybe_update_favorites(config, cities)

    history_df = load_history()

    print("\nFetching live weather data...\n")
    records = []
    for city in cities:
        result = safe_fetch_and_parse(city)
        if result:
            records.append(result)

    if not records:
        print("\nNo valid data was retrieved. Exiting.")
        return

    df = build_dataframe(records)
    df, classifier_note = classify_weather(df, history_df)
    anomalies = detect_anomalies(df, history_df)
    analysis = analyze(df)

    print_report(df, analysis, classifier_note, anomalies, history_df)
    append_history(df)
    print(color_text(f"Historical log updated -> {HISTORY_FILE}", CYAN))

    save_choice = input("Save report & chart to 'output/' folder? [y/n]: ").strip().lower()
    if save_choice == "y":
        save_outputs(df, OUTPUT_DIR)
    else:
        visualize(df)


if __name__ == "__main__":
    main()
