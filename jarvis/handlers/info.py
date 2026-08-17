"""ac/handlers/info.py — Time, date, and weather queries."""

from __future__ import annotations

import time

import re
import requests


def tell_time() -> str:
    return f"The time is {time.strftime('%I:%M %p')}."


def tell_date() -> str:
    return f"Today is {time.strftime('%A, %B %d, %Y')}."


def tell_weather(city: str, country: str) -> str:
    """Fetch current weather from wttr.in (no API key needed)."""
    try:
        url = f"https://wttr.in/{city},{country}?format=3"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        weather_text = resp.text.strip()
        # wttr.in format: "City: ⛅  +28°C"
        # Make it speech-friendly
        clean = weather_text.replace("°C", " degrees Celsius").replace("°F", " degrees Fahrenheit").replace("°", " degrees ")
        clean = clean.replace("+", "")
        clean = re.sub(r"[^\x00-\x7F]+", " ", clean)
        clean = " ".join(clean.split())
        return f"The weather in {city}: {clean}."
    except Exception as exc:
        return f"Couldn't fetch weather right now. {exc}"
