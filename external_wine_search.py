import json
import re
from typing import Any

from google import genai
from google.genai import types


REQUIRED_FIELDS = ("Title", "Type", "Grape", "Region", "Country", "Style", "Characteristics", "Price")


def _extract_json(text: str) -> dict[str, Any]:
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced_match.group(1) if fenced_match else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Search did not return structured wine information.")
    return json.loads(candidate[start : end + 1])


def find_external_wine(title: str) -> dict[str, str] | None:
    client = genai.Client()
    prompt = f"""
Search for the wine named {title!r}. Identify the closest real wine product and return only valid JSON.
Use this exact structure:
{{
  "found": true,
  "Title": "full product name",
  "Type": "Red, White, Rosé, or Sparkling",
  "Grape": "primary grape or blend",
  "Region": "wine region",
  "Country": "country",
  "Style": "short wine style",
  "Characteristics": "comma-separated tasting notes",
  "Price": "current approximate price with currency"
}}
If no reliable wine match exists, return {{"found": false}}. Do not include markdown or commentary.
"""
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0,
        ),
    )
    if not response.text:
        return None
    payload = _extract_json(response.text)
    if not payload.get("found"):
        return None
    wine = {field: str(payload.get(field, "")).strip() for field in REQUIRED_FIELDS}
    return wine if wine["Title"] and wine["Type"] else None
