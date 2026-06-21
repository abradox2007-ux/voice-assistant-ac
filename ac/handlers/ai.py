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

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key.strip())
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a helpful voice assistant named AC. "
                    "Keep your responses short (under 2 sentences), natural-sounding, "
                    "and easy to read aloud by a text-to-speech engine. "
                    "Do not use markdown syntax, symbols, bullet points, or list formats."
                ),
                temperature=0.7,
            ),
        )
        if response.text:
            return response.text.strip()
        return "I generated an empty response. Try asking again."

    except Exception as exc:
        logger.exception("Error calling Gemini API: %s", exc)
        return "I had trouble connecting to my brain. Please check your internet connection or API key."
