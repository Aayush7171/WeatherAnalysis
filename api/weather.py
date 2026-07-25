from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

API_KEY  = os.environ.get("OWM_API_KEY", "")   # set in Vercel dashboard
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

@app.route("/api/weather")
def weather():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "No city provided"}), 400
    try:
        r = requests.get(BASE_URL, params={"q": city, "appid": API_KEY, "units": "metric"}, timeout=8)
        r.raise_for_status()
        d = r.json()
        return jsonify({
            "city"      : d["name"],
            "country"   : d["sys"]["country"],
            "temp"      : d["main"]["temp"],
            "feels"     : d["main"]["feels_like"],
            "humidity"  : d["main"]["humidity"],
            "wind"      : d["wind"]["speed"],
            "condition" : d["weather"][0]["description"].title(),
            "vis"       : round(d.get("visibility", 0) / 1000, 1),
        })
    except requests.exceptions.HTTPError:
        code = r.status_code
        if code == 404: return jsonify({"error": f"City '{city}' not found"}), 404
        if code == 401: return jsonify({"error": "Invalid API key"}), 401
        return jsonify({"error": f"API error {code}"}), code
    except Exception as e:
        return jsonify({"error": str(e)}), 500