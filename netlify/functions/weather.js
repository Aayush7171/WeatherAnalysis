const OPEN_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather";

exports.handler = async function handler(event) {
  const city = event.queryStringParameters?.city?.trim();
  const apiKey = process.env.OWM_API_KEY;

  if (!apiKey) {
    return jsonResponse(500, {
      error: "Missing Netlify environment variable: OWM_API_KEY"
    });
  }

  if (!city) {
    return jsonResponse(400, {
      error: "Missing required query parameter: city"
    });
  }

  const params = new URLSearchParams({
    q: city,
    appid: apiKey,
    units: "metric"
  });

  try {
    const response = await fetch(`${OPEN_WEATHER_URL}?${params.toString()}`);
    const payload = await response.json();

    if (!response.ok) {
      return jsonResponse(response.status, {
        error: payload?.message || `Weather API request failed for ${city}`
      });
    }

    return jsonResponse(200, payload);
  } catch (error) {
    return jsonResponse(500, {
      error: `Unable to fetch weather for ${city}`,
      details: error instanceof Error ? error.message : String(error)
    });
  }
};

function jsonResponse(statusCode, body) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store"
    },
    body: JSON.stringify(body)
  };
}
