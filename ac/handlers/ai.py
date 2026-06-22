"""ac/handlers/ai.py — Handle general conversational queries via Gemini API."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def generate_voice_response(prompt: str, api_key: str) -> str:
    """
    Query Gemini for a conversational response matching the user's prompt.
    Ensures the output is short and friendly for Text-to-Speech playback.
    """
    if not api_key or not api_key.strip():
        return "I need a Gemini API key to answer general questions."

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key.strip())
    config = types.GenerateContentConfig(
        system_instruction=(
            "You are a helpful voice assistant named AC. "
            "Keep your responses short (under 2 sentences), natural-sounding, "
            "and easy to read aloud by a text-to-speech engine. "
            "Do not use markdown syntax, symbols, bullet points, or list formats."
        ),
        temperature=0.7,
    )

    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    last_exc = None

    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            if response.text:
                return response.text.strip()
        except Exception as exc:
            logger.warning("Failed calling Gemini API with model %s: %s", model, exc)
            last_exc = exc

    logger.exception("All Gemini models failed: %s", last_exc)
    return "I had trouble connecting to my brain. Please check your internet connection or API key."
