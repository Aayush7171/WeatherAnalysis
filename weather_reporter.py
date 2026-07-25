import requests
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime


API_KEY = "fe8b56bc86011acbef988a7664f5288b"
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
UNITS = "metric"
OUTPUT_DIR = "output" 

def get_city_input():
    print("\n" + "=" * 55)
    print("  🌦️  Live Weather Reporting System")
    print("=" * 55)
    raw = input("\nEnter city name(s) [comma-separated for multiple]: ").strip()

    if not raw:
        raise ValueError("No city name provided. Please enter at least one city.")

    cities = [c.strip() for c in raw.split(",") if c.strip()]
    print(f"\n📍 Cities queued: {', '.join(cities)}")
    return cities

def fetch_weather(city: str) -> dict:
    params = {
        "q": city,
        "appid": API_KEY,
        "units": UNITS,
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()          # Raises HTTPError for 4xx/5xx
        return response.json()

    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Network error: Could not reach the weather API. Check your internet connection.")
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Request timed out for '{city}'. Try again later.")
    except requests.exceptions.HTTPError as e:
        status = response.status_code
        if status == 401:
            raise PermissionError("Invalid API key. Please check your OpenWeatherMap API key.")
        elif status == 404:
            raise ValueError(f"City '{city}' not found. Please check the spelling and try again.")
        elif status == 429:
            raise RuntimeError("API rate limit exceeded. Wait a moment and retry.")
        else:
            raise RuntimeError(f"HTTP {status} error for '{city}': {e}")

def parse_weather(data: dict) -> dict:
    unit_symbol = "°C" if UNITS == "metric" else "°F"

    parsed = {
        "City":              data.get("name", "Unknown"),
        "Country":           data.get("sys", {}).get("country", "N/A"),
        "Temperature":       data.get("main", {}).get("temp", None),
        "Feels_Like":        data.get("main", {}).get("feels_like", None),
        "Temp_Min":          data.get("main", {}).get("temp_min", None),
        "Temp_Max":          data.get("main", {}).get("temp_max", None),
        "Humidity":          data.get("main", {}).get("humidity", None),
        "Weather_Condition": data.get("weather", [{}])[0].get("description", "N/A").title(),
        "Wind_Speed":        data.get("wind", {}).get("speed", None),
        "Visibility_km":     round(data.get("visibility", 0) / 1000, 1),
        "Unit":              unit_symbol,
        "Timestamp":         datetime.utcfromtimestamp(data.get("dt", 0)).strftime("%Y-%m-%d %H:%M UTC"),
        "Fetched_At":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return parsed

def build_dataframe(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df.set_index("City", inplace=True)
    return df

def analyze(df: pd.DataFrame) -> dict:
    numeric_cols = ["Temperature", "Feels_Like", "Humidity", "Wind_Speed"]
    df_num = df[numeric_cols].copy()

    analysis = {
        "city_count":       len(df),
        "hottest_city":     df["Temperature"].idxmax() if len(df) > 1 else df.index[0],
        "coldest_city":     df["Temperature"].idxmin() if len(df) > 1 else df.index[0],
        "avg_temp":         round(df["Temperature"].mean(), 2),
        "max_temp":         round(df["Temperature"].max(), 2),
        "min_temp":         round(df["Temperature"].min(), 2),
        "avg_humidity":     round(df["Humidity"].mean(), 2),
        "max_wind":         round(df["Wind_Speed"].max(), 2),
        "windiest_city":    df["Wind_Speed"].idxmax(),
        "most_humid_city":  df["Humidity"].idxmax(),
        "stats_table":      df_num.describe().round(2),
    }
    return analysis


def visualize(df: pd.DataFrame, save_path: str = None):
    cities = df.index.tolist()
    n = len(cities)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("🌦️ Live Weather Report", fontsize=16, fontweight="bold", y=1.02)

    colors = plt.cm.coolwarm([i / max(n - 1, 1) for i in range(n)])

    ax1 = axes[0]
    bars = ax1.bar(cities, df["Temperature"], color=colors, edgecolor="white", linewidth=1.2)
    ax1.set_title("Temperature", fontsize=13, fontweight="bold")
    ax1.set_ylabel(f"Temp ({df['Unit'].iloc[0]})")
    ax1.set_xlabel("City")
    for bar, val in zip(bars, df["Temperature"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                 f"{val:.1f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax1.tick_params(axis="x", rotation=30)
    ax1.grid(axis="y", alpha=0.3)

    ax2 = axes[1]
    bars2 = ax2.bar(cities, df["Humidity"], color="#5b9bd5", edgecolor="white", linewidth=1.2)
    ax2.set_title("Humidity", fontsize=13, fontweight="bold")
    ax2.set_ylabel("Humidity (%)")
    ax2.set_xlabel("City")
    ax2.set_ylim(0, 110)
    for bar, val in zip(bars2, df["Humidity"]):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{val}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax2.tick_params(axis="x", rotation=30)
    ax2.grid(axis="y", alpha=0.3)

    ax3 = axes[2]
    bars3 = ax3.bar(cities, df["Wind_Speed"], color="#70ad47", edgecolor="white", linewidth=1.2)
    ax3.set_title("Wind Speed", fontsize=13, fontweight="bold")
    ax3.set_ylabel("Wind Speed (m/s)")
    ax3.set_xlabel("City")
    for bar, val in zip(bars3, df["Wind_Speed"]):
        ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                 f"{val}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax3.tick_params(axis="x", rotation=30)
    ax3.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"\n📊 Chart saved → {save_path}")

    plt.show()


def safe_fetch_and_parse(city: str) -> dict | None:
    try:
        raw = fetch_weather(city)
        parsed = parse_weather(raw)
        print(f"  ✅ {city} — {parsed['Temperature']}{parsed['Unit']}, {parsed['Weather_Condition']}")
        return parsed

    except ValueError as e:
        print(f"  ❌ {city} — City not found: {e}")
    except PermissionError as e:
        print(f"  🔑 {city} — Auth error: {e}")
    except (ConnectionError, TimeoutError) as e:
        print(f"  🌐 {city} — Network error: {e}")
    except RuntimeError as e:
        print(f"  ⚠️  {city} — Runtime error: {e}")
    except Exception as e:
        print(f"  💥 {city} — Unexpected error: {type(e).__name__}: {e}")

    return None

def print_report(df: pd.DataFrame, analysis: dict):
    unit = df["Unit"].iloc[0]

    print("\n" + "=" * 55)
    print("  📋  WEATHER ANALYSIS REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    print("\n📍 City-wise Summary\n")
    display_cols = ["Country", "Temperature", "Feels_Like", "Humidity",
                    "Weather_Condition", "Wind_Speed", "Timestamp"]
    print(df[display_cols].to_string())

    print("\n" + "─" * 55)
    print("  📊 Key Insights")
    print("─" * 55)
    print(f"  Cities Analyzed  : {analysis['city_count']}")
    print(f"  Avg Temperature  : {analysis['avg_temp']} {unit}")
    print(f"  Max Temperature  : {analysis['max_temp']} {unit}  ({analysis['hottest_city']})")
    print(f"  Min Temperature  : {analysis['min_temp']} {unit}  ({analysis['coldest_city']})")
    print(f"  Avg Humidity     : {analysis['avg_humidity']} %")
    print(f"  Most Humid       : {analysis['most_humid_city']}")
    print(f"  Highest Wind     : {analysis['max_wind']} m/s  ({analysis['windiest_city']})")

    print("\n" + "─" * 55)
    print("  📈 Descriptive Statistics")
    print("─" * 55)
    print(analysis["stats_table"].to_string())

    print("\n" + "=" * 55)
    print("  ✅ Report Complete")
    print("=" * 55 + "\n")


def save_outputs(df: pd.DataFrame, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path   = os.path.join(output_dir, f"weather_report_{timestamp}.csv")
    chart_path = os.path.join(output_dir, f"weather_chart_{timestamp}.png")

    df.to_csv(csv_path)
    print(f"💾 CSV saved  → {csv_path}")

    visualize(df, save_path=chart_path)

    return csv_path, chart_path


def main():
    try:
        cities = get_city_input()
    except ValueError as e:
        print(f"\nInput Error: {e}")
        return

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

    analysis = analyze(df)

    print_report(df, analysis)

    save_choice = input("Save report & chart to 'output/' folder? [y/n]: ").strip().lower()
    if save_choice == "y":
        save_outputs(df, OUTPUT_DIR)
    else:
        visualize(df)   


if __name__ == "__main__":
    main()